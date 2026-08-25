"""reprocess_oversized_headshots.py

One-time (re-runnable) maintenance pass: finds every roster headshot file
already on disk, across every roster in the system, that exceeds
SupportMediaService.MAX_HEADSHOT_DIMENSION, and re-encodes it in place using
the exact same SupportMediaService._downscale_for_storage() logic the
upload route now applies to new uploads -- so files already on disk before
that fix landed get brought into line with it too.

Written for the Caledonia roster incident (2026-08-25): 33 of its 38
headshots were unprocessed 7000x8400 camera originals (25-31MB each),
including Ja'kylen Sherrod's, which is what caused the TD-spotlight crest
fallback. This scans every roster, not just Caledonia's, in case the same
raw-upload habit shows up elsewhere.

Originals are backed up before being overwritten (same filename, under a
timestamped backup directory) so this is reversible.

Run: python reprocess_oversized_headshots.py [--dry-run]
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

from PIL import Image

import app as app_module
from support_media_service import SupportMediaService

HEADSHOTS_DIR = Path(app_module.HEADSHOTS_DIR)
BACKUP_DIR = HEADSHOTS_DIR / f"_pre-reprocess-backup-{time.strftime('%Y%m%d-%H%M%S')}"


def human(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def main(dry_run: bool = False) -> int:
    service = app_module.get_support_media_service()

    candidates = sorted(
        p for p in HEADSHOTS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in SupportMediaService.SUPPORTED_HEADSHOT_TYPES
    )
    print(f"Scanning {len(candidates)} headshot files in {HEADSHOTS_DIR}")
    print(f"Threshold: MAX_HEADSHOT_DIMENSION={SupportMediaService.MAX_HEADSHOT_DIMENSION}px")
    print()

    changed: list[tuple[str, int, tuple[int, int], int, tuple[int, int]]] = []
    skipped_unreadable: list[str] = []

    for path in candidates:
        original = path.read_bytes()
        try:
            image = Image.open(path)
            image.load()
        except Exception as exc:
            skipped_unreadable.append(f"{path.name}: {exc}")
            continue

        before_dims = (image.width, image.height)
        resized_bytes = service._downscale_for_storage(image, path.suffix, original)
        if resized_bytes == original:
            continue  # already within bounds

        with Image.open(__import__("io").BytesIO(resized_bytes)) as check:
            after_dims = (check.width, check.height)

        changed.append((path.name, len(original), before_dims, len(resized_bytes), after_dims))

        if not dry_run:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, BACKUP_DIR / path.name)
            path.write_bytes(resized_bytes)

    if not changed:
        print("Nothing to reprocess -- every headshot is already within bounds.")
        return 0

    print(f"{'DRY RUN -- ' if dry_run else ''}Reprocessed {len(changed)} oversized file(s):")
    print()
    for name, before_size, before_dims, after_size, after_dims in changed:
        print(
            f"  {name}\n"
            f"    {human(before_size):>8}  {before_dims[0]}x{before_dims[1]}"
            f"  ->  {human(after_size):>8}  {after_dims[0]}x{after_dims[1]}"
        )
    if skipped_unreadable:
        print()
        print(f"Skipped {len(skipped_unreadable)} unreadable file(s):")
        for line in skipped_unreadable:
            print(f"  {line}")

    if not dry_run:
        print()
        print(f"Originals backed up to: {BACKUP_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
