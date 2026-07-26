from __future__ import annotations

from pathlib import Path

from flask import Flask

from routes.weather_routes import WeatherRoutesDependencies, create_weather_blueprint
from weather_service import WeatherResult


ROOT = Path(__file__).resolve().parents[1]


class Service:
    def __init__(self):
        self.calls = []
        self.result = WeatherResult("OK", {"weather": {}})

    def public_state(self):
        self.calls.append(("public_state",))
        return WeatherResult("OK", {"overlay": {"visible": False}})

    def status(self):
        self.calls.append(("status",))
        return self.result

    def refresh(self, *, force=False):
        self.calls.append(("refresh", force))
        return self.result

    def geocode_active_venue(self):
        self.calls.append(("geocode",))
        return self.result

    def approve_alert(self, alert_id, *, visible=True):
        self.calls.append(("approve", alert_id, visible))
        return self.result

    def dismiss_alert(self, alert_id=""):
        self.calls.append(("dismiss", alert_id))
        return self.result

    def set_overlay(self, payload):
        self.calls.append(("overlay", payload))
        return self.result

    def start_delay(self, payload):
        self.calls.append(("delay", payload))
        return self.result

    def resume_game(self, payload=None):
        self.calls.append(("resume", payload))
        return self.result

    def record_lightning(self):
        self.calls.append(("lightning",))
        return self.result

    def reset_lightning_timer(self, confirmation):
        self.calls.append(("reset", confirmation))
        return self.result


def app_and_service():
    app = Flask("weather_routes_test", template_folder=str(ROOT / "templates"))
    app.config.update(TESTING=True)
    service = Service()

    def require_auth(func):
        setattr(func, "_csrn_requires_auth", True)
        return func

    app.register_blueprint(
        create_weather_blueprint(
            WeatherRoutesDependencies(
                require_auth=require_auth,
                get_weather_service=lambda: service,
            )
        )
    )
    return app, service


def test_public_overlay_page_is_available() -> None:
    app, _ = app_and_service()
    response = app.test_client().get("/weather-overlay")
    assert response.status_code == 200
    assert b"CSRN Weather Overlay" in response.data


def test_public_overlay_state_is_available() -> None:
    app, service = app_and_service()
    response = app.test_client().get("/api/weather/overlay-state")
    assert response.status_code == 200
    assert service.calls == [("public_state",)]


def test_status_uses_weather_service() -> None:
    app, service = app_and_service()
    assert app.test_client().get("/api/weather/status").status_code == 200
    assert service.calls == [("status",)]


def test_refresh_passes_force_flag() -> None:
    app, service = app_and_service()
    response = app.test_client().post("/api/weather/refresh", json={"force": True})
    assert response.status_code == 200
    assert service.calls == [("refresh", True)]


def test_refresh_throttle_returns_429() -> None:
    app, service = app_and_service()
    service.result = WeatherResult("POLL_THROTTLED", {"retry_after": 30})
    response = app.test_client().post("/api/weather/refresh", json={})
    assert response.status_code == 429


def test_refresh_fetch_failure_returns_503() -> None:
    app, service = app_and_service()
    service.result = WeatherResult("FETCH_FAILED", {"message": "offline"})
    assert app.test_client().post("/api/weather/refresh", json={}).status_code == 503


def test_geocode_missing_location_returns_conflict() -> None:
    app, service = app_and_service()
    service.result = WeatherResult("VENUE_ADDRESS_REQUIRED")
    assert app.test_client().post("/api/weather/geocode", json={}).status_code == 409


def test_approve_alert_preserves_full_alert_id() -> None:
    app, service = app_and_service()
    response = app.test_client().post("/api/weather/alerts/urn:oid:alert/123/approve", json={"visible": False})
    assert response.status_code == 200
    assert service.calls == [("approve", "urn:oid:alert/123", False)]


def test_missing_alert_returns_404() -> None:
    app, service = app_and_service()
    service.result = WeatherResult("ALERT_NOT_FOUND")
    response = app.test_client().post("/api/weather/alerts/missing/approve", json={})
    assert response.status_code == 404


def test_overlay_validation_returns_400() -> None:
    app, service = app_and_service()
    service.result = WeatherResult("OVERLAY_MODE_INVALID")
    response = app.test_client().post("/api/weather/overlay", json={"visible": True, "mode": "bad"})
    assert response.status_code == 400


def test_delay_and_resume_routes_call_service() -> None:
    app, service = app_and_service()
    client = app.test_client()
    assert client.post("/api/weather/delay/start", json={"message": "Delay"}).status_code == 200
    assert client.post("/api/weather/delay/resume", json={"message": "Resume"}).status_code == 200
    assert service.calls == [("delay", {"message": "Delay"}), ("resume", {"message": "Resume"})]


def test_lightning_routes_require_confirmation_for_reset() -> None:
    app, service = app_and_service()
    client = app.test_client()
    assert client.post("/api/weather/lightning/observed", json={}).status_code == 200
    service.result = WeatherResult("CONFIRMATION_REQUIRED")
    response = client.post("/api/weather/lightning/reset", json={"confirmation": "no"})
    assert response.status_code == 409


def test_all_management_routes_are_marked_authenticated() -> None:
    app, _ = app_and_service()
    public = {"weather_routes.weather_overlay", "weather_routes.weather_overlay_state"}
    endpoints = [rule.endpoint for rule in app.url_map.iter_rules() if rule.endpoint.startswith("weather_routes.")]
    for endpoint in endpoints:
        if endpoint in public:
            assert not getattr(app.view_functions[endpoint], "_csrn_requires_auth", False)
        else:
            assert getattr(app.view_functions[endpoint], "_csrn_requires_auth", False)
