"""Command line entry point: punchlist --images DIR --out DIR [--client mock|claude]."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .pipeline import DEFAULT_REVIEW_THRESHOLD, build_punch_list
from .render import to_csv, to_markdown
from .vision import VisionClient, list_images


def make_client(kind: str, model: str | None = None, recordings: Path | None = None) -> VisionClient:
    if kind == "mock":
        from .mock_client import MockVisionClient

        return MockVisionClient(recordings)
    if kind == "claude":
        from .claude_client import ClaudeVisionClient

        return ClaudeVisionClient(model=model)
    raise ValueError(f"unknown client: {kind}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="punchlist",
        description="Turn a folder of job site photos into a punch list (Markdown and CSV).",
    )
    parser.add_argument("--images", type=Path, required=True, help="folder of photos")
    parser.add_argument("--out", type=Path, default=Path("out"), help="output folder (default: out)")
    parser.add_argument("--project", default="Untitled project", help="project name for the heading")
    parser.add_argument("--client", choices=["mock", "claude"], default="mock")
    parser.add_argument("--model", default=None, help="Claude model id (default: PUNCHLIST_MODEL or claude-sonnet-5-5)")
    parser.add_argument("--recordings", type=Path, default=None, help="recordings file for the mock client")
    parser.add_argument(
        "--review-threshold",
        type=float,
        default=float(os.environ.get("PUNCHLIST_REVIEW_THRESHOLD", DEFAULT_REVIEW_THRESHOLD)),
        help="flag items below this confidence for review",
    )
    args = parser.parse_args(argv)

    try:
        images = list_images(args.images)
        client = make_client(args.client, args.model, args.recordings)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not images:
        print(f"error: no supported images in {args.images}", file=sys.stderr)
        return 2

    punch = build_punch_list(images, client, project=args.project, review_threshold=args.review_threshold)

    args.out.mkdir(parents=True, exist_ok=True)
    md_path = args.out / "punch_list.md"
    csv_path = args.out / "punch_list.csv"
    md_path.write_text(to_markdown(punch), encoding="utf-8", newline="\n")
    csv_path.write_text(to_csv(punch), encoding="utf-8", newline="\n")

    print(f"client: {client.name}")
    print(f"photos: {punch.photo_count} ({len(punch.skipped)} skipped)")
    print(f"items:  {len(punch.items)} across {len(punch.rooms())} rooms")
    print(f"wrote:  {md_path.as_posix()}")
    print(f"wrote:  {csv_path.as_posix()}")
    # Every photo failing means the run produced nothing useful.
    return 1 if punch.photo_count == len(punch.skipped) else 0
