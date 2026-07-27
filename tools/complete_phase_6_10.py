from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "phase/6.10-commercial-ux-navigation-onboarding"
FOCUSED_TESTS = (
    "tests/test_credential_vault.py",
    "tests/test_oauth_onboarding_service.py",
    "tests/test_commercial_ux_service.py",
    "tests/test_commercial_ux_routes.py",
    "tests/test_commercial_ux_architecture.py",
    "tests/test_phase_6_10_migration.py",
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
    if output("git", "status", "--porcelain"):
        print("ERROR: Working tree must be clean before Phase 6.10 completion.")
        return 3
    run("git", "fetch", "origin")
    local = output("git", "rev-parse", "HEAD")
    remote = output("git", "rev-parse", f"origin/{EXPECTED_BRANCH}")
    if local != remote:
        print("ERROR: Local branch is not synchronized with origin. Pull before completing Phase 6.10.")
        return 4

    run("git", "config", "gc.auto", "0")
    run(sys.executable, "tools/ci_apply.py")

    app = (ROOT / "app.py").read_text(encoding="utf-8")
    index = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    setup = (ROOT / "templates" / "setup_hub.html").read_text(encoding="utf-8")
    social = (ROOT / "templates" / "social_manager.html").read_text(encoding="utf-8")
    oauth = (ROOT / "oauth_onboarding_service.py").read_text(encoding="utf-8")
    service = (ROOT / "social_service.py").read_text(encoding="utf-8")
    vault = (ROOT / "credential_vault.py").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md").read_text(encoding="utf-8")

    requirements = {
        "runtime identity": "Version 1.13.0-alpha.6j — Commercial UX and Account Onboarding" in app,
        "setup navigation": "Setup &amp; Integrations" in index and "window.location.href='/setup'" in index,
        "theme selector": '<label>Theme<select id="cfgTheme">' in index and '<label>Theme<input id="cfgTheme">' not in index,
        "feature directory": "All product areas" in setup,
        "Facebook guided connection": "Facebook Page" in setup and "Connect ${escapeHtml(provider.label)}" in setup,
        "manual X workflow": all(value in social for value in ("Copy X Text", "Download X Graphic", "Open X", "x.com/intent/post")),
        "no X OAuth UI": "Connect X" not in setup and "No API fees" in setup,
        "X publication blocked": "X_MANUAL_ASSISTED_ONLY" in service and 'str(account.get("platform", "")) != "x"' in service,
        "no raw customer token fields": all(value not in setup for value in ("access_token", "refresh_token", "client_secret", "app_secret", "credentialRef")),
        "Facebook broker": "CSRN_META_OAUTH_BROKER_URL" in oauth,
        "Facebook-only OAuth start": 'if provider not in {"facebook"}' in oauth,
        "Windows protected storage": "CryptProtectData" in vault and "CryptUnprotectData" in vault,
        "exact disconnect confirmation": "DISCONNECT SOCIAL ACCOUNT" in oauth,
        "Phase 6.11 recap": "### 6.11 Grounded Game Recap Engine" in roadmap and "must not invent" in roadmap,
    }
    missing = [name for name, present in requirements.items() if not present]
    if missing:
        print("ERROR: Phase 6.10 safety or usability requirement missing: " + ", ".join(missing))
        return 5

    append_once(
        ROOT / "BUILD_JOURNAL.md",
        "Phase 6.10 - Commercial UX, Navigation, and Account Onboarding",
        """
Phase 6.10 - Commercial UX, Navigation, and Account Onboarding
- Added a unified Setup & Integrations hub and discoverable Command Center entry point.
- Replaced the free-text theme setting with controlled presets and linked the visual gallery.
- Added guided Facebook Page onboarding through the PossumFrog OAuth broker.
- Added no-fee manual assisted X publishing with prepared copy, downloadable graphics, and Open X controls.
- Explicitly blocked X API account configuration, automatic X publication, and X auto-queue processing.
- Added Windows DPAPI protected credential storage, connection tests, and disconnect controls for Facebook.
- Shifted the grounded recap engine to Phase 6.11 and preserved the no-invented-data policy.
""",
    )
    append_once(
        ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md",
        "Commercial UX implementation status: Phase 6.10 foundation integrated.",
        "Commercial UX implementation status: Phase 6.10 foundation integrated.",
    )

    print("Running focused Phase 6.10 validation...")
    run(sys.executable, "-m", "pytest", "-q", *FOCUSED_TESTS)
    print("Running full repository validation...")
    run(sys.executable, "tools/dev_workflow.py", "validate")

    for relative in (
        "tests/test_phase_6_10_migration.py",
        "tools/apply_phase_6_10.py",
        "tools/apply_phase_6_10_x_manual_policy.py",
        "tools/ci_apply.py",
        "tools/complete_phase_6_10.py",
    ):
        path = ROOT / relative
        if path.exists():
            path.unlink()

    run("git", "diff", "--check")
    run("git", "add", "-A")
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False).returncode
    if staged == 0:
        print("ERROR: No staged Phase 6.10 completion changes were found.")
        return 6
    run("git", "commit", "-m", "Phase 6.10: complete commercial UX and account onboarding")
    run("git", "push", "origin", EXPECTED_BRANCH)

    print("Phase 6.10 completion commits pushed successfully.")
    print("Expected focused total: 41 passed.")
    print("Expected final CI total after cleanup: 1181 passed.")
    print("Next planned stage: Phase 6.11 Grounded Game Recap Engine.")
    print("Facebook live publishing requires the registered PossumFrog Meta application and OAuth broker.")
    print("X uses manual assisted publishing and requires no developer account or API credits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
