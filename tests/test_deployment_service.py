from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

from deployment_service import DeploymentService
from product_paths import PRODUCT_ID, resolve_product_paths


class Entitlements:
    def status(self):
        return SimpleNamespace(data={"licensing": {"valid": True, "reason": "ACTIVE"}})


class Snapshot:
    ok = True
    data = {"snapshot": {"snapshot_id": "pre-update"}}


def service(tmp_path: Path, *, version: str = "1.13.0-alpha.6f", snapshot=None) -> DeploymentService:
    base = tmp_path / "app"
    base.mkdir(parents=True, exist_ok=True)
    version_file = base / "VERSION.txt"
    version_file.write_text(version, encoding="utf-8")
    paths = resolve_product_paths(base, env={"CSRN_RUNTIME_ROOT": str(tmp_path / "runtime")})
    return DeploymentService(
        paths=paths,
        version_file=version_file,
        entitlement_service=Entitlements(),
        create_snapshot=snapshot,
        clock=lambda: 1000,
    )


def package(tmp_path: Path, *, version: str = "1.13.0-alpha.6g", product_id: str = PRODUCT_ID):
    root = tmp_path / "package"
    root.mkdir(parents=True, exist_ok=True)
    target = root / "app.bin"
    target.write_bytes(b"release-binary")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = {
        "schema": 1,
        "product_id": product_id,
        "version": version,
        "build": "test",
        "files": [{"path": "app.bin", "size": target.stat().st_size, "sha256": digest}],
    }
    (root / "release.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root, manifest


def test_status_reports_external_runtime_paths(tmp_path: Path) -> None:
    current = service(tmp_path)
    status = current.status().data["deployment"]
    assert status["installed_mode"] is True
    assert status["paths"]["data"] == str(current.paths.data_dir)
    assert status["update_policy"]["in_process_binary_replacement"] is False


def test_missing_manifest_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    assert service(tmp_path).validate_update(root).code == "MANIFEST_INVALID"


def test_wrong_product_is_rejected(tmp_path: Path) -> None:
    root, _ = package(tmp_path, product_id="wrong.product")
    assert service(tmp_path).validate_update(root).code == "PRODUCT_MISMATCH"


def test_valid_update_is_hash_verified(tmp_path: Path) -> None:
    root, _ = package(tmp_path)
    result = service(tmp_path).validate_update(root)
    assert result.code == "UPDATE_VALIDATED"
    assert result.data["update"]["validated_files"][0]["path"] == "app.bin"


def test_corrupt_update_is_rejected(tmp_path: Path) -> None:
    root, _ = package(tmp_path)
    (root / "app.bin").write_bytes(b"tampered")
    result = service(tmp_path).validate_update(root)
    assert result.code == "PACKAGE_CORRUPT"


def test_unsafe_manifest_path_is_rejected(tmp_path: Path) -> None:
    root, manifest = package(tmp_path)
    manifest["files"] = [{"path": "../outside.bin", "size": 0, "sha256": "x"}]
    (root / "release.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert service(tmp_path).validate_update(root).code == "PACKAGE_CORRUPT"


def test_downgrade_is_blocked_by_default(tmp_path: Path) -> None:
    root, _ = package(tmp_path, version="1.12.9")
    result = service(tmp_path).validate_update(root)
    assert result.code == "DOWNGRADE_BLOCKED"


def test_downgrade_can_be_inspected_explicitly(tmp_path: Path) -> None:
    root, _ = package(tmp_path, version="1.12.9")
    result = service(tmp_path).validate_update(root, allow_downgrade=True)
    assert result.code == "UPDATE_VALIDATED"


def test_prepare_update_requires_confirmation(tmp_path: Path) -> None:
    root, _ = package(tmp_path)
    result = service(tmp_path).prepare_update(root, confirmation="no")
    assert result.code == "CONFIRMATION_REQUIRED"


def test_prepare_update_creates_snapshot_and_external_plan(tmp_path: Path) -> None:
    root, _ = package(tmp_path)
    current = service(tmp_path, snapshot=lambda **_: Snapshot())
    result = current.prepare_update(root, confirmation="PREPARE CSRN UPDATE")
    assert result.code == "UPDATE_PLAN_READY"
    assert result.data["update_plan"]["external_updater_required"] is True
    assert (current.paths.updates_dir / "pending_update.json").exists()


def test_support_bundle_redacts_secrets(tmp_path: Path) -> None:
    current = service(tmp_path)
    config = current.paths.data_dir / "Settings" / "config.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"obs": {"password": "secret"}, "token": "hidden"}), encoding="utf-8")
    result = current.create_support_bundle(note="Customer report")
    bundle = Path(result.data["support_bundle"]["path"])
    with zipfile.ZipFile(bundle) as archive:
        text = archive.read("diagnostics/config.json").decode("utf-8")
    assert "secret" not in text
    assert "hidden" not in text
    assert "[REDACTED]" in text


def test_support_bundle_does_not_include_security_file(tmp_path: Path) -> None:
    current = service(tmp_path)
    current.paths.security_file.write_text('{"secret_key":"private"}', encoding="utf-8")
    result = current.create_support_bundle()
    with zipfile.ZipFile(result.data["support_bundle"]["path"]) as archive:
        assert all("security.json" not in name for name in archive.namelist())


def test_support_bundle_redacts_secrets_from_logs_and_excludes_facebook_vault(tmp_path: Path) -> None:
    current = service(tmp_path)
    log = current.paths.logs_dir / "application.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "access_token=EAATESTTOKEN\nAuthorization: Bearer EAABEARER\napp_secret: supersecret\n",
        encoding="utf-8",
    )
    vault = current.paths.data_dir / "Social" / "facebook_credentials.dat"
    vault.parent.mkdir(parents=True, exist_ok=True)
    vault.write_bytes(b"encrypted-but-sensitive")

    result = current.create_support_bundle()
    with zipfile.ZipFile(result.data["support_bundle"]["path"]) as archive:
        names = archive.namelist()
        log_text = archive.read("logs/application.log").decode("utf-8")
    assert all("facebook_credentials.dat" not in name for name in names)
    assert "EAATESTTOKEN" not in log_text
    assert "EAABEARER" not in log_text
    assert "supersecret" not in log_text
    assert log_text.count("[REDACTED]") == 3


