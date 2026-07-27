from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "phase/6.7-installer-updates-licensing-foundation"
FOCUSED_TESTS = (
    "tests/test_product_paths.py",
    "tests/test_entitlement_service.py",
    "tests/test_deployment_service.py",
    "tests/test_deployment_routes.py",
    "tests/test_deployment_architecture.py",
    "tests/test_phase_6_7_migration.py",
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

    path_source = (ROOT / "product_paths.py").read_text(encoding="utf-8")
    if "%LOCALAPPDATA%" in path_source or "runtime_root" not in path_source:
        print("ERROR: Stable runtime path implementation is missing or malformed.")
        return 3

    entitlement_source = (ROOT / "entitlement_service.py").read_text(encoding="utf-8")
    if "A production activation provider must verify" not in entitlement_source:
        print("ERROR: Production license verification boundary is missing.")
        return 4
    if "hmac" in entitlement_source.casefold():
        print("ERROR: A client-side shared license secret was introduced.")
        return 5

    deployment_source = (ROOT / "deployment_service.py").read_text(encoding="utf-8")
    for required in ("sha256", "DOWNGRADE_BLOCKED", "external_updater_required", "[REDACTED]"):
        if required not in deployment_source:
            print(f"ERROR: Deployment safety requirement missing: {required}")
            return 6

    installer = (ROOT / "packaging" / "windows" / "csrn-production-suite.iss").read_text(encoding="utf-8")
    if "Customer runtime data" not in installer or "PrivilegesRequired=lowest" not in installer:
        print("ERROR: Windows installer data-preservation policy is missing.")
        return 7

    roadmap = (ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md").read_text(encoding="utf-8")
    if "### 6.9 Social Publishing Engine" not in roadmap:
        print("ERROR: The Social Publishing Engine requirement is missing from the roadmap.")
        return 8

    print("Running focused Phase 6.7 validation...")
    run(sys.executable, "-m", "pytest", "-q", *FOCUSED_TESTS)

    print("Running full repository validation...")
    run(sys.executable, "tools/dev_workflow.py", "validate")

    for relative in (
        "tests/test_phase_6_7_migration.py",
        "tools/ci_apply.py",
        "tools/complete_phase_6_7.py",
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
        print("ERROR: No staged Phase 6.7 completion changes were found.")
        return 9

    run(
        "git",
        "commit",
        "-m",
        "Phase 6.7: complete Installer Updates and Licensing Foundation",
    )
    run("git", "push", "origin", EXPECTED_BRANCH)

    print("Phase 6.7 completion commits pushed successfully.")
    print("Expected focused total: 56 passed.")
    print("Expected final CI total after cleanup: 1035 passed.")
    print("Next planned stage: Phase 6.8 Graphics Theme Engine.")
    print("Social Publishing Engine remains Phase 6.9.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
