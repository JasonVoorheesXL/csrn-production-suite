from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


LoadMapping = Callable[[], dict[str, Any]]
LoadRows = Callable[[], list[dict[str, Any]]]
SaveRows = Callable[[list[dict[str, Any]]], None]
JsonFetcher = Callable[[str, dict[str, str]], dict[str, Any]]
Clock = Callable[[], float]


@dataclass(frozen=True)
class WeatherResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code in {
            "OK",
            "REFRESHED",
            "GEOCODED",
            "ALERT_APPROVED",
            "ALERT_DISMISSED",
            "OVERLAY_UPDATED",
            "DELAY_STARTED",
            "GAME_RESUMING",
            "LIGHTNING_RECORDED",
            "LIGHTNING_TIMER_RESET",
        }


def fetch_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=12) as response:  # nosec B310 - fixed HTTPS public APIs
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Weather service returned a non-object JSON response.")
    return data


class VenueWeatherService:
    """Flask-independent venue weather, alert, delay, and lightning boundary."""

    MODES = {"hidden", "bug", "advisory", "emergency", "delay", "resumption"}
    SEVERITY_ORDER = {
        "Extreme": 4,
        "Severe": 3,
        "Moderate": 2,
        "Minor": 1,
        "Unknown": 0,
    }
    DEFAULT_STATE: dict[str, Any] = {
        "venue": {},
        "conditions": {},
        "alerts": [],
        "selected_alert_id": "",
        "overlay": {
            "visible": False,
            "mode": "hidden",
            "message": "",
            "updated_at": 0,
        },
        "delay": {
            "active": False,
            "started_at": 0,
            "resumed_at": 0,
            "message": "",
            "source": "",
        },
        "lightning": {
            "active": False,
            "last_observed_at": 0,
            "clear_at": 0,
            "reset_at": 0,
        },
        "history": [],
        "last_attempt_at": 0,
        "last_success_at": 0,
        "stale": True,
        "error": "Weather has not been refreshed.",
    }

    def __init__(
        self,
        *,
        state_file: Path,
        load_state: LoadMapping,
        load_config: LoadMapping,
        load_venues: LoadRows,
        save_venues: SaveRows,
        load_schools: LoadRows,
        fetcher: JsonFetcher = fetch_json,
        clock: Clock = time.time,
    ) -> None:
        self.state_file = Path(state_file)
        self._load_broadcast_state = load_state
        self._load_config = load_config
        self._load_venues = load_venues
        self._save_venues = save_venues
        self._load_schools = load_schools
        self._fetcher = fetcher
        self._clock = clock
        self._lock = Lock()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def status(self) -> WeatherResult:
        with self._lock:
            state = self._load()
            venue = self._resolve_venue()
            if venue:
                state["venue"] = self._venue_public(venue)
            self._apply_time_state(state)
            return WeatherResult("OK", {"weather": copy.deepcopy(state), "config": self._weather_config()})

    def public_state(self) -> WeatherResult:
        with self._lock:
            state = self._load()
            self._apply_time_state(state)
            selected = self._find_alert(state, state.get("selected_alert_id", ""))
            return WeatherResult(
                "OK",
                {
                    "venue": copy.deepcopy(state.get("venue", {})),
                    "conditions": copy.deepcopy(state.get("conditions", {})),
                    "alert": copy.deepcopy(selected or {}),
                    "overlay": copy.deepcopy(state.get("overlay", {})),
                    "delay": copy.deepcopy(state.get("delay", {})),
                    "lightning": copy.deepcopy(state.get("lightning", {})),
                    "stale": bool(state.get("stale", True)),
                    "error": str(state.get("error", "")),
                    "last_success_at": int(state.get("last_success_at", 0) or 0),
                },
            )

    def resolve_active_venue(self) -> WeatherResult:
        venue = self._resolve_venue()
        if venue is None:
            return WeatherResult("VENUE_NOT_FOUND")
        return WeatherResult("OK", {"venue": self._venue_public(venue)})

    def geocode_active_venue(self) -> WeatherResult:
        with self._lock:
            venue = self._resolve_venue()
            if venue is None:
                return WeatherResult("VENUE_NOT_FOUND")
            address = self._address(venue)
            if not address:
                return WeatherResult("VENUE_ADDRESS_REQUIRED")
            url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + urlencode(
                {
                    "address": address,
                    "benchmark": "Public_AR_Current",
                    "format": "json",
                }
            )
            try:
                payload = self._fetcher(url, {"Accept": "application/json"})
                matches = payload.get("result", {}).get("addressMatches", [])
                coordinates = matches[0]["coordinates"] if matches else None
                latitude = float(coordinates["y"]) if coordinates else None
                longitude = float(coordinates["x"]) if coordinates else None
            except (KeyError, TypeError, ValueError, OSError) as exc:
                return WeatherResult("GEOCODE_FAILED", {"message": str(exc)})
            if latitude is None or longitude is None:
                return WeatherResult("GEOCODE_NOT_FOUND")

            venues = self._load_venues()
            updated = None
            for row in venues:
                if str(row.get("id", "")) == str(venue.get("id", "")):
                    row["latitude"] = latitude
                    row["longitude"] = longitude
                    row["venue_address_source"] = "census-geocoder"
                    row["venue_verified"] = True
                    row["updated_at"] = int(self._clock())
                    updated = row
                    break
            if updated is None:
                return WeatherResult("VENUE_NOT_FOUND")
            self._save_venues(venues)
            state = self._load()
            state["venue"] = self._venue_public(updated)
            self._history(state, "venue_geocoded", {"venue_id": updated.get("id", "")})
            self._write(state)
            return WeatherResult("GEOCODED", {"venue": self._venue_public(updated)})

    def refresh(self, *, force: bool = False) -> WeatherResult:
        with self._lock:
            state = self._load()
            config = self._weather_config()
            now = int(self._clock())
            minimum = max(30, int(config.get("refresh_seconds", 60)))
            elapsed = now - int(state.get("last_attempt_at", 0) or 0)
            if not force and state.get("last_attempt_at") and elapsed < minimum:
                self._apply_time_state(state)
                return WeatherResult(
                    "POLL_THROTTLED",
                    {"retry_after": minimum - elapsed, "weather": copy.deepcopy(state)},
                )

            venue = self._resolve_venue()
            state["last_attempt_at"] = now
            if venue is None:
                state.update({"stale": True, "error": "No active game venue could be resolved."})
                self._write(state)
                return WeatherResult("VENUE_NOT_FOUND", {"weather": state})
            latitude = self._coordinate(venue.get("latitude"))
            longitude = self._coordinate(venue.get("longitude"))
            state["venue"] = self._venue_public(venue)
            if latitude is None or longitude is None:
                state.update({"stale": True, "error": "The active venue needs latitude and longitude."})
                self._write(state)
                return WeatherResult("LOCATION_REQUIRED", {"venue": state["venue"], "weather": state})

            headers = {
                "Accept": "application/geo+json, application/json",
                "User-Agent": str(config.get("user_agent") or "CSRN-Production-Suite/1.13"),
            }
            point = f"{latitude:.4f},{longitude:.4f}"
            try:
                points = self._fetcher(f"https://api.weather.gov/points/{point}", headers)
                hourly_url = str(points.get("properties", {}).get("forecastHourly", ""))
                if not hourly_url.startswith("https://api.weather.gov/"):
                    raise ValueError("NWS points response did not include a valid hourly forecast URL.")
                hourly = self._fetcher(hourly_url, headers)
                alert_payload = self._fetcher(
                    "https://api.weather.gov/alerts/active?" + urlencode({"point": point}),
                    headers,
                )
                conditions = self._normalize_conditions(hourly)
                alerts = self._normalize_alerts(alert_payload, state.get("alerts", []), now)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                state.update({"stale": True, "error": str(exc)})
                self._history(state, "refresh_failed", {"message": str(exc)})
                self._write(state)
                return WeatherResult("FETCH_FAILED", {"message": str(exc), "weather": state})

            previous_ids = {str(item.get("id", "")) for item in state.get("alerts", [])}
            current_ids = {str(item.get("id", "")) for item in alerts}
            for alert_id in sorted(current_ids - previous_ids):
                self._history(state, "alert_received", {"alert_id": alert_id})
            for alert_id in sorted(previous_ids - current_ids):
                self._history(state, "alert_expired_or_cancelled", {"alert_id": alert_id})

            selected_id = str(state.get("selected_alert_id", ""))
            if selected_id and selected_id not in current_ids:
                state["selected_alert_id"] = ""
                if state.get("overlay", {}).get("mode") in {"advisory", "emergency"}:
                    state["overlay"] = self._overlay(False, "hidden", "", now)

            state.update(
                {
                    "venue": self._venue_public(venue),
                    "conditions": conditions,
                    "alerts": alerts,
                    "last_success_at": now,
                    "stale": False,
                    "error": "",
                }
            )
            self._history(state, "weather_refreshed", {"alerts": len(alerts)})
            self._write(state)
            return WeatherResult("REFRESHED", {"weather": copy.deepcopy(state)})

    def approve_alert(self, alert_id: Any, *, visible: bool = True) -> WeatherResult:
        if not isinstance(visible, bool):
            return WeatherResult("VISIBLE_MUST_BE_BOOLEAN")
        with self._lock:
            state = self._load()
            alert = self._find_alert(state, alert_id)
            if alert is None:
                return WeatherResult("ALERT_NOT_FOUND")
            now = int(self._clock())
            state["selected_alert_id"] = str(alert.get("id", ""))
            alert["displayed_at"] = now if visible else int(alert.get("displayed_at", 0) or 0)
            mode = "emergency" if self.SEVERITY_ORDER.get(str(alert.get("severity", "Unknown")), 0) >= 3 else "advisory"
            state["overlay"] = self._overlay(visible, mode if visible else "hidden", "", now)
            self._history(state, "alert_displayed" if visible else "alert_selected", {"alert_id": alert.get("id", "")})
            self._write(state)
            return WeatherResult("ALERT_APPROVED", {"weather": state, "alert": copy.deepcopy(alert)})

    def dismiss_alert(self, alert_id: Any = "") -> WeatherResult:
        with self._lock:
            state = self._load()
            target = str(alert_id or state.get("selected_alert_id", ""))
            alert = self._find_alert(state, target)
            if target and alert is None:
                return WeatherResult("ALERT_NOT_FOUND")
            now = int(self._clock())
            if alert is not None:
                alert["dismissed_at"] = now
            state["selected_alert_id"] = ""
            state["overlay"] = self._overlay(False, "hidden", "", now)
            self._history(state, "alert_dismissed", {"alert_id": target})
            self._write(state)
            return WeatherResult("ALERT_DISMISSED", {"weather": state})

    def set_overlay(self, payload: Any) -> WeatherResult:
        if not isinstance(payload, dict):
            return WeatherResult("OVERLAY_REQUIRED")
        visible = payload.get("visible")
        if not isinstance(visible, bool):
            return WeatherResult("VISIBLE_MUST_BE_BOOLEAN")
        mode = str(payload.get("mode", "bug" if visible else "hidden")).strip().lower()
        if mode not in self.MODES:
            return WeatherResult("OVERLAY_MODE_INVALID")
        message = self._text(payload.get("message", ""), 500)
        with self._lock:
            state = self._load()
            now = int(self._clock())
            state["overlay"] = self._overlay(visible, mode, message, now)
            self._history(state, "overlay_updated", {"visible": visible, "mode": mode})
            self._write(state)
            return WeatherResult("OVERLAY_UPDATED", {"weather": state})

    def start_delay(self, payload: Any) -> WeatherResult:
        incoming = payload if isinstance(payload, dict) else {}
        message = self._text(incoming.get("message") or "Game delayed due to weather.", 500)
        source = self._text(incoming.get("source") or "school-officials", 120)
        with self._lock:
            state = self._load()
            now = int(self._clock())
            state["delay"] = {
                "active": True,
                "started_at": now,
                "resumed_at": 0,
                "message": message,
                "source": source,
            }
            state["overlay"] = self._overlay(True, "delay", message, now)
            self._history(state, "weather_delay_started", {"source": source, "message": message})
            self._write(state)
            return WeatherResult("DELAY_STARTED", {"weather": state})

    def resume_game(self, payload: Any = None) -> WeatherResult:
        incoming = payload if isinstance(payload, dict) else {}
        message = self._text(incoming.get("message") or "Game resuming.", 500)
        with self._lock:
            state = self._load()
            now = int(self._clock())
            delay = state.get("delay", {})
            delay.update({"active": False, "resumed_at": now, "message": message})
            state["delay"] = delay
            state["overlay"] = self._overlay(True, "resumption", message, now)
            self._history(state, "game_resuming", {"message": message})
            self._write(state)
            return WeatherResult("GAME_RESUMING", {"weather": state})

    def record_lightning(self) -> WeatherResult:
        with self._lock:
            state = self._load()
            now = int(self._clock())
            state["lightning"] = {
                "active": True,
                "last_observed_at": now,
                "clear_at": now + 30 * 60,
                "reset_at": 0,
            }
            self._history(state, "lightning_observed", {"clear_at": now + 30 * 60})
            self._write(state)
            self._apply_time_state(state)
            return WeatherResult("LIGHTNING_RECORDED", {"weather": state})

    def reset_lightning_timer(self, confirmation: Any) -> WeatherResult:
        if str(confirmation or "").strip() != "RESET LIGHTNING TIMER":
            return WeatherResult("CONFIRMATION_REQUIRED")
        with self._lock:
            state = self._load()
            now = int(self._clock())
            state["lightning"] = {
                "active": False,
                "last_observed_at": 0,
                "clear_at": 0,
                "reset_at": now,
            }
            self._history(state, "lightning_timer_reset", {})
            self._write(state)
            return WeatherResult("LIGHTNING_TIMER_RESET", {"weather": state})

    def _resolve_venue(self) -> dict[str, Any] | None:
        state = self._load_broadcast_state() or {}
        venues = [row for row in self._load_venues() if row.get("active", True) is not False]
        venue_id = str(state.get("venue_id", "")).strip()
        if venue_id:
            match = next((row for row in venues if str(row.get("id", "")) == venue_id), None)
            if match:
                return copy.deepcopy(match)
        venue_name = str(state.get("venue", "")).strip().casefold()
        if venue_name:
            match = next((row for row in venues if str(row.get("name", "")).strip().casefold() == venue_name), None)
            if match:
                return copy.deepcopy(match)

        config = self._weather_config()
        if config.get("use_home_venue_address", True):
            school_id = str(state.get("home_school_id", "")).strip()
            schools = self._load_schools()
            school = next((row for row in schools if str(row.get("id", "")) == school_id), None)
            explicit = str((school or {}).get("venue_id", "")).strip()
            if explicit:
                match = next((row for row in venues if str(row.get("id", "")) == explicit), None)
                if match:
                    return copy.deepcopy(match)
            if school_id:
                matches = [row for row in venues if str(row.get("school_id", "")) == school_id]
                sport = str(state.get("sport", "")).strip().casefold()
                exact = next((row for row in matches if str(row.get("sport", "")).strip().casefold() == sport), None)
                if exact or matches:
                    return copy.deepcopy(exact or matches[0])
        return None

    def _weather_config(self) -> dict[str, Any]:
        config = self._load_config() or {}
        weather = config.get("weather", {}) if isinstance(config, dict) else {}
        weather = weather if isinstance(weather, dict) else {}
        return {
            "use_home_venue_address": bool(weather.get("use_home_venue_address", True)),
            "default_alert_radius_miles": int(weather.get("default_alert_radius_miles", 25) or 25),
            "refresh_seconds": max(30, int(weather.get("refresh_seconds", 60) or 60)),
            "stale_after_seconds": max(60, int(weather.get("stale_after_seconds", 180) or 180)),
            "user_agent": str(weather.get("user_agent") or "CSRN-Production-Suite/1.13 (weather@localhost)"),
        }

    def _load(self) -> dict[str, Any]:
        if not self.state_file.exists():
            state = copy.deepcopy(self.DEFAULT_STATE)
            self._write(state)
            return state
        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raw = {}
        state = copy.deepcopy(self.DEFAULT_STATE)
        if isinstance(raw, dict):
            state.update(copy.deepcopy(raw))
        for key in ("overlay", "delay", "lightning"):
            merged = copy.deepcopy(self.DEFAULT_STATE[key])
            if isinstance(state.get(key), dict):
                merged.update(state[key])
            state[key] = merged
        if not isinstance(state.get("alerts"), list):
            state["alerts"] = []
        if not isinstance(state.get("history"), list):
            state["history"] = []
        return state

    def _write(self, state: dict[str, Any]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.state_file)

    def _apply_time_state(self, state: dict[str, Any]) -> None:
        now = int(self._clock())
        stale_after = self._weather_config()["stale_after_seconds"]
        last_success = int(state.get("last_success_at", 0) or 0)
        if not last_success or now - last_success > stale_after:
            state["stale"] = True
            if not state.get("error"):
                state["error"] = "Weather data is stale."
        lightning = state.get("lightning", {})
        clear_at = int(lightning.get("clear_at", 0) or 0)
        lightning["remaining_seconds"] = max(0, clear_at - now) if lightning.get("active") else 0
        lightning["timer_elapsed"] = bool(lightning.get("active") and clear_at and now >= clear_at)
        lightning["safety_note"] = "Timer completion does not declare the venue safe; school officials make the resumption decision."

    @classmethod
    def _normalize_conditions(cls, payload: dict[str, Any]) -> dict[str, Any]:
        periods = payload.get("properties", {}).get("periods", [])
        period = periods[0] if isinstance(periods, list) and periods else {}
        probability = period.get("probabilityOfPrecipitation", {})
        return {
            "start_time": str(period.get("startTime", "")),
            "temperature": period.get("temperature"),
            "temperature_unit": str(period.get("temperatureUnit", "")),
            "wind_speed": str(period.get("windSpeed", "")),
            "wind_direction": str(period.get("windDirection", "")),
            "precipitation_probability": probability.get("value") if isinstance(probability, dict) else None,
            "short_forecast": str(period.get("shortForecast", "")),
            "detailed_forecast": str(period.get("detailedForecast", "")),
            "source": "National Weather Service",
        }

    @classmethod
    def _normalize_alerts(
        cls,
        payload: dict[str, Any],
        previous: list[dict[str, Any]],
        now: int,
    ) -> list[dict[str, Any]]:
        prior = {str(item.get("id", "")): item for item in previous if isinstance(item, dict)}
        features = payload.get("features", [])
        rows: list[dict[str, Any]] = []
        for feature in features if isinstance(features, list) else []:
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties", {})
            properties = properties if isinstance(properties, dict) else {}
            alert_id = str(feature.get("id") or properties.get("id") or "").strip()
            if not alert_id:
                continue
            old = prior.get(alert_id, {})
            rows.append(
                {
                    "id": alert_id,
                    "event": cls._text(properties.get("event", "Weather Alert"), 160),
                    "headline": cls._text(properties.get("headline", ""), 300),
                    "description": cls._text(properties.get("description", ""), 3000),
                    "instruction": cls._text(properties.get("instruction", ""), 2000),
                    "severity": str(properties.get("severity", "Unknown")),
                    "urgency": str(properties.get("urgency", "Unknown")),
                    "certainty": str(properties.get("certainty", "Unknown")),
                    "area_desc": cls._text(properties.get("areaDesc", ""), 500),
                    "effective": str(properties.get("effective", "")),
                    "expires": str(properties.get("expires", "")),
                    "sent": str(properties.get("sent", "")),
                    "sender_name": str(properties.get("senderName", "National Weather Service")),
                    "received_at": int(old.get("received_at", now) or now),
                    "displayed_at": int(old.get("displayed_at", 0) or 0),
                    "dismissed_at": int(old.get("dismissed_at", 0) or 0),
                }
            )
        rows.sort(
            key=lambda item: (
                -cls.SEVERITY_ORDER.get(str(item.get("severity", "Unknown")), 0),
                str(item.get("event", "")),
            )
        )
        return rows

    @staticmethod
    def _coordinate(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _text(value: Any, limit: int) -> str:
        return " ".join(str(value or "").replace("\x00", " ").split())[:limit]

    @classmethod
    def _venue_public(cls, venue: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(venue.get("id", "")),
            "name": str(venue.get("name", "")),
            "address": cls._address(venue),
            "latitude": cls._coordinate(venue.get("latitude")),
            "longitude": cls._coordinate(venue.get("longitude")),
            "verified": bool(venue.get("venue_verified", False)),
        }

    @staticmethod
    def _address(venue: dict[str, Any]) -> str:
        parts = [
            str(venue.get("address1", "")).strip(),
            str(venue.get("address2", "")).strip(),
            str(venue.get("city", "")).strip(),
            str(venue.get("state", "")).strip(),
            str(venue.get("postal_code", "")).strip(),
        ]
        return ", ".join(part for part in parts if part)

    @staticmethod
    def _overlay(visible: bool, mode: str, message: str, now: int) -> dict[str, Any]:
        return {
            "visible": bool(visible),
            "mode": str(mode),
            "message": str(message),
            "updated_at": int(now),
            "sponsor_allowed": False if mode in {"emergency", "delay"} else True,
        }

    @staticmethod
    def _find_alert(state: dict[str, Any], alert_id: Any) -> dict[str, Any] | None:
        target = str(alert_id or "")
        return next(
            (item for item in state.get("alerts", []) if str(item.get("id", "")) == target),
            None,
        )

    def _history(self, state: dict[str, Any], action: str, detail: dict[str, Any]) -> None:
        rows = list(state.get("history", []))
        rows.append({"action": action, "detail": copy.deepcopy(detail), "at": int(self._clock())})
        state["history"] = rows[-500:]
