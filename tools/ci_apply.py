from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected integration anchor was not found in {path}: {old!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_all(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            return
        raise RuntimeError(f"Expected integration text was not found in {path}: {old!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    replace(
        "app.py",
        "from weather_service import VenueWeatherService\nfrom broadcast_lifecycle_service import BroadcastLifecycleService",
        "from weather_service import VenueWeatherService\nfrom operational_rehearsal_service import OperationalRehearsalService\nfrom broadcast_lifecycle_service import BroadcastLifecycleService",
    )
    replace(
        "app.py",
        "from routes.weather_routes import (\n    WeatherRoutesDependencies,\n    create_weather_blueprint,\n)\nfrom association_import_service import AssociationImportService",
        "from routes.weather_routes import (\n    WeatherRoutesDependencies,\n    create_weather_blueprint,\n)\nfrom routes.rehearsal_routes import (\n    RehearsalRoutesDependencies,\n    create_rehearsal_blueprint,\n)\nfrom association_import_service import AssociationImportService",
    )
    replace(
        "app.py",
        'WEATHER_STATE_FILE = DATA_DIR / "Weather" / "weather_state.json"\n',
        'WEATHER_STATE_FILE = DATA_DIR / "Weather" / "weather_state.json"\nREHEARSAL_STATE_FILE = DATA_DIR / "Rehearsals" / "rehearsals.json"\nRELEASE_MANIFEST_FILE = DATA_DIR / "Releases" / "game_day_release_manifest.json"\n',
    )
    replace(
        "app.py",
        '    "Version 1.13.0-alpha.6e — Venue Weather Monitoring"\n)\nRUNTIME_BUILD = "V1.13A6E-VENUE-WEATHER-MONITORING"',
        '    "Version 1.13.0-alpha.6f — Operational Rehearsal and Release Freeze"\n)\nRUNTIME_BUILD = "V1.13A6F-OPERATIONAL-REHEARSAL-RELEASE-FREEZE"',
    )
    replace(
        "app.py",
        'for name in ("Schools", "Venues", "Logos", "Sources", "Imports", "Broadcasts", "Rosters", "Personnel", "Assets", "Sponsors", "Statistics", "Logs", "Backups", "Settings"):',
        'for name in ("Schools", "Venues", "Logos", "Sources", "Imports", "Broadcasts", "Rosters", "Personnel", "Assets", "Sponsors", "Statistics", "Logs", "Backups", "Settings", "Rehearsals", "Releases"):',
    )

    rehearsal_block = '''WEATHER_ROUTES_BLUEPRINT = create_weather_blueprint(
    WeatherRoutesDependencies(
        require_auth=require_auth,
        get_weather_service=lambda: get_weather_service(),
    )
)
APPLICATION_BLUEPRINTS.append(WEATHER_ROUTES_BLUEPRINT)


def rehearsal_system_gates() -> dict[str, Any]:
    preflight = get_game_day_safety_service().preflight().data.get("preflight", {})
    commissioning = get_commissioning_service().report().data.get("report", {})
    recovery = get_recovery_service().status().data.get("recovery", {})
    caption = get_caption_service().status().data
    weather = get_weather_service().status().data.get("weather", {})

    channels = [
        item
        for item in caption.get("profile", {}).get("channels", [])
        if item.get("enabled")
    ]
    names = [str(item.get("speaker", "")).strip() for item in channels]
    placeholders = {
        f"Announcer {index}" for index in range(1, 13)
    }
    captions_ready = (
        len(names) >= 2
        and len({name.casefold() for name in names if name}) == len(names)
        and all(name and name not in placeholders for name in names)
    )

    venue = weather.get("venue", {}) if isinstance(weather, dict) else {}
    latitude = venue.get("latitude") if isinstance(venue, dict) else None
    longitude = venue.get("longitude") if isinstance(venue, dict) else None
    weather_ready = bool(
        latitude is not None
        and longitude is not None
        and int(weather.get("last_success_at", 0) or 0) > 0
        and not weather.get("stale", True)
    )

    recovery_ready = bool(
        not recovery.get("unclean_shutdown")
        and not recovery.get("live_broadcast_active", True)
    )

    return {
        "game_day_preflight": {
            "label": "Game-day preflight",
            "ready": bool(preflight.get("ready", False)),
            "note": "All required storage, state, and backup checks pass."
            if preflight.get("ready")
            else "Game-day preflight has a required failure.",
        },
        "hardware_obs_commissioning": {
            "label": "Hardware and OBS commissioning",
            "ready": bool(commissioning.get("ready", False)),
            "note": "P4next, OBS, recording, and network commissioning is complete."
            if commissioning.get("ready")
            else "Hardware or OBS commissioning remains incomplete.",
        },
        "recovery_state": {
            "label": "Recovery and shutdown state",
            "ready": recovery_ready,
            "note": "No unclean shutdown is unresolved and no broadcast is live."
            if recovery_ready
            else "Resolve the unclean-shutdown marker or stop the live broadcast.",
        },
        "caption_assignments": {
            "label": "Customer-assigned caption channels",
            "ready": captions_ready,
            "note": "At least two unique customer-assigned speakers are configured."
            if captions_ready
            else "Assign at least two unique speaker names; neutral Announcer placeholders do not satisfy release readiness.",
        },
        "weather_monitoring": {
            "label": "Venue weather monitoring",
            "ready": weather_ready,
            "note": "The active venue has coordinates and a fresh successful weather update."
            if weather_ready
            else "Verify venue coordinates and complete a non-stale weather refresh.",
        },
    }


REHEARSAL_SERVICE: OperationalRehearsalService | None = None


def get_rehearsal_service() -> OperationalRehearsalService:
    global REHEARSAL_SERVICE
    if REHEARSAL_SERVICE is None:
        REHEARSAL_SERVICE = OperationalRehearsalService(
            state_file=REHEARSAL_STATE_FILE,
            release_manifest_file=RELEASE_MANIFEST_FILE,
            version_file=VERSION_FILE,
            load_system_gates=rehearsal_system_gates,
            create_snapshot=lambda **kwargs: get_game_day_safety_service().create_snapshot(**kwargs),
            register_known_good=lambda **kwargs: get_recovery_service().register_known_good(**kwargs),
            clock=time.time,
        )
    return REHEARSAL_SERVICE


REHEARSAL_ROUTES_BLUEPRINT = create_rehearsal_blueprint(
    RehearsalRoutesDependencies(
        require_auth=require_auth,
        get_rehearsal_service=lambda: get_rehearsal_service(),
    )
)
APPLICATION_BLUEPRINTS.append(REHEARSAL_ROUTES_BLUEPRINT)
'''
    replace(
        "app.py",
        '''WEATHER_ROUTES_BLUEPRINT = create_weather_blueprint(
    WeatherRoutesDependencies(
        require_auth=require_auth,
        get_weather_service=lambda: get_weather_service(),
    )
)
APPLICATION_BLUEPRINTS.append(WEATHER_ROUTES_BLUEPRINT)
''',
        rehearsal_block,
    )

    replace(
        "phase5_architecture.py",
        '    "recovery_routes",\n',
        '    "recovery_routes",\n    "rehearsal_routes",\n',
    )
    replace_all(
        "tests/test_core_repository_runtime.py",
        "Version 1.13.0-alpha.6d — Channel-Based Captioning",
        "Version 1.13.0-alpha.6f — Operational Rehearsal and Release Freeze",
    )
    replace_all(
        "tests/test_core_repository_runtime.py",
        "V1.13A6D-CHANNEL-BASED-CAPTIONING",
        "V1.13A6F-OPERATIONAL-REHEARSAL-RELEASE-FREEZE",
    )
    (ROOT / "VERSION.txt").write_text("1.13.0-alpha.6f\n", encoding="utf-8")
    print("Phase 6.6 operational rehearsal and release-freeze integration applied.")


if __name__ == "__main__":
    main()
