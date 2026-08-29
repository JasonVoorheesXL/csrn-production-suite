"""Sweep orphaned atomic-write temp files left behind by JsonPersistenceEngine.

JsonPersistenceEngine.save() writes each state file by creating
``.<name>.<rand>.tmp`` next to it via ``tempfile.mkstemp`` and then
``os.replace``-ing it into place. When that final rename loses a race (most
often the Google-Drive sync client holding a handle on the destination) the
``.tmp`` file is left on disk. Over a season these accumulate -- tonight's
audit found ~45 MB of ``.state.json.*.tmp`` debris in the repo root.

This is a manual janitor. It is NOT wired into startup and touches nothing
the running app depends on: a live write in progress is protected by the
``--min-age-minutes`` floor (default 60), and the tool refuses to delete the
real ``state.json`` itself. Dry-run by default; pass ``--apply`` to delete.

Examples
--------
    python tools/sweep_state_tmp.py                 # dry run, repo root
    python tools/sweep_state_tmp.py --apply
    python tools/sweep_state_tmp.py --dir "%LOCALAPPDATA%\\PossumFrog\\CSRN Production Suite\\GameDay" --apply
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_PATTERN = ".state.json.*.tmp"
DEFAULT_MIN_AGE_MINUTES = 60


def find_orphan_tmp(
    directory: Path,
    *,
    pattern: str = DEFAULT_PATTERN,
    min_age_seconds: float = DEFAULT_MIN_AGE_MINUTES * 60,
    now: float | None = None,
) -> list[Path]:
    """Return temp files under *directory* matching *pattern* and older than
    *min_age_seconds*, newest first.

    A real data file (``state.json``) never matches the ``.tmp`` suffix, so it
    can never be selected here.
    """

    current = time.time() if now is None else now
    matches: list[tuple[float, Path]] = []
    for candidate in directory.glob(pattern):
        if not candidate.is_file():
            continue
        if candidate.suffix != ".tmp":
            continue
        try:
            age = current - candidate.stat().st_mtime
        except OSError:
            continue
        if age < min_age_seconds:
            continue
        matches.append((candidate.stat().st_mtime, candidate))
    matches.sort(reverse=True)
    return [path for _mtime, path in matches]


def _format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dir",
        default=str(ROOT),
        help="Directory to sweep (default: repo root, where the Drive-side "
        "state.json mirror lives).",
    )
    parser.add_argument(
        "--pattern",
        default=DEFAULT_PATTERN,
        help=f"Glob for temp files (default: {DEFAULT_PATTERN!r}).",
    )
    parser.add_argument(
        "--min-age-minutes",
        type=int,
        default=DEFAULT_MIN_AGE_MINUTES,
        help="Only remove temp files older than this, so an in-flight write is "
        f"never touched (default: {DEFAULT_MIN_AGE_MINUTES}).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete. Without this the tool only reports.",
    )
    args = parser.parse_args(argv)

    directory = Path(os.path.expandvars(args.dir)).expanduser()
    if not directory.is_dir():
        print(f"Not a directory: {directory}")
        return 1

    stale = find_orphan_tmp(
        directory,
        pattern=args.pattern,
        min_age_seconds=args.min_age_minutes * 60,
    )
    if not stale:
        print(f"No orphaned temp files matching {args.pattern!r} in {directory}.")
        return 0

    total = 0
    removed = 0
    for path in stale:
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        total += size
        if args.apply:
            try:
                path.unlink()
                removed += 1
                print(f"removed  {path.name}  ({_format_size(size)})")
            except OSError as exc:
                print(f"SKIP     {path.name}  ({exc})")
        else:
            print(f"would remove  {path.name}  ({_format_size(size)})")

    verb = "Removed" if args.apply else "Would remove"
    count = removed if args.apply else len(stale)
    print(f"\n{verb} {count} file(s), {_format_size(total)}.")
    if not args.apply:
        print("Re-run with --apply to delete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
