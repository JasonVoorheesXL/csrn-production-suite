from __future__ import annotations

import argparse
import ast
import py_compile
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_BRANCH = "develop-1.13"


class WorkflowError(RuntimeError):
    """Raised when a guarded workflow operation cannot continue safely."""


@dataclass(frozen=True)
class RuntimeIdentity:
    version: str
    build: str


def run_command(
    args: Sequence[str],
    *,
    root: Path = ROOT,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        cwd=root,
        text=True,
        capture_output=capture_output,
    )
    if check and result.returncode != 0:
        command = " ".join(args)
        detail = (result.stderr or result.stdout or "").strip()
        raise WorkflowError(
            f"Command failed ({result.returncode}): {command}"
            + (f"\n{detail}" if detail else "")
        )
    return result


def git_output(*args: str, root: Path = ROOT) -> str:
    return run_command(
        ("git", *args),
        root=root,
        capture_output=True,
    ).stdout.strip()


def current_branch(root: Path = ROOT) -> str:
    return git_output("branch", "--show-current", root=root)


def working_tree_status(root: Path = ROOT) -> str:
    return git_output("status", "--short", root=root)


def require_clean_tree(root: Path = ROOT) -> None:
    status = working_tree_status(root)
    if status:
        raise WorkflowError(
            "Working tree is not clean. Commit, restore, or review these files first:\n"
            + status
        )


def conflict_ref_files(root: Path = ROOT) -> list[Path]:
    git_dir = root / ".git"
    if not git_dir.exists():
        return []

    matches: list[Path] = []
    for path in git_dir.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.casefold()
        if "(1)" in name or "conflict" in name:
            matches.append(path.relative_to(root))
    return sorted(matches)


def runtime_identity(app_path: Path) -> RuntimeIdentity:
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    values: dict[str, str] = {}

    for node in tree.body:
        name: str | None = None
        value_node: ast.expr | None = None

        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                name = target.id
                value_node = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
            value_node = node.value

        if name not in {"RUNTIME_VERSION", "RUNTIME_BUILD"} or value_node is None:
            continue

        value = ast.literal_eval(value_node)
        if not isinstance(value, str):
            raise WorkflowError(f"{name} must be a string literal in {app_path}.")
        values[name] = value

    missing = {"RUNTIME_VERSION", "RUNTIME_BUILD"} - values.keys()
    if missing:
        raise WorkflowError(
            f"Missing runtime identity fields in {app_path}: {', '.join(sorted(missing))}"
        )

    return RuntimeIdentity(
        version=values["RUNTIME_VERSION"],
        build=values["RUNTIME_BUILD"],
    )


def version_token(runtime_version: str) -> str:
    match = re.match(r"^Version\s+(\S+)", runtime_version)
    if not match:
        raise WorkflowError(
            f"Runtime version does not use the expected format: {runtime_version}"
        )
    return match.group(1)


def version_file_token(version_file: str) -> str:
    lines = [
        line.strip()
        for line in version_file.splitlines()
        if line.strip()
    ]
    version_line = next(
        (line for line in lines if line.startswith("Version ")),
        "",
    )
    if version_line:
        return version_token(version_line)
    if len(lines) == 1 and re.fullmatch(
        r"\d+\.\d+\.\d+-alpha\.\d+[a-z]",
        lines[0],
    ):
        return lines[0]
    raise WorkflowError(
        "VERSION.txt must contain either one semantic version token or a "
        "canonical 'Version ...' line."
    )


def render_version_file(identity: RuntimeIdentity) -> str:
    return (
        "CSRN Production Suite\n"
        f"{identity.version}\n"
        f"Build {identity.build}\n"
    )


def validate_identity(root: Path = ROOT) -> RuntimeIdentity:
    identity = runtime_identity(root / "app.py")
    version_file = (root / "VERSION.txt").read_text(encoding="utf-8").strip()
    runtime_token = version_token(identity.version)
    file_token = version_file_token(version_file)

    if file_token != runtime_token:
        raise WorkflowError(
            "Version identity mismatch:\n"
            f"  VERSION.txt: {file_token}\n"
            f"  app.py:      {runtime_token}"
        )
    return identity


def tracked_python_files(root: Path = ROOT) -> list[Path]:
    output = git_output("ls-files", "*.py", root=root)
    files: list[Path] = []
    for relative in output.splitlines():
        normalized = relative.replace("\\", "/")
        if normalized.startswith("qrcode/"):
            continue
        path = root / relative
        if path.is_file():
            files.append(path)
    return files


def compile_tracked_python(root: Path = ROOT) -> int:
    files = tracked_python_files(root)
    for path in files:
        py_compile.compile(str(path), doraise=True)
    return len(files)


def validate_repository(
    root: Path = ROOT,
    *,
    run_tests: bool = True,
) -> None:
    conflicts = conflict_ref_files(root)
    if conflicts:
        rendered = "\n".join(f"  {path}" for path in conflicts)
        raise WorkflowError(
            "Potential Git sync-conflict files were found:\n" + rendered
        )

    compiled = compile_tracked_python(root)
    print(f"Compiled {compiled} tracked Python files.")

    run_command(("git", "diff", "--check"), root=root)
    print("Git diff check passed.")

    identity = validate_identity(root)
    print(f"Identity passed: {identity.version} / {identity.build}")

    if run_tests:
        run_command(
            (
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--ignore=qrcode",
            ),
            root=root,
        )


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-")
    if not slug:
        raise WorkflowError("A non-empty phase name is required.")
    return slug


def build_identity(version: str, title: str) -> RuntimeIdentity:
    match = re.fullmatch(
        r"(\d+)\.(\d+)\.(\d+)-alpha\.(\d+)([a-z])",
        version,
    )
    if not match:
        raise WorkflowError(
            "Version must use the form 1.13.0-alpha.4b."
        )

    major, minor, _patch, phase, letter = match.groups()
    title = title.strip()
    if not title:
        raise WorkflowError("A build title is required.")

    build_slug = slugify(title).upper()
    return RuntimeIdentity(
        version=f"Version {version} — {title}",
        build=f"V{major}.{minor}A{phase}{letter.upper()}-{build_slug}",
    )


def update_identity(
    root: Path,
    version: str,
    title: str,
) -> RuntimeIdentity:
    old = runtime_identity(root / "app.py")
    new = build_identity(version, title)

    app_path = root / "app.py"
    app_text = app_path.read_text(encoding="utf-8")
    if old.version not in app_text or old.build not in app_text:
        raise WorkflowError("Current app identity text could not be located.")
    app_text = app_text.replace(old.version, new.version, 1)
    app_text = app_text.replace(old.build, new.build, 1)
    app_path.write_text(app_text, encoding="utf-8")

    runtime_test = root / "tests" / "test_core_repository_runtime.py"
    if runtime_test.exists():
        test_text = runtime_test.read_text(encoding="utf-8")
        if old.version not in test_text or old.build not in test_text:
            raise WorkflowError(
                "Current identity was not found in test_core_repository_runtime.py."
            )
        test_text = test_text.replace(old.version, new.version)
        test_text = test_text.replace(old.build, new.build)
        runtime_test.write_text(test_text, encoding="utf-8")

    (root / "VERSION.txt").write_text(
        render_version_file(new),
        encoding="utf-8",
    )
    return new


def start_phase(
    phase: str,
    name: str,
    *,
    root: Path = ROOT,
    base_branch: str = DEFAULT_BASE_BRANCH,
    push: bool = False,
    run_tests: bool = True,
) -> str:
    require_clean_tree(root)

    branch = current_branch(root)
    if branch != base_branch:
        raise WorkflowError(
            f"Start phases from {base_branch}; current branch is {branch}."
        )

    validate_repository(root, run_tests=run_tests)

    phase_branch = f"phase/{phase}-{slugify(name).lower()}"
    exists = run_command(
        ("git", "show-ref", "--verify", "--quiet", f"refs/heads/{phase_branch}"),
        root=root,
        check=False,
    )
    if exists.returncode == 0:
        raise WorkflowError(f"Local branch already exists: {phase_branch}")

    run_command(("git", "switch", "-c", phase_branch), root=root)
    if push:
        run_command(("git", "push", "-u", "origin", phase_branch), root=root)

    return phase_branch


def command_status(_args: argparse.Namespace) -> int:
    identity = validate_identity(ROOT)
    status = working_tree_status(ROOT)
    conflicts = conflict_ref_files(ROOT)

    print(f"Branch:  {current_branch(ROOT)}")
    print(f"Version: {identity.version}")
    print(f"Build:   {identity.build}")
    print("Tree:    clean" if not status else "Tree:    modified")
    if status:
        print(status)

    if conflicts:
        print("Potential Git conflict files:")
        for path in conflicts:
            print(f"  {path}")
        return 1

    print("Git refs: no conflict-copy filenames detected")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    validate_repository(ROOT, run_tests=not args.skip_tests)
    return 0


def command_version(args: argparse.Namespace) -> int:
    require_clean_tree(ROOT)
    identity = update_identity(ROOT, args.version, args.title)
    run_command(("git", "diff", "--check"), root=ROOT)
    print(f"Updated runtime identity to {identity.version}")
    print(f"Build identifier: {identity.build}")
    print("Review and commit VERSION.txt, app.py, and the runtime identity test.")
    return 0


def command_start(args: argparse.Namespace) -> int:
    branch = start_phase(
        args.phase,
        args.name,
        root=ROOT,
        base_branch=args.base,
        push=args.push,
        run_tests=not args.skip_tests,
    )
    print(f"Created branch: {branch}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Guarded developer workflow automation for CSRN Production Suite."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser(
        "status",
        help="Show branch, identity, tree state, and Git conflict-ref health.",
    )
    status_parser.set_defaults(handler=command_status)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Compile tracked Python files, check identity, and run tests.",
    )
    validate_parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Run compile and consistency checks without pytest.",
    )
    validate_parser.set_defaults(handler=command_validate)

    version_parser = subparsers.add_parser(
        "version",
        help="Update VERSION.txt and runtime identity fields together.",
    )
    version_parser.add_argument("version", help="Example: 1.13.0-alpha.4b")
    version_parser.add_argument("title", help="Example: Broadcast Package Service")
    version_parser.set_defaults(handler=command_version)

    start_parser = subparsers.add_parser(
        "start",
        help="Validate the base branch and create a guarded phase branch.",
    )
    start_parser.add_argument("phase", help="Example: 4.3")
    start_parser.add_argument("name", help="Example: broadcast-package-service")
    start_parser.add_argument(
        "--base",
        default=DEFAULT_BASE_BRANCH,
        help=f"Required starting branch. Default: {DEFAULT_BASE_BRANCH}",
    )
    start_parser.add_argument(
        "--push",
        action="store_true",
        help="Push the new branch and set upstream tracking.",
    )
    start_parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip pytest during baseline validation.",
    )
    start_parser.set_defaults(handler=command_start)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except WorkflowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
