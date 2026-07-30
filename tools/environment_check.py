from __future__ import annotations

import argparse
import sys
from importlib import metadata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_PYTHON = (3, 13, 14)
PROFILE_FILES = {
    "runtime": ("requirements.txt",),
    "development": ("requirements.txt", "requirements-dev.txt"),
}


class EnvironmentError(RuntimeError):
    """Raised when the active Python environment does not match the lock."""


def requirement_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-r "):
            continue
        if "==" not in line:
            raise EnvironmentError(
                f"{path.name} contains a non-exact requirement: {line}"
            )
        name, version = (part.strip() for part in line.split("==", 1))
        if not name or not version:
            raise EnvironmentError(f"Invalid requirement in {path.name}: {line}")
        pins[name.casefold()] = version
    return pins


def profile_pins(profile: str, root: Path = ROOT) -> dict[str, str]:
    pins: dict[str, str] = {}
    for filename in PROFILE_FILES[profile]:
        pins.update(requirement_pins(root / filename))
    return pins


def environment_errors(profile: str, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    actual_python = sys.version_info[:3]
    if actual_python != SUPPORTED_PYTHON:
        errors.append(
            "Python "
            + ".".join(str(part) for part in SUPPORTED_PYTHON)
            + " is required; found "
            + ".".join(str(part) for part in actual_python)
            + "."
        )

    for name, expected in sorted(profile_pins(profile, root).items()):
        try:
            actual = metadata.version(name)
        except metadata.PackageNotFoundError:
            errors.append(f"{name}=={expected} is not installed.")
            continue
        if actual != expected:
            errors.append(f"{name} must be {expected}; found {actual}.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that the active CSRN Python environment matches its lock."
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_FILES),
        default="runtime",
    )
    args = parser.parse_args()

    errors = environment_errors(args.profile)
    if errors:
        print("CSRN environment verification failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(
        "CSRN "
        f"{args.profile} environment verified on "
        "Python " + ".".join(str(part) for part in SUPPORTED_PYTHON) + "."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
