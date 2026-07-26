from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "phase/6.5-venue-weather-alert-overlay"
FOCUSED_TESTS = (
    "tests/test_weather_service.py",
    "tests/test_weather_routes.py",
    "tests/test_weather_worker.py",
    "tests/test_weather_architecture.py",
    "tests/test_phase_6_5_migration.py",
)


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(args))
    return subprocess.run(args, cwd=ROOT, text=True, check=check)


def output(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def main() -> int:
    branch = output("git", "branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        print(f"ERROR: Expected branch {EXPECTED_BRANCH!r}; current branch is {branch!r}.")
        return 2

    run("git", "config", "gc.auto", "0")
    run(sys.executable, "tools/ci_apply.py")

    print("Running focused Phase 6.5 validation...")
    run(sys.executable, "-m", "pytest", "-q", *FOCUSED_TESTS)

    print("Running full repository validation...")
    run(sys.executable, "tools/dev_workflow.py", "validate")

    for relative in (
        "tests/test_phase_6_5_migration.py",
        "tools/ci_apply.py",
        "tools/complete_phase_6_5.py",
    ):
        path = ROOT / relative
        if path.exists():
            path.unlink()

    run("git", "diff", "--check")
    run("git", "add", "-A")
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=ROOT,
        check=False,
    ).returncode
    if staged == 0:
        print("ERROR: No staged Phase 6.5 completion changes were found.")
        return 3

    run("git", "commit", "-m", "Phase 6.5: complete Venue Weather Monitoring and Alert Overlay")
    run("git", "push", "origin", EXPECTED_BRANCH)

    print("Phase 6.5 completion commits pushed successfully.")
    print("Expected focused total: 52 passed.")
    print("Expected final CI total after cleanup: 946 passed.")
    print("Next planned stage: Phase 6.6 Operational Rehearsal and Release Freeze.")
    print("Social Publishing Engine remains Phase 6.9.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
