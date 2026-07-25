from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "phase/4.15-state-service"


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
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    return all(
        marker in text
        for marker in (
            "from state_service import StateService",
            "STATE_SERVICE: StateService | None = None",
            'return get_state_service().load().data["state"]',
            'get_state_service().save(state)',
            'return get_state_service().public(state).data["state"]',
        )
    )


def main() -> None:
    branch = output("git", "branch", "--show-current")
    if branch != BRANCH:
        raise CompletionError(
            f"Run this only on {BRANCH}; current branch is {branch or 'detached HEAD'}."
        )

    initial_paths = status_paths()
    if not initial_paths:
        print("Applying StateService integration...")
        run((sys.executable, "tools/apply_phase_4_15.py"))
    elif initial_paths == {"app.py"} and integration_present():
        print("Resuming from the already-applied StateService integration...")
    else:
        rendered = ", ".join(sorted(initial_paths)) or "unknown files"
        raise CompletionError(
            "Working tree contains unexpected changes before Phase 4.15 completion: "
            + rendered
        )

    if status_paths() != {"app.py"}:
        raise CompletionError(
            "StateService integration changed unexpected files: "
            + ", ".join(sorted(status_paths()))
        )

    print("Running focused StateService validation...")
    run((sys.executable, "-m", "py_compile", "app.py", "state_service.py"))
    run(
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_state_service.py",
            "tests/test_state_routes.py",
            "tests/test_phase_4_15_migration.py",
        )
    )

    run(("git", "add", "app.py"))
    run(("git", "diff", "--cached", "--check"))
    run(("git", "commit", "-m", "Phase 4.15: integrate State Service"))

    print("Updating the Phase 4.15 runtime identity...")
    run(
        (
            sys.executable,
            "tools/dev_workflow.py",
            "version",
            "1.13.0-alpha.4o",
            "State Service",
        )
    )

    print("Running full repository validation...")
    run((sys.executable, "tools/dev_workflow.py", "validate"))

    run(("git", "rm", "tools/apply_phase_4_15.py"))
    run(("git", "rm", "tools/ci_apply.py"))
    run(("git", "rm", "tests/test_phase_4_15_migration.py"))
    run(("git", "rm", "tools/complete_phase_4_15.py"))
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
    run(("git", "commit", "-m", "Phase 4.15: complete State Service"))
    run(("git", "push", "origin", BRANCH))

    final_status = output("git", "status", "--short")
    if final_status:
        raise CompletionError(
            "Phase commits were pushed, but the local tree is not clean:\n"
            + final_status
        )

    print("Phase 4.15 completion commits pushed successfully.")
    print("Expected focused total: 16 passed.")
    print("Expected final CI total after cleanup: 344 passed.")


if __name__ == "__main__":
    try:
        main()
    except CompletionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
