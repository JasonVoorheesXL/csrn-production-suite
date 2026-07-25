from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "phase/4.12-logo-service"
VERSION = "1.13.0-alpha.4l"
TITLE = "Logo Service"
BUILD = "V1.13A4L-LOGO-SERVICE"


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
            "from logo_service import LogoService",
            "LOGO_SERVICE: LogoService | None = None",
            "get_logo_service().process_candidate(",
            "get_logo_service().list_records(",
            "return LogoService.extract_colors(image)",
        )
    )


def version_present() -> bool:
    version_text = (ROOT / "VERSION.txt").read_text(encoding="utf-8")
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    return VERSION in version_text and VERSION in app_text and BUILD in app_text


def run_focused_validation() -> None:
    print("Running focused LogoService validation...")
    run(
        (
            sys.executable,
            "-m",
            "py_compile",
            "app.py",
            "logo_service.py",
            "tests/test_logo_service.py",
            "tests/test_logo_routes.py",
        )
    )
    run(
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_logo_service.py",
            "tests/test_logo_routes.py",
            "tests/test_phase_4_12_migration.py",
        )
    )


def main() -> None:
    branch = output("git", "branch", "--show-current")
    if branch != BRANCH:
        raise CompletionError(
            f"Run this only on {BRANCH}; current branch is {branch or 'detached HEAD'}."
        )

    paths = status_paths()
    integrated = integration_present()
    versioned = version_present()
    version_paths = {
        "VERSION.txt",
        "app.py",
        "tests/test_core_repository_runtime.py",
    }

    if not paths and not integrated:
        print("Applying LogoService integration...")
        run((sys.executable, "tools/apply_phase_4_12.py"))
        integrated = integration_present()
    elif paths == {"app.py"} and integrated:
        print("Resuming from the already-applied LogoService integration...")
    elif not paths and integrated and not versioned:
        print("Resuming after the LogoService integration commit...")
    elif paths.issubset(version_paths) and integrated and versioned:
        print("Resuming after interrupted Phase 4.12 full validation...")
    elif paths:
        rendered = ", ".join(sorted(paths))
        raise CompletionError(
            "Working tree contains unexpected changes before Phase 4.12 completion: "
            + rendered
        )

    if not integrated:
        raise CompletionError("LogoService integration markers are incomplete.")

    current_paths = status_paths()
    if current_paths == {"app.py"}:
        run_focused_validation()
        run(("git", "add", "app.py"))
        run(("git", "diff", "--cached", "--check"))
        run(("git", "commit", "-m", "Phase 4.12: integrate Logo Service"))
    elif not current_paths and not versioned:
        run_focused_validation()
    elif current_paths.issubset(version_paths) and versioned:
        run_focused_validation()
    elif current_paths:
        raise CompletionError(
            "Unexpected files after LogoService integration: "
            + ", ".join(sorted(current_paths))
        )

    if not version_present():
        print("Updating the Phase 4.12 runtime identity...")
        run(
            (
                sys.executable,
                "tools/dev_workflow.py",
                "version",
                VERSION,
                TITLE,
            )
        )

    print("Running full repository validation...")
    run((sys.executable, "tools/dev_workflow.py", "validate"))

    temporary_files = (
        "tools/apply_phase_4_12.py",
        "tools/ci_apply.py",
        "tests/test_phase_4_12_migration.py",
        "tools/complete_phase_4_12.py",
    )
    for relative in temporary_files:
        if (ROOT / relative).exists():
            run(("git", "rm", relative))

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
    run(("git", "commit", "-m", "Phase 4.12: complete Logo Service"))
    run(("git", "push", "origin", BRANCH))

    final_status = output("git", "status", "--short")
    if final_status:
        raise CompletionError(
            "Phase commits were pushed, but the local tree is not clean:\n"
            + final_status
        )

    print("Phase 4.12 completion commits pushed successfully.")
    print("Expected focused total: 16 passed.")
    print("Expected final CI total after cleanup: 295 passed.")


if __name__ == "__main__":
    try:
        main()
    except CompletionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
