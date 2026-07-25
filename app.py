from __future__ import annotations

import copy
import json
import hashlib
import os
import re
import secrets
import time
import shutil
from functools import wraps
from pathlib import Path
from datetime import date
from threading import Lock
from typing import Any, Callable
from urllib.parse import urlparse, quote

from flask import Flask, jsonify, render_template, request, session, send_from_directory, Response
from werkzeug.security import check_password_hash, generate_password_hash
from PIL import Image, ImageChops
from obs_client import (
    OBSConnectionError,
    set_program_visual_mode,
    set_scorebug_visibility,
    validate_obs_read_only,
)
from upgrade_manager import inspect_candidate, migrate
from persistence_engine import JsonPersistenceEngine
from core_repositories import ConfigurationRepository, StateRepository, SecurityRepository
from security_service import SecurityService
from broadcast_package_service import BroadcastPackageService
from school_service import SchoolService
from roster_service import RosterService
from sponsor_service import SponsorService
from venue_service import VenueService
from broadcast_service import BroadcastService
from personnel_service import PersonnelService
from asset_service import AssetService
from graphics_service import GraphicsService
from logo_service import LogoService
from obs_service import OBSService
from configuration_service import ConfigurationService
from state_service import StateService
from diagnostics_service import DiagnosticsService
from upgrade_service import UpgradeService
from event_service import EventService
from rules_service import RulesService
from statistics_service import StatisticsService
from game_operations_service import GameOperationsService
from support_media_service import SupportMediaService
from broadcast_lifecycle_service import BroadcastLifecycleService
from routes.system_routes import (
    SystemRoutesDependencies,
    create_system_blueprint,
)
from routes.security_upgrade_routes import (
    SecurityUpgradeRoutesDependencies,
    create_security_upgrade_blueprint,
)
from routes.school_routes import (
    SchoolRoutesDependencies,
    create_school_blueprint,
)
from routes.association_routes import (
    AssociationRoutesDependencies,
    create_association_blueprint,
)
from association_import_service import AssociationImportService
from association_supplement_service import AssociationSupplementService
from association_profile_service import AssociationProfileService
from association_source_service import AssociationSourceService
from association_workflow_service import AssociationWorkflowService
from school_repository import SchoolRepository
from roster_repository import RosterRepository
from sponsor_repository import SponsorRepository
from venue_repository import VenueRepository
from broadcast_repository import BroadcastRepository

# Phase 3 repository boundaries remain integrated below.

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "state.json"
SECURITY_FILE = BASE_DIR / "security.json"
DATA_DIR = BASE_DIR / "Data"
CONFIG_FILE = DATA_DIR / "Settings" / "config.json"
SCHOOLS_FILE = DATA_DIR / "Schools" / "schools.json"
BROADCASTERS_FILE = DATA_DIR / "Settings" / "broadcasters.json"
ROSTERS_FILE = DATA_DIR / "Rosters" / "rosters.json"
HEADSHOTS_DIR = DATA_DIR / "Rosters" / "Headshots"
PERSONNEL_HEADSHOTS_DIR = DATA_DIR / "Personnel" / "Headshots"
ASSETS_FILE = DATA_DIR / "Assets" / "assets.json"
ASSET_UPLOAD_DIR = DATA_DIR / "Assets" / "Files"
SPONSORS_FILE = DATA_DIR / "Sponsors" / "sponsors.json"
SPONSOR_UPLOAD_DIR = DATA_DIR / "Sponsors" / "Logos"
VENUES_FILE = DATA_DIR / "Venues" / "venues.json"
LOGOS_FILE = DATA_DIR / "Logos" / "logos.json"
IMPORTS_DIR = DATA_DIR / "Imports"
ASSOCIATION_PROFILES_DIR = IMPORTS_DIR / "Profiles"
MHSAA_5A_FILE = IMPORTS_DIR / "mhsaa_2025_27_football_5a.json"
MHSAA_5A_ENRICHMENT_FILE = IMPORTS_DIR / "mhsaa_5a_enrichment.json"
MHSAA_5A_BRANDING_FILE = IMPORTS_DIR / "mhsaa_5a_branding.json"
MHSAA_5A_PROFILE_FILE = (
    IMPORTS_DIR
    / "Profiles"
    / "mhsaa_football_5a_2025_27.json"
)
BROADCAST_INDEX_FILE = DATA_DIR / "Broadcasts" / "broadcasts.json"
PACKAGES_FILE = DATA_DIR / "Packages" / "broadcast_packages.json"
BUILD_JOURNAL_FILE = DATA_DIR / "Logs" / "build_journal.json"
VERSION_FILE = BASE_DIR / "VERSION.txt"

app = Flask(__name__)
lock = Lock()
obs_status_lock = Lock()
upgrade_lock = Lock()
roster_io_lock = Lock()
_roster_recovery_checked = False
_roster_cache: list[dict[str, Any]] | None = None
_roster_cache_mtime_ns: int | None = None
for _path in (SPONSORS_FILE.parent, SPONSOR_UPLOAD_DIR, PACKAGES_FILE.parent):
    _path.mkdir(parents=True, exist_ok=True)
last_upgrade_report: dict[str, Any] = {
    "status": "NOT_RUN",
    "source_build": "",
    "backup_path": "",
    "copied_files": 0,
    "merged_config": False,
    "security_migrated": False,
    "errors": [],
}
last_obs_status: dict[str, Any] = {
    "reachable": False,
    "authenticated": False,
    "error": "OBS has not been tested in this session.",
    "checked_at": 0,
}

DEFAULT_STATE: dict[str, Any] = {
    "broadcast_created": False,
    "sport": "Football",
    "level": "Varsity",
    "division": "Boys",
    "home_team": "Caledonia",
    "visitor_team": "Visitor",
    "home_school_id": "",
    "visitor_school_id": "",
    "home_identity": {},
    "visitor_identity": {},
    "venue": "Caledonia High School",
    "date": "",
    "scheduled_start": "",
    "home_score": 0,
    "visitor_score": 0,
    "quarter": "1",
    "down": "1st",
    "distance": "Off",
    "clock_visible": False,
    "clock_seconds": 720,
    "clock_running": False,
    "clock_started_at": 0,
    "home_direction": "right",
    "visitor_direction": "left",
    "possession": "home",
    "scorebug_visible": False,
    "visual_mode": "graphic",
    "broadcast_phase": "pregame",
    "crew": {"play_by_play": "", "color_analyst": "", "sideline_reporter": "", "statistician": "", "producer": ""},
    "broadcast_id": "",
    "season": "",
    "week": "1",
    "classification": "",
    "venue_id": "",
    "status": "planned",
    "history": [],
    "events": [],
    "plays": [],
    "last_event": {},
    "next_play_number": 1,
    "ball_spot": "",
    "correction_log": [],
    "game_data_authority": "broadcaster",
    "statistician_enabled": False,
    "ticker_visible": True,
    "ticker_speed": "slow",
    "ticker_pause": 2,
    "production_type": "game",
    "lower_third": {
        "visible": False,
        "eyebrow": "CSRN",
        "headline": "",
        "secondary": "",
        "footer": "",
        "logo_source": "csrn",
        "accent_source": "csrn",
        "custom_accent": "#C9203B",
        "duration": 0,
        "expires_at": 0,
        "updated_at": 0
    },
    "personnel_graphic": {
        "visible": False, "personnel_id": "", "graphic_type": "coach_id", "full_name": "", "display_name": "",
        "title": "", "role": "", "organization": "", "headshot": "", "logo": "", "accent": "#C9203B",
        "eyebrow": "COACH", "sponsor_id": "", "sponsor_lead_in": "", "sponsor_name": "", "sponsor_logo": "", "duration": 0,
        "expires_at": 0, "updated_at": 0
    },
    "player_graphic": {
        "visible": False,
        "graphic_type": "player_id",
        "roster_id": "",
        "player_id": "",
        "school_id": "",
        "full_name": "",
        "display_name": "",
        "number": "",
        "position": "",
        "secondary_position": "",
        "grade": "",
        "height": "",
        "weight": "",
        "headshot": "",
        "team_logo": "",
        "team_name": "",
        "team_color": "#C9203B",
        "play_detail": "",
        "eyebrow": "PLAYER PROFILE",
        "sponsor_id": "",
        "sponsor_lead_in": "",
        "sponsor_name": "",
        "sponsor_logo": "",
        "duration": 0,
        "expires_at": 0,
        "updated_at": 0
    },
}

DEFAULT_SECURITY: dict[str, Any] = {
    "pin_hash": "",
    "secret_key": secrets.token_hex(32),
    "failed_attempts": 0,
    "locked_until": 0,
}


RUNTIME_VERSION = (
    "Version 1.13.0-alpha.5c — School and Association Routes"
)
RUNTIME_BUILD = "V1.13A5C-SCHOOL-AND-ASSOCIATION-ROUTES"


DEFAULT_CONFIG: dict[str, Any] = {
    "organization": {
        "name": "Caledonia Sports Radio Network",
        "short_name": "CSRN",
        "logo_path": "static/csrn-logo.png",
        "primary_color": "#C9203B",
        "secondary_color": "#000000",
        "accent_color": "#FFFFFF",
    },
    "broadcast_defaults": {
        "venue": "Caledonia High School",
        "sport": "Football",
        "timezone": "America/Chicago",
        "theme": "CSRN Dark",
        "home_school_id": "caledonia",
        "visual_mode": "graphic",
    },
    "folders": {
        "graphics": "Graphics",
        "assets": "Assets",
        "obs": "OBS",
        "broadcast_archive": "Data/Broadcasts",
        "exports": "Exports",
        "backups": "Data/Backups",
    },
    "obs": {
        "websocket_enabled": False,
        "controlled_commands": False,
        "host": "127.0.0.1",
        "port": 4455,
        "password": "",
        "scene_collection": "CSRN Master",
        "profile": "CSRN Production",
        "required_scene": "10.01 - FOOTBALL SCOREBUG",
        "browser_source": "BRWSR - Football Scorebug",
        "program_visual_scene": "10.02 - PROGRAM VISUAL",
        "graphic_source": "IMG - Broadcast Background",
        "camera_source": "CAM - Primary Camera",
    },
    "weather": {
        "use_home_venue_address": True,
        "default_alert_radius_miles": 25,
    },
    "social": {
        "facebook": "",
        "youtube": "",
        "x": "",
        "website": "",
    },
    "application": {
        "version": RUNTIME_VERSION,
        "build": RUNTIME_BUILD,
        "rules_edition": "NFHS",
        "automatic_backup": True,
        "auto_save": True,
        "operator_timeout_hours": 12,
        "upgrade_manager_enabled": True,
        "last_migration_status": "",
    },
}

SESSION_SECONDS = 12 * 60 * 60
MAX_ATTEMPTS = 3
LOCKOUT_SECONDS = 60


def ensure_data_architecture() -> None:
    for name in ("Schools", "Venues", "Logos", "Sources", "Imports", "Broadcasts", "Rosters", "Personnel", "Assets", "Sponsors", "Statistics", "Logs", "Backups", "Settings"):
        (DATA_DIR / name).mkdir(parents=True, exist_ok=True)
    ASSOCIATION_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    HEADSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    PERSONNEL_HEADSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    SPONSOR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

CORE_BACKUP_DIR = DATA_DIR / "Backups" / "Core"
CORE_QUARANTINE_DIR = DATA_DIR / "Backups" / "Quarantine"
CORE_PERSISTENCE = JsonPersistenceEngine(CORE_BACKUP_DIR, CORE_QUARANTINE_DIR)
CONFIG_REPOSITORY = ConfigurationRepository(
    CORE_PERSISTENCE,
    CONFIG_FILE,
    DEFAULT_CONFIG,
    runtime_identity={
    "version": RUNTIME_VERSION,
    "build": RUNTIME_BUILD,
},
)
STATE_REPOSITORY = StateRepository(CORE_PERSISTENCE, STATE_FILE, DEFAULT_STATE)
SECURITY_REPOSITORY = SecurityRepository(CORE_PERSISTENCE, SECURITY_FILE, DEFAULT_SECURITY)
SECURITY_SERVICE = SecurityService(
    SECURITY_REPOSITORY,
    max_attempts=MAX_ATTEMPTS,
    lockout_seconds=LOCKOUT_SECONDS,
)


def load_config() -> dict[str, Any]:
    ensure_data_architecture()
    return CONFIG_REPOSITORY.load()


def save_config(config: dict[str, Any]) -> None:
    ensure_data_architecture()
    CONFIG_REPOSITORY.save(config)


def update_config_values(
    patch: dict[str, Any],
) -> dict[str, Any]:
    ensure_data_architecture()
    return CONFIG_REPOSITORY.update(patch)


CONFIGURATION_SERVICE: ConfigurationService | None = None


def get_configuration_service() -> ConfigurationService:
    global CONFIGURATION_SERVICE
    if CONFIGURATION_SERVICE is None:
        CONFIGURATION_SERVICE = ConfigurationService(
            load_config=load_config,
            save_config=save_config,
            runtime_version=RUNTIME_VERSION,
            runtime_build=RUNTIME_BUILD,
        )
    return CONFIGURATION_SERVICE


def application_identity() -> dict[str, str]:
    """Return package identity from VERSION.txt with safe config fallbacks."""
    cfg = load_config()
    application = cfg.get("application", {})
    version = str(
        application.get("version") or RUNTIME_VERSION
    )
    build = str(
        application.get("build") or RUNTIME_BUILD
    )
    product = "CSRN Production Suite"
    if VERSION_FILE.exists():
        try:
            lines = [line.strip() for line in VERSION_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                product = lines[0]
            version_line = next((line for line in lines if line.lower().startswith("version ")), "")
            feature_line = next((line for line in lines if line.lower().endswith("v1") or "library" in line.lower()), "")
            build_line = next((line for line in lines if line.lower().startswith("build ")), "")
            if version_line:
                version = version_line
                if feature_line and feature_line != version_line:
                    version = f"{version_line} — {feature_line}"
            if build_line:
                build = build_line.removeprefix("Build ").strip()
        except OSError:
            pass
    return {"product": product, "version": version, "build": build}


def load_packages() -> list[dict[str, Any]]:
    data = load_json(PACKAGES_FILE, {"packages": []})
    items = data if isinstance(data, list) else data.get("packages", [])
    return [x for x in items if isinstance(x, dict)]

def save_packages(items: list[dict[str, Any]]) -> None:
    PACKAGES_FILE.parent.mkdir(parents=True, exist_ok=True)
    PACKAGES_FILE.write_text(json.dumps({"packages": items}, indent=2), encoding="utf-8")

BROADCAST_PACKAGE_SERVICE: BroadcastPackageService | None = None


def get_broadcast_package_service() -> BroadcastPackageService:
    global BROADCAST_PACKAGE_SERVICE

    if BROADCAST_PACKAGE_SERVICE is None:
        BROADCAST_PACKAGE_SERVICE = BroadcastPackageService(
            load_packages=load_packages,
            save_packages=save_packages,
            load_broadcasts=load_broadcasts,
            load_rosters=load_rosters,
            load_personnel=load_broadcasters,
            load_sponsors=load_sponsors,
            load_config=load_config,
            sponsor_contract_state=sponsor_contract_state,
            load_state=load_state,
            save_state=save_state,
        )

    return BROADCAST_PACKAGE_SERVICE


def package_health(package: dict[str, Any]) -> dict[str, Any]:
    return get_broadcast_package_service().health(package)


def package_record(
    data: dict[str, Any],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return get_broadcast_package_service().record(data, existing)


DIAGNOSTICS_SERVICE: DiagnosticsService | None = None


def get_diagnostics_service() -> DiagnosticsService:
    global DIAGNOSTICS_SERVICE
    if DIAGNOSTICS_SERVICE is None:
        DIAGNOSTICS_SERVICE = DiagnosticsService(
            base_dir=BASE_DIR,
            data_dir=DATA_DIR,
            config_file=CONFIG_FILE,
            schools_file=SCHOOLS_FILE,
            broadcasters_file=BROADCASTERS_FILE,
            rosters_file=ROSTERS_FILE,
            venues_file=VENUES_FILE,
            logos_file=LOGOS_FILE,
            packages_file=PACKAGES_FILE,
            assets_file=ASSETS_FILE,
            sponsors_file=SPONSORS_FILE,
            load_config=load_config,
            load_state=load_state,
            public_state=public_state,
            load_obs_status=load_obs_status,
            authenticated=authenticated,
            migrate_venues=migrate_venue_names,
        )
    return DIAGNOSTICS_SERVICE


def diagnostic_status() -> dict[str, Any]:
    return get_diagnostics_service().diagnostics().data["diagnostics"]


def normalize_school_id(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "school"

def next_csrn_school_id(state: str, classification: str, schools: list[dict[str, Any]] | None = None) -> str:
    state_code = (state or "MS").strip().upper()
    class_code = str(classification or "").strip().upper().replace("CLASS", "").strip()
    prefix = f"{state_code}{class_code}-" if class_code else f"{state_code}-"
    existing = schools if schools is not None else load_schools()
    used: set[int] = set()
    for school in existing:
        value = str(school.get("csrn_id", "")).upper()
        if value.startswith(prefix):
            try:
                used.add(int(value.rsplit("-", 1)[1]))
            except (ValueError, IndexError):
                pass
    number = 1
    while number in used:
        number += 1
    return f"{prefix}{number:03d}"



def reconcile_5a_csrn_ids(schools: list[dict[str, Any]]) -> bool:
    """Reserve MS5A-001 for Caledonia and MS5A-002 for New Hope.

    Remaining 5A schools are assigned stable alphabetical IDs beginning at 003.
    This migration is intentionally limited to the early 5A pilot database.
    """
    five_a = [s for s in schools if str(s.get("state", "MS")).upper() == "MS" and str(s.get("classification", "")).upper() == "5A"]
    if not five_a:
        return False
    def key_name(s):
        return str(s.get("official_name") or s.get("broadcast_name") or "").casefold()
    cal = next((s for s in five_a if "caledonia" in key_name(s)), None)
    nh = next((s for s in five_a if key_name(s).startswith("new hope") or "new hope" in key_name(s)), None)
    ordered=[]
    if cal: ordered.append(cal)
    if nh and nh is not cal: ordered.append(nh)
    ordered.extend(sorted([s for s in five_a if s not in ordered], key=key_name))
    changed=False
    for number, school in enumerate(ordered, start=1):
        expected=f"MS5A-{number:03d}"
        if school.get("csrn_id") != expected:
            school["csrn_id"] = expected
            changed=True
    return changed

def ensure_school_schema(school: dict[str, Any], schools: list[dict[str, Any]]) -> dict[str, Any]:
    school.setdefault("short_name", school.get("broadcast_name", ""))
    school.setdefault("city", "")
    school.setdefault("county", "")
    school.setdefault("active", True)
    school.setdefault("preferred_scorebug_name", school.get("broadcast_name", ""))
    school.setdefault("pronunciation_guide", "")
    school.setdefault("venue_id", "")
    school.setdefault("csrn_id", "")
    if not school["csrn_id"] and school.get("state") and school.get("classification"):
        school["csrn_id"] = next_csrn_school_id(str(school.get("state")), str(school.get("classification")), schools)
    metadata = school.setdefault("logo_metadata", {})
    metadata.setdefault("source_url", "")
    metadata.setdefault("transparent_background_status", "unknown")
    metadata.setdefault("approval_status", school.get("logo_status", "candidate"))
    metadata["shape_standard"] = "round"
    metadata["master_canvas"] = "1024x1024-round"
    metadata["safe_area"] = "circle-90-percent"
    metadata["scorebug_derivative"] = "256x256-round"
    return school

SCHOOL_REPOSITORY = SchoolRepository(
    CORE_PERSISTENCE,
    SCHOOLS_FILE,
    school_normalizer=ensure_school_schema,
    collection_normalizer=reconcile_5a_csrn_ids,
)

def load_schools() -> list[dict[str, Any]]:
    ensure_data_architecture()
    return SCHOOL_REPOSITORY.load()

def save_schools(schools: list[dict[str, Any]]) -> None:
    ensure_data_architecture()
    SCHOOL_REPOSITORY.save(schools)


SCHOOL_SERVICE: SchoolService | None = None


def get_school_service() -> SchoolService:
    global SCHOOL_SERVICE

    if SCHOOL_SERVICE is None:
        SCHOOL_SERVICE = SchoolService(
            load_schools=load_schools,
            save_schools=save_schools,
            load_logos=load_logos,
            save_logos=save_logos,
        )

    return SCHOOL_SERVICE


VENUE_REPOSITORY = VenueRepository(
    CORE_PERSISTENCE,
    VENUES_FILE,
)


def load_venues() -> list[dict[str, Any]]:
    ensure_data_architecture()
    return VENUE_REPOSITORY.load()


def save_venues(items: list[dict[str, Any]]) -> None:
    ensure_data_architecture()
    VENUE_REPOSITORY.save(items)


VENUE_SERVICE: VenueService | None = None


def get_venue_service() -> VenueService:
    global VENUE_SERVICE

    if VENUE_SERVICE is None:
        VENUE_SERVICE = VenueService(
            load_venues=load_venues,
            save_venues=save_venues,
            load_schools=load_schools,
            load_broadcasts=load_broadcasts,
        )

    return VENUE_SERVICE


ASSOCIATION_IMPORT_SERVICE: AssociationImportService | None = None


def get_association_import_service() -> AssociationImportService:
    global ASSOCIATION_IMPORT_SERVICE

    if ASSOCIATION_IMPORT_SERVICE is None:
        ASSOCIATION_IMPORT_SERVICE = AssociationImportService(
            school_service=get_school_service(),
            load_schools=load_schools,
            load_venues=load_venues,
            save_venues=save_venues,
        )

    return ASSOCIATION_IMPORT_SERVICE


ASSOCIATION_SUPPLEMENT_SERVICE: AssociationSupplementService | None = None


def get_association_supplement_service() -> AssociationSupplementService:
    global ASSOCIATION_SUPPLEMENT_SERVICE

    if ASSOCIATION_SUPPLEMENT_SERVICE is None:
        ASSOCIATION_SUPPLEMENT_SERVICE = AssociationSupplementService(
            load_schools=load_schools,
            save_schools=save_schools,
            load_venues=load_venues,
            save_venues=save_venues,
        )

    return ASSOCIATION_SUPPLEMENT_SERVICE


ASSOCIATION_PROFILE_SERVICE: AssociationProfileService | None = None


def get_association_profile_service() -> AssociationProfileService:
    global ASSOCIATION_PROFILE_SERVICE

    if ASSOCIATION_PROFILE_SERVICE is None:
        ASSOCIATION_PROFILE_SERVICE = AssociationProfileService(
            ASSOCIATION_PROFILES_DIR,
            protected_ids={"mhsaa-football-5a-2025-27"},
        )

    return ASSOCIATION_PROFILE_SERVICE


ASSOCIATION_SOURCE_SERVICE: AssociationSourceService | None = None


def get_association_source_service() -> AssociationSourceService:
    global ASSOCIATION_SOURCE_SERVICE

    if ASSOCIATION_SOURCE_SERVICE is None:
        ASSOCIATION_SOURCE_SERVICE = AssociationSourceService()

    return ASSOCIATION_SOURCE_SERVICE


ASSOCIATION_WORKFLOW_SERVICE: AssociationWorkflowService | None = None


def get_association_workflow_service() -> AssociationWorkflowService:
    global ASSOCIATION_WORKFLOW_SERVICE

    if ASSOCIATION_WORKFLOW_SERVICE is None:
        ASSOCIATION_WORKFLOW_SERVICE = AssociationWorkflowService(
            source_service=get_association_source_service(),
            import_service=get_association_import_service(),
        )

    return ASSOCIATION_WORKFLOW_SERVICE

def load_assets() -> list[dict[str, Any]]:
    ensure_data_architecture()
    if not ASSETS_FILE.exists():
        save_json(ASSETS_FILE, [])
        return []
    try:
        data = json.loads(ASSETS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else data.get("assets", [])


def save_assets(items: list[dict[str, Any]]) -> None:
    save_json(ASSETS_FILE, items)


ASSET_SERVICE: AssetService | None = None


def get_asset_service() -> AssetService:
    global ASSET_SERVICE
    if ASSET_SERVICE is None:
        ASSET_SERVICE = AssetService(
            load_assets=load_assets,
            save_assets=save_assets,
        )
    return ASSET_SERVICE


def asset_by_id(asset_id: str) -> dict[str, Any] | None:
    result = get_asset_service().read(asset_id)
    return result.data.get("asset") if result.ok else None


def asset_file_hash(path: Path) -> str:
    return AssetService.file_hash(path)


SPONSOR_REPOSITORY = SponsorRepository(
    CORE_PERSISTENCE,
    SPONSORS_FILE,
)


def load_sponsors() -> list[dict[str, Any]]:
    ensure_data_architecture()
    return SPONSOR_REPOSITORY.load()


def save_sponsors(items: list[dict[str, Any]]) -> None:
    ensure_data_architecture()
    SPONSOR_REPOSITORY.save(items)


SPONSOR_SERVICE: SponsorService | None = None


def get_sponsor_service() -> SponsorService:
    global SPONSOR_SERVICE

    if SPONSOR_SERVICE is None:
        SPONSOR_SERVICE = SponsorService(
            load_sponsors=load_sponsors,
            save_sponsors=save_sponsors,
            load_assets=load_assets,
        )

    return SPONSOR_SERVICE


def sponsor_logo_assets() -> list[dict[str, Any]]:
    return get_sponsor_service().logo_assets()


def sponsor_contract_state(record: dict[str, Any]) -> str:
    return get_sponsor_service().contract_state(record)


def clean_sponsor_record(
    data: dict[str, Any],
    sponsor_id: str | None = None,
) -> dict[str, Any]:
    return get_sponsor_service().clean_record(data, sponsor_id)


def active_sponsor_by_id(sponsor_id: str) -> dict[str, Any] | None:
    return get_sponsor_service().active_sponsor_by_id(sponsor_id)


def apply_sponsor_to_graphic(
    graphic: dict[str, Any],
    incoming: dict[str, Any],
) -> str:
    result = get_sponsor_service().apply_to_graphic(graphic, incoming)
    graphic.clear()
    graphic.update(result.data["graphic"])
    return str(result.data.get("warning", ""))


def clean_asset_record(
    incoming: dict[str, Any],
    existing_id: str = "",
) -> dict[str, Any]:
    existing = asset_by_id(existing_id) if existing_id else None
    return get_asset_service().clean_record(
        incoming,
        existing_id,
        existing=existing,
    )


def load_logos() -> list[dict[str, Any]]:
    ensure_data_architecture()
    if not LOGOS_FILE.exists():
        save_json(LOGOS_FILE, [])
    data = load_json(LOGOS_FILE, [])
    return data if isinstance(data, list) else data.get("logos", [])

def save_logos(items: list[dict[str, Any]]) -> None:
    save_json(LOGOS_FILE, items)


LOGO_SERVICE: LogoService | None = None


def get_logo_service() -> LogoService:
    global LOGO_SERVICE
    if LOGO_SERVICE is None:
        LOGO_SERVICE = LogoService(
            load_schools=load_schools,
            save_schools=save_schools,
            load_logos=load_logos,
            save_logos=save_logos,
            normalize_school_id=normalize_school_id,
        )
    return LOGO_SERVICE

def _normalize_broadcast_lifecycle(
    items: list[dict[str, Any]],
) -> bool:
    """Migrate obsolete broadcast lifecycle values."""

    changed = False

    for item in items:
        # Prepared was removed from the operator lifecycle
        # in Version 1.0 Alpha Hotfix 2.
        if str(item.get("status", "")).lower() == "prepared":
            item["status"] = "planned"
            changed = True

        live_state = item.get("live_state")

        if (
            isinstance(live_state, dict)
            and str(live_state.get("status", "")).lower()
            == "prepared"
        ):
            live_state["status"] = "planned"
            changed = True

    return changed


BROADCAST_REPOSITORY = BroadcastRepository(
    CORE_PERSISTENCE,
    BROADCAST_INDEX_FILE,
    normalizer=_normalize_broadcast_lifecycle,
)


def load_broadcasts() -> list[dict[str, Any]]:
    ensure_data_architecture()
    return BROADCAST_REPOSITORY.load()


def save_broadcasts(
    items: list[dict[str, Any]],
) -> None:
    ensure_data_architecture()
    BROADCAST_REPOSITORY.save(items)


def write_broadcast_detail(
    record: dict[str, Any],
    existing_only: bool = False,
) -> None:
    broadcast_id = str(record.get("broadcast_id", "")).strip()
    if not broadcast_id:
        return
    path = DATA_DIR / "Broadcasts" / f"{broadcast_id}.json"
    if existing_only and not path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")


def delete_broadcast_detail(broadcast_id: str) -> None:
    path = DATA_DIR / "Broadcasts" / f"{broadcast_id}.json"
    if path.exists():
        path.unlink()


BROADCAST_SERVICE: BroadcastService | None = None


def get_broadcast_service() -> BroadcastService:
    global BROADCAST_SERVICE

    if BROADCAST_SERVICE is None:
        BROADCAST_SERVICE = BroadcastService(
            load_broadcasts=load_broadcasts,
            save_broadcasts=save_broadcasts,
            get_school=get_school,
            resolve_venue=venue_for_school,
            build_identity=broadcast_identity,
            logo_certification=logo_certification,
            school_monogram=school_monogram,
            load_config=load_config,
            load_state=load_state,
            save_state=save_state,
            default_state=lambda: copy.deepcopy(DEFAULT_STATE),
            write_detail=write_broadcast_detail,
            delete_detail=delete_broadcast_detail,
        )

    return BROADCAST_SERVICE


def normalize_roster_id(value: str) -> str:
    return normalize_school_id(value)

def normalize_player_id(value: str) -> str:
    return normalize_school_id(value)

def _parse_roster_payload(path: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    items = raw if isinstance(raw, list) else raw.get("rosters", []) if isinstance(raw, dict) else []
    return items if isinstance(items, list) else []

def _roster_payload_score(items: list[dict[str, Any]]) -> tuple[int, int]:
    roster_count = len(items)
    player_count = sum(len(r.get("players", [])) for r in items if isinstance(r, dict) and isinstance(r.get("players"), list))
    return player_count, roster_count

def _roster_recovery_candidates() -> list[Path]:
    candidates: list[Path] = []
    # Keep recovery bounded. Searching BASE_DIR.parent recursively on every roster
    # request caused severe latency on OneDrive and large installation folders.
    roots = [DATA_DIR / "Backups", BASE_DIR / "Backups"]
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        try:
            for candidate in root.rglob("rosters.json"):
                try:
                    resolved = str(candidate.resolve())
                except OSError:
                    resolved = str(candidate)
                if resolved == str(ROSTERS_FILE.resolve()) or resolved in seen:
                    continue
                seen.add(resolved)
                candidates.append(candidate)
        except OSError:
            continue
    return candidates

def recover_rosters_if_needed(force: bool = False) -> dict[str, Any]:
    global _roster_recovery_checked
    ensure_data_architecture()
    if _roster_recovery_checked and not force:
        current = _parse_roster_payload(ROSTERS_FILE) if ROSTERS_FILE.exists() else []
        score = _roster_payload_score(current)
        return {"recovered": False, "source": "", "rosters": score[1], "players": score[0], "checked": True}

    current = _parse_roster_payload(ROSTERS_FILE) if ROSTERS_FILE.exists() else []
    current_score = _roster_payload_score(current)
    if current_score[0] > 0:
        _roster_recovery_checked = True
        return {"recovered": False, "source": "", "rosters": current_score[1], "players": current_score[0]}

    best_path: Path | None = None
    best_items: list[dict[str, Any]] = []
    best_score = current_score
    for candidate in _roster_recovery_candidates():
        items = _parse_roster_payload(candidate)
        score = _roster_payload_score(items)
        if score > best_score:
            best_path, best_items, best_score = candidate, items, score

    _roster_recovery_checked = True
    if not best_path or best_score[0] == 0:
        return {"recovered": False, "source": "", "rosters": current_score[1], "players": current_score[0]}

    timestamp = int(time.time())
    if ROSTERS_FILE.exists():
        quarantine = DATA_DIR / "Backups" / "RosterRecovery" / f"rosters-empty-or-invalid-{timestamp}.json"
        quarantine.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(ROSTERS_FILE, quarantine)
        except OSError:
            pass
    _write_rosters_file(best_items, snapshot=False)
    report = {"recovered": True, "source": str(best_path), "rosters": best_score[1], "players": best_score[0], "recovered_at": timestamp}
    save_json(DATA_DIR / "Logs" / "roster_recovery.json", report)
    return report

def _normalize_rosters(items: list[dict[str, Any]]) -> bool:
    changed = False
    for roster in items:
        if not isinstance(roster, dict):
            continue
        defaults = {
            "id": normalize_roster_id(f"{roster.get('school_id','school')}-{roster.get('sport','football')}-{roster.get('season','season')}-{roster.get('level','varsity')}-{roster.get('division','boys')}"),
            "school_id": "", "sport": "Football", "season": "",
            "level": "Varsity", "division": "Boys", "players": [],
        }
        for key, value in defaults.items():
            if key not in roster:
                roster[key] = value
                changed = True
        if not isinstance(roster.get("players"), list):
            roster["players"] = []
            changed = True
        for player in roster["players"]:
            if not isinstance(player, dict):
                continue
            player_defaults = {
                "id": normalize_player_id(f"{player.get('number','')}-{player.get('first_name','')}-{player.get('last_name','')}"),
                "preferred_name": "", "position": "", "secondary_position": "",
                "grade": "", "height": "", "weight": "", "captain": False,
                "starter": False, "status": "active", "headshot": "",
                "pronunciation": "", "pronunciation_verified": False,
            }
            for key, value in player_defaults.items():
                if key not in player:
                    player[key] = value
                    changed = True
    return changed

ROSTER_REPOSITORY = RosterRepository(
    CORE_PERSISTENCE,
    ROSTERS_FILE,
    normalizer=_normalize_rosters,
)

def _write_rosters_file(items: list[dict[str, Any]], snapshot: bool = True) -> None:
    ensure_data_architecture()
    ROSTER_REPOSITORY.save(items)

def load_rosters() -> list[dict[str, Any]]:
    ensure_data_architecture()
    recover_rosters_if_needed()
    return ROSTER_REPOSITORY.load()

def save_rosters(items: list[dict[str, Any]]) -> None:
    ensure_data_architecture()
    ROSTER_REPOSITORY.save(items)


ROSTER_SERVICE: RosterService | None = None


def get_roster_service() -> RosterService:
    global ROSTER_SERVICE

    if ROSTER_SERVICE is None:
        ROSTER_SERVICE = RosterService(
            load_rosters=load_rosters,
            save_rosters=save_rosters,
            load_schools=load_schools,
        )

    return ROSTER_SERVICE

def roster_summary(roster: dict[str, Any], schools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    school_list = schools if schools is not None else load_schools()
    school = next((s for s in school_list if str(s.get("id")) == str(roster.get("school_id"))), {})
    players = roster.get("players", []) if isinstance(roster.get("players"), list) else []
    return {
        **roster,
        "school_name": school.get("broadcast_name") or school.get("official_name") or roster.get("school_id", "Unknown School"),
        "active_count": sum(1 for p in players if str(p.get("status", "active")).lower() == "active"),
        "inactive_count": sum(1 for p in players if str(p.get("status", "active")).lower() == "inactive"),
        "player_count": len(players),
    }


def load_build_journal() -> list[dict[str, Any]]:
    ensure_data_architecture()
    data = load_json(BUILD_JOURNAL_FILE, [])
    return data if isinstance(data, list) else []

def save_build_journal(items: list[dict[str, Any]]) -> None:
    save_json(BUILD_JOURNAL_FILE, items)

def ensure_build_0018_journal() -> None:
    items = load_build_journal()
    if any(item.get("build") == "0018" for item in items):
        return
    items.append({
        "build": "0018",
        "release_date": "2026-07-12",
        "title": "Game Manager & Broadcast Creation",
        "features": ["Game Manager dashboard", "Broadcast database", "Permanent broadcast IDs", "Automatic school branding and venue population", "Broadcast lifecycle status"],
        "database_changes": ["Data/Broadcasts/broadcasts.json", "Broadcast records now link schools and venues by permanent IDs"],
        "known_issues": ["Schedule import is foundation-only and not yet enabled"],
        "test_status": "Packaged for user acceptance",
        "user_approval": "Pending"
    })
    save_build_journal(items)

def football_week_code(value: Any) -> str:
    return BroadcastService.football_week_code(value)


def next_broadcast_id(
    sport: str,
    season: str,
    classification: str,
    week: Any,
) -> str:
    return get_broadcast_service().next_id(
        sport,
        season,
        classification,
        week,
    )


def venue_for_school(
    school: dict[str, Any] | None,
    sport: str = "",
) -> dict[str, Any] | None:
    return get_venue_service().for_school(school, sport)


def school_duplicate_candidates(incoming: dict[str, Any], exclude_id: str = "") -> list[dict[str, Any]]:
    official = str(incoming.get("official_name", "")).strip().casefold()
    broadcast = str(incoming.get("broadcast_name", "")).strip().casefold()
    city = str(incoming.get("city", "") or incoming.get("user_overrides", {}).get("city", "")).strip().casefold()
    district = str(incoming.get("district", "") or incoming.get("source_data", {}).get("district", "")).strip().casefold()
    matches=[]
    for school in load_schools():
        if school.get("id") == exclude_id:
            continue
        names={str(school.get("official_name","")).casefold(), str(school.get("broadcast_name","")).casefold()}
        score=0
        if official and official in names: score += 3
        if broadcast and broadcast in names: score += 2
        school_city=str(school.get("city","") or school.get("user_overrides",{}).get("city","")).casefold()
        school_district=str(school.get("district","") or school.get("source_data",{}).get("district","")).casefold()
        if city and school_city and city == school_city: score += 1
        if district and school_district and district == school_district: score += 1
        if score >= 3:
            matches.append({"id": school.get("id"), "official_name": school.get("official_name"), "broadcast_name": school.get("broadcast_name"), "score": score})
    return matches

def get_school(school_id: str) -> dict[str, Any] | None:
    return next((school for school in load_schools() if school.get("id") == school_id), None)

def school_display_payload(school: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": school.get("id", ""),
        "official_name": school.get("official_name", ""),
        "broadcast_name": school.get("broadcast_name", ""),
        "mascot": school.get("mascot") or school.get("nickname", ""),
        "nickname": school.get("mascot") or school.get("nickname", ""),
        "primary_color": school.get("primary_color", "#C9203B"),
        "secondary_color": school.get("secondary_color", "#FFFFFF"),
        "verification_status": school.get("verification_status", "unverified"),
        "csrn_id": school.get("csrn_id", ""),
        "classification": school.get("classification", ""),
        "region": school.get("region", ""),
        "city": school.get("city", ""),
        "active": school.get("active", True),
    }

def school_monogram(name: str) -> str:
    words = [w for w in re.split(r"[^A-Za-z0-9]+", name or "") if w and w.casefold() not in {"high", "school", "hs", "of", "the", "at", "for"}]
    if not words:
        return "CSRN"
    return (words[0][0] if len(words) == 1 else "".join(w[0] for w in words)).upper()[:4]

def monogram_data_uri(name: str, primary: str, secondary: str) -> str:
    initials = school_monogram(name)
    # Compact ring with typography intentionally filling the interior.
    # Single letters receive the largest treatment; multi-letter marks are
    # horizontally condensed so they stay tall rather than shrinking evenly.
    profiles = {
        1: (306, 1.00),
        2: (282, 0.84),
        3: (236, 0.72),
        4: (198, 0.64),
    }
    font_size, scale_x = profiles.get(min(len(initials), 4), profiles[4])
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">'
        '<circle cx="256" cy="256" r="200" fill="%s" stroke="%s" stroke-width="10"/>'
        '<g transform="translate(256 0) scale(%s 1) translate(-256 0)">'
        '<text x="256" y="341" text-anchor="middle" font-family="Arial Black,Impact,Arial,sans-serif" '
        'font-size="%s" font-weight="900" letter-spacing="-8" fill="%s">%s</text>'
        '</g></svg>'
    ) % (primary, secondary, scale_x, font_size, secondary, initials)
    return "data:image/svg+xml;charset=utf-8," + quote(svg)

def logo_certification(school: dict[str, Any] | None) -> tuple[bool, str]:
    """Return whether the school's current primary logo is certified and its path.

    Certification can be stored on the school record, its logo metadata, or the
    linked Logo Database record. This keeps migrated builds and older records
    compatible while enforcing that candidate artwork never bypasses the
    generated-monogram fallback.
    """
    if not school:
        return False, ""
    approved_values = {"approved", "certified"}
    logo_path = str(school.get("primary_logo", "") or "").strip()
    school_status = str(school.get("logo_status", "") or "").strip().lower()
    metadata = school.get("logo_metadata") if isinstance(school.get("logo_metadata"), dict) else {}
    metadata_status = str(metadata.get("approval_status", "") or "").strip().lower()
    linked_id = str(school.get("default_broadcast_logo_id", "") or "").strip()
    linked_status = ""
    if linked_id:
        linked = next((row for row in load_logos() if str(row.get("id", "")) == linked_id), None)
        if linked:
            linked_status = str(linked.get("approval_status", "") or "").strip().lower()
            logo_path = logo_path or str(linked.get("round_master_path", "") or "").strip()
    certified = bool(logo_path and ({school_status, metadata_status, linked_status} & approved_values))
    return certified, logo_path if certified else ""


def broadcast_identity(school: dict[str, Any] | None, sport: str) -> dict[str, Any]:
    if not school:
        return {}
    primary = school.get("primary_color", "#C9203B")
    secondary = school.get("secondary_color", "#FFFFFF")
    certified, certified_logo = logo_certification(school)
    name = school.get("broadcast_name") or school.get("official_name", "")
    logo = certified_logo or monogram_data_uri(name, primary, secondary)
    return {"school_id": school.get("id", ""), "official_name": school.get("official_name", ""), "broadcast_name": school.get("broadcast_name", ""), "mascot": school.get("mascot") or school.get("nickname", ""), "nickname": school.get("mascot") or school.get("nickname", ""), "primary_color": primary, "secondary_color": secondary, "logo": logo, "logo_certified": certified, "branding_status": "certified_logo" if certified else "generated_monogram", "monogram": school_monogram(name)}




PERSONNEL_CATEGORIES = ("Coach", "Broadcast Talent", "Administrator", "Official", "Interview Guest", "Production Staff", "Other")
STAFF_ROLES = (
    "Head Coach", "Assistant Coach", "Offensive Coordinator", "Defensive Coordinator", "Special Teams Coordinator",
    "Play-by-Play", "Color Analyst", "Sideline Reporter", "Statistician", "Studio Host",
    "Athletic Director", "Principal", "Superintendent", "Official", "Interview Guest",
    "Camera Operator", "Technical Director", "Audio Engineer", "Graphics Operator", "Producer", "Other",
)

def normalize_staff_id(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "staff-member"

def normalize_personnel_headshot_url(value: str) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return ""
    filename = Path(raw).name
    if raw.startswith("/data/Personnel/Headshots/") or raw.startswith("data/Personnel/Headshots/"):
        return f"/personnel-headshots/{filename}"
    return raw

def migrate_broadcaster_record(item: dict[str, Any]) -> dict[str, Any]:
    full_name = str(item.get("full_name") or item.get("name") or "").strip()
    role = str(item.get("role") or item.get("primary_role") or "Other")
    if role not in STAFF_ROLES:
        role = "Other"
    category = str(item.get("category") or ("Broadcast Talent" if role in {"Play-by-Play","Color Analyst","Sideline Reporter","Studio Host","Statistician"} else "Production Staff"))
    if category not in PERSONNEL_CATEGORIES:
        category = "Other"
    return {
        "id": item.get("id") or normalize_staff_id(full_name or "personnel-member"),
        "full_name": full_name, "name": full_name, "preferred_name": str(item.get("preferred_name", "")).strip(),
        "pronunciation": str(item.get("pronunciation", "")).strip(), "pronunciation_verified": bool(item.get("pronunciation_verified", False)),
        "category": category, "role": role, "primary_role": role, "title": str(item.get("title") or role).strip(),
        "organization": str(item.get("organization", "")).strip(), "school_id": str(item.get("school_id", "")).strip(),
        "bio": str(item.get("bio", "")).strip(), "headshot": normalize_personnel_headshot_url(item.get("headshot", "")),
        "status": "inactive" if str(item.get("status", "active")).lower()=="inactive" else "active",
        "producer": bool(item.get("producer", False)),
        "social": item.get("social") or {"facebook":"","x":"","instagram":"","youtube":"","website":""},
    }


def load_broadcasters() -> list[dict[str, Any]]:
    ensure_data_architecture()
    if not BROADCASTERS_FILE.exists():
        BROADCASTERS_FILE.write_text(json.dumps([], indent=2), encoding="utf-8")
    try:
        data = json.loads(BROADCASTERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = []
    items = data if isinstance(data, list) else []
    migrated = [migrate_broadcaster_record(item) for item in items]
    if migrated != items:
        save_broadcasters(migrated)
    return migrated

def save_broadcasters(items: list[dict[str, Any]]) -> None:
    ensure_data_architecture()
    BROADCASTERS_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")

def normalize_social_url(
    platform: str,
    value: str,
) -> tuple[str, bool, str]:
    return ConfigurationService.normalize_social_url(platform, value)


def normalize_social_block(
    block: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    return ConfigurationService.normalize_social_block(block)


PERSONNEL_SERVICE: PersonnelService | None = None


def get_personnel_service() -> PersonnelService:
    global PERSONNEL_SERVICE

    if PERSONNEL_SERVICE is None:
        PERSONNEL_SERVICE = PersonnelService(
            load_personnel=load_broadcasters,
            save_personnel=save_broadcasters,
        )

    return PERSONNEL_SERVICE


GRAPHICS_SERVICE: GraphicsService | None = None


def get_graphics_service() -> GraphicsService:
    global GRAPHICS_SERVICE

    if GRAPHICS_SERVICE is None:
        GRAPHICS_SERVICE = GraphicsService(
            default_state=lambda: copy.deepcopy(DEFAULT_STATE),
            load_rosters=load_rosters,
            load_schools=load_schools,
            load_personnel=load_broadcasters,
            build_identity=broadcast_identity,
            apply_sponsor=apply_sponsor_to_graphic,
        )

    return GRAPHICS_SERVICE


def normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    return get_state_service().normalize(state)

def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        path.write_text(json.dumps(default, indent=2), encoding="utf-8")
        return copy.deepcopy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        path.write_text(json.dumps(default, indent=2), encoding="utf-8")
        return copy.deepcopy(default)

def save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

STATE_SERVICE: StateService | None = None


def persist_linked_state_snapshot(normalized: dict[str, Any]) -> None:
    broadcast_id = str(normalized.get("broadcast_id", "")).strip()
    if not broadcast_id:
        return
    items = load_broadcasts()
    item = next(
        (row for row in items if row.get("broadcast_id") == broadcast_id),
        None,
    )
    if not item:
        return
    snapshot = copy.deepcopy(normalized)
    snapshot["history"] = []
    item["live_state"] = snapshot
    item["status"] = normalized.get(
        "status",
        item.get("status", "planned"),
    )
    item["updated_at"] = int(time.time())
    save_broadcasts(items)
    detail = DATA_DIR / "Broadcasts" / f"{broadcast_id}.json"
    detail.write_text(json.dumps(item, indent=2), encoding="utf-8")


def get_state_service() -> StateService:
    global STATE_SERVICE
    if STATE_SERVICE is None:
        STATE_SERVICE = StateService(
            load_raw=STATE_REPOSITORY.load,
            replace_raw=STATE_REPOSITORY.replace,
            default_state=lambda: copy.deepcopy(DEFAULT_STATE),
            persist_linked_snapshot=persist_linked_state_snapshot,
            resolve_player=resolve_game_roster_player,
            canonical_team_key=canonical_team_key,
            canonical_team_name=canonical_team_name,
        )
    return STATE_SERVICE


def load_state() -> dict[str, Any]:
    return get_state_service().load().data["state"]


def save_state(state: dict[str, Any]) -> None:
    get_state_service().save(state)


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    return get_state_service().public(state).data["state"]

def load_security() -> dict[str, Any]:
    return SECURITY_SERVICE.ensure_secret_key(
        lambda: secrets.token_hex(32)
    )


def save_security(sec: dict[str, Any]) -> None:
    SECURITY_REPOSITORY.save(sec)

security = load_security()
app.secret_key = security["secret_key"]
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=False,
    PERMANENT_SESSION_LIFETIME=SESSION_SECONDS,
)

def pin_is_configured() -> bool:
    return SECURITY_SERVICE.pin_is_configured()

def authenticated() -> bool:
    return bool(session.get("authenticated"))

def require_auth(func: Callable):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not pin_is_configured():
            return jsonify({"error": "PIN_NOT_CONFIGURED"}), 403
        if not authenticated():
            return jsonify({"error": "AUTH_REQUIRED"}), 401
        return func(*args, **kwargs)
    return wrapper

def push_history(state: dict[str, Any]) -> None:
    StateService.push_history(state)


def apply_change(
    changes: dict[str, Any],
    save_undo: bool = True,
) -> dict[str, Any]:
    with lock:
        return get_state_service().apply_change(
            changes,
            save_undo=save_undo,
        ).data["state"]

def load_obs_status() -> dict[str, Any]:
    with obs_status_lock:
        return copy.deepcopy(last_obs_status)


def save_obs_status(status: dict[str, Any]) -> None:
    with obs_status_lock:
        last_obs_status.clear()
        last_obs_status.update(copy.deepcopy(status))


def update_obs_visual_state(mode: str) -> dict[str, Any]:
    with lock:
        state = load_state()
        push_history(state)
        state["visual_mode"] = mode
        save_state(state)
        return state


OBS_SERVICE: OBSService | None = None


def get_obs_service() -> OBSService:
    global OBS_SERVICE
    if OBS_SERVICE is None:
        OBS_SERVICE = OBSService(
            load_config=load_config,
            load_status=load_obs_status,
            save_status=save_obs_status,
            validate_obs=validate_obs_read_only,
            set_scorebug_visibility=set_scorebug_visibility,
            set_program_visual_mode=set_program_visual_mode,
            update_visual_state=update_obs_visual_state,
        )
    return OBS_SERVICE


@app.get("/")
def control_panel():
    identity = application_identity()
    return render_template(
        "index.html",
        app_product=identity["product"],
        app_version=identity["version"],
        app_build=identity["build"],
        copyright_year=2026,
        copyright_owner="Jason Chrest",
    )

@app.get("/api/packages")
@require_auth
def list_packages_route():
    return jsonify(
        get_broadcast_package_service().list_packages()
    )


@app.post("/api/packages")
@require_auth
def create_package_route():
    result = get_broadcast_package_service().create(
        request.get_json(force=True) or {}
    )
    return jsonify(result.data["package"]), 201


@app.put("/api/packages/<package_id>")
@require_auth
def update_package_route(package_id: str):
    result = get_broadcast_package_service().update(
        package_id,
        request.get_json(force=True) or {},
    )
    if result.code == "NOT_FOUND":
        return jsonify({"error": result.code}), 404
    if result.code == "PACKAGE_LOCKED":
        return jsonify({"error": result.code}), 409
    return jsonify(result.data["package"])


@app.delete("/api/packages/<package_id>")
@require_auth
def delete_package_route(package_id: str):
    result = get_broadcast_package_service().delete(package_id)
    if result.code == "NOT_FOUND":
        return jsonify({"error": result.code}), 404
    if result.code == "PACKAGE_LOCKED":
        return jsonify({"error": result.code}), 409
    return jsonify({"deleted": result.data["deleted"]})


@app.post("/api/packages/<package_id>/duplicate")
@require_auth
def duplicate_package_route(package_id: str):
    result = get_broadcast_package_service().duplicate(package_id)
    if result.code == "NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify(result.data["package"]), 201


@app.post("/api/packages/<package_id>/load")
@require_auth
def load_package_route(package_id: str):
    result = get_broadcast_package_service().load(package_id)
    if result.code == "NOT_FOUND":
        return jsonify({"error": result.code}), 404
    if result.code == "BROADCAST_NOT_FOUND":
        return jsonify({"error": result.code}), 409

    return jsonify(
        {
            "package": result.data["package"],
            "state": public_state(result.data["state"]),
            "health": result.data["health"],
        }
    )


@app.get("/api/sponsors")
@require_auth
def api_sponsors_list():
    return jsonify(get_sponsor_service().list_payload())


@app.post("/api/sponsors")
@require_auth
def api_sponsors_create():
    result = get_sponsor_service().create(
        request.get_json(silent=True) or {}
    )
    if result.code == "SPONSOR_NAME_REQUIRED":
        return jsonify({"error": "Sponsor name is required."}), 400
    if result.code == "DUPLICATE_SPONSOR":
        return jsonify(
            {
                "error": result.code,
                "duplicate_sponsor": result.data["duplicate_sponsor"],
            }
        ), 409
    return jsonify({"sponsor": result.data["sponsor"]})


@app.put("/api/sponsors/<sponsor_id>")
@require_auth
def api_sponsors_update(sponsor_id: str):
    result = get_sponsor_service().update(
        sponsor_id,
        request.get_json(silent=True) or {},
    )
    if result.code == "SPONSOR_NOT_FOUND":
        return jsonify({"error": "Sponsor not found."}), 404
    if result.code == "DUPLICATE_SPONSOR":
        return jsonify(
            {
                "error": result.code,
                "duplicate_sponsor": result.data["duplicate_sponsor"],
            }
        ), 409
    return jsonify({"sponsor": result.data["sponsor"]})


@app.delete("/api/sponsors/<sponsor_id>")
@require_auth
def api_sponsors_delete(sponsor_id: str):
    result = get_sponsor_service().delete(sponsor_id)
    if result.code == "SPONSOR_NOT_FOUND":
        return jsonify({"error": "Sponsor not found."}), 404
    return jsonify({"ok": True})


@app.post("/api/sponsors/<sponsor_id>/logo")
@require_auth
def api_sponsor_logo(sponsor_id: str):
    upload = request.files.get("logo")
    if not upload or not upload.filename:
        return jsonify({"error": "Choose a logo file."}), 400
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}:
        return jsonify({"error": "Unsupported logo type."}), 400

    duplicate_action = str(
        request.form.get("duplicate_action", "prompt")
    ).lower()
    sponsor = next(
        (
            item
            for item in load_sponsors()
            if str(item.get("id")) == sponsor_id
        ),
        None,
    )
    if not sponsor:
        return jsonify({"error": "Save the sponsor first."}), 404

    ASSET_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    temp = ASSET_UPLOAD_DIR / f".upload-{secrets.token_hex(8)}{suffix}"
    upload.save(temp)
    sha256 = asset_file_hash(temp)
    assets = load_assets()
    existing = next(
        (
            item
            for item in assets
            if item.get("sha256") == sha256 and item.get("active", True)
        ),
        None,
    )

    if existing and duplicate_action == "prompt":
        temp.unlink(missing_ok=True)
        return jsonify(
            {"error": "DUPLICATE_ASSET", "duplicate_asset": existing}
        ), 409

    if existing and duplicate_action == "reuse":
        temp.unlink(missing_ok=True)
        asset = existing
    elif existing and duplicate_action == "replace":
        current_url = str(existing.get("file_url", ""))
        current_name = (
            current_url.rsplit("/", 1)[-1]
            if current_url.startswith("/asset-files/")
            else ""
        )
        target = (
            ASSET_UPLOAD_DIR / current_name
            if current_name
            else ASSET_UPLOAD_DIR / f"{existing['id']}{suffix}"
        )
        temp.replace(target)
        existing.update(
            {
                "file_url": f"/asset-files/{target.name}",
                "sha256": sha256,
                "original_filename": upload.filename,
                "updated_at": int(time.time()),
            }
        )
        save_assets(assets)
        asset = existing
    else:
        asset_id = f"asset-{int(time.time()*1000)}-{secrets.token_hex(2)}"
        filename = f"{asset_id}{suffix}"
        target = ASSET_UPLOAD_DIR / filename
        temp.replace(target)
        asset = clean_asset_record(
            {
                "id": asset_id,
                "name": f"{sponsor.get('name', 'Sponsor')} Logo",
                "category": "Sponsor",
                "asset_type": "Logo",
                "file_url": f"/asset-files/{filename}",
                "rights_status": "Unverified",
                "rights_owner": sponsor.get("name", ""),
                "notes": "Created automatically from Sponsor Engine upload.",
                "sha256": sha256,
                "original_filename": upload.filename,
                "active": True,
            },
            asset_id,
        )
        assets.append(asset)
        save_assets(assets)

    result = get_sponsor_service().link_asset(
        sponsor_id,
        str(asset.get("id", "")),
    )
    if result.code == "SPONSOR_NOT_FOUND":
        return jsonify({"error": "Save the sponsor first."}), 404

    return jsonify(
        {
            "logo_url": result.data["sponsor"].get("logo_url", ""),
            "asset": asset,
            "duplicate_reused": bool(
                existing and duplicate_action == "reuse"
            ),
            "sponsor": result.data["sponsor"],
        }
    )


@app.put("/api/sponsors/<sponsor_id>/asset")
@require_auth
def api_sponsor_asset_link(sponsor_id: str):
    asset_id = str(
        (request.get_json(silent=True) or {}).get("asset_id", "")
    ).strip()
    result = get_sponsor_service().link_asset(sponsor_id, asset_id)
    if result.code == "INVALID_SPONSOR_LOGO_ASSET":
        return jsonify(
            {"error": "Choose a valid Sponsor Logo asset."}
        ), 400
    if result.code == "SPONSOR_NOT_FOUND":
        return jsonify({"error": "Sponsor not found."}), 404
    return jsonify(result.data)


@app.get("/sponsor-logos/<filename>")
def sponsor_logo_file(filename: str):
    return send_from_directory(SPONSOR_UPLOAD_DIR, filename)

@app.get("/api/assets")
@require_auth
def api_assets_list():
    include_inactive = str(
        request.args.get("include_inactive", "true")
    ).strip().lower() not in {"0", "false", "no", "off"}
    result = get_asset_service().list_records(
        include_inactive=include_inactive,
        category=str(request.args.get("category", "")),
        asset_type=str(request.args.get("asset_type", "")),
        rights_status=str(request.args.get("rights_status", "")),
    )
    return jsonify(result.data)


@app.post("/api/assets")
@require_auth
def api_assets_create():
    result = get_asset_service().create(
        request.get_json(silent=True) or {}
    )
    if result.code == "ASSET_NAME_REQUIRED":
        return jsonify({"error": "Asset name is required."}), 400
    return jsonify({"asset": result.data["asset"]})


@app.put("/api/assets/<asset_id>")
@require_auth
def api_assets_update(asset_id: str):
    result = get_asset_service().update(
        asset_id,
        request.get_json(silent=True) or {},
    )
    if result.code == "ASSET_NOT_FOUND":
        return jsonify({"error": "Asset not found."}), 404
    if result.code == "ASSET_NAME_REQUIRED":
        return jsonify({"error": "Asset name is required."}), 400
    return jsonify({"asset": result.data["asset"]})


@app.delete("/api/assets/<asset_id>")
@require_auth
def api_assets_delete(asset_id: str):
    result = get_asset_service().delete(asset_id)
    if result.code == "ASSET_NOT_FOUND":
        return jsonify({"error": "Asset not found."}), 404
    return jsonify({"ok": True})


@app.post("/api/assets/<asset_id>/upload")
@require_auth
def api_asset_upload(asset_id: str):
    upload = request.files.get("asset")
    if not upload or not upload.filename:
        return jsonify({"error": "Choose a file to upload."}), 400
    suffix = Path(upload.filename).suffix.lower()
    if not AssetService.extension_allowed(upload.filename):
        return jsonify({"error": "Unsupported asset file type."}), 400

    duplicate_action = str(
        request.form.get("duplicate_action", "prompt")
    ).lower()
    service = get_asset_service()
    current_result = service.read(asset_id)
    if current_result.code == "ASSET_NOT_FOUND":
        return jsonify({"error": "Save the asset record before uploading."}), 404

    safe_id = AssetService.normalize_id(asset_id)
    temp = ASSET_UPLOAD_DIR / f".upload-{secrets.token_hex(8)}{suffix}"
    upload.save(temp)
    sha256 = service.file_hash(temp)
    duplicate = service.duplicate_by_hash(sha256, exclude_id=asset_id)

    if duplicate and duplicate_action == "prompt":
        temp.unlink(missing_ok=True)
        return jsonify(
            {"error": "DUPLICATE_ASSET", "duplicate_asset": duplicate}
        ), 409

    if duplicate and duplicate_action == "reuse":
        temp.unlink(missing_ok=True)
        result = service.reuse_duplicate(asset_id, str(duplicate.get("id", "")))
        return jsonify(
            {
                "file_url": result.data["asset"].get("file_url", ""),
                **result.data,
            }
        )

    if duplicate and duplicate_action == "replace":
        existing_url = str(duplicate.get("file_url", ""))
        existing_name = (
            existing_url.rsplit("/", 1)[-1]
            if existing_url.startswith("/asset-files/")
            else f"{duplicate['id']}{suffix}"
        )
        target = ASSET_UPLOAD_DIR / existing_name
        temp.replace(target)
        result = service.replace_duplicate(
            asset_id,
            str(duplicate.get("id", "")),
            file_url=f"/asset-files/{target.name}",
            sha256=sha256,
            original_filename=upload.filename,
        )
        return jsonify(
            {
                "file_url": result.data["asset"]["file_url"],
                **result.data,
            }
        )

    filename = f"{safe_id}-{int(time.time())}{suffix}"
    target = ASSET_UPLOAD_DIR / filename
    temp.replace(target)
    result = service.attach_file(
        asset_id,
        file_url=f"/asset-files/{filename}",
        sha256=sha256,
        original_filename=upload.filename,
    )
    return jsonify(
        {
            "file_url": result.data["asset"]["file_url"],
            "duplicate_asset": duplicate,
            "duplicate_kept": bool(duplicate),
        }
    )


@app.get("/asset-files/<filename>")
def asset_file(filename: str):
    return send_from_directory(ASSET_UPLOAD_DIR, filename)

@app.get("/overlay")
def overlay():
    return render_template("overlay.html")

@app.get("/api/broadcasters")
@require_auth
def list_broadcasters():
    include_inactive = str(
        request.args.get("include_inactive", "true")
    ).strip().lower() not in {"0", "false", "no", "off"}
    result = get_personnel_service().list_records(
        include_inactive=include_inactive,
        category=str(request.args.get("category", "")),
        role=str(request.args.get("role", "")),
        school_id=str(request.args.get("school_id", "")),
    )
    return jsonify(result.data["personnel"])


@app.post("/api/broadcasters")
@require_auth
def create_broadcaster():
    result = get_personnel_service().create(
        request.get_json(force=True) or {}
    )
    if result.code in {"STAFF_NAME_REQUIRED", "INVALID_STAFF_ROLE"}:
        return jsonify({"error": result.code}), 400
    if result.code == "INVALID_SOCIAL_URL":
        return jsonify({"error": result.code, **result.data}), 400
    return jsonify(result.data["personnel"]), 201


@app.put("/api/broadcasters/<broadcaster_id>")
@require_auth
def update_broadcaster(broadcaster_id: str):
    result = get_personnel_service().update(
        broadcaster_id,
        request.get_json(force=True) or {},
    )
    if result.code == "BROADCASTER_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    if result.code in {"STAFF_NAME_REQUIRED", "INVALID_STAFF_ROLE"}:
        return jsonify({"error": result.code}), 400
    if result.code == "INVALID_SOCIAL_URL":
        return jsonify({"error": result.code, **result.data}), 400
    return jsonify(result.data["personnel"])


@app.delete("/api/broadcasters/<broadcaster_id>")
@require_auth
def delete_broadcaster(broadcaster_id: str):
    result = get_personnel_service().delete(broadcaster_id)
    if result.code == "BROADCASTER_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify({"ok": True})


@app.get("/personnel-headshots/<filename>")
def personnel_headshot_file(filename: str):
    return send_from_directory(PERSONNEL_HEADSHOTS_DIR, filename)


@app.post("/api/personnel/<personnel_id>/headshot")
@require_auth
def upload_personnel_headshot(personnel_id: str):
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "FILE_REQUIRED"}), 400
    ext = Path(file.filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        return jsonify({"error": "UNSUPPORTED_IMAGE"}), 400
    PERSONNEL_HEADSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    target = PERSONNEL_HEADSHOTS_DIR / (
        f"{PersonnelService.normalize_id(personnel_id)}{ext}"
    )
    file.save(target)
    relative = "/personnel-headshots/" + target.name
    result = get_personnel_service().attach_headshot(
        personnel_id,
        relative,
    )
    if result.code == "PERSONNEL_NOT_FOUND":
        target.unlink(missing_ok=True)
        return jsonify({"error": result.code}), 404
    return jsonify({"path": result.data["path"]})


@app.post("/api/validate-social")
@require_auth
def validate_social():
    incoming = request.get_json(force=True) or {}
    result = get_personnel_service().validate_social(
        str(incoming.get("platform", "")),
        str(incoming.get("value", "")),
    )
    return jsonify(result.data)


@app.get("/api/rosters")
@require_auth
def list_rosters():
    return jsonify(get_roster_service().list_rosters())


@app.post("/api/rosters")
@require_auth
def create_roster():
    result = get_roster_service().create(
        request.get_json(force=True) or {}
    )
    if result.code == "SCHOOL_AND_SEASON_REQUIRED":
        return jsonify({"error": result.code}), 400
    if result.code == "ROSTER_ALREADY_EXISTS":
        return jsonify(
            {
                "error": result.code,
                "roster": result.data["roster"],
            }
        ), 409
    return jsonify(result.data["roster"]), 201


@app.put("/api/rosters/<roster_id>")
@require_auth
def update_roster(roster_id: str):
    result = get_roster_service().update(
        roster_id,
        request.get_json(force=True) or {},
    )
    if result.code == "ROSTER_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify(result.data["roster"])


@app.delete("/api/rosters/<roster_id>")
@require_auth
def delete_roster(roster_id: str):
    result = get_roster_service().delete(roster_id)
    if result.code == "ROSTER_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify({"ok": True})


@app.post("/api/rosters/<roster_id>/players")
@require_auth
def create_roster_player(roster_id: str):
    result = get_roster_service().create_player(
        roster_id,
        request.get_json(force=True) or {},
    )
    if result.code == "ROSTER_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    if result.code == "PLAYER_NAME_REQUIRED":
        return jsonify({"error": result.code}), 400
    return jsonify(result.data), 201


@app.put("/api/rosters/<roster_id>/players/<player_id>")
@require_auth
def update_roster_player(roster_id: str, player_id: str):
    result = get_roster_service().update_player(
        roster_id,
        player_id,
        request.get_json(force=True) or {},
    )
    if result.code in {"ROSTER_NOT_FOUND", "PLAYER_NOT_FOUND"}:
        return jsonify({"error": result.code}), 404
    return jsonify(result.data)


@app.delete("/api/rosters/<roster_id>/players/<player_id>")
@require_auth
def delete_roster_player(roster_id: str, player_id: str):
    result = get_roster_service().delete_player(roster_id, player_id)
    if result.code in {"ROSTER_NOT_FOUND", "PLAYER_NOT_FOUND"}:
        return jsonify({"error": result.code}), 404
    return jsonify({"ok": True})


@app.post("/api/rosters/<roster_id>/players/import")
@require_auth
def import_roster_players(roster_id: str):
    incoming = request.get_json(force=True) or {}
    result = get_roster_service().import_players(
        roster_id,
        incoming.get("players", []),
    )
    if result.code == "INVALID_PLAYER_LIST":
        return jsonify({"error": result.code}), 400
    if result.code == "ROSTER_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify(result.data)


SCHOOL_ROUTES_BLUEPRINT = create_school_blueprint(
    SchoolRoutesDependencies(
        require_auth=require_auth,
        get_school_service=get_school_service,
    )
)
app.register_blueprint(SCHOOL_ROUTES_BLUEPRINT)

ASSOCIATION_ROUTES_BLUEPRINT = create_association_blueprint(
    AssociationRoutesDependencies(
        require_auth=require_auth,
        get_profile_service=get_association_profile_service,
        get_workflow_service=get_association_workflow_service,
        get_import_service=get_association_import_service,
        get_supplement_service=get_association_supplement_service,
        load_mhsaa_profile=lambda: load_json(MHSAA_5A_PROFILE_FILE, {}),
        load_mhsaa_manifest=lambda: load_json(
            MHSAA_5A_FILE,
            {"schools": []},
        ),
        load_mhsaa_branding_manifest=lambda: load_json(
            MHSAA_5A_BRANDING_FILE,
            {"schools": []},
        ),
        load_mhsaa_enrichment_manifest=lambda: load_json(
            MHSAA_5A_ENRICHMENT_FILE,
            {"schools": []},
        ),
    )
)
app.register_blueprint(ASSOCIATION_ROUTES_BLUEPRINT)


def _hex(rgb: tuple[int, int, int]) -> str:
    return LogoService._hex(rgb)


def extract_logo_colors(image: Image.Image) -> list[str]:
    return LogoService.extract_colors(image)


def normalize_round_logo(source: Image.Image, size: int) -> Image.Image:
    return LogoService.normalize_round_logo(source, size)


@app.get("/school-logos/<school_id>/<filename>")
def school_logo_file(school_id: str, filename: str):
    return send_from_directory(DATA_DIR / "Logos" / normalize_school_id(school_id), filename)

@app.post("/api/schools/<school_id>/logo/process")
@require_auth
def process_school_logo(school_id: str):
    upload = request.files.get("logo")
    if not upload or not upload.filename:
        return jsonify({"error": "LOGO_FILE_REQUIRED"}), 400

    raw = upload.read()
    normalized_school_id = normalize_school_id(school_id)
    folder = DATA_DIR / "Logos" / normalized_school_id

    def write_original(extension: str, payload: bytes) -> str:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"original{extension}"
        path.write_bytes(payload)
        return str(path.relative_to(BASE_DIR)).replace("\\", "/")

    def write_master(image: Image.Image) -> str:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "round-master.png"
        image.save(path)
        return f"/school-logos/{normalized_school_id}/round-master.png"

    def write_scorebug(image: Image.Image) -> str:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "round-scorebug.png"
        image.save(path)
        return f"/school-logos/{normalized_school_id}/round-scorebug.png"

    result = get_logo_service().process_candidate(
        school_id,
        raw=raw,
        original_filename=upload.filename,
        write_original=write_original,
        write_master=write_master,
        write_scorebug=write_scorebug,
    )
    if result.code == "SCHOOL_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    if result.code == "INVALID_IMAGE":
        return jsonify({"error": result.code}), 400
    if result.code == "LOGO_STORAGE_FAILED":
        return jsonify(
            {
                "error": result.code,
                "message": result.data.get("message", ""),
            }
        ), 500
    return jsonify(result.data)


@app.get("/api/venues")
@require_auth
def list_venues():
    include_inactive = str(
        request.args.get("include_inactive", "true")
    ).strip().lower() not in {"0", "false", "no", "off"}
    result = get_venue_service().list_venues(
        school_id=str(request.args.get("school_id", "")),
        sport=str(request.args.get("sport", "")),
        include_inactive=include_inactive,
    )
    return jsonify(result.data["venues"])


@app.get("/api/venues/<venue_id>")
@require_auth
def read_venue(venue_id: str):
    result = get_venue_service().read(venue_id)
    if result.code == "VENUE_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify(result.data["venue"])


@app.post("/api/venues")
@require_auth
def create_venue():
    result = get_venue_service().create(
        request.get_json(silent=True) or {}
    )
    if result.code == "VENUE_NAME_REQUIRED":
        return jsonify({"error": result.code}), 400
    if result.code == "DUPLICATE_VENUE":
        return jsonify(
            {
                "error": result.code,
                "duplicate_venue": result.data["duplicate_venue"],
            }
        ), 409
    return jsonify(result.data["venue"]), 201


@app.put("/api/venues/<venue_id>")
@require_auth
def update_venue(venue_id: str):
    result = get_venue_service().update(
        venue_id,
        request.get_json(silent=True) or {},
    )
    if result.code == "VENUE_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    if result.code == "VENUE_NAME_REQUIRED":
        return jsonify({"error": result.code}), 400
    if result.code == "DUPLICATE_VENUE":
        return jsonify(
            {
                "error": result.code,
                "duplicate_venue": result.data["duplicate_venue"],
            }
        ), 409
    return jsonify(result.data["venue"])


@app.delete("/api/venues/<venue_id>")
@require_auth
def delete_venue(venue_id: str):
    result = get_venue_service().delete(venue_id)
    if result.code == "VENUE_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    if result.code == "VENUE_IN_USE":
        return jsonify({"error": result.code, **result.data}), 409
    return jsonify(result.data)


@app.get("/api/logos")
@require_auth
def list_logos():
    result = get_logo_service().list_records(
        school_id=str(request.args.get("school_id", "")),
        designation=str(request.args.get("designation", "")),
        approval_status=str(request.args.get("approval_status", "")),
    )
    return jsonify(result.data["logos"])


UPGRADE_SERVICE: UpgradeService | None = None


def activate_upgrade_secret_key(secret_key: str) -> None:
    app.secret_key = secret_key


def get_upgrade_service() -> UpgradeService:
    global UPGRADE_SERVICE
    if UPGRADE_SERVICE is None:
        UPGRADE_SERVICE = UpgradeService(
            current_dir=BASE_DIR,
            defaults=DEFAULT_CONFIG,
            inspect_candidate=inspect_candidate,
            migrate=migrate,
            load_security=load_security,
            activate_secret_key=activate_upgrade_secret_key,
            report_store=last_upgrade_report,
            migration_lock=upgrade_lock,
        )
    return UPGRADE_SERVICE


SECURITY_UPGRADE_ROUTES_BLUEPRINT = create_security_upgrade_blueprint(
    SecurityUpgradeRoutesDependencies(
        get_security_service=lambda: SECURITY_SERVICE,
        load_security=load_security,
        authenticated=authenticated,
        clock=time.time,
        get_upgrade_service=get_upgrade_service,
    )
)
app.register_blueprint(SECURITY_UPGRADE_ROUTES_BLUEPRINT)


@app.get("/api/obs/status")
@require_auth
def obs_status():
    result = get_obs_service().status()
    return jsonify(result.data["status"])


@app.post("/api/obs/test")
@require_auth
def test_obs_connection():
    result = get_obs_service().test_connection()
    return jsonify(result.data["obs"])


def command_scorebug_visibility(visible: bool) -> dict[str, Any]:
    result = get_obs_service().scorebug_visibility(visible)
    if not result.ok:
        raise OBSConnectionError(
            str(result.data.get("message", result.code))
        )
    return result.data["obs"]


@app.post("/api/obs/scorebug-visibility")
@require_auth
def obs_scorebug_visibility():
    incoming = request.get_json(force=True) or {}
    result = get_obs_service().scorebug_visibility(incoming.get("visible"))
    if result.code == "VISIBLE_MUST_BE_BOOLEAN":
        return jsonify({"error": result.code}), 400
    if result.code == "OBS_COMMAND_BLOCKED":
        return jsonify(
            {
                "error": result.code,
                "message": result.data.get("message", ""),
            }
        ), 409
    return jsonify(result.data["obs"])


@app.post("/api/obs/program-visual-mode")
@require_auth
def obs_program_visual_mode():
    incoming = request.get_json(force=True) or {}
    result = get_obs_service().program_visual_mode(incoming.get("mode", ""))
    if result.code == "OBS_COMMAND_BLOCKED":
        return jsonify(
            {
                "error": result.code,
                "message": result.data.get("message", ""),
            }
        ), 409
    return jsonify(result.data)


def update_linked_broadcast_status(
    broadcast_id: str,
    status: str,
    extra: dict[str, Any] | None = None,
) -> None:
    get_broadcast_service().update_linked_status(
        broadcast_id,
        status,
        extra,
    )


def migrate_venue_names() -> None:
    get_venue_service().migrate_legacy_names()


def readiness_payload() -> dict[str, Any]:
    return get_diagnostics_service().readiness().data["readiness"]


SYSTEM_ROUTES_BLUEPRINT = create_system_blueprint(
    SystemRoutesDependencies(
        require_auth=require_auth,
        get_configuration_service=get_configuration_service,
        diagnostic_status=diagnostic_status,
        load_state=load_state,
        public_state=public_state,
        readiness_payload=readiness_payload,
        load_build_journal=load_build_journal,
    )
)
app.register_blueprint(SYSTEM_ROUTES_BLUEPRINT)


BROADCAST_LIFECYCLE_SERVICE: BroadcastLifecycleService | None = None


def get_broadcast_lifecycle_service() -> BroadcastLifecycleService:
    global BROADCAST_LIFECYCLE_SERVICE
    if BROADCAST_LIFECYCLE_SERVICE is None:
        BROADCAST_LIFECYCLE_SERVICE = BroadcastLifecycleService(
            load_broadcasts=load_broadcasts,
            load_packages=load_packages,
            load_state=load_state,
            save_state=save_state,
            normalize_state=normalize_state,
            default_state=lambda: copy.deepcopy(DEFAULT_STATE),
            get_school=get_school,
            build_identity=broadcast_identity,
            readiness=readiness_payload,
            update_linked_status=update_linked_broadcast_status,
            load_config=load_config,
            command_scorebug_visibility=command_scorebug_visibility,
            public_state=public_state,
            resume_record=get_broadcast_service().resume_record,
            transaction_lock=lock,
        )
    return BROADCAST_LIFECYCLE_SERVICE


@app.post("/api/broadcasts/<broadcast_id>/load")
@require_auth
def load_planned_broadcast(broadcast_id: str):
    result = get_broadcast_lifecycle_service().load(broadcast_id)
    if result.code == "NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify(result.data["state"])


@app.post("/api/initialize-broadcast")
@require_auth
def initialize_broadcast():
    result = get_broadcast_lifecycle_service().initialize()
    if result.code == "NO_ACTIVE_BROADCAST":
        return jsonify({"error": result.code}), 409
    return jsonify(result.data)


@app.post("/api/start-broadcast")
@require_auth
def start_broadcast():
    result = get_broadcast_lifecycle_service().start()
    if result.code == "NO_ACTIVE_BROADCAST":
        return jsonify({"error": result.code}), 409
    return jsonify(result.data)


@app.post("/api/resume-broadcast")
@require_auth
def resume_broadcast():
    result = get_broadcast_lifecycle_service().resume()
    if result.code == "NO_ACTIVE_BROADCAST":
        return jsonify({"error": result.code}), 409
    return jsonify(result.data["state"])


@app.post("/api/create-broadcast")
@require_auth
def create_broadcast():
    result = get_broadcast_service().create(
        request.get_json(force=True) or {}
    )
    return jsonify(result.data)


@app.get("/api/broadcasts")
@require_auth
def list_broadcasts():
    include_archived = str(
        request.args.get("include_archived", "false")
    ).strip().lower() in {"1", "true", "yes", "y", "on"}
    result = get_broadcast_service().list_records(
        include_archived=include_archived
    )
    return jsonify(result.data["broadcasts"])


@app.get("/api/broadcasts/<broadcast_id>")
@require_auth
def get_broadcast_record(broadcast_id: str):
    result = get_broadcast_service().read(broadcast_id)
    if result.code == "NOT_FOUND":
        return jsonify({"error": "NOT_FOUND"}), 404
    return jsonify(result.data["broadcast"])


@app.put("/api/broadcasts/<broadcast_id>")
@require_auth
def update_broadcast_record(broadcast_id: str):
    result = get_broadcast_service().update(
        broadcast_id,
        request.get_json(force=True) or {},
    )
    if result.code == "NOT_FOUND":
        return jsonify({"error": "NOT_FOUND"}), 404
    return jsonify(result.data)


@app.put("/api/broadcasts/<broadcast_id>/status")
@require_auth
def set_broadcast_status(broadcast_id: str):
    incoming = request.get_json(force=True) or {}
    result = get_broadcast_service().set_status(
        broadcast_id,
        incoming.get("status", ""),
    )
    if result.code == "INVALID_STATUS":
        return jsonify({"error": "INVALID_STATUS"}), 400
    if result.code == "NOT_FOUND":
        return jsonify({"error": "NOT_FOUND"}), 404
    return jsonify(result.data["broadcast"])


@app.delete("/api/broadcasts/<broadcast_id>")
@require_auth
def delete_broadcast_record(broadcast_id: str):
    result = get_broadcast_service().delete(broadcast_id)
    if result.code == "NOT_FOUND":
        return jsonify({"error": "NOT_FOUND"}), 404
    return jsonify(result.data)


GAME_OPERATIONS_SERVICE: GameOperationsService | None = None


def get_game_operations_service() -> GameOperationsService:
    global GAME_OPERATIONS_SERVICE
    if GAME_OPERATIONS_SERVICE is None:
        GAME_OPERATIONS_SERVICE = GameOperationsService(
            load_state=load_state,
            save_state=save_state,
            default_state=lambda: copy.deepcopy(DEFAULT_STATE),
            push_history=push_history,
            source_allowed=EventService.source_allowed,
            locked_payload=EventService.locked_payload,
            update_linked_status=update_linked_broadcast_status,
            load_config=load_config,
            command_scorebug_visibility=command_scorebug_visibility,
            transaction_lock=lock,
        )
    return GAME_OPERATIONS_SERVICE


@app.post("/api/score")
@require_auth
def update_score():
    result = get_game_operations_service().score(
        request.get_json(force=True) or {}
    )
    if result.code == "INVALID_SCORE_REQUEST":
        return jsonify({"error": result.code}), 400
    if result.code == "CONTROL_SOURCE_LOCKED":
        return jsonify(result.data), 409
    return jsonify(result.data["state"])


@app.post("/api/set")
@require_auth
def set_value():
    result = get_game_operations_service().set_values(
        request.get_json(force=True) or {}
    )
    if result.code == "CONTROL_SOURCE_LOCKED":
        return jsonify(result.data), 409
    return jsonify(result.data["state"])


SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None


def get_support_media_service() -> SupportMediaService:
    global SUPPORT_MEDIA_SERVICE
    if SUPPORT_MEDIA_SERVICE is None:
        SUPPORT_MEDIA_SERVICE = SupportMediaService(
            headshots_dir=HEADSHOTS_DIR,
            load_rosters=load_rosters,
            save_rosters=save_rosters,
        )
    return SUPPORT_MEDIA_SERVICE


@app.get("/roster-headshots/<filename>")
def roster_headshot_file(filename: str):
    return send_from_directory(HEADSHOTS_DIR, filename)


@app.post("/api/rosters/<roster_id>/players/<player_id>/headshot")
@require_auth
def upload_player_headshot(roster_id: str, player_id: str):
    upload = request.files.get("headshot")
    if not upload or not upload.filename:
        return jsonify({"error": "HEADSHOT_FILE_REQUIRED"}), 400
    result = get_support_media_service().upload_headshot(
        roster_id,
        player_id,
        original_filename=upload.filename,
        raw=upload.read(),
    )
    if result.code in {
        "HEADSHOT_FILE_REQUIRED",
        "UNSUPPORTED_IMAGE_TYPE",
        "INVALID_IMAGE",
        "IMAGE_TOO_SMALL",
    }:
        return jsonify({"error": result.code}), 400
    if result.code in {"ROSTER_NOT_FOUND", "PLAYER_NOT_FOUND"}:
        return jsonify({"error": result.code}), 404
    if result.code == "HEADSHOT_STORAGE_FAILED":
        return jsonify(
            {
                "error": result.code,
                "message": result.data.get("message", ""),
            }
        ), 500
    return jsonify(
        {
            "headshot": result.data["headshot"],
            "player": result.data["player"],
        }
    )


def activate_primary_graphic(state: dict[str, Any], active: str) -> None:
    """Keep the legacy mutating helper while delegating graphic rules."""
    updated = get_graphics_service().activate_primary(state, active)
    state.clear()
    state.update(updated)


@app.post("/api/graphics/lower-third")
@require_auth
def update_lower_third():
    data = request.get_json(force=True) or {}
    with lock:
        result = get_graphics_service().update_lower_third(load_state(), data)
        state = result.data["state"]
        save_state(state)
    return jsonify(public_state(state))


@app.post("/api/graphics/player")
@require_auth
def update_player_graphic():
    data = request.get_json(force=True) or {}
    with lock:
        result = get_graphics_service().update_player(load_state(), data)
        if result.code == "PLAYER_REQUIRED":
            return jsonify({"error": result.code}), 400
        state = result.data["state"]
        save_state(state)
    response = public_state(state)
    warning = str(result.data.get("sponsor_warning", ""))
    if warning:
        response["sponsor_warning"] = warning
    return jsonify(response)


@app.post("/api/graphics/personnel")
@require_auth
def update_personnel_graphic():
    data = request.get_json(force=True) or {}
    with lock:
        result = get_graphics_service().update_personnel(load_state(), data)
        if result.code == "PERSONNEL_REQUIRED":
            return jsonify({"error": result.code}), 400
        state = result.data["state"]
        save_state(state)
    response = public_state(state)
    warning = str(result.data.get("sponsor_warning", ""))
    if warning:
        response["sponsor_warning"] = warning
    return jsonify(response)


def automation_player(roster_id: str, player_id: str):
    roster = next((r for r in load_rosters() if str(r.get("id")) == str(roster_id)), None)
    player = next((p for p in (roster or {}).get("players", []) if str(p.get("id")) == str(player_id)), None)
    return roster, player

def player_display(player):
    return GraphicsService.player_display(player)


def normalize_position(value):
    return GraphicsService.normalize_position(value)


def event_position(player, defensive=False):
    return GraphicsService.event_position(player, defensive=defensive)


def manual_automation_player(data, team_name):
    if not isinstance(data, dict) or not str(data.get("number", "")).strip():
        return None
    number = str(data.get("number", "")).strip()
    name = str(data.get("name", "")).strip() or f"{team_name} {number}"
    parts = name.split(" ", 1)
    return {
        "id": "",
        "number": number,
        "preferred_name": name,
        "first_name": parts[0] if parts else name,
        "last_name": parts[1] if len(parts) > 1 else "",
        "position": normalize_position(data.get("position")),
        "secondary_position": "",
        "grade": "",
        "height": "",
        "weight": "",
        "headshot": "",
        "manual": True,
    }

def show_automation_player_graphic(
    state,
    roster,
    player,
    graphic_type,
    duration,
    defensive=False,
    eyebrow="",
    play_detail="",
):
    result = get_graphics_service().show_automation_player(
        state,
        roster,
        player,
        graphic_type,
        duration,
        defensive=defensive,
        eyebrow=eyebrow,
        play_detail=play_detail,
    )
    state.clear()
    state.update(result.data["state"])


def canonical_team_key(state: dict[str, Any], value: Any) -> str:
    return StatisticsService.canonical_team_key(state, value)


def canonical_team_name(state: dict[str, Any], value: Any) -> str:
    return StatisticsService.canonical_team_name(state, value)


def resolve_game_roster_player(state: dict[str, Any], team: str, number: Any) -> dict[str, str]:
    """Resolve a jersey against the active broadcast rosters.

    Alpha.3f deliberately prefers rosters linked to the loaded broadcast package,
    then falls back to school/sport matching. Season mismatches no longer make a
    valid linked roster disappear during a resumed broadcast.
    """
    jersey = str(number or "").strip()
    if not jersey:
        return {"number": "", "name": "", "resolved": False}
    team_key = canonical_team_key(state, team)
    school_id = str(state.get(f"{team_key}_school_id", "") or "") if team_key in {"home", "visitor"} else ""
    team_name = canonical_team_name(state, team_key).strip().lower()
    sport = str(state.get("sport") or "Football").strip().lower()
    level = str(state.get("level") or "Varsity").strip().lower()
    all_rosters = load_rosters()
    linked_ids = {str(x) for x in (state.get("package_roster_ids") or []) if str(x).strip()}

    def roster_school_name(roster: dict[str, Any]) -> str:
        school = get_school(str(roster.get("school_id", "") or ""))
        return str((school or {}).get("broadcast_name") or (school or {}).get("official_name") or "").strip().lower()

    def belongs_to_team(roster: dict[str, Any]) -> bool:
        rid = str(roster.get("id", "") or "")
        if linked_ids and rid not in linked_ids:
            return False
        roster_school = str(roster.get("school_id", "") or "")
        school_match = bool(school_id and roster_school == school_id) or bool(team_name and roster_school_name(roster) == team_name)
        sport_match = not roster.get("sport") or str(roster.get("sport", "")).strip().lower() == sport
        return school_match and sport_match

    candidates = [r for r in all_rosters if belongs_to_team(r)]
    if not candidates and linked_ids:
        # Package metadata can become stale; recover by matching the active teams.
        candidates = [r for r in all_rosters if ((school_id and str(r.get("school_id", "")) == school_id) or (team_name and roster_school_name(r) == team_name)) and (not r.get("sport") or str(r.get("sport", "")).strip().lower() == sport)]
    roster = next((r for r in candidates if str(r.get("level", "")).strip().lower() == level), None)
    roster = roster or next((r for r in candidates if str(r.get("level", "")).strip().lower() == "varsity"), None) or (candidates[0] if candidates else None)
    if not roster:
        return {"number": jersey, "name": "", "resolved": False}
    player = next((p for p in roster.get("players", []) if str(p.get("status", "active")).lower() != "inactive" and str(p.get("number", "")).strip() == jersey), None)
    if not player:
        return {"number": jersey, "name": "", "resolved": False}
    name = str(player.get("preferred_name") or f"{player.get('first_name','')} {player.get('last_name','')}".strip()).strip()
    return {"number": jersey, "name": name, "resolved": True, "roster_id": str(roster.get("id", "")), "player_id": str(player.get("id", ""))}

STATISTICS_SERVICE: StatisticsService | None = None


def get_statistics_service() -> StatisticsService:
    global STATISTICS_SERVICE
    if STATISTICS_SERVICE is None:
        STATISTICS_SERVICE = StatisticsService()
    return STATISTICS_SERVICE


def build_statistics(state: dict[str, Any]) -> dict[str, Any]:
    return get_statistics_service().report(state).data["statistics"]


PENALTY_RULES: dict[tuple[str, str], dict[str, Any]] = {
    ("Offensive", "Holding"): {"yards": 10, "replay_down": True},
    ("Offensive", "False Start"): {"yards": 5, "replay_down": True, "dead_ball": True},
    ("Offensive", "Illegal Motion"): {"yards": 5, "replay_down": True},
    ("Offensive", "Illegal Formation"): {"yards": 5, "replay_down": True},
    ("Offensive", "Delay of Game"): {"yards": 5, "replay_down": True},
    ("Offensive", "Intentional Grounding"): {"yards": 5, "loss_of_down": True},
    ("Offensive", "Personal Foul"): {"yards": 15, "replay_down": True},
    ("Offensive", "Unsportsmanlike Conduct"): {"yards": 15, "replay_down": True},
    ("Defensive", "Holding"): {"yards": 10, "automatic_first_down": True},
    ("Defensive", "Pass Interference"): {"yards": 15, "automatic_first_down": True},
    ("Defensive", "Roughing the Passer"): {"yards": 15, "automatic_first_down": True},
    ("Defensive", "Personal Foul"): {"yards": 15, "automatic_first_down": True},
    ("Defensive", "Unsportsmanlike Conduct"): {"yards": 15, "automatic_first_down": True},
    ("Defensive", "Offside"): {"yards": 5, "replay_down": True},
    ("Defensive", "Encroachment"): {"yards": 5, "replay_down": True, "dead_ball": True},
    ("Special Teams", "Kick Catch Interference"): {"yards": 15, "automatic_first_down": False},
    ("Special Teams", "Illegal Block"): {"yards": 10},
    ("Special Teams", "Running Into Kicker"): {"yards": 5},
    ("Special Teams", "Roughing Kicker"): {"yards": 15, "automatic_first_down": True},
}

def int_distance(value: Any, fallback: int = 10) -> int:
    try:
        return max(1, min(99, int(str(value))))
    except (TypeError, ValueError):
        return fallback

def advance_down(down: str) -> str:
    return {"1st": "2nd", "2nd": "3rd", "3rd": "4th", "4th": "1st"}.get(str(down), str(down) or "1st")


def sync_play_from_event(state: dict[str, Any], event: dict[str, Any]) -> None:
    """Keep the Alpha.2 canonical play record synchronized with its source event."""
    plays = list(state.get("plays") or [])
    play = next((row for row in plays if row.get("event_id") == event.get("id") or row.get("play_id") == event.get("play_id")), None)
    if not play:
        return
    auto = event.get("automation") or {}
    before = event.get("before") or {}
    play.update({
        "quarter": str(event.get("quarter", play.get("quarter", "1"))),
        "down": str(before.get("down", play.get("down", ""))),
        "distance": str(before.get("distance", play.get("distance", ""))),
        "ball_spot": str(before.get("ball_spot", play.get("ball_spot", ""))),
        "play_type": auto.get("play_type") or str(event.get("event", "")).lower(),
        "result": event.get("description", play.get("result", "")),
        "yards": auto.get("yards", play.get("yards", "")),
        "undone": bool(event.get("undone", False)),
    })
    state["plays"] = plays

def correction_entry(kind: str, operator: str, before: dict[str, Any], after: dict[str, Any], event_id: str = "", note: str = "") -> dict[str, Any]:
    return {
        "id": f"COR-{int(time.time()*1000)}", "kind": kind, "operator": operator,
        "event_id": event_id, "before": before, "after": after, "note": note,
        "created_at": int(time.time()),
    }

def append_correction(state: dict[str, Any], entry: dict[str, Any]) -> None:
    rows = list(state.get("correction_log") or [])
    rows.append(entry)
    state["correction_log"] = rows[-500:]

def apply_penalty_enforcement(state: dict[str, Any], category: str, name: str, yards: int, outcome: str) -> dict[str, Any]:
    result = {"applied": False, "rule": {}, "down": state.get("down", "1st"), "distance": state.get("distance", "10")}
    if outcome != "accepted":
        return result
    rule = copy.deepcopy(PENALTY_RULES.get((category, name), {}))
    if not rule:
        rule = {"yards": yards}
        if category == "Offensive": rule["replay_down"] = True
        if category == "Defensive" and yards >= 15: rule["automatic_first_down"] = True
    enforced_yards = max(0, yards if yards is not None else int(rule.get("yards", 0)))
    if rule.get("automatic_first_down"):
        state["down"] = "1st"; state["distance"] = "10"
    elif category == "Offensive":
        state["distance"] = str(min(99, int_distance(state.get("distance"), 10) + enforced_yards))
        if rule.get("loss_of_down"):
            state["down"] = advance_down(str(state.get("down", "1st")))
    elif category == "Defensive":
        remaining = int_distance(state.get("distance"), 10) - enforced_yards
        if remaining <= 0:
            state["down"] = "1st"; state["distance"] = "10"
        else:
            state["distance"] = str(remaining)
    result.update({"applied": True, "rule": rule, "down": state.get("down"), "distance": state.get("distance"), "yards": enforced_yards})
    return result

def local_addresses() -> list[str]:
    return get_support_media_service().local_addresses()


@app.get("/api/statistics")
@require_auth
def statistics_report():
    return jsonify(build_statistics(load_state()))

EVENT_SERVICE: EventService | None = None


def get_event_service() -> EventService:
    global EVENT_SERVICE
    if EVENT_SERVICE is None:
        EVENT_SERVICE = EventService(
            load_state=load_state,
            save_state=save_state,
            public_state=public_state,
            push_history=push_history,
            update_linked_status=update_linked_broadcast_status,
            automation_player=automation_player,
            manual_player=manual_automation_player,
            player_display=player_display,
            show_player_graphic=show_automation_player_graphic,
            apply_penalty=apply_penalty_enforcement,
            spot_to_coord=spot_to_coord,
            team_direction=team_direction,
            normalize_state=normalize_state,
            default_player_graphic=lambda: copy.deepcopy(
                DEFAULT_STATE["player_graphic"]
            ),
            transaction_lock=lock,
        )
    return EVENT_SERVICE


def game_data_source_allowed(state: dict[str, Any], source: str) -> bool:
    return EventService.source_allowed(state, source)


def authority_rejection(state: dict[str, Any]):
    return jsonify(EventService.locked_payload(state)), 409


@app.post("/api/control-source")
@require_auth
def set_control_source():
    data = request.get_json(force=True) or {}
    result = get_event_service().set_control_source(data.get("authority", ""))
    if result.code == "INVALID_CONTROL_SOURCE":
        return jsonify({"error": result.code}), 400
    return jsonify(result.data["state"])


@app.post("/api/event-trigger")
@require_auth
def event_trigger():
    result = get_event_service().trigger(request.get_json(force=True) or {})
    if result.code == "INVALID_EVENT":
        return jsonify({"error": result.code}), 400
    if result.code == "NO_ACTIVE_BROADCAST":
        return jsonify({"error": result.code}), 409
    if result.code == "CONTROL_SOURCE_LOCKED":
        return jsonify(result.data), 409
    return jsonify(result.data)


@app.post("/api/game-correction")
@require_auth
def game_correction():
    result = get_event_service().quick_correction(
        request.get_json(force=True) or {}
    )
    if result.code in {"INVALID_DOWN", "INVALID_POSSESSION"}:
        return jsonify({"error": result.code}), 400
    if result.code == "CONTROL_SOURCE_LOCKED":
        return jsonify(result.data), 409
    return jsonify(result.data["state"])


@app.post("/api/events/<event_id>/edit")
@require_auth
def edit_event(event_id: str):
    result = get_event_service().edit(
        event_id,
        request.get_json(force=True) or {},
    )
    if result.code == "EVENT_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    if result.code == "CONTROL_SOURCE_LOCKED":
        return jsonify(result.data), 409
    return jsonify(result.data)


@app.get("/api/corrections")
@require_auth
def corrections_report():
    result = get_event_service().corrections()
    return jsonify(result.data["corrections"])


@app.get("/api/connection-info")
@require_auth
def connection_info():
    result = get_support_media_service().connection_info(5050)
    return jsonify(result.data["connection"])


@app.get("/api/connection-qr")
@require_auth
def connection_qr():
    result = get_support_media_service().qr_svg(
        request.args.get("url", "")
    )
    if result.code == "INVALID_URL":
        return jsonify({"error": result.code}), 400
    if result.code == "QR_GENERATION_FAILED":
        return jsonify(
            {
                "error": result.code,
                "message": result.data.get("message", ""),
            }
        ), 500
    return Response(
        result.data["svg"],
        mimetype=result.data["mimetype"],
        headers=result.data["headers"],
    )


@app.post("/api/toggle-scorebug")
@require_auth
def toggle_scorebug():
    result = get_game_operations_service().toggle_scorebug()
    if result.code == "OBS_COMMAND_BLOCKED":
        return jsonify(
            {
                "error": result.code,
                "message": result.data.get("message", ""),
            }
        ), 409
    return jsonify(result.data["state"])


@app.post("/api/toggle-halftime")
@require_auth
def toggle_halftime():
    result = get_game_operations_service().toggle_halftime()
    return jsonify(result.data["state"])


@app.post("/api/end-game")
@require_auth
def end_game():
    result = get_game_operations_service().end_game()
    return jsonify(result.data["state"])


@app.post("/api/reset-data")
@require_auth
def reset_data():
    result = get_game_operations_service().reset_data()
    return jsonify(result.data["state"])


@app.post("/api/new-broadcast")
@require_auth
def new_broadcast():
    result = get_game_operations_service().new_broadcast()
    return jsonify(result.data["state"])


def spot_to_coord(value: Any) -> int:
    return RulesService.spot_to_coord(value)


def coord_to_spot(coord: int) -> str:
    return RulesService.coord_to_spot(coord)


def team_direction(state: dict[str, Any], team: str) -> int:
    return RulesService.team_direction(state, team)


def opposite(team: str) -> str:
    return RulesService.opposite(team)


def advance_down(down: str) -> str:
    return RulesService.advance_down(down)


RULES_SERVICE: RulesService | None = None


def get_rules_service() -> RulesService:
    global RULES_SERVICE
    if RULES_SERVICE is None:
        RULES_SERVICE = RulesService(
            load_state=load_state,
            save_state=save_state,
            push_history=push_history,
            source_allowed=game_data_source_allowed,
            locked_payload=EventService.locked_payload,
            resolve_player=resolve_game_roster_player,
            show_player_graphic=show_automation_player_graphic,
            transaction_lock=lock,
        )
    return RULES_SERVICE


@app.post("/api/clock-control")
@require_auth
def clock_control():
    result = get_rules_service().clock_control(
        request.get_json(force=True) or {}
    )
    return jsonify(result.data["state"])


@app.post("/api/field-direction")
@require_auth
def field_direction():
    result = get_rules_service().field_direction(
        request.get_json(force=True) or {}
    )
    if result.code == "INVALID_DIRECTION":
        return jsonify({"error": result.code}), 400
    return jsonify(result.data["state"])


@app.post("/api/rules-play")
@require_auth
def rules_play():
    result = get_rules_service().play(request.get_json(force=True) or {})
    if result.code == "INVALID_PLAY":
        return jsonify({"error": result.code}), 400
    if result.code == "NO_ACTIVE_BROADCAST":
        return jsonify({"error": result.code}), 409
    if result.code == "CONTROL_SOURCE_LOCKED":
        return jsonify(result.data), 409
    return jsonify(result.data)


@app.post("/api/undo")
@require_auth
def undo():
    result = get_event_service().undo()
    return jsonify(result.data["state"])


def local_ip() -> str:
    return SupportMediaService.local_ip()


if __name__ == "__main__":
    ensure_data_architecture()
    load_config()
    from waitress import serve

    ip = local_ip()
    print("\nCSRN Production Suite — Command Center is running.")
    print("Laptop: http://127.0.0.1:5050")
    print(f"Phone/iPad: http://{ip}:5050")
    print("OBS overlay: http://127.0.0.1:5050/overlay")
    print("Server: Waitress production server\n")
    serve(app, host="0.0.0.0", port=5050, threads=8)
