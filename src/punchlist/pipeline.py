"""Photos in, punch list out: analyze, normalize, merge duplicates, sort, number."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .models import SEVERITIES, TRADES, Finding, PunchItem, PunchList
from .vision import MEDIA_TYPES, VisionClient, VisionError

DEFAULT_REVIEW_THRESHOLD = 0.6

# Free-text trade names a model or a recording might use, mapped to the fixed list.
TRADE_ALIASES = {
    "electric": "Electrical",
    "electrician": "Electrical",
    "plumber": "Plumbing",
    "sheetrock": "Drywall",
    "plaster": "Drywall",
    "painting": "Paint",
    "painter": "Paint",
    "floor": "Flooring",
    "floors": "Flooring",
    "tile": "Flooring",
    "trim": "Carpentry",
    "carpenter": "Carpentry",
    "millwork": "Carpentry",
    "heating": "HVAC",
    "mechanical": "HVAC",
}

ROOM_ALIASES = {
    "bath": "Bathroom",
    "main bath": "Bathroom",
    "living": "Living Room",
    "lounge": "Living Room",
    "hall": "Hallway",
    "corridor": "Hallway",
    "": "Unknown",
}


def normalize_trade(raw: str) -> str:
    key = raw.strip().lower()
    for trade in TRADES:
        if key == trade.lower():
            return trade
    return TRADE_ALIASES.get(key, "General")


def normalize_room(raw: str) -> str:
    key = re.sub(r"\s+", " ", raw.strip().lower())
    if key in ROOM_ALIASES:
        return ROOM_ALIASES[key]
    # Not str.title(): that turns "kid's room" into "Kid'S Room" and "2nd" into "2Nd".
    return " ".join(word[:1].upper() + word[1:] for word in key.split(" "))


def normalize_severity(raw: str) -> str:
    key = raw.strip().lower()
    return key if key in SEVERITIES else "medium"


def _dedupe_key(room: str, trade: str, description: str) -> tuple[str, str, str]:
    words = re.sub(r"[^a-z0-9 ]", "", description.lower()).split()
    return (room, trade, " ".join(words))


def build_punch_list(
    images: Iterable[Path],
    client: VisionClient,
    project: str = "Untitled project",
    review_threshold: float = DEFAULT_REVIEW_THRESHOLD,
) -> PunchList:
    """Analyze each photo and fold the findings into one ordered punch list.

    A photo that fails analysis is recorded in ``skipped`` and does not stop
    the run. The same defect seen in two photos becomes one item that cites
    both photos, keeping the worse severity and the higher confidence.
    """
    merged: dict[tuple[str, str, str], PunchItem] = {}
    skipped: list[tuple[str, str]] = []
    photo_count = 0

    for image in images:
        photo_count += 1
        if image.suffix.lower() not in MEDIA_TYPES:
            skipped.append(
                (image.name, f"unsupported image type {image.suffix.lower()}; convert to JPEG or PNG")
            )
            continue
        try:
            findings: list[Finding] = client.analyze(image)
        except VisionError as exc:
            skipped.append((image.name, str(exc)))
            continue
        for finding in findings:
            room = normalize_room(finding.room)
            trade = normalize_trade(finding.trade)
            severity = normalize_severity(finding.severity)
            confidence = min(1.0, max(0.0, finding.confidence))
            key = _dedupe_key(room, trade, finding.description)
            item = merged.get(key)
            if item is None:
                merged[key] = PunchItem(
                    item_id="",
                    room=room,
                    trade=trade,
                    description=finding.description.strip(),
                    severity=severity,
                    confidence=confidence,
                    photos=[image.name],
                )
                continue
            if image.name not in item.photos:
                item.photos.append(image.name)
            if SEVERITIES.index(severity) < SEVERITIES.index(item.severity):
                item.severity = severity
            item.confidence = max(item.confidence, confidence)

    items = sorted(
        merged.values(),
        key=lambda i: (
            i.room == "Unknown",  # unknown room sinks to the bottom
            i.room,
            i.trade,
            SEVERITIES.index(i.severity),
            i.description.lower(),
        ),
    )
    for number, item in enumerate(items, start=1):
        item.item_id = f"PL-{number:03d}"
        item.needs_review = item.confidence < review_threshold

    return PunchList(project=project, items=items, photo_count=photo_count, skipped=skipped)
