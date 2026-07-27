from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "phase/6.9-social-publishing-engine"
FOCUSED_TESTS = (
    "tests/test_social_platforms.py",
    "tests/test_social_assets_and_cards.py",
    "tests/test_social_service.py",
    "tests/test_social_routes.py",
    "tests/test_social_architecture.py",
    "tests/test_phase_6_9_migration.py",
)


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(args))
    return subprocess.run(args, cwd=ROOT, text=True, check=check)


def output(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def append_once(path: Path, marker: str, text: str) -> None:
    source = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker not in source:
        path.write_text(source.rstrip() + "\n\n" + text.strip() + "\n", encoding="utf-8")


def main() -> int:
    branch = output("git", "branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        print(f"ERROR: Expected branch {EXPECTED_BRANCH!r}; current branch is {branch!r}.")
        return 2

    run("git", "config", "gc.auto", "0")
    run(sys.executable, "tools/ci_apply.py")

    social_source = (ROOT / "social_service.py").read_text(encoding="utf-8")
    platform_source = (ROOT / "social_platforms.py").read_text(encoding="utf-8")
    route_source = (ROOT / "routes" / "social_routes.py").read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    architecture = (ROOT / "phase5_architecture.py").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md").read_text(encoding="utf-8")

    required_social = (
        "RAW_CREDENTIAL_REJECTED",
        "APPROVE SOCIAL POST",
        "RETRACT SOCIAL POST",
        'EMERGENCY_KINDS = {"WEATHER_EMERGENCY"}',
        "PUBLISH_ATTEMPT",
        "CORRECTION_CREATED",
        "Use only recorded events and available statistics",
    )
    for requirement in required_social:
        if requirement not in social_source:
            print(f"ERROR: Social publishing safety requirement missing: {requirement}")
            return 3

    for secret_name in ("access_token", "refresh_token", "client_secret", "app_secret"):
        if f'state["{secret_name}"]' in social_source:
            print(f"ERROR: Raw credential storage was introduced: {secret_name}")
            return 4

    for requirement in ("/2/media/upload", "/2/tweets", "/photos", "EnvCredentialResolver"):
        if requirement not in platform_source:
            print(f"ERROR: Platform adapter requirement missing: {requirement}")
            return 5

    if route_source.count("@routes.") != route_source.count("@dependencies.require_auth"):
        print("ERROR: Every Social Publishing route must remain authenticated.")
        return 6

    for requirement in (
        "SOCIAL_STATE_FILE",
        "SOCIAL_CARDS_DIR",
        "get_social_service",
        "on_event=lambda event: get_social_service().queue_event(event)",
        "Version 1.13.0-alpha.6i — Social Publishing Engine",
    ):
        if requirement not in app_source:
            print(f"ERROR: Phase 6.9 application integration missing: {requirement}")
            return 7

    if '"social_routes"' not in architecture:
        print("ERROR: Social Publishing blueprint is missing from the architecture audit.")
        return 8
    if "### 6.10 Grounded Game Recap Engine" not in roadmap or "must not invent" not in roadmap:
        print("ERROR: The grounded Phase 6.10 recap requirement is missing.")
        return 9

    append_once(
        ROOT / "BUILD_JOURNAL.md",
        "Phase 6.9 - Social Publishing Engine",
        """
Phase 6.9 - Social Publishing Engine
- Added preview-first X and Facebook Page publishing adapters.
- Added theme-driven event cards with school logos, player headshots, and approved sponsors.
- Added explicit approval, retries, audit history, corrections, retractions, and emergency sponsor suppression.
- Added a grounded postgame data handoff for Phase 6.10.
""",
    )
    append_once(
        ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md",
        "Social Publishing Engine implementation status: Phase 6.9 foundation integrated.",
        "Social Publishing Engine implementation status: Phase 6.9 foundation integrated.",
    )

    print("Running focused Phase 6.9 validation...")
    run(sys.executable, "-m", "pytest", "-q", *FOCUSED_TESTS)

    print("Running full repository validation...")
    run(sys.executable, "tools/dev_workflow.py", "validate")

    for relative in (
        ".github/workflows/phase-6-9-diagnostics.yml",
        "tests/test_phase_6_9_migration.py",
        "tools/ci_apply.py",
        "tools/complete_phase_6_9.py",
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
        print("ERROR: No staged Phase 6.9 completion changes were found.")
        return 10

    run(
        "git",
        "commit",
        "-m",
        "Phase 6.9: complete Social Publishing Engine",
    )
    run("git", "push", "origin", EXPECTED_BRANCH)

    print("Phase 6.9 completion commits pushed successfully.")
    print("Expected focused total: 72 passed.")
    print("Expected final CI total after cleanup: 1142 passed.")
    print("Next planned stage: Phase 6.10 Grounded Game Recap Engine.")
    print("Social Publishing is now implemented with X and Facebook adapters, sponsor/headshot cards, retries, corrections, and audit history.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
