from pathlib import Path

from punchlist.models import Finding
from punchlist.pipeline import (
    build_punch_list,
    normalize_room,
    normalize_severity,
    normalize_trade,
)
from punchlist.vision import VisionError


def test_normalizers_map_aliases_and_fall_back():
    assert normalize_trade("electric") == "Electrical"
    assert normalize_trade(" PLUMBING ") == "Plumbing"
    assert normalize_trade("glazing") == "General"
    assert normalize_room("  main   bath ") == "Bathroom"
    assert normalize_room("bedroom 2") == "Bedroom 2"
    assert normalize_room("") == "Unknown"
    assert normalize_severity("HIGH") == "high"
    assert normalize_severity("urgent") == "medium"


def test_same_defect_in_two_photos_becomes_one_item(fake_client):
    client = fake_client(
        {
            "a.png": [Finding("Kitchen", "Electrical", "Outlet has no cover plate.", "medium", 0.7)],
            "b.png": [Finding("kitchen", "electric", "outlet has no cover plate", "high", 0.9)],
        }
    )
    punch = build_punch_list([Path("a.png"), Path("b.png")], client)
    assert len(punch.items) == 1
    item = punch.items[0]
    assert item.photos == ["a.png", "b.png"]
    assert item.severity == "high"  # worse severity wins
    assert item.confidence == 0.9  # higher confidence wins
    assert item.item_id == "PL-001"


def test_items_sorted_by_room_trade_severity_with_unknown_last(fake_client):
    client = fake_client(
        {
            "a.png": [
                Finding("", "Paint", "Scuff.", "low", 0.9),
                Finding("Kitchen", "Plumbing", "Drip.", "low", 0.9),
                Finding("Kitchen", "Electrical", "Loose fixture.", "low", 0.9),
                Finding("Kitchen", "Electrical", "Bare wire.", "high", 0.9),
                Finding("Bathroom", "Paint", "Drips.", "medium", 0.9),
            ]
        }
    )
    punch = build_punch_list([Path("a.png")], client)
    order = [(i.room, i.trade, i.severity) for i in punch.items]
    assert order == [
        ("Bathroom", "Paint", "medium"),
        ("Kitchen", "Electrical", "high"),
        ("Kitchen", "Electrical", "low"),
        ("Kitchen", "Plumbing", "low"),
        ("Unknown", "Paint", "low"),
    ]
    assert [i.item_id for i in punch.items] == [f"PL-00{n}" for n in range(1, 6)]


def test_low_confidence_flagged_and_confidence_clamped(fake_client):
    client = fake_client(
        {
            "a.png": [
                Finding("Kitchen", "Paint", "Maybe a scuff.", "low", 0.4),
                Finding("Kitchen", "Paint", "Definite drip.", "low", 7.0),
            ]
        }
    )
    punch = build_punch_list([Path("a.png")], client, review_threshold=0.6)
    by_desc = {i.description: i for i in punch.items}
    assert by_desc["Maybe a scuff."].needs_review is True
    assert by_desc["Definite drip."].needs_review is False
    assert by_desc["Definite drip."].confidence == 1.0


def test_failed_photo_is_skipped_not_fatal(fake_client):
    client = fake_client(
        {
            "a.png": VisionError("too dark"),
            "b.png": [Finding("Hallway", "Carpentry", "Door rubs.", "medium", 0.9)],
        }
    )
    punch = build_punch_list([Path("a.png"), Path("b.png")], client)
    assert punch.photo_count == 2
    assert punch.skipped == [("a.png", "too dark")]
    assert len(punch.items) == 1


def test_room_names_keep_apostrophes_and_ordinals():
    assert normalize_room("kid's room") == "Kid's Room"
    assert normalize_room("2nd floor bath") == "2nd Floor Bath"
    assert normalize_room("LIVING ROOM") == "Living Room"


def test_unsupported_photo_format_is_reported_without_calling_the_client(fake_client):
    client = fake_client({"b.jpg": [Finding("Hallway", "Carpentry", "Door rubs.", "medium", 0.9)]})
    punch = build_punch_list([Path("IMG_0001.HEIC"), Path("b.jpg")], client)
    assert punch.photo_count == 2
    assert punch.skipped == [("IMG_0001.HEIC", "unsupported image type .heic; convert to JPEG or PNG")]
    assert len(punch.items) == 1
