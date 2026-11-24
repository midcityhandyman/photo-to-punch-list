"""Plain data types shared by the vision clients, the pipeline and the renderers."""

from __future__ import annotations

from dataclasses import dataclass, field

SEVERITIES = ("high", "medium", "low")

TRADES = (
    "Carpentry",
    "Drywall",
    "Electrical",
    "Flooring",
    "HVAC",
    "Paint",
    "Plumbing",
    "General",
)


@dataclass(frozen=True)
class Finding:
    """One defect a vision client saw in one photo. Raw, not yet normalized."""

    room: str
    trade: str
    description: str
    severity: str = "medium"
    confidence: float = 1.0

    @classmethod
    def from_dict(cls, data: dict) -> "Finding":
        missing = [k for k in ("room", "trade", "description") if not str(data.get(k, "")).strip()]
        if missing:
            raise ValueError(f"finding is missing required fields: {', '.join(missing)}")
        return cls(
            room=str(data["room"]),
            trade=str(data["trade"]),
            description=str(data["description"]),
            severity=str(data.get("severity", "medium")),
            confidence=float(data.get("confidence", 1.0)),
        )


@dataclass
class PunchItem:
    """One line on the punch list. May be backed by several photos."""

    item_id: str
    room: str
    trade: str
    description: str
    severity: str
    confidence: float
    photos: list[str] = field(default_factory=list)
    needs_review: bool = False


@dataclass
class PunchList:
    project: str
    items: list[PunchItem]
    photo_count: int
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (photo, reason)

    def rooms(self) -> list[str]:
        seen: list[str] = []
        for item in self.items:
            if item.room not in seen:
                seen.append(item.room)
        return seen

    def by_room_and_trade(self) -> dict[str, dict[str, list[PunchItem]]]:
        grouped: dict[str, dict[str, list[PunchItem]]] = {}
        for item in self.items:
            grouped.setdefault(item.room, {}).setdefault(item.trade, []).append(item)
        return grouped
