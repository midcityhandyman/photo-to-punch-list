"""Offline vision client that replays recorded responses.

Recordings are keyed by the SHA-256 of the image bytes, so renaming a sample
photo still finds its recording and an unknown photo fails loudly instead of
getting someone else's findings.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import Finding
from .vision import VisionError

DEFAULT_RECORDINGS = Path(__file__).resolve().parents[2] / "samples" / "recordings.json"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MockVisionClient:
    name = "mock"

    def __init__(self, recordings_path: Path | None = None):
        path = Path(recordings_path) if recordings_path else DEFAULT_RECORDINGS
        if not path.is_file():
            raise FileNotFoundError(f"recordings file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        self._by_hash: dict[str, dict] = {r["sha256"]: r for r in data["recordings"]}

    def analyze(self, image_path: Path) -> list[Finding]:
        record = self._by_hash.get(sha256_of(image_path))
        if record is None:
            raise VisionError(
                f"no recorded response for {image_path.name}; "
                "the mock client only knows the bundled sample images"
            )
        if record.get("error"):
            raise VisionError(record["error"])
        return [Finding.from_dict(f) for f in record["findings"]]
