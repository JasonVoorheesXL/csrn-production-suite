from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class RollbackError(RuntimeError):
    pass


def run(args: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=capture,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RollbackError(
            f"Command failed ({result.returncode}): {' '.join(args)}"
            + (f"\n{detail}" if detail else "")
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Move the local source checkout to the registered known-good release."
    )
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args(argv)

    import app as app_module

    service = app_module.get_recovery_service()
    plan = service.rollback_plan()
    if plan.code != "ROLLBACK_PLAN_READY":
        raise RollbackError(f"Rollback is unavailable: {plan.code}")

    commit = str(plan.data["rollback"]["release"]["commit"])
    if args.confirm.strip().lower() != commit.lower():
        raise RollbackError("The confirmation value does not match the known-good commit.")

    status = run(["git", "status", "--porcelain"], capture=True).stdout.strip()
    if status:
        raise RollbackError(
            "The working tree is not clean. Commit, restore, or review changes before rollback."
        )

    run(["git", "cat-file", "-e", f"{commit}^{{commit}}"])
    snapshot = app_module.get_game_day_safety_service().create_snapshot(
        kind="pre-release-rollback",
        note=f"Automatic data snapshot before source rollback to {commit}.",
    )
    if snapshot.code != "SNAPSHOT_CREATED":
        raise RollbackError(f"Pre-rollback snapshot failed: {snapshot.code}")

    run(["git", "switch", "-C", "game-day-known-good", commit])
    print(f"Source rollback completed at {commit}.")
    print("Data was preserved and a pre-release-rollback snapshot was created.")
    print("Run RUN_CSRN_COMMAND_CENTER.bat to restart the known-good build.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RollbackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
