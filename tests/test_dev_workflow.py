from __future__ import annotations

from pathlib import Path

import pytest

from tools.dev_workflow import (
    RuntimeIdentity,
    WorkflowError,
    build_identity,
    conflict_ref_files,
    render_version_file,
    runtime_identity,
    slugify,
    update_identity,
    validate_identity,
    version_file_token,
    version_token,
)


def write_identity_fixture(root: Path) -> RuntimeIdentity:
    old = RuntimeIdentity(
        version="Version 1.13.0-alpha.4a — Service Layer Foundation",
        build="V1.13A4A-SERVICE-LAYER-FOUNDATION",
    )
    (root / "tests").mkdir(parents=True)
    (root / "app.py").write_text(
        "RUNTIME_VERSION = (\n"
        f"    {old.version!r}\n"
        ")\n"
        f"RUNTIME_BUILD = {old.build!r}\n",
        encoding="utf-8",
    )
    (root / "VERSION.txt").write_text(
        render_version_file(old),
        encoding="utf-8",
    )
    (root / "tests" / "test_core_repository_runtime.py").write_text(
        f"EXPECTED_VERSION = {old.version!r}\n"
        f"EXPECTED_BUILD = {old.build!r}\n",
        encoding="utf-8",
    )
    return old


def test_build_identity_uses_version_and_title() -> None:
    identity = build_identity(
        "1.13.0-alpha.4b",
        "Broadcast Package Service",
    )

    assert identity.version == (
        "Version 1.13.0-alpha.4b — Broadcast Package Service"
    )
    assert identity.build == "V1.13A4B-BROADCAST-PACKAGE-SERVICE"
    assert version_token(identity.version) == "1.13.0-alpha.4b"


def test_build_identity_rejects_invalid_version() -> None:
    with pytest.raises(WorkflowError, match="1.13.0-alpha.4b"):
        build_identity("1.13.4b", "Invalid")


def test_runtime_identity_reads_literal_constants(tmp_path: Path) -> None:
    expected = write_identity_fixture(tmp_path)

    assert runtime_identity(tmp_path / "app.py") == expected


def test_validate_identity_reads_canonical_version_file(
    tmp_path: Path,
) -> None:
    expected = write_identity_fixture(tmp_path)

    assert validate_identity(tmp_path) == expected
    assert version_file_token(
        (tmp_path / "VERSION.txt").read_text(encoding="utf-8")
    ) == "1.13.0-alpha.4a"


def test_version_file_token_accepts_legacy_single_token() -> None:
    assert version_file_token("1.13.0-alpha.4a\n") == "1.13.0-alpha.4a"


def test_update_identity_synchronizes_expected_files(tmp_path: Path) -> None:
    old = write_identity_fixture(tmp_path)

    updated = update_identity(
        tmp_path,
        "1.13.0-alpha.4b",
        "Developer Workflow Automation",
    )

    assert updated.version == (
        "Version 1.13.0-alpha.4b — Developer Workflow Automation"
    )
    assert updated.build == "V1.13A4B-DEVELOPER-WORKFLOW-AUTOMATION"
    assert (tmp_path / "VERSION.txt").read_text(encoding="utf-8") == (
        "CSRN Production Suite\n"
        "Version 1.13.0-alpha.4b — Developer Workflow Automation\n"
        "Build V1.13A4B-DEVELOPER-WORKFLOW-AUTOMATION\n"
    )

    app_text = (tmp_path / "app.py").read_text(encoding="utf-8")
    test_text = (
        tmp_path / "tests" / "test_core_repository_runtime.py"
    ).read_text(encoding="utf-8")

    assert old.version not in app_text
    assert old.build not in app_text
    assert updated.version in app_text
    assert updated.build in app_text
    assert updated.version in test_text
    assert updated.build in test_text


def test_conflict_ref_files_detects_sync_copy(tmp_path: Path) -> None:
    ref_dir = tmp_path / ".git" / "refs" / "heads"
    ref_dir.mkdir(parents=True)
    conflict = ref_dir / "develop-1.13 (1)"
    conflict.write_text("deadbeef\n", encoding="utf-8")

    assert conflict_ref_files(tmp_path) == [
        Path(".git/refs/heads/develop-1.13 (1)")
    ]


def test_slugify_normalizes_branch_names() -> None:
    assert slugify(" Broadcast Package Service ") == (
        "Broadcast-Package-Service"
    )
