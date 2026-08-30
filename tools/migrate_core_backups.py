"""Relocate accumulated core backups out of the Drive-synced project tree.

JsonPersistenceEngine snapshots every state/config/security save into
``Data/Backups/Core`` (and quarantines corrupt copies into
``Data/Backups/Quarantine``). In a dev/Drive layout that folder lives inside
the Google-Drive-synced project, where the sync client then has to upload
every snapshot. As of this change the app writes NEW snapshots to a local,
non-synced root (``%LOCALAPPDATA%\\PossumFrog\\CSRN Production Suite\\Backups``
by default, or ``$CSRN_CORE_BACKUP_ROOT``); this tool moves the OLD ones.

Safety:
  * Dry-run by default. Pass ``--apply`` to move.
  * Per-file ``shutil.move``: a file is only removed from the old location
    once it is fully written to the new one.
  * Anything already present at the target is left untouched (never
    overwritten).
  * Nothing the running app depends on is touched -- new snapshots already
    go to the new root regardless of whether this has been run.

Examples
--------
    python tools/migrate_core_backups.py                 # dry run
    python tools/migrate_core_backups.py --apply
    python tools/migrate_core_backups.py --dest "D:\\CSRN-Backups" --apply
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def plan_moves(source_root: Path, dest_root: Path) -> list[tuple[Path, Path]]:
    """(source_file, dest_file) pairs for every Core/Quarantine file that is
    not already present at the destination."""
    moves: list[tuple[Path, Path]] = []
    for sub in ("Core", "Quarantine"):
        old_dir = source_root / sub
        new_dir = dest_root / sub
        if not old_dir.is_dir():
            continue
        for source in sorted(old_dir.rglob("*")):
            if not source.is_file():
                continue
            target = new_dir / source.relative_to(old_dir)
            if target.exists():
                continue
            moves.append((source, target))
    return moves


def main(argv: list[str] | None = None) -> int:
    import app  # resolves CORE_BACKUP_ROOT / LEGACY_CORE_BACKUP_ROOT from env

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source",
        default=str(app.LEGACY_CORE_BACKUP_ROOT),
        help="Old backups root to move FROM (default: the in-Data location).",
    )
    parser.add_argument(
        "--dest",
        default=str(app.CORE_BACKUP_ROOT),
        help="New backups root to move TO (default: the resolved local root).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually move. Without this the tool only reports.",
    )
    args = parser.parse_args(argv)

    source_root = Path(args.source).expanduser()
    dest_root = Path(args.dest).expanduser()

    if source_root.resolve() == dest_root.resolve():
        print(f"Source and destination are the same location ({source_root}); nothing to do.")
        return 0
    if not source_root.is_dir():
        print(f"No old backups directory at {source_root}; nothing to do.")
        return 0

    moves = plan_moves(source_root, dest_root)
    if not moves:
        print(f"No un-migrated core backups under {source_root}.")
        return 0

    total = 0
    moved = 0
    for source, target in moves:
        try:
            size = source.stat().st_size
        except OSError:
            size = 0
        total += size
        rel = source.relative_to(source_root)
        if args.apply:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
                moved += 1
            except OSError as exc:
                print(f"SKIP  {rel}  ({exc})")
                continue
        else:
            print(f"would move  {rel}  ({_format_size(size)})")

    if args.apply:
        (dest_root / ".core-backups-migrated").parent.mkdir(parents=True, exist_ok=True)
        (dest_root / ".core-backups-migrated").write_text("completed\n", encoding="utf-8")
        print(f"\nMoved {moved} file(s), {_format_size(total)} -> {dest_root}")
        emptied = ", ".join(
            str(source_root / sub) for sub in ("Core", "Quarantine") if (source_root / sub).is_dir()
        )
        print(
            f"Only the {emptied} subdir(s) were emptied and are now safe to delete. "
            f"Leave the rest of {source_root} alone -- it holds other backup content "
            f"(Recovery, GameDay, Installers, ...) this tool does not manage."
        )
    else:
        print(f"\nWould move {len(moves)} file(s), {_format_size(total)} -> {dest_root}")
        print("Re-run with --apply to move.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
