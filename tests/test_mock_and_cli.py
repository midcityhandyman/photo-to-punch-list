import csv
import io
import json
from pathlib import Path

import pytest

from punchlist.cli import main
from punchlist.mock_client import MockVisionClient, sha256_of
from punchlist.pipeline import build_punch_list
from punchlist.render import CSV_COLUMNS, to_csv, to_markdown
from punchlist.vision import VisionClient, VisionError, list_images

ROOT = Path(__file__).resolve().parents[1]


def test_every_sample_image_has_a_recording(sample_dir):
    doc = json.loads((ROOT / "samples" / "recordings.json").read_text(encoding="utf-8"))
    recorded = {r["sha256"] for r in doc["recordings"]}
    images = list_images(sample_dir)
    assert len(images) == 7
    assert {sha256_of(p) for p in images} == recorded


def test_mock_client_satisfies_interface_and_replays(sample_dir):
    client = MockVisionClient()
    assert isinstance(client, VisionClient)
    findings = client.analyze(sample_dir / "hallway_01.png")
    assert [f.trade for f in findings] == ["Carpentry", "Electrical"]


def test_mock_client_rejects_unknown_image(tmp_path):
    stranger = tmp_path / "stranger.png"
    stranger.write_bytes(b"not a recorded image")
    with pytest.raises(VisionError, match="no recorded response"):
        MockVisionClient().analyze(stranger)


def test_end_to_end_on_samples(sample_dir):
    punch = build_punch_list(list_images(sample_dir), MockVisionClient(), project="Sample Unit")
    assert punch.photo_count == 7
    assert punch.skipped == [("unknown_01.png", "image is too dark to analyze")]
    # 17 raw findings, one duplicate across the two kitchen photos
    assert len(punch.items) == 16
    assert punch.rooms() == ["Bathroom", "Bedroom 1", "Hallway", "Kitchen", "Living Room"]
    outlet = next(i for i in punch.items if "cover plate" in i.description)
    assert outlet.photos == ["kitchen_01.png", "kitchen_02.png"]
    assert outlet.severity == "high"

    md = to_markdown(punch)
    assert md.startswith("# Punch list: Sample Unit\n")
    assert "## Kitchen" in md and "### Electrical" in md
    assert "(needs review)" in md
    assert "## Photos not analyzed" in md

    rows = list(csv.reader(io.StringIO(to_csv(punch))))
    assert rows[0] == CSV_COLUMNS
    assert len(rows) == 17
    assert rows[1][0] == "PL-001"


def test_markdown_escapes_pipes(fake_client):
    from punchlist.models import Finding

    client = fake_client({"a.png": [Finding("Kitchen", "Paint", "Chip at A|B joint\nsecond line", "low", 0.9)]})
    md = to_markdown(build_punch_list([Path("a.png")], client))
    assert "Chip at A/B joint second line" in md


def test_cli_writes_both_files(sample_dir, tmp_path, capsys):
    code = main(["--images", str(sample_dir), "--out", str(tmp_path), "--project", "Sample Unit"])
    assert code == 0
    assert (tmp_path / "punch_list.md").read_text(encoding="utf-8").startswith("# Punch list")
    assert (tmp_path / "punch_list.csv").read_text(encoding="utf-8").startswith("id,room,trade")
    assert "items:  16 across 5 rooms" in capsys.readouterr().out


def test_cli_errors_on_missing_or_empty_folder(tmp_path, capsys):
    assert main(["--images", str(tmp_path / "nope")]) == 2
    assert main(["--images", str(tmp_path)]) == 2
    assert "error:" in capsys.readouterr().err
