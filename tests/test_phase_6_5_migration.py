from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase_6_5_migration_is_idempotent() -> None:
    runpy.run_path(str(ROOT / "tools" / "ci_apply.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "tools" / "ci_apply.py"), run_name="__main__")


def test_phase_6_5_version_identity_is_applied() -> None:
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "1.13.0-alpha.6e"
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Version 1.13.0-alpha.6e — Venue Weather Monitoring" in source
    assert "V1.13A6E-VENUE-WEATHER-MONITORING" in source


def test_phase_6_5_weather_configuration_is_present() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"refresh_seconds": 60' in source
    assert '"stale_after_seconds": 180' in source
    assert '"user_agent": "CSRN-Production-Suite/1.13 (operator-configurable)"' in source


def test_phase_6_5_route_and_service_are_composed() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from weather_service import VenueWeatherService" in source
    assert "from routes.weather_routes import" in source
    assert "create_weather_blueprint(" in source
