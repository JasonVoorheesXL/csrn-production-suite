from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "phase/6.6-operational-rehearsal-release-freeze"
FOCUSED_TESTS = (
    "tests/test_operational_rehearsal_service.py",
    "tests/test_rehearsal_routes.py",
    "tests/test_rehearsal_architecture.py",
    "tests/test_phase_6_6_migration.py",
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

    service_source = (ROOT / "operational_rehearsal_service.py").read_text(
        encoding="utf-8"
    )
    if 'REQUIRED_REHEARSALS = 2' not in service_source:
        print("ERROR: The two-rehearsal release gate is missing.")
        return 3
    if 'FREEZE GAME DAY RELEASE' not in service_source:
        print("ERROR: The guarded release-freeze confirmation is missing.")
        return 4

    roadmap = (
        ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md"
    ).read_text(encoding="utf-8")
    if "### 6.9 Social Publishing Engine" not in roadmap:
        print("ERROR: The Social Publishing Engine requirement is missing from the roadmap.")
        return 5

    print("Running focused Phase 6.6 validation...")
    run(sys.executable, "-m", "pytest", "-q", *FOCUSED_TESTS)

    print("Running full repository validation...")
    run(sys.executable, "tools/dev_workflow.py", "validate")

    for relative in (
        "tests/test_phase_6_6_migration.py",
        "tools/ci_apply.py",
        "tools/complete_phase_6_6.py",
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
        print("ERROR: No staged Phase 6.6 completion changes were found.")
        return 6

    run(
        "git",
        "commit",
        "-m",
        "Phase 6.6: complete Operational Rehearsal and Release Freeze",
    )
    run("git", "push", "origin", EXPECTED_BRANCH)

    print("Phase 6.6 completion commits pushed successfully.")
    print("Expected focused total: 42 passed.")
    print("Expected final CI total after cleanup: 983 passed.")
    print("The release remains unfrozen until two real operator rehearsals pass.")
    print("Next planned stage: Phase 6.7 Installer, Updates, and Licensing Foundation.")
    print("Social Publishing Engine remains Phase 6.9.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
