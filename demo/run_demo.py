"""Offline demo: run the bundled sample photos through the mock vision client.

    python demo/run_demo.py

Needs no install, no network and no API key. Writes demo/punch_list.md and
demo/punch_list.csv and prints both to the terminal.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from punchlist.cli import main  # noqa: E402


def run() -> int:
    out = ROOT / "demo"
    print("$ punchlist --images samples/images --out demo --project 'Sample Unit 4B' --client mock")
    code = main(
        [
            "--images", str((ROOT / "samples" / "images").relative_to(ROOT)),
            "--out", str(out.relative_to(ROOT)),
            "--project", "Sample Unit 4B",
            "--client", "mock",
        ]
    )
    for name in ("punch_list.md", "punch_list.csv"):
        print()
        print(f"===== demo/{name} =====")
        print((out / name).read_text(encoding="utf-8").rstrip())
    return code


if __name__ == "__main__":
    import os

    os.chdir(ROOT)
    sys.exit(run())
