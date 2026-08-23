from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

def test_r1110_theme_cache_installed_in_app():
    source=(ROOT/"app.py").read_text(encoding="utf-8")
    assert "from theme_public_state_cache import install_theme_public_state_cache" in source
    assert "install_theme_public_state_cache(app)" in source

def test_r1110_theme_cache_contract():
    import theme_public_state_cache as cache
    assert cache._ENDPOINT == "theme_routes.public_theme_state"
    assert 0 < cache._TTL_SECONDS <= 0.500

def test_r1110_theme_public_state_body_is_reused_exactly():
    import app as app_module
    app=app_module.app
    app.config.update(TESTING=True)
    with app.test_client() as client:
        first=client.get("/api/themes/public-state")
        second=client.get("/api/themes/public-state")
        assert first.status_code == second.status_code == 200
        assert first.data == second.data
        assert second.headers.get("X-CSRN-Theme-State-Cache") == "HIT"

def test_r1110_existing_state_cache_remains_installed():
    import app as app_module
    app=app_module.app
    assert getattr(app,"_csrn_state_read_cache_installed",False) is True


