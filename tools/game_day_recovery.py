from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _service():
    import app as app_module

    return app_module.get_recovery_service()


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _render(result) -> None:
    print(json.dumps({"code": result.code, **result.data}, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CSRN game-day recovery controls")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("startup")
    subparsers.add_parser("shutdown")
    subparsers.add_parser("status")
    subparsers.add_parser("clear-unclean")
    subparsers.add_parser("rollback-plan")

    known_good = subparsers.add_parser("mark-known-good")
    known_good.add_argument("--commit", default="")
    known_good.add_argument("--note", default="")

    rehearse = subparsers.add_parser("rehearse")
    rehearse.add_argument("snapshot_id")

    restore = subparsers.add_parser("restore")
    restore.add_argument("snapshot_id")
    restore.add_argument("--confirm", required=True)
    restore.add_argument("--note", default="")

    args = parser.parse_args(argv)
    service = _service()

    if args.command == "startup":
        result = service.mark_startup(pid=os.getpid())
    elif args.command == "shutdown":
        result = service.mark_clean_shutdown()
    elif args.command == "status":
        result = service.status()
    elif args.command == "clear-unclean":
        result = service.clear_unclean_shutdown()
    elif args.command == "rollback-plan":
        result = service.rollback_plan()
    elif args.command == "mark-known-good":
        result = service.register_known_good(
            commit=args.commit or _git_commit(),
            note=args.note,
        )
    elif args.command == "rehearse":
        result = service.rehearse_restore(args.snapshot_id)
    elif args.command == "restore":
        result = service.restore_snapshot(
            args.snapshot_id,
            confirmation=args.confirm,
            note=args.note,
        )
    else:
        parser.error("Unsupported command")
        return 2

    _render(result)
    if result.code in {
        "OK",
        "STARTUP_MARKED",
        "UNCLEAN_SHUTDOWN_DETECTED",
        "CLEAN_SHUTDOWN_MARKED",
        "UNCLEAN_MARKER_CLEARED",
        "KNOWN_GOOD_REGISTERED",
        "ROLLBACK_PLAN_READY",
        "RECOVERY_REHEARSAL_READY",
        "SNAPSHOT_RESTORED",
    }:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
