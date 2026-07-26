from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "phase/6.4-channel-captioning"
INTEGRATION_COMMIT = "Phase 6.4: integrate channel-based captioning"
VERSION = "1.13.0-alpha.6d"
FEATURE = "Channel-Based Captioning"


class CompletionError(RuntimeError):
    pass


def run(args: Sequence[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
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
    result = run(("git", "status", "--porcelain=v1", "-z"), capture=True)
    paths: set[str] = set()
    entries = result.stdout.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        if len(entry) < 4:
            raise CompletionError(f"Unexpected Git status entry: {entry!r}")
        status = entry[:2]
        path = entry[3:]
        if status[0] in {"R", "C"}:
            if index >= len(entries):
                raise CompletionError("Incomplete Git rename/copy status entry.")
            path = entries[index]
            index += 1
        paths.add(path)
    return paths


def integration_present() -> bool:
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    audit_text = (ROOT / "phase5_architecture.py").read_text(encoding="utf-8")
    return (
        "def get_caption_service()" in app_text
        and "CAPTION_ROUTES_BLUEPRINT = " in app_text
        and "APPLICATION_BLUEPRINTS.append(CAPTION_ROUTES_BLUEPRINT)" in app_text
        and '"caption_routes"' in audit_text
        and '"caption_routes.caption_overlay_state"' in audit_text
    )


def version_present() -> bool:
    version_text = (ROOT / "VERSION.txt").read_text(encoding="utf-8")
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    return (
        version_text.strip() == VERSION
        and "Version 1.13.0-alpha.6d — Channel-Based Captioning" in app_text
        and "V1.13A6D-CHANNEL-BASED-CAPTIONING" in app_text
    )


def main() -> None:
    branch = output("git", "branch", "--show-current")
    if branch != BRANCH:
        raise CompletionError(
            f"Run this only on {BRANCH}; current branch is {branch or 'detached HEAD'}."
        )

    run(("git", "config", "--local", "gc.auto", "0"))

    initial_paths = status_paths()
    head_message = output("git", "log", "-1", "--pretty=%s")
    integration_committed = integration_present() and head_message == INTEGRATION_COMMIT
    integration_paths = {"app.py", "phase5_architecture.py"}
    version_paths = {"VERSION.txt", "app.py", "tests/test_core_repository_runtime.py"}

    if not initial_paths and not integration_committed:
        print("Applying channel-based captioning integration...")
        run((sys.executable, "tools/apply_phase_6_4.py"))
    elif initial_paths == integration_paths and integration_present():
        print("Resuming from the already-applied caption integration...")
    elif integration_committed and initial_paths.issubset(version_paths):
        print("Resuming after the caption integration commit...")
    elif not initial_paths and integration_committed:
        print("Resuming after the caption integration commit...")
    else:
        rendered = ", ".join(sorted(initial_paths)) or "unknown files"
        raise CompletionError(
            "Working tree contains unexpected changes before Phase 6.4 completion: "
            + rendered
        )

    print("Running focused channel captioning validation...")
    run(
        (
            sys.executable,
            "-m",
            "py_compile",
            "app.py",
            "caption_service.py",
            "caption_worker.py",
            "routes/caption_routes.py",
            "tools/run_caption_worker.py",
        )
    )
    run(
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_caption_service.py",
            "tests/test_caption_routes.py",
            "tests/test_caption_worker.py",
            "tests/test_caption_architecture.py",
            "tests/test_phase_6_4_migration.py",
        )
    )

    if not integration_committed:
        changed = status_paths()
        if changed != integration_paths:
            raise CompletionError(
                "Caption integration changed unexpected files: "
                + ", ".join(sorted(changed))
            )
        run(("git", "add", *sorted(integration_paths)))
        run(("git", "diff", "--cached", "--check"))
        run(("git", "commit", "-m", INTEGRATION_COMMIT))

    if not version_present():
        if status_paths():
            raise CompletionError(
                "Runtime identity cannot be updated with a dirty tree: "
                + ", ".join(sorted(status_paths()))
            )
        print("Updating the Phase 6.4 runtime identity...")
        run(
            (
                sys.executable,
                "tools/dev_workflow.py",
                "version",
                VERSION,
                FEATURE,
            )
        )
    else:
        print("Phase 6.4 runtime identity is already updated.")

    print("Running full repository validation...")
    run((sys.executable, "tools/dev_workflow.py", "validate"))

    run(("git", "rm", "tools/apply_phase_6_4.py"))
    run(("git", "rm", "tools/ci_apply.py"))
    run(("git", "rm", "tests/test_phase_6_4_migration.py"))
    run(("git", "rm", "tools/complete_phase_6_4.py"))
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
    run(("git", "commit", "-m", "Phase 6.4: complete Channel-Based Captioning"))
    run(("git", "push", "origin", BRANCH))

    final_status = output("git", "status", "--short")
    if final_status:
        raise CompletionError(
            "Phase commits were pushed, but the local tree is not clean:\n"
            + final_status
        )

    print("Phase 6.4 completion commits pushed successfully.")
    print("Expected focused total: 51 passed.")
    print("Expected final CI total after cleanup: 897 passed.")
    print("Next planned stage: Phase 6.5 Venue Weather Monitoring and Alert Overlay.")


if __name__ == "__main__":
    try:
        main()
    except CompletionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
