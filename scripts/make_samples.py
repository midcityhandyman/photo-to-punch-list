"""Generate the bundled synthetic sample photos with nothing but the standard library.

These are flat-colour placeholder scenes (a wall, a floor band, a few
rectangles), not photographs. They exist so the mock client has real image
bytes to hash. After regenerating, run with --update-recordings so the
SHA-256 keys in samples/recordings.json match the new files.
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "samples" / "images"
RECORDINGS = ROOT / "samples" / "recordings.json"
WIDTH, HEIGHT = 160, 120

# name: (wall colour, floor colour, [(x, y, w, h, colour), ...])
SCENES = {
    "kitchen_01.png": ((232, 226, 208), (150, 120, 90), [(20, 40, 50, 45, (245, 245, 240)), (100, 55, 14, 20, (60, 60, 60))]),
    "kitchen_02.png": ((232, 226, 208), (150, 120, 90), [(60, 30, 70, 50, (245, 245, 240)), (25, 60, 14, 20, (60, 60, 60))]),
    "bathroom_01.png": ((200, 220, 228), (230, 230, 230), [(50, 50, 60, 35, (255, 255, 255)), (75, 30, 10, 20, (170, 170, 175))]),
    "bedroom_01.png": ((214, 205, 225), (176, 146, 110), [(15, 25, 45, 60, (250, 250, 250)), (110, 70, 30, 6, (120, 90, 60))]),
    "hallway_01.png": ((225, 225, 215), (120, 100, 80), [(65, 15, 30, 85, (140, 105, 75)), (20, 20, 16, 10, (250, 250, 245))]),
    "living_room_01.png": ((236, 230, 220), (165, 135, 100), [(30, 20, 100, 55, (190, 215, 235)), (10, 92, 140, 4, (250, 250, 250))]),
    "unknown_01.png": ((90, 90, 90), (70, 70, 70), [(40, 30, 80, 60, (40, 40, 40))]),
}


def png_bytes(wall, floor, rects) -> bytes:
    rows = bytearray()
    for y in range(HEIGHT):
        rows.append(0)  # filter type: none
        for x in range(WIDTH):
            colour = wall if y < 96 else floor
            for rx, ry, rw, rh, rc in rects:
                if rx <= x < rx + rw and ry <= y < ry + rh:
                    colour = rc
            rows.extend(colour)

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b"")


def main() -> int:
    IMAGES.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, (wall, floor, rects) in SCENES.items():
        data = png_bytes(wall, floor, rects)
        (IMAGES / name).write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
        print(f"wrote {name} ({len(data)} bytes)")

    if "--update-recordings" in sys.argv:
        doc = json.loads(RECORDINGS.read_text(encoding="utf-8"))
        for record in doc["recordings"]:
            record["sha256"] = hashes[record["image"]]
        RECORDINGS.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("updated sha256 keys in samples/recordings.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
