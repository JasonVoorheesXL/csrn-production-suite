from __future__ import annotations

from pathlib import Path

from weather_service import VenueWeatherService


def venue(**overrides):
    row = {
        "id": "venue-1",
        "school_id": "school-1",
        "sport": "Football",
        "name": "Panther Stadium",
        "address1": "105 Cavalier Drive",
        "city": "Caledonia",
        "state": "MS",
        "postal_code": "39740",
        "latitude": 33.682,
        "longitude": -88.325,
        "active": True,
    }
    row.update(overrides)
    return row


def alert(alert_id="alert-1", severity="Severe"):
    return {
        "id": alert_id,
        "properties": {
            "event": "Severe Thunderstorm Warning",
            "headline": "Severe Thunderstorm Warning issued for Lowndes County",
            "description": "Storms are moving through the area.",
            "instruction": "Move to an interior room.",
            "severity": severity,
            "urgency": "Immediate",
            "certainty": "Observed",
            "areaDesc": "Lowndes County",
            "effective": "2026-07-26T20:00:00-05:00",
            "expires": "2026-07-26T21:00:00-05:00",
            "sent": "2026-07-26T19:55:00-05:00",
            "senderName": "NWS Memphis TN",
        },
    }


def fetcher_factory(alerts=None, *, fail=False, geocode=True):
    alerts = [alert()] if alerts is None else alerts

    def fetcher(url, headers):
        assert isinstance(headers, dict)
        if fail:
            raise OSError("network unavailable")
        if "geocoding.geo.census.gov" in url:
            matches = [{"coordinates": {"x": -88.3255, "y": 33.6825}}] if geocode else []
            return {"result": {"addressMatches": matches}}
        if "/points/" in url:
            return {"properties": {"forecastHourly": "https://api.weather.gov/gridpoints/MEG/1,2/forecast/hourly"}}
        if "/gridpoints/" in url:
            return {
                "properties": {
                    "periods": [
                        {
                            "startTime": "2026-07-26T20:00:00-05:00",
                            "temperature": 82,
                            "temperatureUnit": "F",
                            "windSpeed": "9 mph",
                            "windDirection": "SW",
                            "probabilityOfPrecipitation": {"value": 35},
                            "shortForecast": "Cloudy",
                            "detailedForecast": "Cloudy with a chance of rain.",
                        }
                    ]
                }
            }
        if "/alerts/active" in url:
            return {"features": alerts}
        raise AssertionError(url)

    return fetcher


def make_service(
    tmp_path: Path,
    *,
    now=None,
    venues=None,
    schools=None,
    state=None,
    config=None,
    fetcher=None,
):
    current = now or [1000.0]
    venue_rows = list(venues if venues is not None else [venue()])
    school_rows = list(schools if schools is not None else [{"id": "school-1", "venue_id": "venue-1"}])
    broadcast = dict(state or {"venue_id": "venue-1", "venue": "Panther Stadium", "home_school_id": "school-1", "sport": "Football"})
    settings = {
        "weather": {
            "use_home_venue_address": True,
            "refresh_seconds": 60,
            "stale_after_seconds": 180,
            "user_agent": "CSRN-Test/1.0 (test@example.com)",
        }
    }
    if config:
        settings["weather"].update(config)

    def save_venues(rows):
        venue_rows[:] = rows

    service = VenueWeatherService(
        state_file=tmp_path / "Weather" / "weather_state.json",
        load_state=lambda: dict(broadcast),
        load_config=lambda: settings,
        load_venues=lambda: venue_rows,
        save_venues=save_venues,
        load_schools=lambda: school_rows,
        fetcher=fetcher or fetcher_factory(),
        clock=lambda: current[0],
    )
    return service, current, venue_rows


def test_status_creates_default_state_file(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    result = service.status()
    assert result.ok
    assert result.data["weather"]["venue"]["id"] == "venue-1"
    assert service.state_file.exists()


def test_resolve_active_venue_prefers_explicit_venue_id(tmp_path: Path) -> None:
    rows = [venue(id="venue-1", name="One"), venue(id="venue-2", name="Two")]
    service, _, _ = make_service(tmp_path, venues=rows, state={"venue_id": "venue-2"})
    assert service.resolve_active_venue().data["venue"]["name"] == "Two"


def test_resolve_active_venue_falls_back_to_home_school(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path, state={"home_school_id": "school-1", "sport": "Football"})
    assert service.resolve_active_venue().data["venue"]["id"] == "venue-1"


def test_resolve_active_venue_reports_missing(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path, venues=[], schools=[], state={})
    assert service.resolve_active_venue().code == "VENUE_NOT_FOUND"


def test_geocode_updates_active_venue_coordinates(tmp_path: Path) -> None:
    service, _, rows = make_service(tmp_path, venues=[venue(latitude=None, longitude=None)])
    result = service.geocode_active_venue()
    assert result.code == "GEOCODED"
    assert rows[0]["latitude"] == 33.6825
    assert rows[0]["longitude"] == -88.3255
    assert rows[0]["venue_address_source"] == "census-geocoder"


def test_geocode_requires_address(tmp_path: Path) -> None:
    service, _, _ = make_service(
        tmp_path,
        venues=[venue(address1="", city="", state="", postal_code="", latitude=None, longitude=None)],
    )
    assert service.geocode_active_venue().code == "VENUE_ADDRESS_REQUIRED"


def test_geocode_handles_no_match(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path, fetcher=fetcher_factory(geocode=False))
    assert service.geocode_active_venue().code == "GEOCODE_NOT_FOUND"


def test_refresh_requires_coordinates(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path, venues=[venue(latitude=None, longitude=None)])
    assert service.refresh(force=True).code == "LOCATION_REQUIRED"


def test_refresh_persists_conditions_and_alerts(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    result = service.refresh(force=True)
    weather = result.data["weather"]
    assert result.code == "REFRESHED"
    assert weather["conditions"]["temperature"] == 82
    assert weather["conditions"]["precipitation_probability"] == 35
    assert weather["alerts"][0]["severity"] == "Severe"
    assert weather["stale"] is False


def test_refresh_enforces_minimum_poll_interval(tmp_path: Path) -> None:
    service, now, _ = make_service(tmp_path)
    assert service.refresh(force=True).ok
    now[0] += 10
    result = service.refresh()
    assert result.code == "POLL_THROTTLED"
    assert result.data["retry_after"] == 50


def test_refresh_failure_retains_last_known_data(tmp_path: Path) -> None:
    service, now, _ = make_service(tmp_path)
    assert service.refresh(force=True).ok
    service._fetcher = fetcher_factory(fail=True)
    now[0] += 61
    result = service.refresh()
    assert result.code == "FETCH_FAILED"
    assert result.data["weather"]["conditions"]["temperature"] == 82
    assert result.data["weather"]["stale"] is True


def test_approve_severe_alert_uses_emergency_overlay(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    service.refresh(force=True)
    result = service.approve_alert("alert-1")
    assert result.code == "ALERT_APPROVED"
    assert result.data["weather"]["overlay"]["mode"] == "emergency"
    assert result.data["weather"]["overlay"]["sponsor_allowed"] is False


def test_approve_moderate_alert_uses_advisory_overlay(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path, fetcher=fetcher_factory([alert(severity="Moderate")]))
    service.refresh(force=True)
    result = service.approve_alert("alert-1")
    assert result.data["weather"]["overlay"]["mode"] == "advisory"


def test_approve_missing_alert_returns_not_found(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    assert service.approve_alert("missing").code == "ALERT_NOT_FOUND"


def test_dismiss_alert_hides_overlay(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    service.refresh(force=True)
    service.approve_alert("alert-1")
    result = service.dismiss_alert()
    assert result.code == "ALERT_DISMISSED"
    assert result.data["weather"]["overlay"]["visible"] is False


def test_operator_can_show_weather_bug(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    result = service.set_overlay({"visible": True, "mode": "bug"})
    assert result.code == "OVERLAY_UPDATED"
    assert result.data["weather"]["overlay"]["mode"] == "bug"


def test_overlay_rejects_invalid_mode(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    assert service.set_overlay({"visible": True, "mode": "sponsor"}).code == "OVERLAY_MODE_INVALID"


def test_start_delay_disables_sponsor_branding(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    result = service.start_delay({"message": "Shelter in place", "source": "athletic-director"})
    weather = result.data["weather"]
    assert result.code == "DELAY_STARTED"
    assert weather["delay"]["active"] is True
    assert weather["overlay"]["sponsor_allowed"] is False


def test_resume_game_uses_resumption_overlay(tmp_path: Path) -> None:
    service, now, _ = make_service(tmp_path)
    service.start_delay({})
    now[0] += 300
    result = service.resume_game({"message": "Teams returning to the field"})
    assert result.code == "GAME_RESUMING"
    assert result.data["weather"]["overlay"]["mode"] == "resumption"
    assert result.data["weather"]["delay"]["active"] is False


def test_lightning_observation_starts_thirty_minute_timer(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    result = service.record_lightning()
    lightning = result.data["weather"]["lightning"]
    assert result.code == "LIGHTNING_RECORDED"
    assert lightning["clear_at"] - lightning["last_observed_at"] == 1800
    assert lightning["remaining_seconds"] == 1800


def test_elapsed_lightning_timer_does_not_declare_safe(tmp_path: Path) -> None:
    service, now, _ = make_service(tmp_path)
    service.record_lightning()
    now[0] += 1801
    lightning = service.public_state().data["lightning"]
    assert lightning["timer_elapsed"] is True
    assert "does not declare" in lightning["safety_note"]


def test_lightning_reset_requires_exact_confirmation(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    service.record_lightning()
    assert service.reset_lightning_timer("yes").code == "CONFIRMATION_REQUIRED"
    assert service.reset_lightning_timer("RESET LIGHTNING TIMER").code == "LIGHTNING_TIMER_RESET"


def test_weather_becomes_stale_after_configured_age(tmp_path: Path) -> None:
    service, now, _ = make_service(tmp_path)
    service.refresh(force=True)
    now[0] += 181
    assert service.public_state().data["stale"] is True


def test_expired_selected_alert_is_removed_on_refresh(tmp_path: Path) -> None:
    service, now, _ = make_service(tmp_path)
    service.refresh(force=True)
    service.approve_alert("alert-1")
    service._fetcher = fetcher_factory([])
    now[0] += 61
    result = service.refresh()
    assert result.data["weather"]["selected_alert_id"] == ""
    assert result.data["weather"]["overlay"]["visible"] is False


def test_history_records_weather_operations(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    service.refresh(force=True)
    service.record_lightning()
    actions = [item["action"] for item in service.status().data["weather"]["history"]]
    assert "weather_refreshed" in actions
    assert "lightning_observed" in actions


