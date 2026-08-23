from __future__ import annotations

from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]
CACHE_HEADERS = {
    "X-CSRN-State-Cache",
    "X-CSRN-Runtime-State-Cache",
    "X-CSRN-Theme-State-Cache",
}


def _reset_read_caches() -> None:
    import runtime_state_cache
    import state_read_cache
    import theme_public_state_cache

    for cache in (runtime_state_cache, state_read_cache, theme_public_state_cache):
        cache._cached = None
        cache._building = False


def test_r1d_cache_modules_target_only_public_read_endpoints() -> None:
    import runtime_state_cache
    import state_read_cache
    import theme_public_state_cache

    assert state_read_cache._ENDPOINT == "system_routes.get_state"
    assert runtime_state_cache._ENDPOINT == "system_routes.get_runtime_state"
    assert theme_public_state_cache._ENDPOINT == "theme_routes.public_theme_state"

    app = app_module.app
    rules = {rule.endpoint: rule for rule in app.url_map.iter_rules()}
    for endpoint in (
        state_read_cache._ENDPOINT,
        runtime_state_cache._ENDPOINT,
        theme_public_state_cache._ENDPOINT,
    ):
        assert endpoint in rules
        methods = rules[endpoint].methods - {"HEAD", "OPTIONS"}
        assert methods == {"GET"}


def test_r1d_cache_installation_occurs_after_app_factory_and_before_main() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    app_pos = source.rfind("app = create_app()")
    main_pos = source.rfind('if __name__ == "__main__"')
    installs = [
        source.rfind("install_state_read_cache(app)"),
        source.rfind("install_runtime_state_cache(app)"),
        source.rfind("install_theme_public_state_cache(app)"),
    ]
    assert app_pos >= 0
    assert all(position > app_pos for position in installs)
    if main_pos >= 0:
        assert all(position < main_pos for position in installs)


def test_r1d_public_read_endpoints_emit_only_their_own_cache_headers() -> None:
    _reset_read_caches()
    app = app_module.app
    app.config.update(TESTING=True)

    expectations = {
        "/api/state": "X-CSRN-State-Cache",
        "/api/runtime-state": "X-CSRN-Runtime-State-Cache",
        "/api/themes/public-state": "X-CSRN-Theme-State-Cache",
    }
    with app.test_client() as client:
        for path, expected_header in expectations.items():
            first = client.get(path)
            second = client.get(path)
            assert first.status_code == second.status_code == 200
            assert first.data == second.data
            assert second.headers.get(expected_header) == "HIT"
            leaked = CACHE_HEADERS - {expected_header}
            assert all(header not in second.headers for header in leaked)


def test_r1d_mutation_routes_are_not_read_cache_wrapped() -> None:
    _reset_read_caches()
    app = app_module.app
    app.config.update(TESTING=True)

    with app.test_client() as client:
        for response in (
            client.post("/api/set", json={"clock": "11:00"}),
            client.post("/api/themes/preview", json={"preset_id": "modern_network"}),
        ):
            assert response.status_code in {200, 400, 401, 403, 409}
            assert all(header not in response.headers for header in CACHE_HEADERS)


def test_r1d_command_center_keeps_authoritative_mutation_response_contract() -> None:
    command_center = (ROOT / "templates" / "index.html").read_text(
        encoding="utf-8"
    )

    assert "Mutation responses are authoritative" in command_center
    assert "fetch('/api/state',{credentials:'same-origin',cache:'no-store'" in command_center
    assert "/api/runtime-state" not in command_center


