from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "phase/5.3-school-association-routes"
INTEGRATION_COMMIT = "Phase 5.3: integrate school and association route Blueprints"
VERSION = "1.13.0-alpha.5c"
FEATURE = "School and Association Routes"


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
    required = (
        "from routes.school_routes import (",
        "from routes.association_routes import (",
        "SCHOOL_ROUTES_BLUEPRINT = create_school_blueprint(",
        "ASSOCIATION_ROUTES_BLUEPRINT = create_association_blueprint(",
        "app.register_blueprint(SCHOOL_ROUTES_BLUEPRINT)",
        "app.register_blueprint(ASSOCIATION_ROUTES_BLUEPRINT)",
    )
    removed = (
        '@app.get("/api/schools")',
        '@app.post("/api/schools")',
        '@app.get("/api/imports/associations/profiles")',
        '@app.post("/api/imports/associations/preview")',
        '@app.post("/api/imports/mhsaa/5A")',
        "def _association_error_status(",
        "def _association_request_payload(",
    )
    return all(marker in text for marker in required) and all(
        marker not in text for marker in removed
    )


def version_present() -> bool:
    version_text = (ROOT / "VERSION.txt").read_text(encoding="utf-8")
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    identity = "Version 1.13.0-alpha.5c — School and Association Routes"
    return (
        identity in version_text
        and identity in app_text
        and "V1.13A5C-SCHOOL-AND-ASSOCIATION-ROUTES" in app_text
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
    integration_committed = (
        integration_present() and head_message == INTEGRATION_COMMIT
    )
    version_paths = {
        "VERSION.txt",
        "app.py",
        "tests/test_core_repository_runtime.py",
    }

    if not initial_paths and not integration_committed:
        print("Applying school and association route integration...")
        run((sys.executable, "tools/apply_phase_5_3.py"))
    elif initial_paths == {"app.py"} and integration_present():
        print("Resuming from the already-applied route integration...")
    elif integration_committed and initial_paths.issubset(version_paths):
        print("Resuming after the route integration commit...")
    elif not initial_paths and integration_committed:
        print("Resuming after the route integration commit...")
    else:
        rendered = ", ".join(sorted(initial_paths)) or "unknown files"
        raise CompletionError(
            "Working tree contains unexpected changes before Phase 5.3 completion: "
            + rendered
        )

    print("Running focused school and association route validation...")
    run(
        (
            sys.executable,
            "-m",
            "py_compile",
            "app.py",
            "routes/school_routes.py",
            "routes/association_routes.py",
        )
    )
    run(
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_school_routes_blueprint.py",
            "tests/test_association_routes_blueprint.py",
            "tests/test_school_association_route_architecture.py",
            "tests/test_phase_5_3_migration.py",
        )
    )

    if not integration_committed:
        if status_paths() != {"app.py"}:
            raise CompletionError(
                "Route integration changed unexpected files: "
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
        print("Updating the Phase 5.3 runtime identity...")
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
        print("Phase 5.3 runtime identity is already updated.")

    print("Running full repository validation...")
    run((sys.executable, "tools/dev_workflow.py", "validate"))

    run(("git", "rm", "tools/apply_phase_5_3.py"))
    run(("git", "rm", "tools/ci_apply.py"))
    run(("git", "rm", "tests/test_phase_5_3_migration.py"))
    run(("git", "rm", "tools/complete_phase_5_3.py"))
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
            "Phase 5.3: complete School and Association Routes",
        )
    )
    run(("git", "push", "origin", BRANCH))

    final_status = output("git", "status", "--short")
    if final_status:
        raise CompletionError(
            "Phase commits were pushed, but the local tree is not clean:\n"
            + final_status
        )

    print("Phase 5.3 completion commits pushed successfully.")
    print("Expected focused total: 29 passed.")
    print("Expected final CI total after cleanup: 595 passed.")


if __name__ == "__main__":
    try:
        main()
    except CompletionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
