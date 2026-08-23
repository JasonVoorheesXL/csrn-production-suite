from __future__ import annotations

import json
from pathlib import Path

from product_paths import migrate_legacy_runtime, resolve_product_paths


def test_source_checkout_keeps_existing_layout(tmp_path: Path) -> None:
    paths = resolve_product_paths(tmp_path, env={}, frozen=False)
    assert paths.installed_mode is False
    assert paths.data_dir == tmp_path.resolve() / "Data"
    assert paths.state_file == tmp_path.resolve() / "state.json"


def test_installed_mode_uses_local_app_data(tmp_path: Path) -> None:
    local = tmp_path / "Local"
    paths = resolve_product_paths(tmp_path / "app", env={"LOCALAPPDATA": str(local)}, frozen=True)
    assert paths.installed_mode is True
    assert paths.runtime_root == (local / "PossumFrog" / "CSRN Production Suite").resolve()
    assert paths.data_dir == paths.runtime_root / "Data"


def test_installed_environment_flag_is_supported(tmp_path: Path) -> None:
    paths = resolve_product_paths(
        tmp_path / "app",
        env={"CSRN_INSTALLED": "yes", "LOCALAPPDATA": str(tmp_path / "Local")},
    )
    assert paths.installed_mode is True


def test_runtime_root_override_is_authoritative(tmp_path: Path) -> None:
    runtime = tmp_path / "CustomerData"
    paths = resolve_product_paths(tmp_path / "app", env={"CSRN_RUNTIME_ROOT": str(runtime)})
    assert paths.runtime_root == runtime.resolve()
    assert paths.data_dir == runtime.resolve() / "Data"


def test_data_root_override_can_be_separate(tmp_path: Path) -> None:
    data = tmp_path / "SeparateData"
    paths = resolve_product_paths(tmp_path / "app", env={"CSRN_DATA_ROOT": str(data)})
    assert paths.installed_mode is True
    assert paths.data_dir == data.resolve()


def test_ensure_creates_runtime_directories(tmp_path: Path) -> None:
    paths = resolve_product_paths(
        tmp_path / "app",
        env={"CSRN_RUNTIME_ROOT": str(tmp_path / "runtime")},
    )
    paths.ensure()
    assert paths.data_dir.is_dir()
    assert paths.logs_dir.is_dir()
    assert paths.license_file.parent.is_dir()


def test_legacy_migration_requires_exact_confirmation(tmp_path: Path) -> None:
    paths = resolve_product_paths(
        tmp_path / "app",
        env={"CSRN_RUNTIME_ROOT": str(tmp_path / "runtime")},
    )
    assert migrate_legacy_runtime(paths, confirmation="no")["status"] == "CONFIRMATION_REQUIRED"


def test_legacy_migration_copies_runtime_data(tmp_path: Path) -> None:
    app = tmp_path / "app"
    (app / "Data" / "Schools").mkdir(parents=True)
    (app / "Data" / "Schools" / "schools.json").write_text("[]", encoding="utf-8")
    (app / "state.json").write_text(json.dumps({"status": "planned"}), encoding="utf-8")
    paths = resolve_product_paths(app, env={"CSRN_RUNTIME_ROOT": str(tmp_path / "runtime")})
    result = migrate_legacy_runtime(paths, confirmation="MIGRATE LEGACY CSRN DATA")
    assert result["status"] == "MIGRATED"
    assert (paths.data_dir / "Schools" / "schools.json").exists()
    assert paths.state_file.exists()


def test_legacy_migration_does_not_overwrite_existing_customer_data(tmp_path: Path) -> None:
    app = tmp_path / "app"
    (app / "Data" / "Settings").mkdir(parents=True)
    (app / "Data" / "Settings" / "config.json").write_text('{"source":"legacy"}', encoding="utf-8")
    paths = resolve_product_paths(app, env={"CSRN_RUNTIME_ROOT": str(tmp_path / "runtime")})
    paths.ensure()
    target = paths.data_dir / "Settings" / "config.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"source":"customer"}', encoding="utf-8")
    migrate_legacy_runtime(paths, confirmation="MIGRATE LEGACY CSRN DATA")
    assert json.loads(target.read_text(encoding="utf-8"))["source"] == "customer"


def test_legacy_migration_is_one_time(tmp_path: Path) -> None:
    app = tmp_path / "app"
    (app / "Data").mkdir(parents=True)
    paths = resolve_product_paths(app, env={"CSRN_RUNTIME_ROOT": str(tmp_path / "runtime")})
    first = migrate_legacy_runtime(paths, confirmation="MIGRATE LEGACY CSRN DATA")
    second = migrate_legacy_runtime(paths, confirmation="MIGRATE LEGACY CSRN DATA")
    assert first["status"] == "MIGRATED"
    assert second["status"] == "ALREADY_MIGRATED"


