"""Round 16 -- the license gate + the frozen (pywebview) build together.

license-foundation's tests were written before the two branches merged.
These cover the combination: the sys.frozen startup path (15D) must reach
EntitlementService's gate exactly like dev-mode "installed" does, the
placeholder public key must fail closed, and no signer / private-key code
path may be reachable from the frozen app.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import app as app_module
import csrn_desktop
import license_service as ls
from entitlement_service import EntitlementService
from product_paths import resolve_product_paths

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# Task B -- .spec bundling: license verify is in, the signer is out.
# --------------------------------------------------------------------------


def test_spec_bundles_license_service_and_excludes_the_issuer() -> None:
    spec = (ROOT / "packaging/windows/CSRNProductionSuite.spec").read_text(encoding="utf-8")
    assert '"license_service"' in spec
    assert '"entitlement_service"' in spec
    assert '"tools.issue_license"' in spec  # excludes list
    assert "issue_license" in spec.split("excludes=", 1)[1].split("\n", 1)[0]


def test_frozen_app_never_reaches_a_signer_or_a_private_key() -> None:
    # The only module allowed to sign / generate / hold a private key is the
    # owner tool, which the .spec excludes. Nothing else in the shipped tree
    # may reference the signing surface.
    signer_surface = (
        "sign_license(",
        "ed25519_sign(",
        "CSRN_LICENSE_PRIVATE_KEY",
        "--genkey",
        "secret_expand",  # private-half derivation
    )
    shipped = [
        ROOT / "app.py",
        ROOT / "csrn_desktop.py",
        ROOT / "entitlement_service.py",
        *(ROOT / "routes").glob("*.py"),
    ]
    for path in shipped:
        text = path.read_text(encoding="utf-8")
        for token in signer_surface:
            assert token not in text, f"{path.name} references signer surface {token!r}"

    # license_service.py is bundled (verify needs it) and DOES contain the
    # RFC reference block incl. a sign function -- but with no caller in the
    # shipped tree and no private key in the app, it is inert. Confirm the
    # app only ever calls the verify side.
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    ent_text = (ROOT / "entitlement_service.py").read_text(encoding="utf-8")
    assert "verify_license" in app_text
    assert "sign_license" not in app_text and "sign_license" not in ent_text


# --------------------------------------------------------------------------
# Round 16: the real embedded key fails closed against non-matching sigs.
# --------------------------------------------------------------------------


def test_frozen_build_rejects_a_license_signed_by_the_wrong_key(tmp_path) -> None:
    # The shipped key is the owner's real public key (not the placeholder),
    # and runtime verification actually checks against it.
    assert ls.LICENSE_PUBLIC_KEY_HEX != "0" * 64
    assert ls.license_public_key_configured() is True

    # A well-formed license signed by a DIFFERENT keypair: a signature IS
    # present, but it does not match the embedded key.
    wrong_seed = bytes(range(1, 33))
    signed = ls.sign_license(
        {
            "product_id": "possumfrog.csrn-production-suite",
            "license_id": "x",
            "status": "active",
            "customer": "Anyone",
            "issued_at": 1,
            "expires_at": 0,
            "features": sorted(EntitlementService.CORE_FEATURES),
            "sports": ["football"],
        },
        wrong_seed,
    )
    ok, reason = ls.verify_license(signed)  # module global = owner key
    assert ok is False
    assert reason == "LICENSE_SIGNATURE_INVALID"  # not "no key", not "no signature"

    paths = resolve_product_paths(
        tmp_path / "app",
        env={"CSRN_RUNTIME_ROOT": str(tmp_path / "runtime")},
        frozen=True,  # <-- frozen build
    )
    assert paths.installed_mode is True
    service = EntitlementService(paths=paths, verifier=ls.verify_license, clock=lambda: 1_000)
    paths.license_file.parent.mkdir(parents=True, exist_ok=True)
    import json

    paths.license_file.write_text(json.dumps(signed), encoding="utf-8")
    assert service.status().data["licensing"]["valid"] is False


# --------------------------------------------------------------------------
# Task C -- frozen startup path reaches the gate.
# --------------------------------------------------------------------------


def test_frozen_flag_makes_product_paths_installed_and_gate_enforced(monkeypatch) -> None:
    # _installed_build() is the gate's "enforce?" seam; it reads
    # PRODUCT_PATHS.installed_mode, which resolve_product_paths sets True for
    # a frozen build. Prove the chain rather than just monkeypatching the seam.
    paths = resolve_product_paths(ROOT, frozen=True)
    assert paths.installed_mode is True

    monkeypatch.setattr(app_module, "PRODUCT_PATHS", paths)
    assert app_module._installed_build() is True


def test_frozen_serve_path_installs_the_license_gate(monkeypatch) -> None:
    # csrn_desktop --serve-only -> run_server_only() -> import app ->
    # module scope runs _install_license_gate(app). So the frozen serve path
    # gets the gate for free. Assert the wiring is at import scope.
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "\n_install_license_gate(app)\n" in src

    served = {}
    monkeypatch.setattr(app_module, "run_command_center", lambda: served.setdefault("ran", True))
    monkeypatch.setattr(csrn_desktop, "run", lambda **k: pytest.fail("serve-only must not open a window"))
    assert csrn_desktop.main(["--serve-only"]) == 0
    assert served == {"ran": True}
    # the app object the serve path uses carries before_request gates
    gate_names = {
        getattr(fn, "__name__", "")
        for fn in app_module.app.before_request_funcs.get(None, [])
    }
    assert "_gate" in gate_names


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    with app_module.app.test_client() as test_client:
        with test_client.session_transaction() as session:
            session["authenticated"] = True
        yield test_client


def test_frozen_build_with_no_license_shows_screen_and_402s_broadcast(client, monkeypatch) -> None:
    # frozen build (installed) + missing license, via the real seams.
    monkeypatch.setattr(app_module, "_installed_build", lambda: True)
    monkeypatch.setattr(
        app_module,
        "_current_licensing",
        lambda: {"valid": False, "reason": "UNLICENSED", "license": None},
    )

    home = client.get("/")
    assert home.status_code == 200
    assert b"License required" in home.data

    api = client.get("/api/state")
    assert api.status_code == 402
    assert api.get_json().get("error") == "LICENSE_REQUIRED"

    # essentials still reachable so a license can be installed / support can help
    assert client.get("/api/health").status_code == 200
