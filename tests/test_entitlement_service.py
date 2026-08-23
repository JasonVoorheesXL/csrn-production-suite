from __future__ import annotations

from pathlib import Path

from entitlement_service import EntitlementService
from product_paths import PRODUCT_ID, resolve_product_paths


def service(tmp_path: Path, *, installed: bool = True, verifier=None, now: int = 1000) -> EntitlementService:
    env = {"CSRN_RUNTIME_ROOT": str(tmp_path / "runtime")} if installed else {}
    paths = resolve_product_paths(tmp_path / "app", env=env, frozen=False)
    return EntitlementService(
        paths=paths,
        verifier=verifier,
        clock=lambda: now,
        environment={},
    )


def payload(**overrides):
    base = {
        "product_id": PRODUCT_ID,
        "license_id": "license-123",
        "status": "active",
        "customer": "Example School",
        "issued_at": 900,
        "expires_at": 2000,
        "features": ["core_broadcast", "captions", "social_publish"],
        "sports": ["Football"],
        "provider": "test-provider",
        "signature": "opaque-provider-signature",
    }
    base.update(overrides)
    return base


def test_installation_request_is_persistent(tmp_path: Path) -> None:
    current = service(tmp_path)
    first = current.installation_request().data["activation_request"]["installation_id"]
    second = current.installation_request().data["activation_request"]["installation_id"]
    assert first == second


def test_source_checkout_is_development_enabled(tmp_path: Path) -> None:
    current = service(tmp_path, installed=False)
    status = current.status().data["licensing"]
    assert status["valid"] is True
    assert status["reason"] == "DEVELOPMENT"


def test_installed_build_without_license_is_unlicensed(tmp_path: Path) -> None:
    status = service(tmp_path).status().data["licensing"]
    assert status["valid"] is False
    assert status["reason"] == "UNLICENSED"


def test_license_requires_object(tmp_path: Path) -> None:
    assert service(tmp_path).install_license(None).code == "LICENSE_OBJECT_REQUIRED"


def test_license_rejects_wrong_product(tmp_path: Path) -> None:
    result = service(tmp_path).install_license(payload(product_id="other.product"))
    assert result.code == "PRODUCT_MISMATCH"


def test_license_rejects_unknown_features_and_normalizes_entitlements(tmp_path: Path) -> None:
    current = service(tmp_path, verifier=lambda _: (True, "ok"))
    result = current.install_license(payload(features=["captions", "unknown", "captions"]))
    assert result.ok
    assert result.data["license"]["features"] == ["captions"]


def test_production_install_requires_provider_verifier(tmp_path: Path) -> None:
    result = service(tmp_path).install_license(payload())
    assert result.code == "VERIFIER_NOT_CONFIGURED"
    assert not service(tmp_path).paths.license_file.exists()


def test_invalid_provider_signature_is_rejected(tmp_path: Path) -> None:
    result = service(tmp_path, verifier=lambda _: (False, "bad signature")).install_license(payload())
    assert result.code == "SIGNATURE_INVALID"


def test_license_can_be_bound_to_installation(tmp_path: Path) -> None:
    current = service(tmp_path, verifier=lambda _: (True, "ok"))
    installation_id = current.installation_request().data["activation_request"]["installation_id"]
    assert current.install_license(payload(installation_id=installation_id)).ok
    other = current.install_license(payload(installation_id="different-installation"))
    assert other.code == "INSTALLATION_MISMATCH"


def test_expired_license_is_not_valid(tmp_path: Path) -> None:
    current = service(tmp_path, verifier=lambda _: (True, "ok"), now=3000)
    assert current.install_license(payload(expires_at=2000)).ok
    status = current.status().data["licensing"]
    assert status["valid"] is False
    assert status["reason"] == "EXPIRED"


def test_allows_checks_feature_and_sport(tmp_path: Path) -> None:
    current = service(tmp_path, verifier=lambda _: (True, "ok"))
    assert current.install_license(payload()).ok
    assert current.allows("captions", sport="Football") is True
    assert current.allows("weather", sport="Football") is False
    assert current.allows("captions", sport="Baseball") is False


def test_license_removal_requires_exact_confirmation(tmp_path: Path) -> None:
    current = service(tmp_path, verifier=lambda _: (True, "ok"))
    current.install_license(payload())
    assert current.remove_license("no").code == "CONFIRMATION_REQUIRED"
    assert current.remove_license("REMOVE CSRN LICENSE").code == "LICENSE_REMOVED"
    assert not current.paths.license_file.exists()


def test_public_license_never_exposes_signature(tmp_path: Path) -> None:
    current = service(tmp_path, verifier=lambda _: (True, "ok"))
    result = current.install_license(payload())
    assert "signature" not in result.data["license"]


