from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fresh_app():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import app as app_module

    return app_module.app


def test_runtime_state_cache_module_is_installed_before_main_server_start():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from runtime_state_cache import install_runtime_state_cache" in source
    assert "install_runtime_state_cache(app)" in source
    main_pos = source.rfind("if __name__")
    install_pos = source.rfind("install_runtime_state_cache(app)")
    assert install_pos >= 0
    if main_pos >= 0:
        assert install_pos < main_pos


def test_runtime_state_cache_preserves_exact_response_body_within_ttl():
    app = _fresh_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        first = client.get("/api/runtime-state")
        second = client.get("/api/runtime-state")
        assert first.status_code == second.status_code == 200
        assert first.data == second.data
        assert first.headers.get("X-CSRN-Runtime-State-Cache") in {"MISS", "HIT"}
        assert second.headers.get("X-CSRN-Runtime-State-Cache") == "HIT"


def test_runtime_state_cache_ttl_is_subsecond_and_bounded():
    import runtime_state_cache

    assert 0 < runtime_state_cache._TTL_SECONDS <= 0.250


def test_runtime_state_cache_targets_only_runtime_state_endpoint():
    app = _fresh_app()
    assert app.view_functions.get("system_routes.get_runtime_state") is not None

    import runtime_state_cache

    source = Path(runtime_state_cache.__file__).read_text(encoding="utf-8")
    assert '_ENDPOINT = "system_routes.get_runtime_state"' in source
    assert "app.view_functions[_ENDPOINT] = cached_get_runtime_state" in source


