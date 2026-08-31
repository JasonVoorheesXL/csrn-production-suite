from __future__ import annotations

import copy
import json
import os
import sys
import threading
import time
import inspect
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request


_LOCK = threading.RLock()
_NWS_CACHE: dict[str, Any] = {"key": "", "at": 0, "periods": []}

# Eyebrows the automatic/statistician spotlight paths actually use
# (rules_service.py's _show_player_spotlight() and event_service.py's
# automatic branch). "PLAYER PROFILE" is the graphic's idle/manual default,
# not a real in-game moment, so it's deliberately excluded.
_SPOTLIGHT_EYEBROWS = {
    "TOUCHDOWN",
    "SACK",
    "TURNOVER",
    "FIRST DOWN",
    "TWO-POINT CONVERSION",
    "DEFENSIVE TOUCHDOWN",
}


def _csrn_app() -> Any:
    for name in ("__main__", "app"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "load_state"):
            return module
    import app as csrn_app
    return csrn_app


def _runtime_file() -> Path:
    return Path(__file__).resolve().parent / "Data" / "Runtime" / "pregame_presentation.json"


def _overlay_template() -> Path:
    return Path(__file__).resolve().parent / "templates" / "pregame_universal_overlay.html"


def _read_store() -> dict[str, Any]:
    path = _runtime_file()
    if not path.exists():
        return {"broadcasts": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {"broadcasts": {}}
    except Exception:
        return {"broadcasts": {}}


def _write_store(data: dict[str, Any]) -> None:
    path = _runtime_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _default_settings() -> dict[str, Any]:
    return {
        "mode": "auto",
        "transition_mode": "manual",
        "rotation_seconds": 10,
        "storylines": [],
        "delay_type": "weather",
        "delay_note": "",
        "estimated_start": "",
        "updated_at": 0,
    }


def _state() -> dict[str, Any]:
    csrn_app = _csrn_app()
    raw = csrn_app.load_state()
    return raw if isinstance(raw, dict) else {}


def _broadcast_records() -> list[dict[str, Any]]:
    csrn_app = _csrn_app()
    try:
        result = csrn_app.get_broadcast_service().list_records()
        rows = result.data.get("broadcasts", []) if getattr(result, "ok", False) else []
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def _weather_service_payload() -> dict[str, Any]:
    import app as csrn_app
    try:
        service = csrn_app.get_weather_service()

        def read_status() -> dict[str, Any]:
            result = service.status()
            data = getattr(result, "data", {}) or {}
            weather = data.get("weather", {})
            return weather if isinstance(weather, dict) else {}

        weather = read_status()
        has_useful = bool(
            weather.get("forecast")
            or weather.get("current")
            or weather.get("observation")
            or weather.get("short_forecast")
            or int(weather.get("last_success_at", 0) or 0) > 0
        )

        # Existing CSRN weather service may require an explicit refresh before the
        # first pregame read. Call only bound zero-required-argument refresh-like
        # methods so this compatibility layer cannot guess an unsafe signature.
        if not has_useful:
            for name in ("refresh", "update", "refresh_weather"):
                fn = getattr(service, name, None)
                if not callable(fn):
                    continue
                try:
                    sig = inspect.signature(fn)
                    required = [
                        p for p in sig.parameters.values()
                        if p.default is inspect.Parameter.empty
                        and p.kind in (
                            inspect.Parameter.POSITIONAL_ONLY,
                            inspect.Parameter.POSITIONAL_OR_KEYWORD,
                            inspect.Parameter.KEYWORD_ONLY,
                        )
                    ]
                    if required:
                        continue
                    fn()
                    weather = read_status()
                    break
                except Exception:
                    continue
        return weather
    except Exception:
        return {}


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _geocode_place(query: str) -> tuple[float | None, float | None, str]:
    query = str(query or "").strip()
    if not query:
        return None, None, ""
    try:
        url = (
            "https://geocoding-api.open-meteo.com/v1/search?"
            + urllib.parse.urlencode({
                "name": query,
                "count": 5,
                "language": "en",
                "format": "json",
            })
        )
        raw = _json_get(url)
        results = raw.get("results", [])
        if not isinstance(results, list):
            return None, None, ""
        for row in results:
            if not isinstance(row, dict):
                continue
            country = str(row.get("country_code", "") or "").upper()
            admin1 = str(row.get("admin1", "") or "")
            # Prefer US / Mississippi matches for this current CSRN build.
            if country and country != "US":
                continue
            if admin1 and "mississippi" not in admin1.casefold():
                continue
            lat = _float(row.get("latitude"))
            lon = _float(row.get("longitude"))
            if lat is None or lon is None:
                continue
            label = ", ".join(x for x in [str(row.get("name", "") or ""), admin1] if x)
            return lat, lon, label
    except Exception:
        pass
    return None, None, ""


def _venue_coordinates(weather: dict[str, Any], active: dict[str, Any], state: dict[str, Any]) -> tuple[float | None, float | None, str]:
    candidates: list[dict[str, Any]] = []
    venue = weather.get("venue", {})
    if isinstance(venue, dict):
        candidates.append(venue)
    candidates.extend([active, state])

    csrn_app = _csrn_app()
    venue_row: dict[str, Any] = {}
    try:
        venue_id = str(active.get("venue_id") or state.get("venue_id") or "").strip()
        venue_name = str(active.get("venue") or state.get("venue") or "").strip().casefold()
        rows = csrn_app.load_venues()
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if venue_id and str(row.get("id", "") or "") == venue_id:
                    venue_row = row
                    candidates.insert(0, row)
                    break
                if venue_name and str(row.get("name", "") or "").strip().casefold() == venue_name:
                    venue_row = row
                    candidates.append(row)
    except Exception:
        pass

    for row in candidates:
        lat = _float(row.get("latitude", row.get("lat")))
        lon = _float(row.get("longitude", row.get("lon", row.get("lng"))))
        if lat is not None and lon is not None:
            label = str(row.get("name") or row.get("city") or active.get("venue") or "")
            return lat, lon, label

    # Venue records often have no lat/lon. Build a geocoding query from the home
    # school's stored city/state; this is enough to get game-area hourly weather.
    home_school_id = str(active.get("home_school_id") or state.get("home_school_id") or "").strip()
    home_school = _school_by_id(home_school_id)
    city = str(
        venue_row.get("city")
        or home_school.get("city")
        or active.get("venue_city")
        or state.get("venue_city")
        or ""
    ).strip()
    region = str(
        venue_row.get("state")
        or home_school.get("state")
        or active.get("venue_state")
        or state.get("venue_state")
        or "MS"
    ).strip()
    address = str(
        venue_row.get("address1")
        or venue_row.get("address")
        or home_school.get("address1")
        or ""
    ).strip()

    queries = []
    if address and city:
        queries.append(f"{address}, {city}, {region}")
    if city:
        queries.append(f"{city}, {region}")
    venue_name = str(active.get("venue") or state.get("venue") or "").strip()
    if venue_name and city:
        queries.append(f"{venue_name}, {city}, {region}")

    # Last-resort inference for the current Houston home game if imported school
    # data did not carry a city into the game snapshot.
    home_name = str(active.get("home_team") or state.get("home_team") or "").casefold()
    if not queries and "houston" in home_name:
        queries.append("Houston, Mississippi")

    for query in queries:
        lat, lon, label = _geocode_place(query)
        if lat is not None and lon is not None:
            return lat, lon, label or query

    return None, None, ""


def _json_get(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CSRN-Production-Suite/1.14 pregame-weather",
            "Accept": "application/geo+json,application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=12) as response:
        raw = json.loads(response.read().decode("utf-8", errors="replace"))
        return raw if isinstance(raw, dict) else {}


def _nws_hourly_periods(lat: float | None, lon: float | None) -> list[dict[str, Any]]:
    if lat is None or lon is None:
        return []
    key = f"{lat:.4f},{lon:.4f}"
    now = int(time.time())
    if _NWS_CACHE.get("key") == key and now - int(_NWS_CACHE.get("at", 0) or 0) < 600:
        cached = _NWS_CACHE.get("periods", [])
        return copy.deepcopy(cached) if isinstance(cached, list) else []
    try:
        point = _json_get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}")
        hourly_url = str(point.get("properties", {}).get("forecastHourly", "") or "")
        if not hourly_url:
            return []
        forecast = _json_get(hourly_url)
        raw_periods = forecast.get("properties", {}).get("periods", [])
        periods: list[dict[str, Any]] = []
        if isinstance(raw_periods, list):
            for period in raw_periods[:168]:
                if not isinstance(period, dict):
                    continue
                probability = period.get("probabilityOfPrecipitation", {})
                probability_value = (
                    probability.get("value")
                    if isinstance(probability, dict)
                    else probability
                )
                periods.append({
                    "start_time": str(period.get("startTime", "")),
                    "end_time": str(period.get("endTime", "")),
                    "temperature": period.get("temperature"),
                    "temperature_unit": str(period.get("temperatureUnit", "")),
                    "wind_speed": str(period.get("windSpeed", "")),
                    "wind_direction": str(period.get("windDirection", "")),
                    "precipitation_probability": probability_value,
                    "short_forecast": str(period.get("shortForecast", "")),
                    "detailed_forecast": str(period.get("detailedForecast", "")),
                })
        _NWS_CACHE.update({"key": key, "at": now, "periods": periods})
        return copy.deepcopy(periods)
    except Exception:
        return []


def _parse_game_start(game: dict[str, Any]) -> datetime | None:
    date = str(game.get("date", "") or "").strip()
    raw = str(game.get("scheduled_start", "") or "").strip()
    if not date or not raw:
        return None
    import re
    match = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)?$", raw, re.I)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    ampm = str(match.group(3) or "").upper()
    if ampm == "PM" and hour < 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    try:
        # Keep local clock semantics; NWS ISO timestamps carry their own offsets.
        return datetime.fromisoformat(f"{date}T{hour:02d}:{minute:02d}:00")
    except ValueError:
        return None


def _game_forecast(periods: list[dict[str, Any]], game: dict[str, Any]) -> list[dict[str, Any]]:
    start = _parse_game_start(game)
    if start is None:
        return periods[:5]
    selected: list[dict[str, Any]] = []
    for period in periods:
        try:
            when = datetime.fromisoformat(str(period.get("start_time", "")).replace("Z", "+00:00"))
            local_when = when.replace(tzinfo=None)
        except Exception:
            continue
        # One hour before scheduled start through four hours after kickoff.
        if start - timedelta(hours=1) <= local_when <= start + timedelta(hours=4):
            selected.append(period)
    return selected[:6]


def _weather(active: dict[str, Any], state: dict[str, Any], game: dict[str, Any]) -> dict[str, Any]:
    weather = _weather_service_payload()
    lat, lon, location_label = _venue_coordinates(weather, active, state)
    periods = _nws_hourly_periods(lat, lon)
    weather = copy.deepcopy(weather)
    weather["location_resolution"] = {
        "latitude": lat,
        "longitude": lon,
        "label": location_label,
        "resolved": lat is not None and lon is not None,
    }
    if periods:
        weather["hourly_forecast"] = periods
        weather["game_forecast"] = _game_forecast(periods, game)
        weather["source"] = "National Weather Service"
    else:
        weather.setdefault("game_forecast", [])
    return weather


def _first_half_spotlights(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Real spotlight moments from the first half, for the halftime rotation.

    Sourced directly from state["events"] -- every event that already fired
    a player-spotlight graphic (rules_service.py's _show_player_spotlight(),
    or event_service.py's automatic branch) carries the fully-resolved
    graphic snapshot at event["after"]["player_graphic"] (headshot, team
    logo/color, eyebrow, play detail -- everything needed to render a card).
    Nothing here re-resolves a roster lookup; it only reads what was already
    captured at the moment the graphic actually showed.
    """
    events = state.get("events")
    if not isinstance(events, list):
        return []
    spotlights: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        if str(event.get("quarter", "")).strip() not in {"1", "2"}:
            continue
        after = event.get("after")
        graphic = after.get("player_graphic") if isinstance(after, dict) else None
        if not isinstance(graphic, dict) or not graphic.get("visible"):
            continue
        eyebrow = str(graphic.get("eyebrow", "")).strip().upper()
        if eyebrow not in _SPOTLIGHT_EYEBROWS:
            continue
        spotlights.append({
            "event_id": str(event.get("id", "")),
            "quarter": str(event.get("quarter", "")),
            "eyebrow": eyebrow,
            "graphic_type": str(graphic.get("graphic_type", "")),
            "full_name": str(graphic.get("full_name") or graphic.get("display_name") or ""),
            "display_name": str(graphic.get("display_name") or graphic.get("full_name") or ""),
            "number": str(graphic.get("number", "")),
            "position": str(graphic.get("position", "")),
            "headshot": str(graphic.get("headshot", "")),
            "team_logo": str(graphic.get("team_logo", "")),
            "team_name": str(graphic.get("team_name", "")),
            "team_color": str(graphic.get("team_color", "") or "#C9203B"),
            "play_detail": str(graphic.get("play_detail", "")),
            "passer_name": str(graphic.get("passer_name", "")),
            "created_at": int(event.get("created_at", 0) or 0),
        })
    return spotlights


def _halftime_sponsors() -> list[dict[str, Any]]:
    """Active sponsors for the halftime rotation.

    Not a new list or pull mechanism: it reads the same sponsor roster the
    Sponsor Advertisement / Sponsor Spotlight controls pick from
    (SponsorService.list_payload()), filtered to currently-active sponsors
    that have a logo, and hands the overlay {name, logo} to cycle through its
    existing card rotation.
    """
    try:
        payload = _csrn_app().get_sponsor_service().list_payload()
    except Exception:
        return []
    rows = payload.get("sponsors", []) if isinstance(payload, dict) else []
    sponsors: list[dict[str, Any]] = []
    for source in rows if isinstance(rows, list) else []:
        if not isinstance(source, dict):
            continue
        if not source.get("active", True):
            continue
        if str(source.get("effective_status", "")).strip().lower() == "expired":
            continue
        logo = str(source.get("logo_url", "") or "").strip()
        name = str(source.get("name", "") or "").strip()
        if not name or not logo:
            continue
        lead_ins = source.get("lead_ins") if isinstance(source.get("lead_ins"), list) else []
        sponsors.append({
            "name": name,
            "logo": logo,
            "package": str(source.get("package", "") or "").strip(),
            "lead_in": str(lead_ins[0] if lead_ins else "Proud sponsor of tonight's broadcast"),
        })
    return sponsors


def _config() -> dict[str, Any]:
    csrn_app = _csrn_app()
    try:
        value = csrn_app.load_config()
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _schools() -> list[dict[str, Any]]:
    csrn_app = _csrn_app()
    try:
        rows = csrn_app.load_schools()
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def _school_by_id(school_id: str) -> dict[str, Any]:
    target = str(school_id or "").strip()
    if not target:
        return {}
    for row in _schools():
        if not isinstance(row, dict):
            continue
        if target in {
            str(row.get("id", "") or ""),
            str(row.get("csrn_id", "") or ""),
            str(row.get("school_id", "") or ""),
        }:
            return row
    return {}


def _school_by_name(name: str) -> dict[str, Any]:
    target = str(name or "").strip().casefold()
    if not target:
        return {}
    for row in _schools():
        if not isinstance(row, dict):
            continue
        names = {
            str(row.get("broadcast_name", "") or "").strip().casefold(),
            str(row.get("preferred_scorebug_name", "") or "").strip().casefold(),
            str(row.get("short_name", "") or "").strip().casefold(),
            str(row.get("official_name", "") or "").strip().casefold(),
        }
        if target in names:
            return row
    return {}


def _caledonia_school() -> dict[str, Any]:
    # CSRN's own team is authoritative for the "Next Matchup" pregame card.
    for candidate in ("Caledonia", "Caledonia High School"):
        row = _school_by_name(candidate)
        if row:
            return row
    return {}


def _record_for_state(state: dict[str, Any]) -> dict[str, Any]:
    bid = str(state.get("broadcast_id", "") or "")
    if not bid:
        return {}
    for row in _broadcast_records():
        if str(row.get("broadcast_id", "")) == bid:
            return row
    return {}


def _record_dict(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {"wins": 0, "losses": 0, "ties": 0}
    return {
        "wins": int(value.get("wins", 0) or 0),
        "losses": int(value.get("losses", 0) or 0),
        "ties": int(value.get("ties", 0) or 0),
    }


def _identity(state: dict[str, Any], side: str) -> dict[str, Any]:
    value = state.get(f"{side}_identity", {})
    result = copy.deepcopy(value) if isinstance(value, dict) else {}

    team_name = state.get(f"{side}_team", side.title())

    result.setdefault("name", team_name)
    result.setdefault("team_name", team_name)

    school = {}

    school_id = str(
        result.get("school_id")
        or state.get(f"{side}_school_id")
        or ""
    ).strip()

    if school_id:
        school = _school_by_id(school_id)

    if not school:
        school = _school_by_name(str(team_name or ""))

    programs = school.get("programs", {}) if isinstance(school, dict) else {}
    if not isinstance(programs, dict):
        programs = {}

    football = programs.get("Football", {})
    if not isinstance(football, dict):
        football = {}

    result["football_social"] = {
        "facebook": str(football.get("facebook") or "").strip(),
        "x": str(football.get("x") or "").strip(),
    }

    return result


def _school_identifiers(row: dict[str, Any]) -> set[str]:
    return {
        str(row.get("id", "") or "").strip(),
        str(row.get("csrn_id", "") or "").strip(),
        str(row.get("school_id", "") or "").strip(),
    } - {""}


def _row_side_matches_school(row: dict[str, Any], side: str, school: dict[str, Any]) -> bool:
    identifiers = _school_identifiers(school)
    side_id = str(row.get(f"{side}_school_id", "") or "").strip()
    if side_id and side_id in identifiers:
        return True
    names = {
        str(school.get("broadcast_name", "") or "").strip().casefold(),
        str(school.get("preferred_scorebug_name", "") or "").strip().casefold(),
        str(school.get("short_name", "") or "").strip().casefold(),
        str(school.get("official_name", "") or "").strip().casefold(),
    } - {""}
    side_name = str(row.get(f"{side}_team", "") or "").strip().casefold()
    return bool(side_name and side_name in names)


def _next_matchup(active: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    # User-facing CSRN pregame "Next Matchup" is intentionally about Caledonia,
    # regardless of whether Caledonia is home or visitor in the current game.
    primary = _caledonia_school()
    if not primary:
        return {}

    active_date = str(active.get("date") or state.get("date") or "")
    active_id = str(active.get("broadcast_id") or state.get("broadcast_id") or "")
    rows: list[dict[str, Any]] = []

    for row in _broadcast_records():
        if not isinstance(row, dict):
            continue
        if str(row.get("broadcast_id", "") or "") == active_id:
            continue
        if str(row.get("status", "") or "").lower() == "completed":
            continue
        date = str(row.get("date", "") or "")
        if active_date and date and date <= active_date:
            continue
        if not (_row_side_matches_school(row, "home", primary) or _row_side_matches_school(row, "visitor", primary)):
            continue
        rows.append(row)

    rows.sort(key=lambda x: (str(x.get("date", "")), str(x.get("scheduled_start", ""))))
    if not rows:
        return {}

    row = rows[0]
    primary_home = _row_side_matches_school(row, "home", primary)
    opponent = row.get("visitor_team", "") if primary_home else row.get("home_team", "")
    return {
        "date": row.get("date", ""),
        "scheduled_start": row.get("scheduled_start", ""),
        "week": row.get("week", ""),
        "home_team": row.get("home_team", ""),
        "visitor_team": row.get("visitor_team", ""),
        "opponent": opponent,
        "location": "Home" if primary_home else "Away",
        "venue": row.get("venue", ""),
        "contest_type": row.get("contest_type", ""),
        "primary_school_id": next(iter(_school_identifiers(primary)), ""),
        "primary_team": str(primary.get("broadcast_name", "Caledonia") or "Caledonia"),
    }


def _presentation_settings(broadcast_id: str) -> dict[str, Any]:
    store = _read_store()
    rows = store.get("broadcasts", {})
    existing = rows.get(broadcast_id, {}) if isinstance(rows, dict) else {}
    result = _default_settings()
    if isinstance(existing, dict):
        result.update(existing)
    return result


def _save_settings(broadcast_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        store = _read_store()
        rows = store.setdefault("broadcasts", {})
        current = _default_settings()
        if isinstance(rows.get(broadcast_id), dict):
            current.update(rows[broadcast_id])
        current.update(copy.deepcopy(updates))
        current["updated_at"] = int(time.time())
        rows[broadcast_id] = current
        _write_store(store)
        return copy.deepcopy(current)


def _automatic_storylines(active: dict[str, Any], game: dict[str, Any], next_matchup: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    contest = str(game.get("contest_type", "") or "").strip().lower()
    week = str(game.get("week", "") or "").strip()
    home_class = str(game.get("home_classification", "") or "").strip()
    visitor_class = str(game.get("visitor_classification", "") or "").strip()

    if contest in {"scrimmage", "exhibition"}:
        label = "scrimmage" if contest == "scrimmage" else "exhibition"
        if week == "0":
            rows.append(f"Week 0 {label}: tonight's result will not count toward the official season record.")
        else:
            rows.append(f"Tonight is a {label}; official win-loss records are not affected.")

    if home_class and visitor_class and home_class != visitor_class:
        rows.append(f"{visitor_class} {game.get('visitor_team', 'Visitor')} visits {home_class} {game.get('home_team', 'Home')}.")

    designations = active.get("special_designations", [])
    if isinstance(designations, list):
        labels = {
            "homecoming": "Homecoming",
            "senior_night": "Senior Night",
            "rivalry": "Rivalry game",
            "playoff": "Playoff game",
            "championship": "Championship game",
        }
        for item in designations:
            text = labels.get(str(item).lower())
            if text:
                rows.append(text + ".")

    if next_matchup.get("opponent"):
        rows.append(
            f"Next up: {next_matchup.get('opponent')} on {next_matchup.get('date') or 'the next scheduled date'}"
            + (f" at {next_matchup.get('scheduled_start')}" if next_matchup.get("scheduled_start") else "")
            + "."
        )

    return rows[:6]


def _organization_branding() -> dict[str, Any]:
    cfg = _config()
    organization = cfg.get("organization", {})
    if not isinstance(organization, dict):
        organization = {}
    defaults = cfg.get("broadcast_defaults", {})
    if not isinstance(defaults, dict):
        defaults = {}

    default_school = _school_by_id(str(defaults.get("home_school_id", "") or ""))
    # Configured org logo only -- no hard-coded csrn-logo.png fallback
    # (Round 13 Task A). Empty means the customer has not set a logo yet.
    logo = str(
        organization.get("logo_path")
        or organization.get("logo")
        or organization.get("logo_url")
        or ""
    ).strip()

    social = cfg.get("social", {})
    if not isinstance(social, dict):
        social = {}

    return {
        "name": str(organization.get("name") or "Caledonia Sports Radio Network").strip(),
        "short_name": str(organization.get("short_name") or "CSRN").strip(),
        "logo": logo,
        "primary_color": str(organization.get("primary_color") or "#C9203B").strip(),
        "secondary_color": str(organization.get("secondary_color") or "#000000").strip(),
        "accent_color": str(organization.get("accent_color") or "#FFFFFF").strip(),
        "social": {
            "facebook": str(social.get("facebook") or "").strip(),
            "youtube": str(social.get("youtube") or "").strip(),
            "x": str(social.get("x") or "").strip(),
            "website": str(social.get("website") or "").strip(),
        },
        "default_school_id": str(defaults.get("home_school_id") or "").strip(),
    }


def _payload() -> dict[str, Any]:
    state = _state()
    active = _record_for_state(state)
    bid = str(state.get("broadcast_id", "") or active.get("broadcast_id", "") or "")
    settings = _presentation_settings(bid) if bid else _default_settings()

    home = _identity(state, "home")
    visitor = _identity(state, "visitor")
    game = {
        "broadcast_id": bid,
        "status": active.get("status", state.get("status", "")),
        "broadcast_phase": state.get("broadcast_phase", ""),
        "special_game_phase": state.get("special_game_phase", ""),
        "sport": active.get("sport", state.get("sport", "")),
        "week": active.get("week", state.get("week", "")),
        "contest_type": active.get("contest_type", state.get("contest_type", "")),
        "date": active.get("date", state.get("date", "")),
        "scheduled_start": active.get("scheduled_start", state.get("scheduled_start", "")),
        "venue": active.get("venue", state.get("venue", "")),
        "home_team": state.get("home_team", active.get("home_team", "Home")),
        "visitor_team": state.get("visitor_team", active.get("visitor_team", "Visitor")),
        "home_score": int(state.get("home_score", 0) or 0),
        "visitor_score": int(state.get("visitor_score", 0) or 0),
        "quarter": str(state.get("quarter", "") or ""),
        "clock_seconds": int(state.get("clock_seconds", 0) or 0),
        "clock_visible": bool(state.get("clock_visible", True)),
        "down": state.get("down", ""),
        "distance": state.get("distance", ""),
        "ball_spot": state.get("ball_spot", ""),
        "possession": state.get("possession", ""),
        "home_record": _record_dict(active.get("home_pregame_record", state.get("home_pregame_record"))),
        "visitor_record": _record_dict(active.get("visitor_pregame_record", state.get("visitor_pregame_record"))),
        "home_classification": active.get("home_classification", state.get("home_classification", "")),
        "visitor_classification": active.get("visitor_classification", state.get("visitor_classification", "")),
        "home_region": active.get("home_region", state.get("home_region", "")),
        "visitor_region": active.get("visitor_region", state.get("visitor_region", "")),
    }
    next_matchup = _next_matchup(active, state)
    weather = _weather(active, state, game)
    automatic_storylines = _automatic_storylines(active, game, next_matchup)
    return {
        "settings": settings,
        "game": game,
        "home_identity": home,
        "visitor_identity": visitor,
        "weather": weather,
        "first_half_spotlights": _first_half_spotlights(state),
        "halftime_sponsors": _halftime_sponsors(),
        "next_matchup": next_matchup,
        "automatic_storylines": automatic_storylines,
        "organization": _organization_branding(),
        "pregame_diagnostics": {
            "broadcast_records": len(_broadcast_records()),
            "caledonia_school_found": bool(_caledonia_school()),
            "next_matchup_found": bool(next_matchup),
            "weather_location_resolved": bool(weather.get("location_resolution", {}).get("resolved")),
            "weather_game_periods": len(weather.get("game_forecast", [])) if isinstance(weather.get("game_forecast"), list) else 0,
        },
        "server_time": int(time.time()),
    }


def build_pregame_presentation_blueprint() -> Blueprint:
    """Build the pregame/halftime/delay overlay blueprint.

    The application factory owns registration now -- app.py appends this
    blueprint to APPLICATION_BLUEPRINTS before create_app(). `install_
    pregame_presentation()` below stays only for any caller outside that path.
    """

    csrn_app = _csrn_app()
    require_auth = getattr(csrn_app, "require_auth", lambda fn: fn)

    bp = Blueprint("pregame_presentation", __name__)

    @bp.get("/pregame-overlay")
    def overlay():
        path = _overlay_template()
        if not path.exists():
            return Response("Pregame overlay template missing.", status=500, mimetype="text/plain")
        return Response(path.read_text(encoding="utf-8"), mimetype="text/html")

    @bp.get("/api/pregame-presentation")
    def status():
        return jsonify(_payload())

    @bp.post("/api/pregame-presentation/settings")
    @require_auth
    def settings():
        state = _state()
        bid = str(state.get("broadcast_id", "") or "")
        if not bid:
            return jsonify({"error": "NO_BROADCAST", "message": "Load a broadcast before configuring the pregame presentation."}), 400
        incoming = request.get_json(silent=True) or {}
        transition = str(incoming.get("transition_mode", "manual")).lower()
        if transition not in {"manual", "scheduled", "fallback"}:
            transition = "manual"
        rotation = max(6, min(30, int(incoming.get("rotation_seconds", 10) or 10)))
        storylines = incoming.get("storylines", [])
        if not isinstance(storylines, list):
            storylines = []
        storylines = [str(x).strip()[:180] for x in storylines if str(x).strip()][:10]
        _save_settings(bid, {
            "transition_mode": transition,
            "rotation_seconds": rotation,
            "storylines": storylines,
        })
        return jsonify(_payload())

    @bp.post("/api/pregame-presentation/organization-logo")
    @require_auth
    def upload_organization_logo():
        upload = request.files.get("logo")
        if upload is None or not upload.filename:
            return jsonify({"error": "NO_LOGO", "message": "Choose a PNG, JPG, or WebP image."}), 400

        suffix = Path(upload.filename).suffix.lower()
        allowed = {".png", ".jpg", ".jpeg", ".webp"}
        if suffix not in allowed:
            return jsonify({"error": "INVALID_LOGO_TYPE", "message": "Organization logo must be PNG, JPG, or WebP."}), 400

        upload.stream.seek(0, 2)
        size = upload.stream.tell()
        upload.stream.seek(0)
        if size > 8 * 1024 * 1024:
            return jsonify({"error": "LOGO_TOO_LARGE", "message": "Organization logo must be 8 MB or smaller."}), 400

        static_dir = Path(__file__).resolve().parent / "static" / "organization"
        static_dir.mkdir(parents=True, exist_ok=True)
        target = static_dir / f"organization-logo{suffix}"
        for old in static_dir.glob("organization-logo.*"):
            try:
                if old != target:
                    old.unlink()
            except OSError:
                pass
        upload.save(target)
        return jsonify({
            "ok": True,
            "logo_path": f"/static/organization/{target.name}",
        })

    @bp.get("/api/pregame-presentation/<broadcast_id>/settings")
    @require_auth
    def broadcast_settings_get(broadcast_id: str):
        target = str(broadcast_id or "").strip()
        if not target:
            return jsonify({"error": "NO_BROADCAST_ID"}), 400
        return jsonify({"broadcast_id": target, "settings": _presentation_settings(target)})

    @bp.post("/api/pregame-presentation/<broadcast_id>/settings")
    @require_auth
    def broadcast_settings_save(broadcast_id: str):
        target = str(broadcast_id or "").strip()
        if not target:
            return jsonify({"error": "NO_BROADCAST_ID"}), 400
        incoming = request.get_json(silent=True) or {}
        updates: dict[str, Any] = {}
        if "storylines" in incoming:
            storylines = incoming.get("storylines", [])
            if not isinstance(storylines, list):
                storylines = []
            updates["storylines"] = [
                str(x).strip()[:180]
                for x in storylines
                if str(x).strip()
            ][:10]
        if "transition_mode" in incoming:
            transition = str(incoming.get("transition_mode", "manual")).lower()
            updates["transition_mode"] = transition if transition in {"manual", "scheduled", "fallback"} else "manual"
        if "rotation_seconds" in incoming:
            updates["rotation_seconds"] = max(6, min(30, int(incoming.get("rotation_seconds", 10) or 10)))
        settings = _save_settings(target, updates)
        return jsonify({"broadcast_id": target, "settings": settings})

    @bp.post("/api/pregame-presentation/mode")
    @require_auth
    def mode():
        state = _state()
        bid = str(state.get("broadcast_id", "") or "")
        if not bid:
            return jsonify({"error": "NO_BROADCAST", "message": "Load a broadcast first."}), 400
        incoming = request.get_json(silent=True) or {}
        value = str(incoming.get("mode", "auto")).lower()
        if value not in {"auto", "pregame"}:
            value = "auto"
        _save_settings(bid, {"mode": value})
        return jsonify(_payload())

    @bp.post("/api/pregame-presentation/delay")
    @require_auth
    def delay():
        state = _state()
        bid = str(state.get("broadcast_id", "") or "")
        if not bid:
            return jsonify({"error": "NO_BROADCAST", "message": "Load a broadcast first."}), 400
        incoming = request.get_json(silent=True) or {}
        delay_type = str(incoming.get("delay_type", "weather")).lower()
        if delay_type not in {"weather", "field", "officials", "team", "other"}:
            delay_type = "other"
        _save_settings(bid, {
            "mode": "delayed",
            "delay_type": delay_type,
            "delay_note": str(incoming.get("delay_note", "") or "").strip()[:220],
            "estimated_start": str(incoming.get("estimated_start", "") or "").strip()[:8],
        })
        return jsonify(_payload())

    @bp.post("/api/pregame-presentation/resume")
    @require_auth
    def resume():
        state = _state()
        bid = str(state.get("broadcast_id", "") or "")
        if not bid:
            return jsonify({"error": "NO_BROADCAST", "message": "Load a broadcast first."}), 400
        _save_settings(bid, {
            "mode": "auto",
            "delay_note": "",
            "estimated_start": "",
        })
        return jsonify(_payload())

    return bp


def install_pregame_presentation(app: Any) -> None:
    """Register the pregame blueprint on an already-constructed app.

    The factory path (app.py -> APPLICATION_BLUEPRINTS -> create_application)
    is the primary registration route; this remains for direct/legacy callers
    and is idempotent per app.
    """
    if getattr(app, "_csrn_pregame_presentation_installed", False):
        return
    if "pregame_presentation" not in app.blueprints:
        app.register_blueprint(build_pregame_presentation_blueprint())
    app._csrn_pregame_presentation_installed = True
