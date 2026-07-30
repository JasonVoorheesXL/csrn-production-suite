from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

from tools.build_release_package import BuildError, build, sha256
from tools.environment_check import (
    EnvironmentError,
    profile_pins,
    requirement_pins,
)


ROOT = Path(__file__).resolve().parents[1]


def run_git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
    )


def test_runtime_and_development_requirements_are_exactly_pinned() -> None:
    runtime = profile_pins("runtime")
    development = profile_pins("development")

    assert runtime
    assert development.items() >= runtime.items()
    assert runtime["flask"] == "3.0.3"
    assert runtime["pillow"] == "12.3.0"
    assert development["pytest"] == "9.1.1"


def test_requirement_parser_rejects_floating_versions(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("Pillow>=12.0\n", encoding="utf-8")

    with pytest.raises(EnvironmentError, match="non-exact"):
        requirement_pins(requirements)


def test_command_center_startup_never_installs_or_upgrades_packages() -> None:
    launcher = (ROOT / "RUN_CSRN_COMMAND_CENTER.bat").read_text(encoding="utf-8")

    assert "environment_check.py --profile runtime" in launcher
    assert "pip install" not in launcher
    assert "pip --upgrade" not in launcher
    assert "SETUP_CSRN_ENVIRONMENT.bat" in launcher


def test_ci_installs_and_verifies_the_development_lock() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(
        encoding="utf-8"
    )

    assert "-r requirements-dev.txt" in workflow
    assert "environment_check.py --profile development" in workflow
    assert "pip install pytest" not in workflow
    assert "pip install --upgrade pip" not in workflow


def test_pytest_discovery_is_confined_to_authoritative_tests() -> None:
    config = (ROOT / "pytest.ini").read_text(encoding="utf-8")
    workflow = (ROOT / "tools/dev_workflow.py").read_text(encoding="utf-8")

    assert "testpaths = tests" in config
    assert "    Data" in config
    assert '"tests",' in workflow
    assert '"--ignore=qrcode",' not in workflow


def test_release_build_is_deterministic_and_uses_only_tracked_files(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("print('tracked')\n", encoding="utf-8")
    (source / "untracked.txt").write_text("exclude me\n", encoding="utf-8")
    (source / "Data").mkdir()
    (source / "Data" / "security.json").write_text(
        '{"secret": true}\n',
        encoding="utf-8",
    )
    run_git(source, "init")
    run_git(source, "config", "user.name", "CSRN Test")
    run_git(source, "config", "user.email", "tests@csrn.invalid")
    run_git(source, "add", "app.py")
    run_git(source, "commit", "-m", "fixture")

    first = build(
        tmp_path / "first",
        version="1.13.0-alpha.8f",
        build_id="V1.13A8F-SOURCE-ALIGNMENT",
        root=source,
        epoch=1_700_000_000,
    )
    second = build(
        tmp_path / "second",
        version="1.13.0-alpha.8f",
        build_id="V1.13A8F-SOURCE-ALIGNMENT",
        root=source,
        epoch=1_700_000_000,
    )

    first_archive = Path(str(first["archive"]))
    second_archive = Path(str(second["archive"]))
    assert sha256(first_archive) == sha256(second_archive)
    with zipfile.ZipFile(first_archive) as archive:
        names = archive.namelist()
    assert any(name.endswith("/app.py") for name in names)
    assert not any(name.endswith("/untracked.txt") for name in names)
    assert not any("/Data/" in name for name in names)


def test_release_build_rejects_path_tokens(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="Version"):
        build(
            tmp_path,
            version="../unsafe",
            build_id="SAFE",
            root=ROOT,
            epoch=1_700_000_000,
        )


def test_release_build_rejects_modified_tracked_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    tracked = source / "app.py"
    tracked.write_text("print('committed')\n", encoding="utf-8")
    run_git(source, "init")
    run_git(source, "config", "user.name", "CSRN Test")
    run_git(source, "config", "user.email", "tests@csrn.invalid")
    run_git(source, "add", "app.py")
    run_git(source, "commit", "-m", "fixture")
    tracked.write_text("print('dirty')\n", encoding="utf-8")

    with pytest.raises(BuildError, match="Tracked files are modified"):
        build(
            tmp_path / "output",
            version="1.13.0-alpha.8f",
            build_id="V1.13A8F-SOURCE-ALIGNMENT",
            root=source,
            epoch=1_700_000_000,
        )
