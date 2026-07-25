from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "phase/4.10-asset-service"
IDENTITY_PATHS = {
    "VERSION.txt",
    "app.py",
    "tests/test_core_repository_runtime.py",
}


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


def asset_integration_present() -> bool:
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    return all(
        marker in app_text
        for marker in (
            "from asset_service import AssetService",
            "ASSET_SERVICE: AssetService | None = None",
            "def get_asset_service() -> AssetService:",
            "result = get_asset_service().create(",
            "result = get_asset_service().update(",
            "result = get_asset_service().delete(",
            "service.duplicate_by_hash(sha256, exclude_id=asset_id)",
            "service.attach_file(",
        )
    )


def runtime_identity_present() -> bool:
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    version_text = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
    runtime_test = (
        ROOT / "tests" / "test_core_repository_runtime.py"
    ).read_text(encoding="utf-8")
    markers = (
        "Version 1.13.0-alpha.4j — Asset Service",
        "V1.13A4J-ASSET-SERVICE",
    )
    return (
        all(marker in app_text for marker in markers)
        and version_text == "1.13.0-alpha.4j"
        and all(marker in runtime_test for marker in markers)
    )


def remove_tracked_file(path: str) -> None:
    if (ROOT / path).exists():
        run(("git", "rm", path))


def main() -> None:
    branch = output("git", "branch", "--show-current")
    if branch != BRANCH:
        raise CompletionError(
            f"Run this only on {BRANCH}; current branch is {branch or 'detached HEAD'}."
        )

    initial_paths = status_paths()
    integrated = asset_integration_present()
    versioned = runtime_identity_present()

    if not initial_paths and not integrated:
        print("Applying AssetService integration...")
        run((sys.executable, "tools/apply_phase_4_10.py"))
    elif initial_paths == {"app.py"} and integrated and not versioned:
        print("Resuming from the already-applied AssetService integration...")
    elif initial_paths == IDENTITY_PATHS and integrated and versioned:
        print("Resuming after an interrupted Phase 4.10 full validation...")
    elif not initial_paths and integrated:
        print("Resuming from the committed AssetService integration...")
    else:
        rendered = ", ".join(sorted(initial_paths)) or "unknown files"
        raise CompletionError(
            "Working tree contains unexpected changes before Phase 4.10 completion: "
            + rendered
        )

    changed = status_paths()
    if changed not in (set(), {"app.py"}, IDENTITY_PATHS):
        raise CompletionError(
            "Asset integration changed unexpected files: "
            + ", ".join(sorted(changed))
        )
    if not asset_integration_present():
        raise CompletionError("AssetService integration markers are incomplete.")

    print("Running focused AssetService validation...")
    run(
        (
            sys.executable,
            "-m",
            "py_compile",
            "app.py",
            "asset_service.py",
            "tests/test_asset_service.py",
            "tests/test_asset_routes.py",
            "tests/test_phase_4_10_migration.py",
        )
    )
    run(
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_asset_service.py",
            "tests/test_asset_routes.py",
            "tests/test_phase_4_10_migration.py",
        )
    )

    if status_paths() == {"app.py"}:
        run(("git", "add", "app.py"))
        run(("git", "diff", "--cached", "--check"))
        run(("git", "commit", "-m", "Phase 4.10: integrate Asset Service"))

    if not runtime_identity_present():
        if status_paths():
            raise CompletionError(
                "Runtime identity cannot be updated while unrelated changes exist."
            )
        print("Updating the Phase 4.10 runtime identity...")
        run(
            (
                sys.executable,
                "tools/dev_workflow.py",
                "version",
                "1.13.0-alpha.4j",
                "Asset Service",
            )
        )
    else:
        print("Phase 4.10 runtime identity is already applied.")

    print("Running full repository validation...")
    run((sys.executable, "tools/dev_workflow.py", "validate"))

    remove_tracked_file("tools/apply_phase_4_10.py")
    remove_tracked_file("tools/ci_apply.py")
    remove_tracked_file("tests/test_phase_4_10_migration.py")
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
    run(("git", "commit", "-m", "Phase 4.10: complete Asset Service"))
    run(("git", "push", "origin", BRANCH))

    final_status = output("git", "status", "--short")
    if final_status:
        raise CompletionError(
            "Phase commits were pushed, but the local tree is not clean:\n"
            + final_status
        )

    print("Phase 4.10 completion commits pushed successfully.")
    print("Expected focused total: 21 passed.")
    print("Expected final CI total after cleanup: 260 passed.")


if __name__ == "__main__":
    try:
        main()
    except CompletionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
