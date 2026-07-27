from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "phase/6.8-graphics-theme-engine"
FOCUSED_TESTS = (
    "tests/test_theme_service.py",
    "tests/test_theme_routes.py",
    "tests/test_theme_architecture.py",
    "tests/test_phase_6_8_migration.py",
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

    service_source = (ROOT / "theme_service.py").read_text(encoding="utf-8")
    required_presets = (
        "Classic 1980s Broadcast",
        "Early Cable Sports",
        "Modern Network",
        "Minimal Radio",
        "Heritage Press Box",
        "Friday Night Stadium",
        "Digital Neon",
        "Collegiate Traditional",
    )
    for preset in required_presets:
        if preset not in service_source:
            print(f"ERROR: Required original theme preset is missing: {preset}")
            return 3
    for forbidden in ("ESPN", "Fox Sports", "CBS Sports", "NBC Sports", "TNT Sports"):
        if forbidden in service_source:
            print(f"ERROR: Network-branded theme content was introduced: {forbidden}")
            return 4
    if "OVERRIDE_KEYS" not in service_source or "raw_css" in service_source:
        print("ERROR: Controlled theme override boundary is missing or raw CSS was introduced.")
        return 5

    for template_name in ("overlay.html", "captions.html", "weather.html"):
        source = (ROOT / "templates" / template_name).read_text(encoding="utf-8")
        if source.count('/themes/current.css') != 1:
            print(f"ERROR: Shared theme stylesheet is not integrated exactly once in {template_name}.")
            return 6

    roadmap = (ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md").read_text(encoding="utf-8")
    if "### 6.9 Social Publishing Engine" not in roadmap:
        print("ERROR: The Social Publishing Engine requirement is missing from the roadmap.")
        return 7
    if "player headshots" not in roadmap or "approved sponsor assets" not in roadmap:
        print("ERROR: Social Publishing media requirements are incomplete.")
        return 8

    print("Running focused Phase 6.8 validation...")
    run(sys.executable, "-m", "pytest", "-q", *FOCUSED_TESTS)

    print("Running full repository validation...")
    run(sys.executable, "tools/dev_workflow.py", "validate")

    for relative in (
        "tests/test_phase_6_8_migration.py",
        "tools/ci_apply.py",
        "tools/complete_phase_6_8.py",
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
        print("ERROR: No staged Phase 6.8 completion changes were found.")
        return 9

    run(
        "git",
        "commit",
        "-m",
        "Phase 6.8: complete Graphics Theme Engine",
    )
    run("git", "push", "origin", EXPECTED_BRANCH)

    print("Phase 6.8 completion commits pushed successfully.")
    print("Expected focused total: 46 passed.")
    print("Expected final CI total after cleanup: 1075 passed.")
    print("Next planned stage: Phase 6.9 Social Publishing Engine.")
    print("Social Publishing includes Facebook and X event posts, sponsors, player headshots, retries, corrections, audit history, and postgame handoff.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
