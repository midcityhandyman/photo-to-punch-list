"""The vision client interface. Everything else depends on this, not on a vendor SDK."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from .models import Finding

MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# Photo formats that turn up in a camera roll but that the vision API does not
# accept. They are listed so the run can report them instead of dropping them.
UNSUPPORTED_PHOTO_SUFFIXES = {".heic", ".heif", ".tif", ".tiff", ".bmp"}


class VisionError(Exception):
    """A photo could not be analyzed. The pipeline records it and moves on."""


@runtime_checkable
class VisionClient(Protocol):
    """Looks at one photo and returns the defects it can see."""

    name: str

    def analyze(self, image_path: Path) -> list[Finding]:
        ...


def media_type_for(image_path: Path) -> str:
    try:
        return MEDIA_TYPES[image_path.suffix.lower()]
    except KeyError:
        raise VisionError(f"unsupported image type: {image_path.suffix or '(none)'}") from None


def list_images(folder: Path) -> list[Path]:
    """Photos in a folder, sorted by name so runs are repeatable.

    Includes photo formats the vision API does not accept (HEIC and similar);
    the pipeline reports those as not analyzed without calling the client.
    """
    if not folder.is_dir():
        raise FileNotFoundError(f"image folder not found: {folder}")
    wanted = MEDIA_TYPES.keys() | UNSUPPORTED_PHOTO_SUFFIXES
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in wanted)
