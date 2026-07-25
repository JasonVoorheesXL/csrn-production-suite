from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "phase/4.14-configuration-service"
VERSION = "1.13.0-alpha.4n"
FEATURE = "Configuration Service"


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
    result = run(
        ("git", "status", "--porcelain=v1", "-z"),
        capture=True,
    )
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


def app_text() -> str:
    return (ROOT / "app.py").read_text(encoding="utf-8")


def integration_present() -> bool:
    text = app_text()
    return all(
        marker in text
        for marker in (
            "from configuration_service import ConfigurationService",
            "CONFIGURATION_SERVICE: ConfigurationService | None = None",
            "get_configuration_service().read()",
            "get_configuration_service().update(incoming)",
        )
    )


def version_present() -> bool:
    text = app_text()
    return (
        "Version 1.13.0-alpha.4n — Configuration Service" in text
        and "V1.13A4N-CONFIGURATION-SERVICE" in text
    )


def run_focused_validation() -> None:
    print("Running focused ConfigurationService validation...")
    run(
        (
            sys.executable,
            "-m",
            "py_compile",
            "app.py",
            "configuration_service.py",
        )
    )
    run(
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_configuration_service.py",
            "tests/test_configuration_routes.py",
            "tests/test_phase_4_14_migration.py",
        )
    )


def commit_integration() -> None:
    run(("git", "add", "app.py"))
    run(("git", "diff", "--cached", "--check"))
    run(
        (
            "git",
            "commit",
            "-m",
            "Phase 4.14: integrate Configuration Service",
        )
    )


def main() -> None:
    branch = output("git", "branch", "--show-current")
    if branch != BRANCH:
        raise CompletionError(
            f"Run this only on {BRANCH}; current branch is "
            f"{branch or 'detached HEAD'}."
        )

    paths = status_paths()
    integrated = integration_present()
    versioned = version_present()

    if not paths and not integrated:
        print("Applying ConfigurationService integration...")
        run((sys.executable, "tools/apply_phase_4_14.py"))
        if status_paths() != {"app.py"}:
            raise CompletionError(
                "ConfigurationService integration changed unexpected files."
            )
        run_focused_validation()
        commit_integration()
    elif paths == {"app.py"} and integrated and not versioned:
        print("Resuming from the already-applied ConfigurationService integration...")
        run_focused_validation()
        commit_integration()
    elif not paths and integrated and not versioned:
        print("Resuming after the ConfigurationService integration commit...")
        run_focused_validation()
    elif paths.issubset(
        {"VERSION.txt", "app.py", "tests/test_core_repository_runtime.py"}
    ) and paths and integrated and versioned:
        print("Resuming after interrupted Phase 4.14 full validation...")
        run_focused_validation()
    else:
        rendered = ", ".join(sorted(paths)) or "clean tree"
        raise CompletionError(
            "Working tree is not in a recognized Phase 4.14 state: "
            + rendered
        )

    if not version_present():
        if status_paths():
            raise CompletionError(
                "The tree must be clean before updating the runtime identity."
            )
        print("Updating the Phase 4.14 runtime identity...")
        run(
            (
                sys.executable,
                "tools/dev_workflow.py",
                "version",
                VERSION,
                FEATURE,
            )
        )

    print("Running full repository validation...")
    run((sys.executable, "tools/dev_workflow.py", "validate"))

    run(("git", "rm", "tools/apply_phase_4_14.py"))
    run(("git", "rm", "tools/ci_apply.py"))
    run(("git", "rm", "tests/test_phase_4_14_migration.py"))
    run(("git", "rm", "tools/complete_phase_4_14.py"))
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
    run(
        (
            "git",
            "commit",
            "-m",
            "Phase 4.14: complete Configuration Service",
        )
    )
    run(("git", "push", "origin", BRANCH))

    final_status = output("git", "status", "--short")
    if final_status:
        raise CompletionError(
            "Phase commits were pushed, but the local tree is not clean:\n"
            + final_status
        )

    print("Phase 4.14 completion commits pushed successfully.")
    print("Expected focused total: 16 passed.")
    print("Expected final CI total after cleanup: 329 passed.")


if __name__ == "__main__":
    try:
        main()
    except CompletionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
