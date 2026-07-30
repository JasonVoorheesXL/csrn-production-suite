from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
SUPPORTED_PYTHON = (3, 13, 14)
PROFILE_REQUIREMENTS = {
    "runtime": ROOT / "requirements.txt",
    "development": ROOT / "requirements-dev.txt",
}


class SetupError(RuntimeError):
    """Raised when the guarded environment setup cannot continue."""


def venv_python(venv: Path = VENV) -> Path:
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def python_is_supported(executable: Path) -> bool:
    if not executable.is_file():
        return False
    result = subprocess.run(
        [
            str(executable),
            "-c",
            (
                "import sys; "
                f"raise SystemExit(sys.version_info[:3] != {SUPPORTED_PYTHON!r})"
            ),
        ],
        cwd=ROOT,
        check=False,
    )
    return result.returncode == 0


def stale_destination(root: Path = ROOT) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = root / f".venv-stale-{stamp}"
    suffix = 1
    while candidate.exists():
        candidate = root / f".venv-stale-{stamp}-{suffix}"
        suffix += 1
    return candidate


def prepare_venv(root: Path = ROOT) -> Path:
    venv = root / ".venv"
    executable = venv_python(venv)
    if venv.exists() and not python_is_supported(executable):
        destination = stale_destination(root)
        print(f"Preserving incompatible environment as {destination.name}...")
        venv.replace(destination)

    if not venv.exists():
        print("Creating CSRN Python 3.13.14 environment...")
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv)],
            cwd=root,
            check=True,
        )
    return venv_python(venv)


def setup(profile: str, root: Path = ROOT) -> None:
    if sys.version_info[:3] != SUPPORTED_PYTHON:
        raise SetupError(
            "Run this setup with Python "
            + ".".join(str(part) for part in SUPPORTED_PYTHON)
            + "."
        )

    executable = prepare_venv(root)
    requirements = PROFILE_REQUIREMENTS[profile]
    print(f"Synchronizing {profile} packages from {requirements.name}...")
    subprocess.run(
        [
            str(executable),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(requirements),
        ],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [
            str(executable),
            str(root / "tools" / "environment_check.py"),
            "--profile",
            profile,
        ],
        cwd=root,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or synchronize the guarded CSRN Python environment."
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_REQUIREMENTS),
        default="runtime",
    )
    args = parser.parse_args()
    try:
        setup(args.profile)
    except (OSError, SetupError, subprocess.CalledProcessError) as exc:
        print(f"CSRN environment setup failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
