from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


SOURCE_ROOT = Path(r"F:\VerbalVis2\backend\logs")
TARGET_DIR = Path(r"F:\VerbalVis2\backend\formative study log\formative intent log")
MANIFEST_NAME = "move_manifest.csv"


def collect_logs() -> list[Path]:
    return sorted(SOURCE_ROOT.rglob("conversation.log"), key=lambda path: str(path).lower())


def next_destination(index: int) -> Path:
    return TARGET_DIR / f"conversation_{index:03d}.log"


def move_logs(dry_run: bool = False) -> list[tuple[int, Path, Path, int]]:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    source_files = collect_logs()
    moves: list[tuple[int, Path, Path, int]] = []

    for index, source in enumerate(source_files, start=1):
        destination = next_destination(index)
        if destination.exists():
            raise FileExistsError(f"Destination already exists: {destination}")
        moves.append((index, source, destination, source.stat().st_size))

    if dry_run:
        return moves

    manifest_path = TARGET_DIR / MANIFEST_NAME
    with manifest_path.open("w", newline="", encoding="utf-8-sig") as manifest_file:
        writer = csv.writer(manifest_file)
        writer.writerow(["number", "source", "destination", "bytes"])
        for index, source, destination, size in moves:
            shutil.move(str(source), str(destination))
            writer.writerow([f"{index:03d}", str(source), str(destination), size])

    return moves


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Move all backend conversation.log files into the formative intent log folder."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned moves without changing files.")
    args = parser.parse_args()

    moves = move_logs(dry_run=args.dry_run)
    action = "Would move" if args.dry_run else "Moved"
    print(f"{action} {len(moves)} files into {TARGET_DIR}")
    for index, source, destination, size in moves:
        print(f"{index:03d}: {source} -> {destination} ({size} bytes)")


if __name__ == "__main__":
    main()
