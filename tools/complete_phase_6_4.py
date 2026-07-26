from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "phase/6.4-channel-captioning"
FOCUSED_TESTS = (
    "tests/test_caption_service.py",
    "tests/test_caption_routes.py",
    "tests/test_caption_worker.py",
    "tests/test_caption_architecture.py",
    "tests/test_phase_6_4_migration.py",
    "tests/test_commissioning_service.py",
)
WORKFLOW_PHASE_BLOCK = """      - name: Apply commercial channel defaults
        run: python tools/fix_phase_6_4_commercial_defaults.py

"""


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(args))
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        check=check,
    )


def output(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def main() -> int:
    branch = output("git", "branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        print(f"ERROR: Expected branch {EXPECTED_BRANCH!r}; current branch is {branch!r}.")
        return 2

    run(sys.executable, "tools/fix_phase_6_4_commercial_defaults.py")

    caption_source = (ROOT / "caption_service.py").read_text(encoding="utf-8")
    commissioning_source = (ROOT / "commissioning_service.py").read_text(encoding="utf-8")
    product_defaults = caption_source + "\n" + commissioning_source
    forbidden = ('"speaker": "Jason"', '"speaker": "Jordan"')
    remaining = [item for item in forbidden if item in product_defaults]
    if remaining:
        print("ERROR: Personal broadcaster names remain in commercial defaults:", remaining)
        return 3

    print("Running focused Phase 6.4 validation...")
    run(sys.executable, "-m", "pytest", "-q", *FOCUSED_TESTS)

    print("Running full repository validation...")
    run(sys.executable, "tools/dev_workflow.py", "validate")

    workflow = ROOT / ".github" / "workflows" / "validate.yml"
    workflow_text = workflow.read_text(encoding="utf-8")
    if WORKFLOW_PHASE_BLOCK not in workflow_text:
        print("ERROR: Phase-specific workflow block was not found.")
        return 4
    workflow.write_text(
        workflow_text.replace(WORKFLOW_PHASE_BLOCK, ""),
        encoding="utf-8",
    )

    for relative in (
        "tools/fix_phase_6_4_commercial_defaults.py",
        "tools/complete_phase_6_4.py",
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
        print("ERROR: No staged Phase 6.4 completion changes were found.")
        return 5

    run(
        "git",
        "commit",
        "-m",
        "Phase 6.4: complete Channel-Based Captioning",
    )
    run("git", "push", "origin", EXPECTED_BRANCH)

    print("Phase 6.4 completion commits pushed successfully.")
    print("Commercial defaults use neutral announcer labels.")
    print("Speaker names remain assignable per installation and channel.")
    print("Expected focused total: 52 passed.")
    print("Expected final CI total after cleanup: 898 passed.")
    print("Next planned stage: Phase 6.5 Venue Weather Monitoring and Alert Overlay.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
