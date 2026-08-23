import json
from pathlib import Path

import pytest

import production_template_service as service

ROOT = Path(__file__).resolve().parents[1]


def test_gate165_state_defaults_to_legacy(tmp_path, monkeypatch):
    monkeypatch.setenv("CSRN_PRODUCTION_TEMPLATE_STATE_PATH", str(tmp_path / "state.json"))
    state = service.read_production_template_state()
    assert state["package_id"] == "legacy"
    assert state["authoritative"] is True


@pytest.mark.parametrize("package_id", sorted(service.APPROVED_PACKAGE_IDS))
def test_gate165_round_trip_persistence(tmp_path, monkeypatch, package_id):
    path = tmp_path / "state.json"
    monkeypatch.setenv("CSRN_PRODUCTION_TEMPLATE_STATE_PATH", str(path))
    written = service.write_production_template_state(package_id)
    assert written["package_id"] == package_id
    assert service.read_production_template_state()["package_id"] == package_id
    assert json.loads(path.read_text(encoding="utf-8"))["package_id"] == package_id


def test_gate165_invalid_package_rejected(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    monkeypatch.setenv("CSRN_PRODUCTION_TEMPLATE_STATE_PATH", str(path))
    with pytest.raises(ValueError, match="invalid_production_template"):
        service.write_production_template_state("not_real")
    assert not path.exists()


def test_gate165_routes_live_in_blueprint_layer_not_app():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "register_production_template_routes" not in app_source
    route_sources = [path.read_text(encoding="utf-8") for path in (ROOT / "routes").rglob("*.py")]
    joined = "\n".join(route_sources)
    assert '"/api/production-template"' in joined
    assert "enrich_theme_public_state_response" in joined


def test_gate165_menu_uses_authoritative_server_state():
    js = (ROOT / "static/csrn-production-template-menu.js").read_text(encoding="utf-8")
    assert 'API = "/api/production-template"' in js
    assert "localStorage" not in js
    assert 'method:"POST"' in js
    assert "renderBindingEnabled" in js


def test_gate165_live_overlay_still_does_not_directly_embed_layout_engines():
    overlay = (ROOT / "templates/overlay.html").read_text(encoding="utf-8")
    for engine in (
        "csrn-broadcast-layout-engine.js",
        "csrn-friday-night-stadium-engine.js",
        "csrn-eight-bit-gameday-engine.js",
        "csrn-heritage-press-engine.js",
        "csrn-neon-r2-engine.js",
    ):
        assert engine not in overlay


