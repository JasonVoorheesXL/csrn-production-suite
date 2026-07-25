from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "phase/4.7-venue-service"


class CompletionError(RuntimeError):
    pass


def run(
    args: Sequence[str],
    *,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        cwd=ROOT,
        text=True,
        capture_output=capture,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise CompletionError(
            f"Command failed ({result.returncode}): {' '.join(args)}"
            + (f"\n{detail}" if detail else "")
        )
    return result


def output(*args: str) -> str:
    return run(args, capture=True).stdout.strip()


def status_paths() -> set[str]:
    paths: set[str] = set()
    for line in output("git", "status", "--short").splitlines():
        if line.strip():
            paths.add(line[3:].strip())
    return paths


def main() -> None:
    branch = output("git", "branch", "--show-current")
    if branch != BRANCH:
        raise CompletionError(
            f"Run this only on {BRANCH}; current branch is {branch or 'detached HEAD'}."
        )

    initial_status = output("git", "status", "--short")
    if initial_status:
        raise CompletionError(
            "Working tree must be clean before Phase 4.7 completion:\n"
            + initial_status
        )

    print("Applying VenueService integration...")
    run((sys.executable, "tools/apply_phase_4_7.py"))
    changed = status_paths()
    if changed != {"app.py"}:
        raise CompletionError(
            "Venue integration changed unexpected files: "
            + ", ".join(sorted(changed))
        )

    print("Running focused VenueService validation...")
    run((sys.executable, "-m", "py_compile", "app.py", "venue_service.py"))
    run(
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_venue_service.py",
            "tests/test_venue_routes.py",
            "tests/test_phase_4_7_migration.py",
        )
    )

    run(("git", "add", "app.py"))
    run(("git", "diff", "--cached", "--check"))
    run(("git", "commit", "-m", "Phase 4.7: integrate Venue Service"))

    print("Updating the Phase 4.7 runtime identity...")
    run(
        (
            sys.executable,
            "tools/dev_workflow.py",
            "version",
            "1.13.0-alpha.4g",
            "Venue Service",
        )
    )

    print("Running full repository validation...")
    run((sys.executable, "tools/dev_workflow.py", "validate"))

    run(("git", "rm", "tools/apply_phase_4_7.py"))
    run(("git", "rm", "tests/test_phase_4_7_migration.py"))
    run(
        (
            "git",
            "add",
            "VERSION.txt",
            "app.py",
            "tests/test_core_repository_runtime.py",
        )
    )
    run(("git", "diff", "--cached", "--check"))
    run(("git", "commit", "-m", "Phase 4.7: complete Venue Service"))
    run(("git", "push", "origin", BRANCH))

    final_status = output("git", "status", "--short")
    if final_status:
        raise CompletionError(
            "Phase commits were pushed, but the local tree is not clean:\n"
            + final_status
        )

    print("Phase 4.7 completion commits pushed successfully.")
    print("Expected final CI total after cleanup: 205 passed.")


if __name__ == "__main__":
    try:
        main()
    except CompletionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
