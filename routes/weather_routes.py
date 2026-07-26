from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, render_template, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class WeatherRoutesDependencies:
    require_auth: RouteDecorator
    get_weather_service: Callable[[], Any]


def create_weather_blueprint(dependencies: WeatherRoutesDependencies) -> Blueprint:
    routes = Blueprint("weather_routes", __name__)

    @routes.get("/weather-overlay")
    def weather_overlay():
        return render_template("weather.html")

    @routes.get("/api/weather/overlay-state")
    def weather_overlay_state():
        result = dependencies.get_weather_service().public_state()
        return jsonify(result.data)

    @routes.get("/api/weather/status")
    @dependencies.require_auth
    def weather_status():
        result = dependencies.get_weather_service().status()
        return jsonify(result.data)

    @routes.post("/api/weather/refresh")
    @dependencies.require_auth
    def refresh_weather():
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_weather_service().refresh(force=bool(incoming.get("force", False)))
        if result.code == "POLL_THROTTLED":
            return jsonify({"status": result.code, **result.data}), 429
        if result.code in {"VENUE_NOT_FOUND", "LOCATION_REQUIRED"}:
            return jsonify({"error": result.code, **result.data}), 409
        if result.code == "FETCH_FAILED":
            return jsonify({"error": result.code, **result.data}), 503
        return jsonify(result.data)

    @routes.post("/api/weather/geocode")
    @dependencies.require_auth
    def geocode_weather_venue():
        result = dependencies.get_weather_service().geocode_active_venue()
        if result.code in {"VENUE_NOT_FOUND", "VENUE_ADDRESS_REQUIRED", "GEOCODE_NOT_FOUND"}:
            return jsonify({"error": result.code, **result.data}), 409
        if result.code == "GEOCODE_FAILED":
            return jsonify({"error": result.code, **result.data}), 503
        return jsonify(result.data)

    @routes.post("/api/weather/alerts/<path:alert_id>/approve")
    @dependencies.require_auth
    def approve_weather_alert(alert_id: str):
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_weather_service().approve_alert(
            alert_id,
            visible=incoming.get("visible", True),
        )
        if result.code == "VISIBLE_MUST_BE_BOOLEAN":
            return jsonify({"error": result.code}), 400
        if result.code == "ALERT_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify(result.data)

    @routes.post("/api/weather/alerts/dismiss")
    @dependencies.require_auth
    def dismiss_weather_alert():
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_weather_service().dismiss_alert(incoming.get("alert_id", ""))
        if result.code == "ALERT_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify(result.data)

    @routes.post("/api/weather/overlay")
    @dependencies.require_auth
    def update_weather_overlay():
        result = dependencies.get_weather_service().set_overlay(
            request.get_json(force=True, silent=True)
        )
        if result.code in {"OVERLAY_REQUIRED", "VISIBLE_MUST_BE_BOOLEAN", "OVERLAY_MODE_INVALID"}:
            return jsonify({"error": result.code}), 400
        return jsonify(result.data)

    @routes.post("/api/weather/delay/start")
    @dependencies.require_auth
    def start_weather_delay():
        result = dependencies.get_weather_service().start_delay(
            request.get_json(force=True, silent=True)
        )
        return jsonify(result.data)

    @routes.post("/api/weather/delay/resume")
    @dependencies.require_auth
    def resume_after_weather():
        result = dependencies.get_weather_service().resume_game(
            request.get_json(force=True, silent=True)
        )
        return jsonify(result.data)

    @routes.post("/api/weather/lightning/observed")
    @dependencies.require_auth
    def record_lightning_observation():
        result = dependencies.get_weather_service().record_lightning()
        return jsonify(result.data)

    @routes.post("/api/weather/lightning/reset")
    @dependencies.require_auth
    def reset_lightning_timer():
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_weather_service().reset_lightning_timer(
            incoming.get("confirmation")
        )
        if result.code == "CONFIRMATION_REQUIRED":
            return jsonify({"error": result.code}), 409
        return jsonify(result.data)

    return routes
