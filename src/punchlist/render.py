"""Render a punch list as Markdown (for people) and CSV (for spreadsheets)."""

from __future__ import annotations

import csv
import io

from .models import SEVERITIES, PunchList

CSV_COLUMNS = [
    "id",
    "room",
    "trade",
    "description",
    "severity",
    "confidence",
    "needs_review",
    "photos",
    "status",
]


def _cell(text: str) -> str:
    """Keep free text from breaking a Markdown table or list line."""
    return text.replace("|", "/").replace("\n", " ").strip()


def to_markdown(punch: PunchList) -> str:
    lines = [f"# Punch list: {_cell(punch.project)}", ""]
    review = sum(1 for i in punch.items if i.needs_review)
    lines.append(
        f"{len(punch.items)} items from {punch.photo_count} photos "
        f"across {len(punch.rooms())} rooms. {review} flagged for review."
    )
    lines.append("")

    if punch.items:
        lines += ["## Summary by trade", "", "| Trade | High | Medium | Low | Total |", "|---|---|---|---|---|"]
        counts: dict[str, dict[str, int]] = {}
        for item in punch.items:
            counts.setdefault(item.trade, dict.fromkeys(SEVERITIES, 0))[item.severity] += 1
        for trade in sorted(counts):
            row = counts[trade]
            lines.append(
                f"| {trade} | {row['high']} | {row['medium']} | {row['low']} | {sum(row.values())} |"
            )
        lines.append("")

    for room, trades in punch.by_room_and_trade().items():
        lines += [f"## {_cell(room)}", ""]
        for trade, items in trades.items():
            lines += [f"### {trade}", ""]
            for item in items:
                flag = " (needs review)" if item.needs_review else ""
                photos = ", ".join(item.photos)
                lines.append(
                    f"- [ ] **{item.item_id}** [{item.severity}] "
                    f"{_cell(item.description)}{flag} (photos: {photos})"
                )
            lines.append("")

    if punch.skipped:
        lines += ["## Photos not analyzed", ""]
        for photo, reason in punch.skipped:
            lines.append(f"- {photo}: {_cell(reason)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def to_csv(punch: PunchList) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for item in punch.items:
        writer.writerow(
            [
                item.item_id,
                item.room,
                item.trade,
                item.description,
                item.severity,
                f"{item.confidence:.2f}",
                "yes" if item.needs_review else "no",
                "; ".join(item.photos),
                "open",
            ]
        )
    return buffer.getvalue()
