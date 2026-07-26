from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected integration marker was not found in {path}: {old!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_once(
        "app.py",
        "from caption_service import CaptionService\n",
        "from caption_service import CaptionService\nfrom weather_service import VenueWeatherService\n",
    )
    replace_once(
        "app.py",
        "from routes.caption_routes import (\n    CaptionRoutesDependencies,\n    create_caption_blueprint,\n)\n",
        "from routes.caption_routes import (\n    CaptionRoutesDependencies,\n    create_caption_blueprint,\n)\nfrom routes.weather_routes import (\n    WeatherRoutesDependencies,\n    create_weather_blueprint,\n)\n",
    )
    replace_once(
        "app.py",
        "CAPTION_TRANSCRIPTS_DIR = DATA_DIR / \"Captions\" / \"Transcripts\"\n",
        "CAPTION_TRANSCRIPTS_DIR = DATA_DIR / \"Captions\" / \"Transcripts\"\nWEATHER_STATE_FILE = DATA_DIR / \"Weather\" / \"weather_state.json\"\n",
    )
    replace_once(
        "app.py",
        'RUNTIME_VERSION = (\n    "Version 1.13.0-alpha.6d — Channel-Based Captioning"\n)\nRUNTIME_BUILD = "V1.13A6D-CHANNEL-BASED-CAPTIONING"\n',
        'RUNTIME_VERSION = (\n    "Version 1.13.0-alpha.6e — Venue Weather Monitoring"\n)\nRUNTIME_BUILD = "V1.13A6E-VENUE-WEATHER-MONITORING"\n',
    )
    replace_once(
        "app.py",
        '    "weather": {\n        "use_home_venue_address": True,\n        "default_alert_radius_miles": 25,\n    },\n',
        '    "weather": {\n        "use_home_venue_address": True,\n        "default_alert_radius_miles": 25,\n        "refresh_seconds": 60,\n        "stale_after_seconds": 180,\n        "user_agent": "CSRN-Production-Suite/1.13 (operator-configurable)",\n    },\n',
    )
    replace_once(
        "app.py",
        "CAPTION_ROUTES_BLUEPRINT = create_caption_blueprint(\n    CaptionRoutesDependencies(\n        require_auth=require_auth,\n        get_caption_service=lambda: get_caption_service(),\n    )\n)\nAPPLICATION_BLUEPRINTS.append(CAPTION_ROUTES_BLUEPRINT)\n",
        "CAPTION_ROUTES_BLUEPRINT = create_caption_blueprint(\n    CaptionRoutesDependencies(\n        require_auth=require_auth,\n        get_caption_service=lambda: get_caption_service(),\n    )\n)\nAPPLICATION_BLUEPRINTS.append(CAPTION_ROUTES_BLUEPRINT)\n\n\nWEATHER_SERVICE: VenueWeatherService | None = None\n\n\ndef get_weather_service() -> VenueWeatherService:\n    global WEATHER_SERVICE\n    if WEATHER_SERVICE is None:\n        WEATHER_SERVICE = VenueWeatherService(\n            state_file=WEATHER_STATE_FILE,\n            load_state=load_state,\n            load_config=load_config,\n            load_venues=load_venues,\n            save_venues=save_venues,\n            load_schools=load_schools,\n            clock=time.time,\n        )\n    return WEATHER_SERVICE\n\n\nWEATHER_ROUTES_BLUEPRINT = create_weather_blueprint(\n    WeatherRoutesDependencies(\n        require_auth=require_auth,\n        get_weather_service=lambda: get_weather_service(),\n    )\n)\nAPPLICATION_BLUEPRINTS.append(WEATHER_ROUTES_BLUEPRINT)\n",
    )
    replace_once(
        "phase5_architecture.py",
        '    "venue_routes",\n',
        '    "venue_routes",\n    "weather_routes",\n',
    )
    replace_once(
        "phase5_architecture.py",
        '    "system_routes.get_state",\n',
        '    "system_routes.get_state",\n    "weather_routes.weather_overlay",\n    "weather_routes.weather_overlay_state",\n',
    )
    (ROOT / "VERSION.txt").write_text("1.13.0-alpha.6e\n", encoding="utf-8")
    print("Phase 6.5 venue weather integration applied.")


if __name__ == "__main__":
    main()
