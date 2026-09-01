"""Relocate game-day safety snapshots out of the Drive-synced project tree
and sweep dead leftovers (Round 19).

GameDaySafetyService.create_snapshot writes a verified copy of game state
on every launch into ``Data/Backups/GameDay``. In a dev/Drive layout that
folder lives inside the Google-Drive-synced project, where the sync client
then uploads every snapshot -- which ballooned to ~8 GB once each snapshot
started carrying the full media library (Round 17 audit). As of Round 19
the app writes NEW snapshots to a local, non-synced root
(``%LOCALAPPDATA%\\PossumFrog\\CSRN Production Suite\\GameDay`` by default,
or ``$CSRN_GAME_DAY_BACKUP_ROOT``) and no longer copies media into them.
This tool moves the OLD real snapshots and deletes provable junk.

Classification of each entry under the old GameDay root:
  * dir with a valid schema-1 ``manifest.json``  -> MIGRATE (move, then
    re-verify hashes at the new location);
  * dir named ``.tmp-*``                         -> SWEEP (crashed staging);
  * dir with no readable ``manifest.json``       -> SWEEP (pre-schema
    orphan -- invisible to the service, never restorable, never pruned);
  * loose file (e.g. ``_r1121-*.json``)          -> SWEEP.

Safety:
  * Dry-run by default. Pass ``--apply`` to act.
  * MIGRATE uses ``shutil.move`` then ``verify_snapshot`` at the new
    location; a snapshot that fails verification is moved BACK and the run
    stops.
  * Anything already present at the target is left untouched.
  * SWEEP only ever touches ``.tmp-*`` dirs, manifest-less dirs, and loose
    files -- never a dir that verifies as a real snapshot.

    python tools/migrate_gameday_backups.py            # dry run
    python tools/migrate_gameday_backups.py --apply
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fmt(num_bytes: float) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _make_verifier(backup_root: Path):
    from game_day_safety_service import GameDaySafetyService

    return GameDaySafetyService(
        base_dir=backup_root,
        data_dir=backup_root,
        backup_root=backup_root,
        state_file=backup_root / "state.json",
        security_file=backup_root / "security.json",
        config_file=backup_root / "config.json",
        version_file=backup_root / "VERSION.txt",
        minimum_free_bytes=0,
    )


def classify(old_root: Path):
    from game_day_safety_service import GameDaySafetyService

    migrate: list[Path] = []
    sweep: list[Path] = []
    for entry in sorted(old_root.iterdir()):
        if entry.is_file():
            sweep.append(entry)
            continue
        if entry.name.startswith(".tmp-"):
            sweep.append(entry)
            continue
        manifest = entry / "manifest.json"
        ok = False
        if manifest.is_file():
            try:
                import json

                data = json.loads(manifest.read_text(encoding="utf-8"))
                ok = (
                    isinstance(data, dict)
                    and data.get("schema") == GameDaySafetyService.SNAPSHOT_SCHEMA
                )
            except (OSError, ValueError):
                ok = False
        (migrate if ok else sweep).append(entry)
    return migrate, sweep


def main(argv: list[str] | None = None) -> int:
    import app

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", default=str(app.LEGACY_GAME_DAY_BACKUP_DIR))
    parser.add_argument("--dest", default=str(app.GAME_DAY_BACKUP_DIR))
    parser.add_argument("--apply", action="store_true", help="Actually move/delete.")
    args = parser.parse_args(argv)

    source = Path(args.source).expanduser()
    dest = Path(args.dest).expanduser()

    if source.resolve() == dest.resolve():
        print(f"Source and destination are the same ({source}); nothing to do.")
        return 0
    if not source.is_dir():
        print(f"No old GameDay backups directory at {source}; nothing to do.")
        return 0

    migrate, sweep = classify(source)
    mig_bytes = sum(_dir_size(d) for d in migrate)
    swp_bytes = sum(_dir_size(p) if p.is_dir() else p.stat().st_size for p in sweep)

    print(f"source: {source}")
    print(f"dest  : {dest}\n")
    print(f"MIGRATE  {len(migrate):>3} real snapshot(s)   {_fmt(mig_bytes)}")
    for d in migrate:
        print(f"  {'move ' if args.apply else 'would move '}{d.name}  ({_fmt(_dir_size(d))})")
    print(f"\nSWEEP    {len(sweep):>3} dead entr(y/ies)   {_fmt(swp_bytes)}")
    for p in sweep:
        print(f"  {'delete ' if args.apply else 'would delete '}{p.name}"
              f"  ({'file' if p.is_file() else 'dir'})")

    if not args.apply:
        print(f"\nDry run. Total reclaimed from {source}: {_fmt(mig_bytes + swp_bytes)}.")
        print("Re-run with --apply.")
        return 0

    dest.mkdir(parents=True, exist_ok=True)
    verifier = _make_verifier(dest)
    moved = 0
    for d in migrate:
        target = dest / d.name
        if target.exists():
            print(f"SKIP  {d.name} (already at destination)")
            continue
        shutil.move(str(d), str(target))
        result = verifier.verify_snapshot(d.name)
        if result.code != "SNAPSHOT_VERIFIED":
            shutil.move(str(target), str(d))  # roll the move back
            print(f"ABORT  {d.name} failed verification at the new location "
                  f"({result.code}); moved back. Nothing else changed.")
            return 1
        moved += 1

    deleted = 0
    for p in sweep:
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            deleted += 1
        except OSError as exc:
            print(f"SKIP  {p.name} ({exc})")

    (dest / ".gameday-backups-migrated").write_text("completed\n", encoding="utf-8")
    print(f"\nMigrated {moved} snapshot(s) ({_fmt(mig_bytes)}) -> {dest}, all re-verified.")
    print(f"Swept {deleted} dead entr(y/ies) ({_fmt(swp_bytes)}) from {source}.")
    remaining = _dir_size(source) if source.is_dir() else 0
    print(f"{source} now holds {_fmt(remaining)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
