from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from flask import Flask

from application_factory import (
    build_route_manifest,
    direct_route_endpoints,
    duplicate_route_methods,
)


EXPECTED_BLUEPRINTS = {
    "asset_routes",
    "association_routes",
    "broadcast_lifecycle_routes",
    "broadcast_package_routes",
    "broadcast_routes",
    "caption_routes",
    "coin_toss_routes",
    "commissioning_routes",
    "deployment_routes",
    "graphics_routes",
    "game_day_safety_routes",
    "live_game_routes",
    "logo_routes",
    "mhsaa_division_routes",
    "obs_routes",
    "page_routes",
    "personnel_routes",
    # The halftime/pregame/delay overlay (pregame_universal_overlay.html) --
    # added after this allowlist was last updated.
    "pregame_presentation",
    "recovery_routes",
    "recap_routes",
    "rehearsal_routes",
    "roster_routes",
    "school_routes",
    "security_upgrade_routes",
    "social_routes",
    "sponsor_routes",
    "support_routes",
    "system_routes",
    "theme_routes",
    "venue_routes",
    "weather_routes",
}

PUBLIC_ENDPOINTS = {
    "asset_routes.asset_file",
    # Sponsor ad video served to the overlay's own OBS browser source, same
    # public-media pattern as asset_file/sponsor_logo_file/roster_headshot_file.
    "asset_routes.sponsor_ad_file",
    "caption_routes.caption_overlay",
    "caption_routes.caption_overlay_state",
    "live_game_routes.statistics_overlay_state",
    "logo_routes.school_logo_file",
    "page_routes.control_panel",
    "page_routes.overlay",
    "personnel_routes.personnel_headshot_file",
    # The halftime/pregame/delay overlay: OBS has no operator login session,
    # same reasoning as every other overlay-facing endpoint in this set.
    "pregame_presentation.overlay",
    "pregame_presentation.status",
    "security_upgrade_routes.login",
    "security_upgrade_routes.logout",
    "security_upgrade_routes.run_upgrade_migration",
    "security_upgrade_routes.security_status",
    "security_upgrade_routes.setup_pin",
    "security_upgrade_routes.upgrade_candidate",
    "security_upgrade_routes.upgrade_status",
    "social_routes.complete_facebook_connection",
    "sponsor_routes.sponsor_logo_file",
    "support_routes.roster_headshot_file",
    "system_routes.get_state",
    "system_routes.get_runtime_state",
    # GET /api/health: dependency-free liveness probe for
    # CSRN_GAME_DAY_LAUNCHER.ps1, which has no operator session and must be
    # able to reach it even when the state write path is stuck.
    "system_routes.get_health",
    # POST /api/overlay-health: the overlay itself (running unauthenticated
    # in OBS) self-reports health/status back to the server; there is no
    # operator session to authenticate it with.
    "system_routes.report_overlay_health",
    "theme_routes.current_theme_css",
    "theme_routes.public_theme_state",
    "weather_routes.weather_overlay",
    "weather_routes.weather_overlay_state",
}


def audit_phase5_architecture(
    application: Flask,
    app_source: Path,
) -> dict[str, Any]:
    """Audit the completed Phase 5 route and factory architecture."""

    errors: list[str] = []
    manifest = build_route_manifest(application)
    non_static = tuple(entry for entry in manifest if entry.endpoint != "static")

    actual_blueprints = set(application.blueprints)
    missing = sorted(EXPECTED_BLUEPRINTS - actual_blueprints)
    unexpected = sorted(actual_blueprints - EXPECTED_BLUEPRINTS)
    if missing:
        errors.append("Missing Blueprints: " + ", ".join(missing))
    if unexpected:
        errors.append("Unexpected Blueprints: " + ", ".join(unexpected))

    duplicates = duplicate_route_methods(manifest)
    if duplicates:
        errors.append(f"Duplicate route methods: {duplicates!r}")

    direct = direct_route_endpoints(manifest)
    if direct:
        errors.append("Direct application endpoints: " + ", ".join(direct))

    actual_public = {
        entry.endpoint for entry in non_static if not entry.auth_required
    }
    missing_public = sorted(PUBLIC_ENDPOINTS - actual_public)
    unexpected_public = sorted(actual_public - PUBLIC_ENDPOINTS)
    if missing_public:
        errors.append(
            "Expected public endpoints marked authenticated: "
            + ", ".join(missing_public)
        )
    if unexpected_public:
        errors.append(
            "Unexpected public endpoints: " + ", ".join(unexpected_public)
        )

    source = app_source.read_text(encoding="utf-8")
    decorators = re.findall(
        r"(?m)^\s*@app\.(?:get|post|put|delete|patch|route)\(",
        source,
    )
    if decorators:
        errors.append(f"Direct @app route decorators remain: {len(decorators)}")
    if "app.register_blueprint(" in source:
        errors.append("Blueprint registration remains distributed in app.py")
    if "app = Flask(__name__)" in source:
        errors.append("Legacy module-level Flask construction remains")
    if "def create_app(" not in source or "app = create_app()" not in source:
        errors.append("Application factory entry points are missing")

    return {
        "ok": not errors,
        "errors": errors,
        "blueprints": sorted(actual_blueprints),
        "routes": len(non_static),
        "authenticated_routes": sum(
            1 for entry in non_static if entry.auth_required
        ),
        "public_routes": sum(
            1 for entry in non_static if not entry.auth_required
        ),
        "app_lines": len(source.splitlines()),
    }
