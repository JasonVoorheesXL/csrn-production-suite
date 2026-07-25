from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "phase/4.22-support-media-service"
INTEGRATION_COMMIT = "Phase 4.22: integrate Support Media Service"
VERSION = "1.13.0-alpha.4v"
FEATURE = "Support Media Service"


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
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    return all(
        marker in text
        for marker in (
            "from support_media_service import SupportMediaService",
            "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None",
            "get_support_media_service().upload_headshot",
            "get_support_media_service().connection_info",
            "get_support_media_service().qr_svg",
            "return get_support_media_service().local_addresses()",
            "return SupportMediaService.local_ip()",
        )
    )


def version_present() -> bool:
    version_text = (ROOT / "VERSION.txt").read_text(encoding="utf-8")
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    return (
        "Version 1.13.0-alpha.4v — Support Media Service" in version_text
        and "Version 1.13.0-alpha.4v — Support Media Service" in app_text
        and "V1.13A4V-SUPPORT-MEDIA-SERVICE" in app_text
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
    version_paths = {"VERSION.txt", "app.py", "tests/test_core_repository_runtime.py"}

    if not initial_paths and not integration_committed:
        print("Applying SupportMediaService integration...")
        run((sys.executable, "tools/apply_phase_4_22.py"))
    elif initial_paths == {"app.py"} and integration_present():
        print("Resuming from the already-applied SupportMediaService integration...")
    elif integration_committed and initial_paths.issubset(version_paths):
        print("Resuming after the SupportMediaService integration commit...")
    elif not initial_paths and integration_committed:
        print("Resuming after the SupportMediaService integration commit...")
    else:
        rendered = ", ".join(sorted(initial_paths)) or "unknown files"
        raise CompletionError(
            "Working tree contains unexpected changes before Phase 4.22 completion: "
            + rendered
        )

    print("Running focused SupportMediaService validation...")
    run(
        (
            sys.executable,
            "-m",
            "py_compile",
            "app.py",
            "support_media_service.py",
        )
    )
    run(
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_support_media_service.py",
            "tests/test_support_media_routes.py",
            "tests/test_phase_4_22_migration.py",
        )
    )

    if not integration_committed:
        if status_paths() != {"app.py"}:
            raise CompletionError(
                "SupportMediaService integration changed unexpected files: "
                + ", ".join(sorted(status_paths()))
            )
        run(("git", "add", "app.py"))
        run(("git", "diff", "--cached", "--check"))
        run(("git", "commit", "-m", INTEGRATION_COMMIT))

    if not version_present():
        if status_paths():
            raise CompletionError(
                "Runtime identity cannot be updated with a dirty tree: "
                + ", ".join(sorted(status_paths()))
            )
        print("Updating the Phase 4.22 runtime identity...")
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
        print("Phase 4.22 runtime identity is already updated.")

    print("Running full repository validation...")
    run((sys.executable, "tools/dev_workflow.py", "validate"))

    run(("git", "rm", "tools/apply_phase_4_22.py"))
    run(("git", "rm", "tools/ci_apply.py"))
    run(("git", "rm", "tests/test_phase_4_22_migration.py"))
    run(("git", "rm", "tools/complete_phase_4_22.py"))
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
    run(("git", "commit", "-m", "Phase 4.22: complete Support Media Service"))
    run(("git", "push", "origin", BRANCH))

    final_status = output("git", "status", "--short")
    if final_status:
        raise CompletionError(
            "Phase commits were pushed, but the local tree is not clean:\n"
            + final_status
        )

    print("Phase 4.22 completion commits pushed successfully.")
    print("Expected focused total: 24 passed.")
    print("Expected final CI total after cleanup: 504 passed.")


if __name__ == "__main__":
    try:
        main()
    except CompletionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
