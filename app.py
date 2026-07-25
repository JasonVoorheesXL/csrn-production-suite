from __future__ import annotations

import copy
import io
import json
import hashlib
import os
import re
import secrets
import socket
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
import qrcode
import qrcode.image.svg
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

# Phase 3.5: BroadcastRespository integrated

# Phase 3.4: VenueRepository integrated

# Phase 3.3: SponsorRepository integrated

# Phase 3.2: RosterRepository integrated

# Phase 3.1: SchoolRepository integrated

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
    "Version 1.13.0-alpha.4f — Sponsor Service"
)
RUNTIME_BUILD = "V1.13A4F-SPONSOR-SERVICE"


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


def diagnostic_status() -> dict[str, Any]:
    cfg = load_config()
    required = {
        "Configuration": CONFIG_FILE,
        "Data folder": DATA_DIR,
        "Schools folder": DATA_DIR / "Schools",
        "Broadcasts folder": DATA_DIR / "Broadcasts",
        "Backups folder": DATA_DIR / "Backups",
        "Logo file": BASE_DIR / cfg["organization"].get("logo_path", "static/csrn-logo.png"),
        "School database": SCHOOLS_FILE,
        "Broadcaster profiles": BROADCASTERS_FILE,
        "Roster database": ROSTERS_FILE,
        "Venue database": VENUES_FILE,
        "Logo database": LOGOS_FILE,
        "Broadcast packages": PACKAGES_FILE,
    }
    return {
        "checks": [
            {"name": name, "ok": path.exists(), "path": str(path)}
            for name, path in required.items()
        ],
        "version": cfg["application"].get("version", "1.0 Alpha"),
        "build": cfg["application"].get("build", "0007"),
        "authenticated": authenticated(),
        "config_file": str(CONFIG_FILE),
        "data_folder": str(DATA_DIR),
        "obs": copy.deepcopy(last_obs_status),
        "engines": [
            {"name":"Roster Engine","version":"v1.1","status":"Healthy" if ROSTERS_FILE.exists() else "Needs Attention"},
            {"name":"Personnel Engine","version":"v1.0","status":"Healthy" if BROADCASTERS_FILE.exists() else "Needs Attention"},
            {"name":"Graphics Engine","version":"v2.1","status":"Healthy"},
            {"name":"Graphics Library","version":"v1.0","status":"Healthy"},
            {"name":"Asset Manager","version":"v1.0","status":"Healthy" if ASSETS_FILE.parent.exists() else "Needs Attention"},
            {"name":"Sponsor Engine","version":"v1.0","status":"Healthy" if SPONSORS_FILE.parent.exists() else "Needs Attention"},
            {"name":"Broadcast Package Engine","version":"v1.0","status":"Healthy" if PACKAGES_FILE.parent.exists() else "Needs Attention"},
            {"name":"Lineup Manager","version":"v1.0","status":"Healthy" if ROSTERS_FILE.exists() else "Needs Attention"},
        ],
        "channels": {"primary_graphics":"Healthy","scorebug":"Healthy"},
    }



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

def asset_by_id(asset_id: str) -> dict[str, Any] | None:
    return next((item for item in load_assets() if str(item.get("id")) == str(asset_id)), None)

def asset_file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

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


def clean_asset_record(incoming: dict[str, Any], existing_id: str = "") -> dict[str, Any]:
    category = str(incoming.get("category", "Other")).strip() or "Other"
    return {
        "id": existing_id or str(incoming.get("id", "")).strip() or f"asset-{int(time.time()*1000)}",
        "name": str(incoming.get("name", "")).strip(),
        "category": category,
        "asset_type": str(incoming.get("asset_type", "Other")).strip() or "Other",
        "file_url": str(incoming.get("file_url", "")).strip(),
        "source_url": str(incoming.get("source_url", "")).strip(),
        "rights_status": str(incoming.get("rights_status", "Unverified")).strip() or "Unverified",
        "rights_owner": str(incoming.get("rights_owner", "")).strip(),
        "notes": str(incoming.get("notes", "")).strip(),
        "active": bool(incoming.get("active", True)),
        "sha256": str(incoming.get("sha256", "")).strip(),
        "original_filename": str(incoming.get("original_filename", "")).strip(),
        "created_at": int(incoming.get("created_at", int(time.time())) or int(time.time())),
        "updated_at": int(time.time()),
    }

def load_logos() -> list[dict[str, Any]]:
    ensure_data_architecture()
    if not LOGOS_FILE.exists():
        save_json(LOGOS_FILE, [])
    data = load_json(LOGOS_FILE, [])
    return data if isinstance(data, list) else data.get("logos", [])

def save_logos(items: list[dict[str, Any]]) -> None:
    save_json(LOGOS_FILE, items)

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
    text = str(value or "1").strip().upper().replace("WEEK", "").strip()
    try:
        return f"W{int(text):02d}"
    except ValueError:
        cleaned = ''.join(ch for ch in text if ch.isalnum())[:3] or '01'
        return f"W{cleaned}"

def next_broadcast_id(sport: str, season: str, classification: str, week: Any) -> str:
    sport_code = {"football": "FB", "basketball": "BB", "baseball": "BSB", "softball": "SB"}.get(str(sport).lower(), str(sport)[:3].upper() or "EVT")
    season_code = ''.join(ch for ch in str(season) if ch.isdigit())[:4] or time.strftime("%Y")
    class_code = str(classification or "OPEN").upper().replace("CLASS", "").replace(" ", "")
    prefix = f"{sport_code}-{season_code}-{class_code}-{football_week_code(week)}-"
    used=[]
    for item in load_broadcasts():
        value=str(item.get("broadcast_id", ""))
        if value.startswith(prefix):
            try: used.append(int(value.rsplit("-",1)[1]))
            except (ValueError, IndexError): pass
    number=max(used, default=0)+1
    return f"{prefix}{number:03d}"

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

def normalize_social_url(platform: str, value: str) -> tuple[str, bool, str]:
    value = (value or "").strip()
    if not value:
        return "", True, ""
    if value.startswith("@"):
        value = value[1:]
    if "://" not in value and "/" not in value:
        domains = {
            "facebook": "https://facebook.com/",
            "x": "https://x.com/",
            "instagram": "https://instagram.com/",
            "youtube": "https://youtube.com/@",
        }
        if platform in domains:
            value = domains[platform] + value
        elif platform == "website":
            value = "https://" + value
    elif "://" not in value:
        value = "https://" + value

    try:
        hostname = (urlparse(value).hostname or "").lower()
    except ValueError:
        hostname = ""
    valid_domains = {
        "facebook": ("facebook.com", "www.facebook.com"),
        "x": ("x.com", "twitter.com", "www.x.com", "www.twitter.com"),
        "instagram": ("instagram.com", "www.instagram.com"),
        "youtube": ("youtube.com", "www.youtube.com", "youtu.be"),
    }
    if platform == "website":
        valid = bool(hostname) and value.lower().startswith(("http://", "https://"))
    else:
        valid = any(hostname == domain or hostname.endswith(f".{domain}") for domain in valid_domains.get(platform, ()))
    return value, valid, "" if valid else f"Expected a valid {platform} URL"

def normalize_social_block(block: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    normalized: dict[str, str] = {}
    errors: dict[str, str] = {}
    for platform in ("facebook", "x", "instagram", "youtube", "website"):
        value, valid, message = normalize_social_url(platform, str(block.get(platform, "")))
        normalized[platform] = value
        if not valid:
            errors[platform] = message
    return normalized, errors


def normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(DEFAULT_STATE)
    merged.update(state or {})
    if merged.get("broadcast_phase") not in {"pregame", "live", "halftime", "postgame", "final"}:
        merged["broadcast_phase"] = "pregame"
    if merged.get("possession") not in {"home", "visitor"}:
        merged["possession"] = "home"
    merged.setdefault("history", [])
    merged.setdefault("events", [])
    merged.setdefault("plays", [])
    # Backward-compatible migration: Alpha.1 events become canonical play records.
    if not merged["plays"] and merged["events"]:
        migrated = []
        for event in merged["events"]:
            play_number = int(event.get("play_number", len(migrated) + 1) or len(migrated) + 1)
            before = event.get("before") or {}
            after = event.get("after") or {}
            auto = event.get("automation") or {}
            migrated.append({
                "play_id": f"{merged.get('broadcast_id') or 'GAME'}-{play_number:04d}",
                "play_number": play_number,
                "event_id": event.get("id", ""),
                "broadcast_id": event.get("broadcast_id", merged.get("broadcast_id", "")),
                "quarter": str(event.get("quarter", after.get("quarter", merged.get("quarter", "1")))),
                "clock": str(event.get("clock", "")),
                "offense": event.get("team", before.get("possession", "")),
                "defense": "visitor" if event.get("team") == "home" else "home" if event.get("team") == "visitor" else "",
                "down": str(before.get("down", "")),
                "distance": str(before.get("distance", "")),
                "ball_spot": str(before.get("ball_spot", "")),
                "play_type": auto.get("play_type") or event.get("event", "").lower(),
                "result": event.get("description", ""),
                "yards": auto.get("yards", ""),
                "first_down": event.get("event") == "FIRST_DOWN",
                "touchdown": event.get("event") == "TD" or bool(auto.get("return_td")),
                "turnover": event.get("event") == "TURNOVER",
                "safety": event.get("event") == "SAFETY",
                "notes": "",
                "created_by": event.get("source", "broadcaster"),
                "created_at": event.get("created_at", 0),
                "label": event.get("label", event.get("event", "Play")),
                "undone": bool(event.get("undone", False)),
            })
        merged["plays"] = migrated
    merged.setdefault("correction_log", [])
    merged["next_play_number"] = max(1, int(merged.get("next_play_number", 1) or 1))
    if merged.get("game_data_authority") not in {"broadcaster", "statistician"}:
        merged["game_data_authority"] = "broadcaster"
    merged["statistician_enabled"] = merged.get("game_data_authority") == "statistician"
    return merged

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

def load_state() -> dict[str, Any]:
    state = normalize_state(STATE_REPOSITORY.load())
    if state.get("clock_running"):
        started = int(state.get("clock_started_at", 0) or 0)
        now = int(time.time())
        if started:
            elapsed = max(0, now - started)
            if elapsed:
                state["clock_seconds"] = max(0, int(state.get("clock_seconds", 0) or 0) - elapsed)
                state["clock_started_at"] = now
                if state["clock_seconds"] <= 0:
                    state["clock_running"] = False
                    state["clock_started_at"] = 0
                STATE_REPOSITORY.replace(normalize_state(state))
        else:
            state["clock_started_at"] = now
            STATE_REPOSITORY.replace(normalize_state(state))
    return state

def save_state(state: dict[str, Any]) -> None:
    normalized = normalize_state(state)
    STATE_REPOSITORY.replace(normalized)
    broadcast_id = str(normalized.get("broadcast_id", "")).strip()
    if not broadcast_id:
        return
    items = load_broadcasts()
    item = next((row for row in items if row.get("broadcast_id") == broadcast_id), None)
    if not item:
        return
    snapshot = copy.deepcopy(normalized)
    snapshot["history"] = []
    item["live_state"] = snapshot
    item["status"] = normalized.get("status", item.get("status", "planned"))
    item["updated_at"] = int(time.time())
    save_broadcasts(items)
    detail = DATA_DIR / "Broadcasts" / f"{broadcast_id}.json"
    detail.write_text(json.dumps(item, indent=2), encoding="utf-8")

def public_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return overlay-safe state. Logo values are application-relative HTTP paths."""
    result = copy.deepcopy(state)
    for key in ("home_identity", "visitor_identity"):
        identity = result.get(key)
        if isinstance(identity, dict):
            logo = str(identity.get("logo", "") or "")
            # Never expose local filesystem paths; retain only application URLs.
            if logo and not (logo.startswith("/") or logo.startswith("data:image/svg+xml") or logo.startswith("http://") or logo.startswith("https://")):
                identity["logo"] = ""
    personnel = result.get("personnel_graphic")
    if isinstance(personnel, dict):
        for field in ("headshot", "logo", "sponsor_logo"):
            value = str(personnel.get(field, "") or "")
            if value and not (value.startswith("/") or value.startswith("data:image/svg+xml") or value.startswith("http://") or value.startswith("https://")):
                personnel[field] = ""
    graphic = result.get("player_graphic")
    if isinstance(graphic, dict):
        for field in ("headshot", "team_logo", "sponsor_logo"):
            value = str(graphic.get(field, "") or "")
            if value and not (value.startswith("/") or value.startswith("data:image/svg+xml") or value.startswith("http://") or value.startswith("https://")):
                graphic[field] = ""
    # Alpha.3e: resolve roster names at display time so older jersey-only plays
    # immediately benefit from the active game roster without rewriting history.
    enriched_plays = []
    for source_play in list(result.get("plays") or []):
        play = copy.deepcopy(source_play)
        offense = canonical_team_key(result, play.get("offense", ""))
        defense = canonical_team_key(result, play.get("defense", ""))
        play["offense_name"] = canonical_team_name(result, offense)
        play["defense_name"] = canonical_team_name(result, defense)
        role_specs = (
            ("player", offense), ("passer", offense), ("receiver", offense),
            ("kicker", offense), ("returner", defense), ("sacker", defense),
        )
        for role, team_key in role_specs:
            number_key, name_key = f"{role}_number", f"{role}_name"
            number = str(play.get(number_key, "") or "").strip()
            if number and not str(play.get(name_key, "") or "").strip():
                resolved = resolve_game_roster_player(result, team_key, number)
                if resolved.get("name"):
                    play[name_key] = resolved["name"]
        # Rebuild legacy jersey-only results for the common offensive play types.
        kind = str(play.get("play_type", "") or "").lower()
        yards = play.get("yards", "")
        if kind == "run" and play.get("player_number") and play.get("player_name"):
            suffix = "kneel" if play.get("kneel") else "run"
            play["result"] = f"#{play['player_number']} {play['player_name']} {suffix} for {yards} yards"
            if play.get("touchdown"):
                play["result"] += ", touchdown"
            elif play.get("first_down"):
                play["result"] += ", first down"
        elif kind == "pass":
            outcome = str(play.get("pass_outcome", "complete") or "complete").lower()
            passer = f"#{play.get('passer_number','')} {play.get('passer_name','')}".strip()
            receiver = f"#{play.get('receiver_number','')} {play.get('receiver_name','')}".strip()
            if outcome == "complete" and receiver:
                play["result"] = f"{passer} complete to {receiver} for {yards} yards".strip()
                if play.get("touchdown"):
                    play["result"] += ", touchdown"
            elif outcome == "incomplete":
                play["result"] = f"{passer} pass incomplete".strip()
        enriched_plays.append(play)
    result["plays"] = enriched_plays
    return result

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
    snapshot = {k: copy.deepcopy(v) for k, v in state.items() if k != "history"}
    state.setdefault("history", []).append(snapshot)
    state["history"] = state["history"][-50:]

def apply_change(changes: dict[str, Any], save_undo: bool = True) -> dict[str, Any]:
    with lock:
        state = load_state()
        if save_undo:
            push_history(state)
        state.update(changes)
        save_state(state)
        return state

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
    return jsonify({"assets": load_assets()})

@app.post("/api/assets")
@require_auth
def api_assets_create():
    incoming = request.get_json(silent=True) or {}
    record = clean_asset_record(incoming)
    if not record["name"]:
        return jsonify({"error": "Asset name is required."}), 400
    items = load_assets(); items.append(record); save_assets(items)
    return jsonify({"asset": record})

@app.put("/api/assets/<asset_id>")
@require_auth
def api_assets_update(asset_id: str):
    incoming = request.get_json(silent=True) or {}
    items = load_assets(); found = False
    for index, item in enumerate(items):
        if str(item.get("id")) == asset_id:
            items[index] = clean_asset_record({**item, **incoming}, asset_id); found = True; break
    if not found: return jsonify({"error": "Asset not found."}), 404
    save_assets(items); return jsonify({"asset": items[index]})

@app.delete("/api/assets/<asset_id>")
@require_auth
def api_assets_delete(asset_id: str):
    items = load_assets(); remaining = [x for x in items if str(x.get("id")) != asset_id]
    if len(remaining) == len(items): return jsonify({"error": "Asset not found."}), 404
    save_assets(remaining); return jsonify({"ok": True})

@app.post("/api/assets/<asset_id>/upload")
@require_auth
def api_asset_upload(asset_id: str):
    upload = request.files.get("asset")
    if not upload or not upload.filename: return jsonify({"error": "Choose a file to upload."}), 400
    suffix = Path(upload.filename).suffix.lower()
    allowed = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".mp4", ".webm", ".mp3", ".wav", ".pdf"}
    if suffix not in allowed: return jsonify({"error": "Unsupported asset file type."}), 400
    duplicate_action = str(request.form.get("duplicate_action", "prompt")).lower()
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", asset_id).strip("-") or "asset"
    temp = ASSET_UPLOAD_DIR / f".upload-{secrets.token_hex(8)}{suffix}"
    upload.save(temp)
    sha256 = asset_file_hash(temp)
    items = load_assets(); found = False
    current = next((x for x in items if str(x.get("id")) == asset_id), None)
    if not current:
        temp.unlink(missing_ok=True)
        return jsonify({"error": "Save the asset record before uploading."}), 404
    duplicate = next((x for x in items if str(x.get("id")) != asset_id and x.get("sha256") == sha256 and x.get("active", True)), None)
    if duplicate and duplicate_action == "prompt":
        temp.unlink(missing_ok=True)
        return jsonify({"error": "DUPLICATE_ASSET", "duplicate_asset": duplicate}), 409
    if duplicate and duplicate_action == "reuse":
        temp.unlink(missing_ok=True)
        items = [x for x in items if str(x.get("id")) != asset_id]
        save_assets(items)
        return jsonify({"file_url": duplicate.get("file_url", ""), "asset": duplicate, "duplicate_asset": duplicate, "duplicate_reused": True, "pending_asset_removed": True})
    if duplicate and duplicate_action == "replace":
        existing_url = str(duplicate.get("file_url", ""))
        existing_name = existing_url.rsplit("/", 1)[-1] if existing_url.startswith("/asset-files/") else f"{duplicate['id']}{suffix}"
        target = ASSET_UPLOAD_DIR / existing_name
        temp.replace(target)
        duplicate.update({"file_url": f"/asset-files/{target.name}", "sha256": sha256, "original_filename": upload.filename, "updated_at": int(time.time())})
        items = [x for x in items if str(x.get("id")) != asset_id]
        save_assets(items)
        return jsonify({"file_url": duplicate["file_url"], "asset": duplicate, "duplicate_asset": duplicate, "duplicate_replaced": True, "pending_asset_removed": True})
    filename = f"{safe_id}-{int(time.time())}{suffix}"
    target = ASSET_UPLOAD_DIR / filename
    temp.replace(target)
    current.update({"file_url": f"/asset-files/{filename}", "sha256": sha256, "original_filename": upload.filename, "updated_at": int(time.time())})
    save_assets(items)
    return jsonify({"file_url": current["file_url"], "duplicate_asset": duplicate, "duplicate_kept": bool(duplicate)})

@app.get("/asset-files/<filename>")
def asset_file(filename: str):
    return send_from_directory(ASSET_UPLOAD_DIR, filename)

@app.get("/overlay")
def overlay():
    return render_template("overlay.html")

@app.get("/api/security-status")
def security_status():
    sec = load_security()
    remaining = max(0, int(sec.get("locked_until", 0) - time.time()))
    return jsonify({
        "pin_configured": bool(sec.get("pin_hash")),
        "authenticated": authenticated(),
        "locked_seconds": remaining,
    })

@app.post("/api/setup-pin")
def setup_pin():
    data = request.get_json(force=True)
    pin = str(data.get("pin", ""))
    confirm = str(data.get("confirm", ""))

    result = SECURITY_SERVICE.setup_pin(pin, confirm)
    if not result.ok:
        status = {
            "PIN_ALREADY_CONFIGURED": 409,
            "PIN_MUST_BE_6_DIGITS": 400,
            "PIN_MISMATCH": 400,
        }[result.code]
        return jsonify({"error": result.code}), status

    session.clear()
    session.permanent = True
    session["authenticated"] = True
    return jsonify({"ok": True})


@app.post("/api/login")
def login():
    data = request.get_json(force=True)
    pin = str(data.get("pin", ""))
    result = SECURITY_SERVICE.authenticate(pin)

    if result.ok:
        session.clear()
        session.permanent = True
        session["authenticated"] = True
        return jsonify({"ok": True})

    payload = {"error": result.code, **result.data}
    if result.code == "LOCKED":
        return jsonify(payload), 429

    return jsonify(payload), 401


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})




@app.get("/api/broadcasters")
@require_auth
def list_broadcasters():
    return jsonify(load_broadcasters())

@app.post("/api/broadcasters")
@require_auth
def create_broadcaster():
    incoming = request.get_json(force=True)
    name = str(incoming.get("full_name") or incoming.get("name", "")).strip()
    role = str(incoming.get("role") or incoming.get("primary_role", "Other"))
    if not name:
        return jsonify({"error": "STAFF_NAME_REQUIRED"}), 400
    if role not in STAFF_ROLES:
        return jsonify({"error": "INVALID_STAFF_ROLE"}), 400

    social, errors = normalize_social_block(incoming.get("social") or {})
    if errors:
        return jsonify({"error": "INVALID_SOCIAL_URL", "fields": errors}), 400

    items = load_broadcasters()
    staff_id = normalize_staff_id(incoming.get("id") or name)
    base_id = staff_id
    suffix = 2
    while any(item.get("id") == staff_id for item in items):
        staff_id = f"{base_id}-{suffix}"
        suffix += 1

    record = {
        "id": staff_id,
        "full_name": name, "name": name, "preferred_name": str(incoming.get("preferred_name", "")).strip(),
        "pronunciation": str(incoming.get("pronunciation", "")).strip(), "pronunciation_verified": bool(incoming.get("pronunciation_verified", False)),
        "category": str(incoming.get("category", "Other")), "role": role, "primary_role": role,
        "title": role, "organization": str(incoming.get("organization", "")).strip(),
        "school_id": str(incoming.get("school_id", "")).strip(), "bio": str(incoming.get("bio", "")).strip(),
        "headshot": normalize_personnel_headshot_url(incoming.get("headshot", "")), "status": "inactive" if str(incoming.get("status", "active")).lower()=="inactive" else "active",
        "producer": bool(incoming.get("producer", False)), "social": social,
    }
    items.append(record)
    save_broadcasters(items)
    return jsonify(record), 201

@app.put("/api/broadcasters/<broadcaster_id>")
@require_auth
def update_broadcaster(broadcaster_id: str):
    incoming = request.get_json(force=True)
    items = load_broadcasters()
    index = next((i for i, item in enumerate(items) if item.get("id") == broadcaster_id), None)
    if index is None:
        return jsonify({"error": "BROADCASTER_NOT_FOUND"}), 404

    name = str(incoming.get("full_name") or incoming.get("name", items[index].get("full_name") or items[index].get("name", ""))).strip()
    role = str(incoming.get("role") or incoming.get("primary_role", items[index].get("role") or items[index].get("primary_role", "Other")))
    if not name:
        return jsonify({"error": "STAFF_NAME_REQUIRED"}), 400
    if role not in STAFF_ROLES:
        return jsonify({"error": "INVALID_STAFF_ROLE"}), 400

    social, errors = normalize_social_block(incoming.get("social") or {})
    if errors:
        return jsonify({"error": "INVALID_SOCIAL_URL", "fields": errors}), 400

    items[index].update({
        "full_name": name, "name": name, "preferred_name": str(incoming.get("preferred_name", "")).strip(),
        "pronunciation": str(incoming.get("pronunciation", "")).strip(), "pronunciation_verified": bool(incoming.get("pronunciation_verified", False)),
        "category": str(incoming.get("category", "Other")), "role": role, "primary_role": role,
        "title": role, "organization": str(incoming.get("organization", "")).strip(),
        "school_id": str(incoming.get("school_id", "")).strip(), "bio": str(incoming.get("bio", "")).strip(),
        "headshot": normalize_personnel_headshot_url(incoming.get("headshot", "")), "status": "inactive" if str(incoming.get("status", "active")).lower()=="inactive" else "active",
        "producer": bool(incoming.get("producer", False)), "social": social,
    })
    save_broadcasters(items)
    return jsonify(items[index])

@app.delete("/api/broadcasters/<broadcaster_id>")
@require_auth
def delete_broadcaster(broadcaster_id: str):
    items = load_broadcasters()
    if not any(item.get("id") == broadcaster_id for item in items):
        return jsonify({"error": "BROADCASTER_NOT_FOUND"}), 404
    save_broadcasters([item for item in items if item.get("id") != broadcaster_id])
    return jsonify({"ok": True})

@app.get("/personnel-headshots/<filename>")
def personnel_headshot_file(filename: str):
    return send_from_directory(PERSONNEL_HEADSHOTS_DIR, filename)

@app.post("/api/personnel/<personnel_id>/headshot")
@require_auth
def upload_personnel_headshot(personnel_id: str):
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error":"FILE_REQUIRED"}), 400
    ext = Path(file.filename).suffix.lower()
    if ext not in {".png",".jpg",".jpeg",".webp"}:
        return jsonify({"error":"UNSUPPORTED_IMAGE"}), 400
    PERSONNEL_HEADSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    target = PERSONNEL_HEADSHOTS_DIR / f"{normalize_staff_id(personnel_id)}{ext}"
    file.save(target)
    rel = "/personnel-headshots/" + target.name
    items = load_broadcasters()
    for item in items:
        if str(item.get("id")) == personnel_id:
            item["headshot"] = rel
            save_broadcasters(items)
            return jsonify({"path":rel})
    return jsonify({"error":"PERSONNEL_NOT_FOUND"}), 404

@app.post("/api/validate-social")
@require_auth
def validate_social():
    incoming = request.get_json(force=True)
    platform = str(incoming.get("platform", ""))
    value, valid, message = normalize_social_url(platform, str(incoming.get("value", "")))
    return jsonify({"normalized": value, "valid": valid, "message": message})



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


@app.get("/api/schools")
@require_auth
def list_schools():
    return jsonify(get_school_service().list_schools())


@app.get("/api/schools/<school_id>")
@require_auth
def read_school(school_id: str):
    result = get_school_service().read(school_id)
    if result.code == "SCHOOL_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify(result.data["school"])


@app.post("/api/schools")
@require_auth
def create_school():
    result = get_school_service().create(
        request.get_json(force=True) or {}
    )
    if result.code == "SCHOOL_NAME_REQUIRED":
        return jsonify({"error": result.code}), 400
    if result.code == "LIKELY_DUPLICATE":
        return jsonify(
            {
                "error": result.code,
                "matches": result.data["matches"],
            }
        ), 409
    if result.code == "INVALID_SOCIAL_URL":
        return jsonify(
            {
                "error": result.code,
                "fields": result.data["fields"],
            }
        ), 400
    return jsonify(result.data["school"]), 201


@app.put("/api/schools/<school_id>")
@require_auth
def update_school(school_id: str):
    result = get_school_service().update(
        school_id,
        request.get_json(force=True) or {},
    )
    if result.code == "SCHOOL_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    if result.code == "INVALID_SOCIAL_URL":
        return jsonify(
            {
                "error": result.code,
                "fields": result.data["fields"],
            }
        ), 400
    return jsonify(result.data["school"])


@app.delete("/api/schools/<school_id>")
@require_auth
def delete_school(school_id: str):
    result = get_school_service().delete(school_id)
    if result.code == "SCHOOL_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify({"ok": True})


@app.post("/api/schools/duplicate-check")
@require_auth
def duplicate_check():
    incoming = request.get_json(force=True) or {}
    matches = get_school_service().duplicate_candidates(
        incoming,
        str(incoming.get("exclude_id", "")),
    )
    return jsonify({"matches": matches})


def _association_error_status(code: str) -> int:
    if code == "PROFILE_NOT_FOUND":
        return 404
    if code in {
        "PROFILE_ALREADY_EXISTS",
        "PROFILE_ID_CONFLICT",
        "PROFILE_PROTECTED",
        "IMPORT_APPROVAL_REQUIRED",
        "SOURCE_PREVIEW_REQUIRED",
        "SOURCE_CHANGED_SINCE_PREVIEW",
    }:
        return 409
    if code in {"SOURCE_FETCH_FAILED", "SOURCE_HOST_UNRESOLVED"}:
        return 502
    if code in {
        "PROFILE_READ_FAILED",
        "PROFILE_SAVE_FAILED",
        "PROFILE_DELETE_FAILED",
    }:
        return 500
    return 400


def _association_error_response(code: str):
    return jsonify({"error": code}), _association_error_status(code)


def _association_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _association_request_payload():
    supplied_content: bytes | str | None = None
    supplied_content_type = ""

    if request.files or request.form:
        payload: dict[str, Any] = request.form.to_dict(flat=True)
        profile_text = str(payload.get("profile", "")).strip()
        if profile_text:
            try:
                parsed_profile = json.loads(profile_text)
            except json.JSONDecodeError:
                return {}, None, "", "INVALID_PROFILE_JSON"
            if not isinstance(parsed_profile, dict):
                return {}, None, "", "INVALID_PROFILE_PAYLOAD"
            payload["profile"] = parsed_profile

        upload = request.files.get("source")
        if upload is not None and upload.filename:
            supplied_content = upload.read()
            supplied_content_type = str(upload.mimetype or "")
        else:
            supplied_content = payload.get("source_content")
            supplied_content_type = str(
                payload.get("source_content_type", "")
            )
    else:
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return {}, None, "", "INVALID_REQUEST_PAYLOAD"
        supplied_content = payload.get("source_content")
        supplied_content_type = str(payload.get("source_content_type", ""))

    if supplied_content is not None and not isinstance(
        supplied_content,
        (bytes, str),
    ):
        return {}, None, "", "INVALID_SOURCE_CONTENT"
    return payload, supplied_content, supplied_content_type, ""


def _resolve_association_profile(payload: dict[str, Any]):
    inline_profile = payload.get("profile")
    if inline_profile is not None:
        if not isinstance(inline_profile, dict):
            return None, "INVALID_PROFILE_PAYLOAD"
        return inline_profile, ""

    profile_id = str(payload.get("profile_id", "")).strip()
    if not profile_id:
        return None, "PROFILE_ID_REQUIRED"
    result = get_association_profile_service().read(profile_id)
    if not result.ok:
        return None, result.code
    return result.data["profile"], ""


@app.get("/api/imports/associations/profiles")
@require_auth
def list_association_profiles():
    result = get_association_profile_service().list_profiles()
    if not result.ok:
        return _association_error_response(result.code)
    return jsonify(result.data)


@app.get("/api/imports/associations/profiles/<profile_id>")
@require_auth
def read_association_profile(profile_id: str):
    result = get_association_profile_service().read(profile_id)
    if not result.ok:
        return _association_error_response(result.code)
    return jsonify(result.data["profile"])


@app.post("/api/imports/associations/profiles")
@require_auth
def create_association_profile():
    incoming = request.get_json(silent=True) or {}
    result = get_association_profile_service().create(incoming)
    if not result.ok:
        return _association_error_response(result.code)
    return jsonify(result.data["profile"]), 201


@app.put("/api/imports/associations/profiles/<profile_id>")
@require_auth
def update_association_profile(profile_id: str):
    incoming = request.get_json(silent=True) or {}
    result = get_association_profile_service().update(profile_id, incoming)
    if not result.ok:
        return _association_error_response(result.code)
    return jsonify(result.data["profile"])


@app.delete("/api/imports/associations/profiles/<profile_id>")
@require_auth
def delete_association_profile(profile_id: str):
    result = get_association_profile_service().delete(profile_id)
    if not result.ok:
        return _association_error_response(result.code)
    return jsonify(result.data)


@app.post("/api/imports/associations/preview")
@require_auth
def preview_association_import():
    payload, supplied_content, supplied_content_type, error = (
        _association_request_payload()
    )
    if error:
        return _association_error_response(error)
    profile, error = _resolve_association_profile(payload)
    if error:
        return _association_error_response(error)

    result = get_association_workflow_service().preview(
        profile,
        supplied_content=supplied_content,
        supplied_content_type=supplied_content_type,
    )
    if not result.ok:
        return _association_error_response(result.code)
    return jsonify(result.data)


@app.post("/api/imports/associations/import")
@require_auth
def apply_association_import():
    payload, supplied_content, supplied_content_type, error = (
        _association_request_payload()
    )
    if error:
        return _association_error_response(error)
    profile, error = _resolve_association_profile(payload)
    if error:
        return _association_error_response(error)

    create_venues = None
    if "create_venues" in payload:
        create_venues = _association_bool(payload.get("create_venues"))

    result = get_association_workflow_service().apply(
        profile,
        approved=_association_bool(payload.get("approved")),
        expected_sha256=str(payload.get("expected_sha256", "")),
        supplied_content=supplied_content,
        supplied_content_type=supplied_content_type,
        create_venues=create_venues,
        allow_possible_duplicates=_association_bool(
            payload.get("allow_possible_duplicates")
        ),
    )
    if not result.ok:
        return _association_error_response(result.code)
    return jsonify(result.data)


@app.get("/api/imports/mhsaa/5A/analyze")
@require_auth
def analyze_mhsaa_5a():
    profile = load_json(MHSAA_5A_PROFILE_FILE, {})
    manifest = load_json(MHSAA_5A_FILE, {"schools": []})
    result = get_association_import_service().analyze(
        profile,
        manifest.get("schools", []),
    )
    if not result.ok:
        return jsonify({"error": result.code}), 400

    schools = []
    for item in result.data.get("schools", []):
        candidate = dict(item.get("candidate") or {})
        candidate["status"] = item.get("status", "invalid")
        candidate["matches"] = item.get("matches", [])
        schools.append(candidate)

    return jsonify(
        {
            "classification": manifest.get("classification", "5A"),
            "source": manifest.get("source", {}),
            "found": result.data.get("found", len(schools)),
            "new": result.data.get("new", 0),
            "existing": result.data.get("existing", 0),
            "possible_duplicates": result.data.get(
                "possible_duplicates",
                0,
            ),
            "schools": schools,
        }
    )


@app.post("/api/imports/mhsaa/5A")
@require_auth
def import_mhsaa_5a():
    options = request.get_json(silent=True) or {}
    profile = load_json(MHSAA_5A_PROFILE_FILE, {})
    manifest = load_json(MHSAA_5A_FILE, {"schools": []})
    result = get_association_import_service().apply(
        profile,
        manifest.get("schools", []),
        create_venues=bool(options.get("create_venues", True)),
        # The legacy MHSAA importer only blocked exact-name matches.
        # Preserve that behavior while generic imports default to review.
        allow_possible_duplicates=True,
    )
    if not result.ok:
        return jsonify({"error": result.code}), 400

    return jsonify(
        {
            "imported": result.data.get("imported", 0),
            "skipped_existing": (
                result.data.get("enriched_existing", 0)
                + result.data.get("skipped_existing", 0)
            ),
            "created_ids": result.data.get("created_ids", []),
            "total_schools": result.data.get("total_schools", 0),
        }
    )


@app.get("/api/imports/mhsaa/5A/branding/analyze")
@require_auth
def analyze_mhsaa_5a_branding():
    manifest = load_json(MHSAA_5A_BRANDING_FILE, {"schools": []})
    result = get_association_supplement_service().analyze_branding(
        manifest.get("schools", []),
        source=manifest.get("source", {}),
    )
    if not result.ok:
        return jsonify({"error": result.code}), 400
    return jsonify(result.data)


@app.post("/api/imports/mhsaa/5A/branding")
@require_auth
def import_mhsaa_5a_branding():
    manifest = load_json(MHSAA_5A_BRANDING_FILE, {"schools": []})
    result = get_association_supplement_service().apply_branding(
        manifest.get("schools", []),
        source=manifest.get("source", {}),
    )
    if not result.ok:
        return jsonify({"error": result.code}), 400
    return jsonify(result.data)


@app.get("/api/imports/mhsaa/5A/enrichment/analyze")
@require_auth
def analyze_mhsaa_5a_enrichment():
    manifest = load_json(MHSAA_5A_ENRICHMENT_FILE, {"schools": []})
    result = get_association_supplement_service().analyze_enrichment(
        manifest.get("schools", []),
        source=manifest.get("source", {}),
        classification=str(manifest.get("classification", "5A")),
    )
    if not result.ok:
        return jsonify({"error": result.code}), 400
    return jsonify(result.data)


@app.post("/api/imports/mhsaa/5A/enrichment")
@require_auth
def enrich_mhsaa_5a():
    manifest = load_json(MHSAA_5A_ENRICHMENT_FILE, {"schools": []})
    result = get_association_supplement_service().apply_enrichment(
        manifest.get("schools", []),
        source=manifest.get("source", {}),
        venue_sport="Football",
    )
    if not result.ok:
        return jsonify({"error": result.code}), 400
    return jsonify(result.data)


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % rgb

def extract_logo_colors(image: Image.Image) -> list[str]:
    rgba = image.convert("RGBA")
    sample = rgba.copy(); sample.thumbnail((240, 240))
    chromatic=[]; white_count=0; black_count=0; visible=0
    for r,g,b,a in sample.getdata():
        if a < 64:
            continue
        visible += 1
        mx=max(r,g,b); mn=min(r,g,b); saturation=mx-mn
        if r >= 238 and g >= 238 and b >= 238:
            white_count += 1
            continue
        if r <= 28 and g <= 28 and b <= 28:
            black_count += 1
            continue
        if saturation < 16 and 45 < mx < 225:
            continue
        chromatic.append((r,g,b))
    ranked=[]
    if chromatic:
        strip=Image.new("RGB",(len(chromatic),1)); strip.putdata(chromatic)
        quant=strip.quantize(colors=10,method=Image.Quantize.MEDIANCUT).convert("RGB")
        counts=quant.getcolors(maxcolors=256) or []
        ranked=[rgb for _,rgb in sorted(counts,reverse=True)]
    chosen=[]
    for rgb in ranked:
        if all(sum((rgb[i]-other[i])**2 for i in range(3)) > 2600 for other in chosen):
            chosen.append(rgb)
        if len(chosen)==2:
            break
    if not chosen:
        chosen=[(128,128,128)]
    neutral = (255,255,255) if white_count >= black_count else (0,0,0)
    # Prefer a neutral secondary when it is visibly present; school branding commonly pairs one strong color with white/black.
    neutral_share=(max(white_count,black_count)/visible) if visible else 0
    if neutral_share >= 0.035:
        secondary=neutral
    elif len(chosen)>1:
        secondary=chosen[1]
    else:
        secondary=(255,255,255)
    return [_hex(chosen[0]), _hex(secondary)]

def normalize_round_logo(source: Image.Image, size: int) -> Image.Image:
    img=source.convert("RGBA")
    bbox=img.getbbox()
    if bbox: img=img.crop(bbox)
    max_content=int(size*0.92)
    scale=min(max_content/max(1,img.width), max_content/max(1,img.height))
    new_size=(max(1,round(img.width*scale)),max(1,round(img.height*scale)))
    img=img.resize(new_size,Image.Resampling.LANCZOS)
    canvas=Image.new("RGBA",(size,size),(0,0,0,0))
    canvas.alpha_composite(img,((size-img.width)//2,(size-img.height)//2))
    mask=Image.new("L",(size,size),0)
    from PIL import ImageDraw
    ImageDraw.Draw(mask).ellipse((0,0,size-1,size-1),fill=255)
    canvas.putalpha(ImageChops.multiply(canvas.getchannel("A"),mask))
    return canvas


@app.get("/school-logos/<school_id>/<filename>")
def school_logo_file(school_id: str, filename: str):
    return send_from_directory(DATA_DIR / "Logos" / normalize_school_id(school_id), filename)

@app.post("/api/schools/<school_id>/logo/process")
@require_auth
def process_school_logo(school_id: str):
    schools=load_schools(); school=next((x for x in schools if x.get("id")==school_id),None)
    if not school: return jsonify({"error":"SCHOOL_NOT_FOUND"}),404
    upload=request.files.get("logo")
    if not upload or not upload.filename: return jsonify({"error":"LOGO_FILE_REQUIRED"}),400
    try:
        raw=upload.read()
        image=Image.open(io.BytesIO(raw)); image.load()
    except Exception:
        return jsonify({"error":"INVALID_IMAGE"}),400
    folder=DATA_DIR / "Logos" / normalize_school_id(school_id); folder.mkdir(parents=True,exist_ok=True)
    ext=(Path(upload.filename).suffix.lower() or '.png')
    if ext not in ('.png','.jpg','.jpeg','.webp'): ext='.png'
    original=folder / f"original{ext}"; original.write_bytes(raw)
    master=normalize_round_logo(image,1024); scorebug=normalize_round_logo(image,256)
    master.save(folder/'round-master.png'); scorebug.save(folder/'round-scorebug.png')
    colors=extract_logo_colors(master)
    rel_master=f"/school-logos/{normalize_school_id(school_id)}/round-master.png"
    rel_score=f"/school-logos/{normalize_school_id(school_id)}/round-scorebug.png"
    logo_id=f"{school.get('csrn_id') or school_id}-primary"
    school['primary_logo']=rel_master; school['default_broadcast_logo_id']=logo_id; school['logo_status']='candidate'
    school['primary_color']=colors[0]; school['secondary_color']=colors[1]
    school.setdefault('logo_metadata',{}).update({
        'original_filename':upload.filename,'original_path':str(original.relative_to(BASE_DIR)).replace('\\','/'),
        'round_master_path':rel_master,'scorebug_path':rel_score,'approval_status':'candidate',
        'transparent_background_status':'normalized','shape_standard':'round','master_canvas':'1024x1024-round',
        'safe_area':'circle-92-percent','scorebug_derivative':'256x256-round','extracted_colors':colors
    })
    save_schools(schools)
    logos=load_logos(); record=next((x for x in logos if x.get('id')==logo_id),None)
    payload={'id':logo_id,'school_id':school_id,'csrn_school_id':school.get('csrn_id',''),'designation':'primary',
             'approval_status':'candidate','original_path':str(original.relative_to(BASE_DIR)).replace('\\','/'),
             'round_master_path':rel_master,'scorebug_path':rel_score,'extracted_colors':colors}
    if record: record.update(payload)
    else: logos.append(payload)
    save_logos(logos)
    return jsonify({'school':school,'logo':payload,'primary_color':colors[0],'secondary_color':colors[1],
                    'preview_url':rel_master,'message':'Round candidate logo created; review colors and approve before broadcast use.'})

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
    return jsonify(load_logos())


@app.get("/api/upgrade/candidate")
def upgrade_candidate():
    return jsonify(inspect_candidate(BASE_DIR))

@app.get("/api/upgrade/status")
def upgrade_status():
    return jsonify(copy.deepcopy(last_upgrade_report))

@app.post("/api/upgrade/migrate")
def run_upgrade_migration():
    incoming = request.get_json(silent=True) or {}
    include_security = bool(incoming.get("include_security", True))
    with upgrade_lock:
        report = migrate(BASE_DIR, DEFAULT_CONFIG, include_security=include_security)
        last_upgrade_report.clear()
        last_upgrade_report.update(report)
    if report.get("security_migrated"):
        # Migration occurs before authentication, so the migrated session-signing
        # key can be activated safely without restarting the server.
        app.secret_key = load_security()["secret_key"]
    report["active_pin"] = (
        "PREVIOUS_PIN" if report.get("security_migrated")
        else "CREATE_NEW_PIN"
    )
    report["pin_message"] = (
        "Migration is complete. Unlock the Production Suite with the operator PIN from the previous build."
        if report.get("security_migrated") else
        "Migration is complete. Create a new 6-digit operator PIN on this screen."
    )
    return jsonify(report)


@app.get("/api/obs/status")
@require_auth
def obs_status():
    return jsonify(copy.deepcopy(last_obs_status))

@app.post("/api/obs/test")
@require_auth
def test_obs_connection():
    cfg = load_config()
    with obs_status_lock:
        result = validate_obs_read_only(cfg.get("obs", {}))
        last_obs_status.clear()
        last_obs_status.update(result)
    return jsonify(result)


def command_scorebug_visibility(visible: bool) -> dict[str, Any]:
    cfg = load_config()
    obs_settings = cfg.get("obs", {})
    if not obs_settings.get("controlled_commands", False):
        raise OBSConnectionError("Controlled OBS commands are disabled in Settings.")
    result = set_scorebug_visibility(obs_settings, visible)
    with obs_status_lock:
        last_obs_status.clear()
        last_obs_status.update(result)
    return result


@app.post("/api/obs/scorebug-visibility")
@require_auth
def obs_scorebug_visibility():
    incoming = request.get_json(force=True)
    visible = incoming.get("visible")
    if not isinstance(visible, bool):
        return jsonify({"error": "VISIBLE_MUST_BE_BOOLEAN"}), 400
    try:
        result = command_scorebug_visibility(visible)
    except OBSConnectionError as exc:
        return jsonify({"error": "OBS_COMMAND_BLOCKED", "message": str(exc)}), 409
    return jsonify(result)


@app.post("/api/obs/program-visual-mode")
@require_auth
def obs_program_visual_mode():
    incoming = request.get_json(force=True)
    mode = str(incoming.get("mode", "")).lower()
    cfg = load_config()
    if not cfg.get("obs", {}).get("controlled_commands", False):
        return jsonify({"error": "OBS_COMMAND_BLOCKED", "message": "Controlled OBS commands are disabled in Settings."}), 409
    try:
        result = set_program_visual_mode(cfg.get("obs", {}), mode)
    except OBSConnectionError as exc:
        return jsonify({"error": "OBS_COMMAND_BLOCKED", "message": str(exc)}), 409
    with obs_status_lock:
        last_obs_status.clear()
        last_obs_status.update(result)
    with lock:
        state = load_state()
        push_history(state)
        state["visual_mode"] = mode
        save_state(state)
    return jsonify({"state": state, "obs": result})


@app.get("/api/config")
@require_auth
def get_config():
    return jsonify(load_config())

@app.post("/api/config")
@require_auth
def update_config():
    incoming = request.get_json(force=True)
    current = load_config()
    if "social" in incoming:
        normalized_social, social_errors = normalize_social_block(incoming.get("social") or {})
        if social_errors:
            return jsonify({"error": "INVALID_SOCIAL_URL", "fields": social_errors}), 400
        incoming["social"] = normalized_social
    for section in current:
        if section in incoming and isinstance(incoming[section], dict):
            current[section].update(incoming[section])
    # Protect application identity fields.
    current["application"]["version"] = RUNTIME_VERSION
    current["application"]["build"] = RUNTIME_BUILD
    save_config(current)
    return jsonify(current)

@app.get("/api/diagnostics")
@require_auth
def diagnostics():
    return jsonify(diagnostic_status())

@app.get("/api/state")
def get_state():
    # Read-only endpoint for both authenticated control devices and OBS overlay.
    return jsonify(public_state(load_state()))

def update_linked_broadcast_status(broadcast_id: str, status: str, extra: dict[str, Any] | None = None) -> None:
    if not broadcast_id:
        return
    items = load_broadcasts()
    item = next((x for x in items if x.get("broadcast_id") == broadcast_id), None)
    if not item:
        return
    item["status"] = status
    item["updated_at"] = int(time.time())
    if status == "live": item.setdefault("started_at", int(time.time()))
    if status == "completed": item["completed_at"] = int(time.time())
    if extra: item.update(extra)
    save_broadcasts(items)
    path = DATA_DIR / "Broadcasts" / f"{broadcast_id}.json"
    path.write_text(json.dumps(item, indent=2), encoding="utf-8")

def migrate_venue_names() -> None:
    get_venue_service().migrate_legacy_names()


def readiness_payload() -> dict[str, Any]:
    state=load_state(); cfg=load_config(); obs=copy.deepcopy(last_obs_status); checks=[]
    def add(key,label,ok,note,action=""): checks.append({"key":key,"label":label,"ok":bool(ok),"note":note,"action":action})
    add("obs","OBS WebSocket",bool(obs.get("reachable") and obs.get("authenticated")),"Connected and authenticated.","Open OBS, enable the WebSocket server, then retry.")
    add("scene","Scorebug scene",bool(obs.get("required_scene_exists")),"Required scorebug scene found.",f"In OBS create or load scene: {cfg.get('obs',{}).get('required_scene','10.01 - FOOTBALL SCOREBUG')}")
    add("browser","Browser source",bool(obs.get("browser_source_exists")),"Browser source found; a hidden scorebug is still ready.",f"In OBS add Browser Source {cfg.get('obs',{}).get('browser_source','BRWSR - Football Scorebug')} using http://127.0.0.1:5050/overlay")
    add("overlay","Overlay endpoint",True,"Overlay endpoint is reachable.")
    add("visual","Program visual",bool(cfg.get("obs",{}).get("program_visual_scene")),"Program Visual is configured.","Configure the Program Visual scene in Settings.")
    return {"ready":all(c["ok"] for c in checks),"checks":checks,"overlay_url":"http://127.0.0.1:5050/overlay","state":public_state(state)}

@app.get("/api/readiness")
@require_auth
def readiness():
    migrate_venue_names()
    return jsonify(readiness_payload())

@app.post("/api/broadcasts/<broadcast_id>/load")
@require_auth
def load_planned_broadcast(broadcast_id: str):
    item = next((x for x in load_broadcasts() if x.get("broadcast_id") == broadcast_id and not x.get("archived")), None)
    if not item:
        return jsonify({"error": "NOT_FOUND"}), 404
    current = load_state()
    if current.get("broadcast_id") == broadcast_id and current.get("broadcast_created"):
        return jsonify(current)
    snapshot = item.get("live_state") if isinstance(item.get("live_state"), dict) else None
    if snapshot:
        state = normalize_state(snapshot)
    else:
        state = copy.deepcopy(DEFAULT_STATE)
        state.update({
            "broadcast_created": True, "broadcast_id": broadcast_id,
            "sport": item.get("sport", "Football"), "season": item.get("season", ""),
            "week": item.get("week", "1"), "classification": item.get("classification", ""),
            "level": item.get("level", "Varsity"), "division": item.get("division", "Boys"),
            "home_school_id": item.get("home_school_id", ""), "visitor_school_id": item.get("visitor_school_id", ""),
            "home_team": item.get("home_team", "Home"), "visitor_team": item.get("visitor_team", "Visitor"),
            "home_identity": item.get("home_identity") or broadcast_identity(get_school(item.get("home_school_id", "")), item.get("sport", "Football")),
            "visitor_identity": item.get("visitor_identity") or broadcast_identity(get_school(item.get("visitor_school_id", "")), item.get("sport", "Football")),
            "venue_id": item.get("venue_id", ""), "venue": item.get("venue", ""),
            "date": item.get("date", ""), "scheduled_start": item.get("scheduled_start", "07:00 PM"),
            "visual_mode": item.get("visual_mode", "graphic"), "crew": item.get("crew", {}),
            "status": item.get("status", "planned"),
            "broadcast_phase": "final" if item.get("status") == "completed" else ("live" if item.get("status") == "live" else "pregame"),
            "scorebug_visible": False,
            "home_score": item.get("final_home_score", 0) if item.get("status") == "completed" else 0,
            "visitor_score": item.get("final_visitor_score", 0) if item.get("status") == "completed" else 0,
        })
    # Alpha.3f: restore roster links whenever a broadcast is loaded directly,
    # including resumed live-state snapshots created before roster persistence.
    package = next((p for p in load_packages() if p.get("broadcast_id") == broadcast_id), None)
    if package:
        state["broadcast_package_id"] = package.get("id", state.get("broadcast_package_id", ""))
        state["package_roster_ids"] = list(package.get("roster_ids") or state.get("package_roster_ids") or [])
    state["status"] = item.get("status", state.get("status", "planned"))
    state["review_mode"] = state["status"] == "completed"
    # Reconcile a saved snapshot with the status selected in Game Manager.
    # This allows a completed game to be changed back to Live and reopened.
    if state["status"] == "live":
        state["broadcast_phase"] = "live"
    elif state["status"] == "planned":
        state["broadcast_phase"] = "pregame"
    elif state["status"] == "completed":
        state["broadcast_phase"] = "final"
    save_state(state)
    return jsonify(state)

@app.post("/api/initialize-broadcast")
@require_auth
def initialize_broadcast():
    # Compatibility endpoint retained for older clients. The Prepared stage was removed.
    state = load_state()
    if not state.get("broadcast_id"):
        return jsonify({"error": "NO_ACTIVE_BROADCAST"}), 409
    payload = readiness_payload()
    return jsonify({"state": state, "readiness": payload, "deprecated": True})

@app.post("/api/start-broadcast")
@require_auth
def start_broadcast():
    state=load_state()
    if not state.get("broadcast_id"):
        return jsonify({"error":"NO_ACTIVE_BROADCAST"}),409
    state["status"]="live"
    state["broadcast_phase"]="live"
    state["scorebug_visible"]=True
    save_state(state)
    update_linked_broadcast_status(state["broadcast_id"],"live")
    obs_result=None
    if load_config().get("obs", {}).get("controlled_commands", False):
        try:
            obs_result=command_scorebug_visibility(True)
        except OBSConnectionError as exc:
            obs_result={"error":str(exc)}
    record=next((x for x in load_broadcasts() if x.get("broadcast_id")==state["broadcast_id"]),None)
    return jsonify({"state":public_state(state),"broadcast":record,"obs":obs_result})

@app.post("/api/resume-broadcast")
@require_auth
def resume_broadcast():
    """Reopen a completed broadcast without discarding its saved game data."""
    with lock:
        state = load_state()
        broadcast_id = str(state.get("broadcast_id", "")).strip()
        if not broadcast_id:
            return jsonify({"error": "NO_ACTIVE_BROADCAST"}), 409
        state["status"] = "live"
        state["broadcast_phase"] = "live"
        state["review_mode"] = False
        # Keep the scorebug hidden until the operator deliberately shows it.
        state["scorebug_visible"] = False
        save_state(state)
        items = load_broadcasts()
        item = next((row for row in items if row.get("broadcast_id") == broadcast_id), None)
        if item:
            item["status"] = "live"
            item["updated_at"] = int(time.time())
            item.pop("completed_at", None)
            item.pop("final_home_score", None)
            item.pop("final_visitor_score", None)
            save_broadcasts(items)
            detail = DATA_DIR / "Broadcasts" / f"{broadcast_id}.json"
            detail.write_text(json.dumps(item, indent=2), encoding="utf-8")
        return jsonify(public_state(state))

@app.post("/api/create-broadcast")
@require_auth
def create_broadcast():
    data = request.get_json(force=True)
    cfg = load_config()
    defaults = cfg["broadcast_defaults"]
    sport = data.get("sport", defaults.get("sport", "Football"))
    home_school_id = str(data.get("home_school_id", "")).strip()
    visitor_school_id = str(data.get("visitor_school_id", "")).strip()
    home_school = get_school(home_school_id) if home_school_id else None
    visitor_school = get_school(visitor_school_id) if visitor_school_id else None
    home_name = (str(home_school.get("broadcast_name", "")).strip() if home_school else str(data.get("home_team", "")).strip()) or "Home"
    visitor_name = (str(visitor_school.get("broadcast_name", "")).strip() if visitor_school else str(data.get("visitor_team", "")).strip()) or "Visitor"
    classification = str(data.get("classification") or (home_school or {}).get("classification") or (visitor_school or {}).get("classification") or "Open").strip()
    season = str(data.get("season") or time.strftime("%Y")).strip()
    week = str(data.get("week") or "1").strip()
    venue = venue_for_school(home_school, sport)
    venue_name = str(data.get("venue") or (venue or {}).get("name") or defaults.get("venue", "Caledonia High School")).strip()
    venue_id = str((venue or {}).get("id", ""))
    broadcast_id = next_broadcast_id(sport, season, classification, week)
    state = copy.deepcopy(DEFAULT_STATE)
    state.update({
        "broadcast_created": True, "broadcast_id": broadcast_id, "sport": sport,
        "season": season, "week": week, "classification": classification,
        "level": data.get("level", "Varsity"), "division": data.get("division", "Boys"),
        "home_team": home_name, "visitor_team": visitor_name,
        "home_school_id": home_school_id, "visitor_school_id": visitor_school_id,
        "home_identity": broadcast_identity(home_school, sport),
        "visitor_identity": broadcast_identity(visitor_school, sport),
        "venue": venue_name, "venue_id": venue_id,
        "date": data.get("date", ""), "scheduled_start": data.get("scheduled_start", "07:00 PM"),
        "visual_mode": data.get("visual_mode", defaults.get("visual_mode", "graphic")),
        "production_type": str(data.get("production_type", "game") or "game"),
        "broadcast_phase": "pregame", "status": "planned",
        "crew": {key: str(data.get("crew", {}).get(key, "")) for key in ("play_by_play", "color_analyst", "sideline_reporter", "statistician", "producer")},
    })
    # Planning in Game Manager does not change live OBS program state.
    record = {
        "broadcast_id": broadcast_id, "created_at": int(time.time()), "updated_at": int(time.time()),
        "status": "planned", "sport": sport, "season": season, "classification": classification, "week": week,
        "date": state["date"], "scheduled_start": state["scheduled_start"],
        "home_school_id": home_school_id, "visitor_school_id": visitor_school_id,
        "home_team": home_name, "visitor_team": visitor_name,
        "home_identity": state["home_identity"], "visitor_identity": state["visitor_identity"],
        "venue_id": venue_id, "venue": venue_name, "graphics_profile": "CSRN Default",
        "obs_profile": cfg.get("obs", {}).get("profile", "CSRN Production"),
        "visual_mode": state["visual_mode"], "crew": state["crew"],
        "production_type": state.get("production_type", "game")
    }
    with lock:
        items = load_broadcasts()
        items.append(record)
        save_broadcasts(items)
        (DATA_DIR / "Broadcasts" / f"{broadcast_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    warnings=[]
    for side,school in (("Home",home_school),("Visitor",visitor_school)):
        if school and not logo_certification(school)[0]:
            warnings.append(f"{side} has no certified logo; {school_monogram(school.get('broadcast_name') or school.get('official_name',''))} monogram will be used.")
    return jsonify({"broadcast": record, "warnings": warnings})

@app.get("/api/broadcasts")
@require_auth
def list_broadcasts():
    items = [item for item in load_broadcasts() if not item.get("archived")]
    items = sorted(items, key=lambda x: (str(x.get("date", "")), str(x.get("scheduled_start", ""))), reverse=True)
    return jsonify(items)

@app.get("/api/broadcasts/<broadcast_id>")
@require_auth
def get_broadcast_record(broadcast_id: str):
    item=next((x for x in load_broadcasts() if x.get("broadcast_id") == broadcast_id), None)
    return (jsonify(item), 200) if item else (jsonify({"error":"NOT_FOUND"}),404)

@app.put("/api/broadcasts/<broadcast_id>")
@require_auth
def update_broadcast_record(broadcast_id: str):
    data=request.get_json(force=True); items=load_broadcasts(); item=next((x for x in items if x.get("broadcast_id")==broadcast_id),None)
    if not item: return jsonify({"error":"NOT_FOUND"}),404
    home_id=str(data.get("home_school_id",item.get("home_school_id","")) or ""); visitor_id=str(data.get("visitor_school_id",item.get("visitor_school_id","")) or "")
    home=get_school(home_id) if home_id else None; visitor=get_school(visitor_id) if visitor_id else None
    for key in ("sport","season","classification","week","level","division","date","scheduled_start","venue","venue_id","visual_mode","crew"):
        if key in data: item[key]=data[key]
    item.update({"home_school_id":home_id,"visitor_school_id":visitor_id,"home_team":(home or {}).get("broadcast_name") or data.get("home_team") or item.get("home_team"),"visitor_team":(visitor or {}).get("broadcast_name") or data.get("visitor_team") or item.get("visitor_team"),"home_identity":broadcast_identity(home,item.get("sport","Football")) if home else item.get("home_identity",{}),"visitor_identity":broadcast_identity(visitor,item.get("sport","Football")) if visitor else item.get("visitor_identity",{}),"updated_at":int(time.time())})
    save_broadcasts(items); (DATA_DIR/"Broadcasts"/f"{broadcast_id}.json").write_text(json.dumps(item,indent=2),encoding="utf-8")
    state=load_state()
    if state.get("broadcast_id")==broadcast_id:
        for key in ("sport","season","classification","week","level","division","date","scheduled_start","venue","venue_id","visual_mode","crew","home_school_id","visitor_school_id","home_team","visitor_team","home_identity","visitor_identity"):
            if key in item: state[key]=copy.deepcopy(item[key])
        save_state(state)
    warnings=[]
    for side,school in (("Home",home),("Visitor",visitor)):
        if school and not logo_certification(school)[0]: warnings.append(f"{side} has no certified logo; {school_monogram(school.get('broadcast_name') or school.get('official_name',''))} monogram will be used.")
    return jsonify({"broadcast":item,"warnings":warnings})

@app.put("/api/broadcasts/<broadcast_id>/status")
@require_auth
def set_broadcast_status(broadcast_id: str):
    incoming=request.get_json(force=True); status=str(incoming.get("status", "")).lower()
    if status == "prepared":
        status = "planned"
    if status not in {"planned","live","completed"}: return jsonify({"error":"INVALID_STATUS"}),400
    items=load_broadcasts(); item=next((x for x in items if x.get("broadcast_id") == broadcast_id), None)
    if not item: return jsonify({"error":"NOT_FOUND"}),404
    item["status"]=status; item["updated_at"]=int(time.time()); save_broadcasts(items)
    path=DATA_DIR/"Broadcasts"/f"{broadcast_id}.json"
    if path.exists(): path.write_text(json.dumps(item,indent=2),encoding="utf-8")
    return jsonify(item)

@app.delete("/api/broadcasts/<broadcast_id>")
@require_auth
def delete_broadcast_record(broadcast_id: str):
    items=load_broadcasts()
    item=next((x for x in items if x.get("broadcast_id")==broadcast_id),None)
    if not item:
        return jsonify({"error":"NOT_FOUND"}),404
    items=[x for x in items if x.get("broadcast_id")!=broadcast_id]
    save_broadcasts(items)
    detail=DATA_DIR / "Broadcasts" / f"{broadcast_id}.json"
    if detail.exists():
        detail.unlink()
    state=load_state()
    if state.get("broadcast_id")==broadcast_id:
        save_state(copy.deepcopy(DEFAULT_STATE))
    return jsonify({"deleted":broadcast_id})

@app.get("/api/build-journal")
@require_auth
def build_journal():
    return jsonify(load_build_journal())

@app.post("/api/score")
@require_auth
def update_score():
    data = request.get_json(force=True)
    team = data.get("team")
    delta = int(data.get("delta", 0))
    if team not in {"home", "visitor"} or delta not in {-1, 1, 2, 3, 6}:
        return jsonify({"error": "INVALID_SCORE_REQUEST"}), 400
    with lock:
        state = load_state()
        source = str(data.get("source", "broadcaster") or "broadcaster").lower()
        if not game_data_source_allowed(state, source):
            return authority_rejection(state)
        push_history(state)
        key = "home_score" if team == "home" else "visitor_score"
        state[key] = max(0, int(state.get(key, 0)) + delta)
        if state["broadcast_phase"] == "pregame":
            state["broadcast_phase"] = "live"
        save_state(state)
        if state.get("broadcast_id") and state.get("status") != "live":
            state["status"]="live"; save_state(state); update_linked_broadcast_status(state["broadcast_id"],"live")
    return jsonify(state)

@app.post("/api/set")
@require_auth
def set_value():
    data = request.get_json(force=True) or {}
    allowed = {"quarter", "down", "distance", "clock_visible", "possession", "scorebug_visible", "broadcast_phase", "ticker_visible", "ticker_speed", "ticker_pause"}
    game_data_fields = {"quarter", "down", "distance", "possession"}
    changes = {k: v for k, v in data.items() if k in allowed}
    state = load_state()
    source = str(data.get("source", "broadcaster") or "broadcaster").lower()
    if game_data_fields.intersection(changes) and not game_data_source_allowed(state, source):
        return authority_rejection(state)
    return jsonify(apply_change(changes))


@app.get("/roster-headshots/<filename>")
def roster_headshot_file(filename: str):
    return send_from_directory(HEADSHOTS_DIR, filename)

@app.post("/api/rosters/<roster_id>/players/<player_id>/headshot")
@require_auth
def upload_player_headshot(roster_id: str, player_id: str):
    upload = request.files.get("headshot")
    if not upload or not upload.filename:
        return jsonify({"error": "HEADSHOT_FILE_REQUIRED"}), 400
    ext = Path(upload.filename).suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        return jsonify({"error": "UNSUPPORTED_IMAGE_TYPE"}), 400
    try:
        raw = upload.read()
        image = Image.open(io.BytesIO(raw))
        image.load()
        if image.width < 64 or image.height < 64:
            return jsonify({"error": "IMAGE_TOO_SMALL"}), 400
    except Exception:
        return jsonify({"error": "INVALID_IMAGE"}), 400
    rosters = load_rosters()
    roster = next((r for r in rosters if str(r.get("id")) == roster_id), None)
    if not roster:
        return jsonify({"error": "ROSTER_NOT_FOUND"}), 404
    player = next((p for p in roster.get("players", []) if str(p.get("id")) == player_id), None)
    if not player:
        return jsonify({"error": "PLAYER_NOT_FOUND"}), 404
    safe_roster = re.sub(r"[^A-Za-z0-9_-]+", "-", roster_id).strip("-") or "roster"
    safe_player = re.sub(r"[^A-Za-z0-9_-]+", "-", player_id).strip("-") or "player"
    filename = f"{safe_roster}__{safe_player}{ext}"
    path = HEADSHOTS_DIR / filename
    path.write_bytes(raw)
    url = f"/roster-headshots/{filename}"
    player["headshot"] = url
    player["headshot_source"] = "uploaded"
    player["headshot_original_filename"] = upload.filename
    save_rosters(rosters)
    return jsonify({"headshot": url, "player": player})


def activate_primary_graphic(state: dict[str, Any], active: str) -> None:
    """Only one primary identification graphic may be visible at a time."""
    mapping = {"lower_third": "lower_third", "player": "player_graphic", "personnel": "personnel_graphic"}
    for channel, key in mapping.items():
        if channel != active:
            item = dict(state.get(key) or {})
            item["visible"] = False; item["expires_at"] = 0
            state[key] = item
    state["primary_graphic_channel"] = active

@app.post("/api/graphics/lower-third")
@require_auth
def update_lower_third():
    data = request.get_json(force=True) or {}
    action = str(data.get("action", "update")).lower()
    with lock:
        state = load_state()
        current = dict(state.get("lower_third") or {})
        defaults = copy.deepcopy(DEFAULT_STATE["lower_third"])
        defaults.update(current)
        if action == "clear":
            lower = copy.deepcopy(DEFAULT_STATE["lower_third"])
        else:
            lower = defaults
            for key in ("eyebrow", "headline", "secondary", "footer", "logo_source", "accent_source", "custom_accent"):
                if key in data:
                    lower[key] = str(data.get(key, ""))[:180]
            try:
                lower["duration"] = max(0, min(120, int(data.get("duration", lower.get("duration", 0)) or 0)))
            except (TypeError, ValueError):
                lower["duration"] = 0
            if action == "hide":
                lower["visible"] = False
                lower["expires_at"] = 0
            elif action in {"show", "update"}:
                activate_primary_graphic(state, "lower_third")
                lower["visible"] = bool(data.get("visible", action == "show"))
                if lower["visible"] and lower["duration"] > 0:
                    lower["expires_at"] = int(time.time()) + lower["duration"]
                elif lower["visible"]:
                    lower["expires_at"] = 0
            lower["updated_at"] = int(time.time())
        state["lower_third"] = lower
        save_state(state)
    return jsonify(public_state(state))

@app.post("/api/graphics/player")
@require_auth
def update_player_graphic():
    data = request.get_json(force=True) or {}
    action = str(data.get("action", "update")).lower()
    with lock:
        state = load_state()
        current = dict(state.get("player_graphic") or {})
        defaults = copy.deepcopy(DEFAULT_STATE["player_graphic"])
        defaults.update(current)
        if action == "clear":
            graphic = copy.deepcopy(DEFAULT_STATE["player_graphic"])
        else:
            graphic = defaults
            for key in ("graphic_type", "roster_id", "player_id", "eyebrow"):
                if key in data:
                    graphic[key] = str(data.get(key, ""))[:240]
            sponsor_warning = apply_sponsor_to_graphic(graphic, data)
            roster_id = str(data.get("roster_id", graphic.get("roster_id", ""))).strip()
            player_id = str(data.get("player_id", graphic.get("player_id", ""))).strip()
            roster = next((r for r in load_rosters() if str(r.get("id")) == roster_id), None)
            player = next((p for p in (roster or {}).get("players", []) if str(p.get("id")) == player_id), None)
            if roster and player:
                school = next((sc for sc in load_schools() if str(sc.get("id")) == str(roster.get("school_id"))), {})
                full_name = " ".join([str(player.get("first_name", "")).strip(), str(player.get("last_name", "")).strip()]).strip()
                display_name = str(player.get("preferred_name", "")).strip() or full_name
                identity = broadcast_identity(school, str(roster.get("sport", "Football"))) if school else {}
                graphic.update({
                    "school_id": roster.get("school_id", ""),
                    "full_name": full_name,
                    "display_name": display_name,
                    "number": str(player.get("number", "")),
                    "position": str(player.get("position", "")),
                    "secondary_position": str(player.get("secondary_position", "")),
                    "grade": str(player.get("grade", "")),
                    "height": str(player.get("height", "")),
                    "weight": str(player.get("weight", "")),
                    "headshot": str(player.get("headshot", "")),
                    "team_logo": str(identity.get("logo", "")),
                    "team_name": str(school.get("broadcast_name") or school.get("official_name") or roster.get("school_id", "")),
                    "team_color": str(identity.get("primary_color") or school.get("primary_color") or "#C9203B"),
                })
            try:
                graphic["duration"] = max(0, min(120, int(data.get("duration", graphic.get("duration", 0)) or 0)))
            except (TypeError, ValueError):
                graphic["duration"] = 0
            if action == "hide":
                graphic["visible"] = False
                graphic["expires_at"] = 0
            elif action in {"show", "update"}:
                if not graphic.get("player_id"):
                    return jsonify({"error": "PLAYER_REQUIRED"}), 400
                activate_primary_graphic(state, "player")
                graphic["visible"] = bool(data.get("visible", action == "show"))
                if graphic["visible"] and graphic["duration"] > 0:
                    graphic["expires_at"] = int(time.time()) + graphic["duration"]
                elif graphic["visible"]:
                    graphic["expires_at"] = 0
            graphic["updated_at"] = int(time.time())
        state["player_graphic"] = graphic
        save_state(state)
    response = public_state(state)
    if locals().get("sponsor_warning"):
        response["sponsor_warning"] = sponsor_warning
    return jsonify(response)

@app.post("/api/graphics/personnel")
@require_auth
def update_personnel_graphic():
    data=request.get_json(force=True) or {}
    action=str(data.get("action","update")).lower()
    with lock:
        state=load_state(); graphic=copy.deepcopy(DEFAULT_STATE["personnel_graphic"]); graphic.update(state.get("personnel_graphic") or {})
        if action=="clear": graphic=copy.deepcopy(DEFAULT_STATE["personnel_graphic"])
        else:
            pid=str(data.get("personnel_id",graphic.get("personnel_id",""))).strip(); person=next((x for x in load_broadcasters() if str(x.get("id"))==pid),None)
            if person:
                school=next((x for x in load_schools() if str(x.get("id"))==str(person.get("school_id",""))),{})
                identity=broadcast_identity(school,"Football") if school else {}
                full=str(person.get("full_name") or person.get("name") or "").strip(); preferred=str(person.get("preferred_name","")).strip() or full
                graphic.update({"personnel_id":pid,"full_name":full,"display_name":preferred,"title":str(person.get("title") or person.get("role") or ""),"role":str(person.get("role", "")),"organization":str(person.get("organization") or school.get("broadcast_name") or school.get("official_name") or ""),"headshot":str(person.get("headshot","")),"logo":str(identity.get("logo") or "/static/csrn-logo.png"),"accent":str(identity.get("primary_color") or "#C9203B")})
            for key in ("graphic_type","eyebrow"):
                if key in data: graphic[key]=str(data.get(key,""))[:240]
            sponsor_warning=apply_sponsor_to_graphic(graphic,data)
            try: graphic["duration"]=max(0,min(120,int(data.get("duration",graphic.get("duration",0)) or 0)))
            except: graphic["duration"]=0
            if action=="hide": graphic["visible"]=False; graphic["expires_at"]=0
            elif action in {"show","update"}:
                if not graphic.get("personnel_id"): return jsonify({"error":"PERSONNEL_REQUIRED"}),400
                activate_primary_graphic(state, "personnel")
                graphic["visible"]=True
                graphic["expires_at"]=int(time.time())+graphic["duration"] if graphic["duration"] else 0
            graphic["updated_at"]=int(time.time())
        state["personnel_graphic"]=graphic; save_state(state)
    response=public_state(state)
    if locals().get("sponsor_warning"): response["sponsor_warning"]=sponsor_warning
    return jsonify(response)


def automation_player(roster_id: str, player_id: str):
    roster = next((r for r in load_rosters() if str(r.get("id")) == str(roster_id)), None)
    player = next((p for p in (roster or {}).get("players", []) if str(p.get("id")) == str(player_id)), None)
    return roster, player

def player_display(player):
    if not player:
        return ""
    full = " ".join([str(player.get("first_name", "")).strip(), str(player.get("last_name", "")).strip()]).strip()
    return str(player.get("preferred_name", "")).strip() or full


def normalize_position(value):
    value = str(value or "").strip()
    if value.lower() == "athlete":
        return "ATH"
    return value or "ATH"


def event_position(player, defensive=False):
    if not player:
        return "ATH"
    primary = normalize_position(player.get("position"))
    secondary = normalize_position(player.get("secondary_position")) if player.get("secondary_position") else ""
    value = (secondary or primary) if defensive else (primary or secondary)
    if "/" in value:
        value = value.split("/", 1)[0].strip()
    return value or "ATH"


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

def show_automation_player_graphic(state, roster, player, graphic_type, duration, defensive=False, eyebrow="", play_detail=""):
    if not roster or not player or duration <= 0:
        return
    school = next((sc for sc in load_schools() if str(sc.get("id")) == str(roster.get("school_id"))), {})
    identity = broadcast_identity(school, str(roster.get("sport", "Football"))) if school else {}
    full_name = " ".join([str(player.get("first_name", "")).strip(), str(player.get("last_name", "")).strip()]).strip()
    graphic = copy.deepcopy(DEFAULT_STATE["player_graphic"])
    graphic.update({
        "visible": True, "graphic_type": graphic_type, "eyebrow": eyebrow or ("TOUCHDOWN" if graphic_type == "touchdown" else "PLAYER PROFILE"),
        "roster_id": str(roster.get("id", "")), "player_id": str(player.get("id", "")), "school_id": str(roster.get("school_id", "")),
        "full_name": full_name, "display_name": player_display(player), "number": str(player.get("number", "")),
        "position": event_position(player, defensive=defensive), "secondary_position": "",
        "grade": str(player.get("grade", "")), "height": str(player.get("height", "")), "weight": str(player.get("weight", "")),
        "headshot": str(player.get("headshot", "")), "team_logo": str(identity.get("logo", "")),
        "team_name": str(school.get("broadcast_name") or school.get("official_name") or ""),
        "team_color": str(identity.get("primary_color") or school.get("primary_color") or "#C9203B"),
        "play_detail": str(play_detail or ""),
        "duration": duration, "expires_at": int(time.time()) + duration, "updated_at": int(time.time()),
    })
    activate_primary_graphic(state, "player")
    state["player_graphic"] = graphic



def canonical_team_key(state: dict[str, Any], value: Any) -> str:
    text = str(value or "").strip()
    low = text.lower()
    if low in {"home", str(state.get("home_team", "")).strip().lower()}:
        return "home"
    if low in {"visitor", "away", str(state.get("visitor_team", "")).strip().lower()}:
        return "visitor"
    return text

def canonical_team_name(state: dict[str, Any], value: Any) -> str:
    key = canonical_team_key(state, value)
    if key == "home":
        return str(state.get("home_team") or "Home")
    if key == "visitor":
        return str(state.get("visitor_team") or "Visitor")
    return str(value or "")

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

def build_statistics(state: dict[str, Any]) -> dict[str, Any]:
    """Derive scoring and basic offensive yardage from canonical Play Register records."""
    broadcast_id = str(state.get("broadcast_id", ""))
    events = [e for e in list(state.get("events") or []) if not e.get("undone") and (not broadcast_id or not e.get("broadcast_id") or str(e.get("broadcast_id")) == broadcast_id)]
    plays = [p for p in list(state.get("plays") or []) if not p.get("undone") and (not broadcast_id or not p.get("broadcast_id") or str(p.get("broadcast_id")) == broadcast_id)]
    teams = {}
    for key, name, score in (("home", state.get("home_team") or "Home", state.get("home_score",0)), ("visitor", state.get("visitor_team") or "Visitor", state.get("visitor_score",0))):
        teams[key] = {"name":str(name),"score":int(score or 0),"touchdowns":0,"field_goals":0,"extra_points":0,"two_point_conversions":0,"turnovers_gained":0,"rushing_attempts":0,"rushing_yards":0,"pass_attempts":0,"completions":0,"passing_yards":0,"interceptions":0,"total_plays":0,"total_yards":0}
    players = {}
    def prow(team, name, number):
        name=str(name or '').strip(); number=str(number or '').strip()
        if not name and not number:return None
        key=f"{team}|{number}|{name.lower()}"
        if key not in players: players[key]={"team":team,"team_name":teams.get(team,{}).get("name",''),"name":name or f"Player {number}","number":number,"touchdowns":0,"passing_touchdowns":0,"field_goals":0,"extra_points":0,"two_point_conversions":0,"points":0,"rushing_attempts":0,"rushing_yards":0,"pass_attempts":0,"completions":0,"passing_yards":0,"receptions":0,"receiving_yards":0,"interceptions_thrown":0,"fumbles":0,"fumbles_lost":0}
        return players[key]
    scoring=[]
    for e in events:
        team=canonical_team_key(state,e.get('team','')); code=str(e.get('event','')).upper(); a=e.get('automation') or {}; delta=int(e.get('score_delta',0) or 0)
        if team not in teams: continue
        if code=='TD' or (code=='TURNOVER' and a.get('return_td')): teams[team]['touchdowns']+=1
        elif code=='FG': teams[team]['field_goals']+=1
        elif code=='XP': teams[team]['extra_points']+=1
        elif code=='2PT': teams[team]['two_point_conversions']+=1
        if code=='TURNOVER': teams[team]['turnovers_gained']+=1
        sc=prow(team,a.get('player_name',''),a.get('player_number',''))
        if sc:
            sc['points']+=delta
            if code=='TD' or (code=='TURNOVER' and a.get('return_td')):sc['touchdowns']+=1
            elif code=='FG':sc['field_goals']+=1
            elif code=='XP':sc['extra_points']+=1
            elif code=='2PT':sc['two_point_conversions']+=1
        if delta:
            aft=e.get('after') or {}; scoring.append({"quarter":str(e.get('quarter','')),"team":team,"team_name":teams[team]['name'],"label":str(e.get('label') or code),"description":str(e.get('description') or code),"points":delta,"home_score":int(aft.get('home_score',0) or 0),"visitor_score":int(aft.get('visitor_score',0) or 0),"created_at":int(e.get('created_at',0) or 0)})
    for p in plays:
        team=canonical_team_key(state,p.get('offense','')); kind=str(p.get('play_type','')).lower();
        if team not in teams or kind not in {'run','pass'}: continue
        try:y=int(str(p.get('yards','0') or '0'))
        except:y=0
        teams[team]['total_plays']+=1; teams[team]['total_yards']+=y
        ball=prow(team,p.get('player_name',''),p.get('player_number','')); passer=prow(team,p.get('passer_name',''),p.get('passer_number',''))
        if kind=='run':
            teams[team]['rushing_attempts']+=1; teams[team]['rushing_yards']+=y
            if ball: ball['rushing_attempts']+=1; ball['rushing_yards']+=y
        else:
            outcome=str(p.get('pass_outcome','complete')).lower(); teams[team]['pass_attempts']+=1
            if passer: passer['pass_attempts']+=1
            if outcome=='complete':
                teams[team]['completions']+=1; teams[team]['passing_yards']+=y
                if passer: passer['completions']+=1; passer['passing_yards']+=y
                if ball: ball['receptions']+=1; ball['receiving_yards']+=y
            elif outcome=='interception':
                teams[team]['interceptions']+=1
                if passer: passer['interceptions_thrown']+=1
        if p.get('fumble') and ball: ball['fumbles']+=1
        if p.get('fumble_lost') and ball: ball['fumbles_lost']+=1
    for t in teams.values(): t['yards_per_play']=round(t['total_yards']/t['total_plays'],1) if t['total_plays'] else 0
    normalized_plays = []
    for source_play in plays:
        row = copy.deepcopy(source_play)
        offense_key = canonical_team_key(state, row.get("offense"))
        defense_key = canonical_team_key(state, row.get("defense"))
        row["offense"] = offense_key
        row["defense"] = defense_key
        row["offense_name"] = canonical_team_name(state, offense_key)
        row["defense_name"] = canonical_team_name(state, defense_key)
        normalized_plays.append(row)
    return {"broadcast_id":broadcast_id,"sport":str(state.get('sport') or 'Football'),"season":state.get('season',''),"date":state.get('date',''),"venue":state.get('venue',''),"quarter":str(state.get('quarter','')),"status":str(state.get('status','')),"teams":teams,"players":sorted(players.values(),key=lambda x:(x['team_name'],int(x['number']) if str(x['number']).isdigit() else 999,x['name'])),"scoring_summary":scoring,"play_register":normalized_plays,"event_count":len(events),"play_count":len(plays),"scoring_event_count":len(scoring),"generated_at":int(time.time()),"note":"Statistics are derived from canonical Play Register records and scoring events."}


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
    addresses: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                addresses.add(ip)
    except OSError:
        pass
    primary = local_ip()
    if primary and not primary.startswith("127."):
        addresses.add(primary)
    return sorted(addresses)

@app.get("/api/statistics")
@require_auth
def statistics_report():
    return jsonify(build_statistics(load_state()))

def game_data_source_allowed(state: dict[str, Any], source: str) -> bool:
    authority = str(state.get("game_data_authority", "broadcaster") or "broadcaster").lower()
    source = str(source or "broadcaster").lower()
    return source == authority

def authority_rejection(state: dict[str, Any]):
    authority = str(state.get("game_data_authority", "broadcaster") or "broadcaster")
    return jsonify({"error": "CONTROL_SOURCE_LOCKED", "authority": authority, "message": f"Game data is controlled by the {authority} console."}), 409

@app.post("/api/control-source")
@require_auth
def set_control_source():
    data = request.get_json(force=True) or {}
    authority = str(data.get("authority", "")).lower()
    if authority not in {"broadcaster", "statistician"}:
        return jsonify({"error": "INVALID_CONTROL_SOURCE"}), 400
    with lock:
        state = load_state()
        push_history(state)
        state["game_data_authority"] = authority
        state["statistician_enabled"] = authority == "statistician"
        state["control_source_updated_at"] = int(time.time())
        save_state(state)
    return jsonify(public_state(state))

@app.post("/api/event-trigger")
@require_auth
def event_trigger():
    data = request.get_json(force=True) or {}
    team = str(data.get("team", "")).lower()
    event = str(data.get("event", "")).upper()
    if team not in {"home", "visitor"} or event not in {"TD", "FG", "XP", "2PT", "TURNOVER", "FIRST_DOWN", "PENALTY", "EJECTION", "PLAY"}:
        return jsonify({"error": "INVALID_EVENT"}), 400
    with lock:
        state = load_state()
        if not state.get("broadcast_id"):
            return jsonify({"error": "NO_ACTIVE_BROADCAST"}), 409
        source = str(data.get("source", "broadcaster") or "broadcaster").lower()
        if not game_data_source_allowed(state, source):
            return authority_rejection(state)
        push_history(state)
        score_key = "home_score" if team == "home" else "visitor_score"
        before = {"home_score": int(state.get("home_score", 0)), "visitor_score": int(state.get("visitor_score", 0)), "possession": state.get("possession", "home"), "down": state.get("down", "1st"), "distance": state.get("distance", "10"), "ball_spot": state.get("ball_spot", ""), "quarter": state.get("quarter", "1"), "player_graphic": copy.deepcopy(state.get("player_graphic") or {})}
        return_td = bool(data.get("return_td")) and str(data.get("turnover_type", "")) != "downs"
        delta = 6 if event == "TD" or (event == "TURNOVER" and return_td) else 3 if event == "FG" else 2 if event == "2PT" else 1 if event == "XP" else 0
        if delta:
            state[score_key] = max(0, int(state.get(score_key, 0)) + delta)
        if event == "TURNOVER": state["possession"] = team
        if event == "FIRST_DOWN":
            state["down"] = "1st"
            state["distance"] = "10"
        penalty_enforcement = {}
        if event == "PENALTY":
            pcat = str(data.get("penalty_category", "") or "")
            pname = str(data.get("penalty_name", "Penalty") or "Penalty")
            poutcome = str(data.get("penalty_outcome", "accepted") or "accepted").lower()
            pyards = max(0, min(99, int(data.get("penalty_yards", 0) or 0)))
            penalty_enforcement = apply_penalty_enforcement(state, pcat, pname, pyards, poutcome)
        if state.get("status") != "live":
            state["status"] = "live"; state["broadcast_phase"] = "live"; update_linked_broadcast_status(state.get("broadcast_id", ""), "live")
        team_name = state.get("home_team") if team == "home" else state.get("visitor_team")
        roster, player = automation_player(str(data.get("roster_id", "")), str(data.get("player_id", "")))
        _, passer = automation_player(str(data.get("roster_id", "")), str(data.get("passer_id", "")))
        player = player or manual_automation_player(data.get("manual_player"), team_name)
        passer = passer or manual_automation_player(data.get("manual_passer"), team_name)
        if player and not roster:
            roster = {
                "id": "",
                "school_id": state.get("home_school_id") if team == "home" else state.get("visitor_school_id"),
                "sport": "Football",
                "players": [],
            }
        scorer_name, passer_name = player_display(player), player_display(passer)
        yards = str(data.get("yards", "")).strip() if (bool(data.get("statistician_mode")) or event == "PLAY") else ""
        play_type = str(data.get("play_type", "")).lower()
        if event == "TD" and not yards and play_type in {"rush", "reception", "return"}:
            start_coord = spot_to_coord(state.get("ball_spot") or 50)
            direction = team_direction(state, team)
            goal_coord = 100 if direction == 1 else 0
            yards = str(abs(goal_coord - start_coord))
        turnover_type = str(data.get("turnover_type", "")).lower()
        if event == "PLAY":
            play_kind = str(data.get("play_type", "run") or "run").lower()
            outcome = str(data.get("pass_outcome", "complete") or "complete").lower()
            fumble = bool(data.get("fumble"))
            fumble_lost = bool(data.get("fumble_lost"))
            turnover = bool(data.get("turnover")) or fumble_lost or outcome == "interception"
            if play_kind == "pass":
                if outcome == "incomplete":
                    label = "Incomplete Pass"; description = f"{passer_name or team_name} pass incomplete"
                elif outcome == "interception":
                    label = "Interception"; description = f"{passer_name or team_name} pass intercepted"
                elif outcome == "sack":
                    label = "Sack"; description = f"{passer_name or team_name} sacked"
                else:
                    label = "Pass"; description = f"{passer_name or team_name} pass complete to {scorer_name or team_name}"
            else:
                label = "Run"; description = f"{scorer_name or team_name} run"
            if yards not in {"", "0"}: description += f" for {yards} yards"
            elif yards == "0": description += " for no gain"
            if fumble:
                description += ", fumble" + (" lost" if fumble_lost else " recovered")
            if bool(data.get("first_down")):
                description += ", first down"; state["down"] = "1st"; state["distance"] = "10"
            if turnover:
                state["possession"] = "visitor" if team == "home" else "home"
        elif event in {"TD", "2PT"}:
            conversion = event == "2PT"
            label = "Two-Point Conversion" if conversion else "Touchdown"
            event_phrase = "two-point conversion" if conversion else "touchdown"
            if play_type == "reception":
                description = f"{scorer_name or team_name} {event_phrase} reception" + (f" from {passer_name}" if passer_name else "")
            elif play_type == "rush":
                description = f"{scorer_name or team_name} {event_phrase} run"
            elif play_type == "return":
                description = f"{scorer_name or team_name} {event_phrase} return"
            else:
                description = f"{scorer_name or team_name} {event_phrase}"
            if yards:
                description = f"{yards}-yard {description[0].lower() + description[1:]}"
        elif event == "TURNOVER":
            kind = {"interception":"Interception","fumble_recovery":"Fumble recovery","downs":"Turnover on downs","other":"Turnover"}.get(turnover_type,"Turnover")
            label = "Defensive Touchdown" if return_td else kind
            description = f"{scorer_name or team_name} {kind.lower()}" + (" returned for a touchdown" if return_td else "")
            if yards and return_td:
                description = f"{yards}-yard {description.lower()}"
        elif event == "FIRST_DOWN":
            label = "1st Down"
            method = str(data.get("first_down_method", "manual") or "manual").title()
            description = f"{team_name} first down" + (f" ({method})" if method != "Manual" else "")
        elif event == "PENALTY":
            penalty_name = str(data.get("penalty_name", "Penalty") or "Penalty")
            penalty_yards = str(data.get("penalty_yards", "") or "").strip()
            penalty_category = str(data.get("penalty_category", "") or "").strip()
            penalty_outcome = str(data.get("penalty_outcome", "accepted") or "accepted").lower()
            label = "Flag Picked Up" if penalty_outcome == "flag_picked_up" else "Offsetting Penalties" if penalty_outcome == "offset" else "Penalty Declined" if penalty_outcome == "declined" else "Penalty"
            if penalty_outcome == "flag_picked_up":
                description = f"Flag picked up — no penalty on {team_name}"
            elif penalty_outcome == "offset":
                description = "Offsetting penalties — replay down"
            elif penalty_outcome == "declined":
                description = f"Penalty declined, {team_name}" + (f" — {penalty_name}" if penalty_name else "")
            else:
                description = f"Penalty, {team_name}" + (f", {penalty_yards} yards" if penalty_yards else "") + (f" — {penalty_name}" if penalty_name else "")
                if penalty_category:
                    description += f" ({penalty_category})"
        elif event == "EJECTION":
            person_type = str(data.get("ejection_person_type", "Player") or "Player")
            person_name = str(data.get("ejection_person_name", "") or "").strip()
            reason = str(data.get("ejection_reason", "Other") or "Other")
            label = f"{person_type} Ejected"
            description = f"{person_type} ejected" + (f": {person_name}" if person_name else f" — {team_name}") + (f" ({reason})" if reason else "")
        elif event == "FG":
            label = "Field Goal"
            description = f"{scorer_name or team_name} field goal"
            if yards:
                description = f"{yards}-yard field goal by {scorer_name or team_name}"
        else:
            label = "Extra Point"
            description = f"Extra point by {scorer_name or team_name}"
        duration = max(0, min(30, int(data.get("graphic_duration", 0) or 0)))
        if (event in {"TD", "2PT"} or return_td) and player:
            graphic_eyebrow = "TWO-POINT CONVERSION" if event == "2PT" else "DEFENSIVE TOUCHDOWN" if return_td else "TOUCHDOWN"
            show_automation_player_graphic(state, roster, player, "two_point" if event == "2PT" else "touchdown", duration, defensive=(event == "TURNOVER" and return_td), eyebrow=graphic_eyebrow, play_detail=description)
        play_number = int(state.get("next_play_number", 1) or 1)
        state["next_play_number"] = play_number + 1
        event_id = f"EV-{int(time.time()*1000)}"
        broadcast_token = re.sub(r"[^A-Za-z0-9]+", "-", str(state.get("broadcast_id") or "GAME")).strip("-").upper() or "GAME"
        play_id = f"{broadcast_token}-{play_number:04d}"
        payload = {
            "id": event_id, "play_id": play_id, "play_number": play_number, "team": team, "team_name": team_name, "event": event, "label": label,
            "description": description, "score_delta": delta, "created_at": int(time.time()), "quarter": str(state.get("quarter", "1") or "1"),
            "broadcast_id": state.get("broadcast_id", ""), "before": before, "source": source,
            "first_down_method": str(data.get("first_down_method", "") or ""),
            "penalty": {"category": str(data.get("penalty_category", "") or ""), "name": str(data.get("penalty_name", "") or ""), "yards": str(data.get("penalty_yards", "") or ""), "outcome": str(data.get("penalty_outcome", "accepted") or "accepted"), "enforcement": penalty_enforcement},
            "ejection": {"person_type": str(data.get("ejection_person_type", "") or ""), "person_name": str(data.get("ejection_person_name", "") or ""), "reason": str(data.get("ejection_reason", "") or "")},
            "after": {"home_score": int(state.get("home_score",0)), "visitor_score": int(state.get("visitor_score",0)), "possession": state.get("possession","home"), "down": state.get("down","1st"), "distance": state.get("distance","10"), "ball_spot": state.get("ball_spot", ""), "quarter": state.get("quarter", "1")},
            "automation": {"mode": "statistician" if bool(data.get("statistician_mode")) else "quick", "play_type": play_type, "turnover_type": turnover_type, "player_id": str(data.get("player_id", "")), "player_name": scorer_name, "player_number": str(player.get("number", "")) if player else "", "passer_id": str(data.get("passer_id", "")), "passer_name": passer_name, "passer_number": str(passer.get("number", "")) if passer else "", "manual_player": data.get("manual_player"), "manual_passer": data.get("manual_passer"), "yards": yards, "return_td": return_td, "graphic_duration": duration, "pass_outcome": str(data.get("pass_outcome", "") or ""), "fumble": bool(data.get("fumble")), "fumble_lost": bool(data.get("fumble_lost")), "first_down": bool(data.get("first_down")), "turnover": bool(data.get("turnover")) or bool(data.get("fumble_lost")) or str(data.get("pass_outcome", "")).lower() == "interception"},
            "media_trigger": {"key": f"{event.lower()}_{team}", "assigned": bool(player and duration), "graphics": "player_touchdown" if player and duration else None, "audio": None, "video": None},
        }
        play_record = {
            "play_id": play_id,
            "play_number": play_number,
            "event_id": event_id,
            "broadcast_id": state.get("broadcast_id", ""),
            "quarter": str(state.get("quarter", "1") or "1"),
            "clock": str(data.get("clock", "") or ""),
            "offense": team,
            "offense_name": team_name,
            "defense": "visitor" if team == "home" else "home",
            "defense_name": state.get("visitor_team") if team == "home" else state.get("home_team"),
            "down": str(before.get("down", "")),
            "distance": str(before.get("distance", "")),
            "ball_spot": str(before.get("ball_spot", "")),
            "play_type": play_type or event.lower(),
            "result": description,
            "yards": yards,
            "first_down": event == "FIRST_DOWN" or bool(data.get("first_down")),
            "touchdown": event == "TD" or return_td,
            "turnover": event == "TURNOVER" or bool(data.get("turnover")) or bool(data.get("fumble_lost")) or str(data.get("pass_outcome", "")).lower() == "interception",
            "fumble": bool(data.get("fumble")),
            "fumble_lost": bool(data.get("fumble_lost")),
            "pass_outcome": str(data.get("pass_outcome", "") or ""),
            "player_name": scorer_name,
            "player_number": str(player.get("number", "")) if player else str((data.get("manual_player") or {}).get("number", "")),
            "passer_name": passer_name,
            "passer_number": str(passer.get("number", "")) if passer else str((data.get("manual_passer") or {}).get("number", "")),
            "safety": False,
            "notes": str(data.get("notes", "") or ""),
            "created_by": source,
            "created_at": payload["created_at"],
            "label": label,
            "undone": False,
            "statistics_hooks": [],
            "drive_id": "",
        }
        state["last_event"] = payload
        events=list(state.get("events") or []); events.append(payload); state["events"] = events[-200:]
        plays=list(state.get("plays") or []); plays.append(play_record); state["plays"] = plays[-500:]
        save_state(state)
    return jsonify({"state": public_state(state), "trigger": payload, "media_assigned": bool(payload["media_trigger"]["assigned"]), "message": description + (f" (+{delta})" if delta else "")})


@app.post("/api/game-correction")
@require_auth
def game_correction():
    data = request.get_json(force=True) or {}
    with lock:
        state = load_state()
        source = str(data.get("source", "statistician") or "statistician").lower()
        if not game_data_source_allowed(state, source):
            return authority_rejection(state)
        before = {k: copy.deepcopy(state.get(k)) for k in ("down", "distance", "ball_spot", "possession", "quarter")}
        down = str(data.get("down", state.get("down", "1st")))
        if down not in {"1st", "2nd", "3rd", "4th", "Off"}: return jsonify({"error":"INVALID_DOWN"}), 400
        possession = str(data.get("possession", state.get("possession", "home")))
        if possession not in {"home", "visitor"}: return jsonify({"error":"INVALID_POSSESSION"}), 400
        state["down"] = down
        state["distance"] = "Off" if down == "Off" else str(max(1, min(99, int(data.get("distance", int_distance(state.get("distance"),10)) or 10))))
        state["ball_spot"] = str(data.get("ball_spot", state.get("ball_spot", "")))[:40]
        state["possession"] = possession
        state["quarter"] = str(data.get("quarter", state.get("quarter", "1")))[:10]
        after = {k: copy.deepcopy(state.get(k)) for k in before}
        append_correction(state, correction_entry("quick_correction", source, before, after, note=str(data.get("note", ""))[:200]))
        save_state(state)
    return jsonify(public_state(state))

@app.post("/api/events/<event_id>/edit")
@require_auth
def edit_event(event_id: str):
    data = request.get_json(force=True) or {}
    with lock:
        state = load_state()
        source = str(data.get("source", "statistician") or "statistician").lower()
        if not game_data_source_allowed(state, source): return authority_rejection(state)
        events = list(state.get("events") or [])
        event = next((row for row in events if row.get("id") == event_id), None)
        if not event: return jsonify({"error":"EVENT_NOT_FOUND"}), 404
        before = copy.deepcopy(event)
        if "yards" in data:
            yards = str(max(-100, min(100, int(data.get("yards", 0) or 0))))
            event.setdefault("automation", {})["yards"] = yards
            desc = str(event.get("description", ""))
            desc = re.sub(r"^-?\\d+-yard\\s+", "", desc, flags=re.I)
            if yards not in {"", "0"}: event["description"] = f"{yards}-yard {desc[0].lower()+desc[1:] if desc else 'play'}"
        for field in ("description", "quarter"):
            if field in data: event[field] = str(data.get(field, ""))[:300]
        after_state = event.setdefault("after", {})
        for field in ("down", "distance", "ball_spot", "possession"):
            if field in data: after_state[field] = str(data.get(field, ""))[:40]
        if "down" in data: state["down"] = after_state["down"]
        if "distance" in data: state["distance"] = after_state["distance"]
        if "ball_spot" in data: state["ball_spot"] = after_state["ball_spot"]
        if "possession" in data and after_state["possession"] in {"home","visitor"}: state["possession"] = after_state["possession"]
        play = next((row for row in list(state.get("plays") or []) if row.get("event_id") == event_id or row.get("play_id") == event.get("play_id")), None)
        if play:
            if "yards" in data: play["yards"] = int(data.get("yards", 0) or 0)
            if "start_spot" in data: play["ball_spot"] = str(data.get("start_spot", ""))[:40]
            if "end_spot" in data: play["end_spot"] = str(data.get("end_spot", ""))[:40]
            if "description" in data: play["result"] = event.get("description", play.get("result", ""))
            if "quarter" in data: play["quarter"] = event.get("quarter", play.get("quarter", ""))
            if "down" in data: play["resulting_down"] = after_state.get("down", "")
            if "distance" in data: play["resulting_distance"] = after_state.get("distance", "")
        append_correction(state, correction_entry("event_edit", source, before, copy.deepcopy(event), event_id, str(data.get("note", ""))[:200]))
        state["events"] = events
        state["last_event"] = event
        save_state(state)
    return jsonify({"state": public_state(state), "event": event})

@app.get("/api/corrections")
@require_auth
def corrections_report():
    state = load_state()
    return jsonify(list(reversed(state.get("correction_log") or [])))

@app.get("/api/connection-info")
@require_auth
def connection_info():
    addresses = local_addresses()
    return jsonify({
        "port": 5050,
        "addresses": [{"ip": ip, "url": f"http://{ip}:5050"} for ip in addresses],
        "localhost": "http://127.0.0.1:5050",
        "guidance": "For USB tethering, connect the phone by USB, enable USB tethering, then refresh this panel and use the newly listed address from the second device. Some phones cannot browse back to the laptop while serving as the tethering device; use a separate statistician phone/tablet when that occurs.",
    })

@app.get("/api/connection-qr")
@require_auth
def connection_qr():
    url = str(request.args.get("url", "") or "")
    if not re.match(r"^https?://", url):
        return jsonify({"error": "INVALID_URL"}), 400
    image = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    stream = io.BytesIO()
    image.save(stream)
    return Response(stream.getvalue(), mimetype="image/svg+xml", headers={"Cache-Control": "no-store"})

@app.post("/api/toggle-scorebug")
@require_auth
def toggle_scorebug():
    with lock:
        state = load_state()
        active_broadcast_id = state.get("broadcast_id", "")
        next_visible = not bool(state.get("scorebug_visible"))
        if load_config().get("obs", {}).get("controlled_commands", False):
            try:
                command_scorebug_visibility(next_visible)
            except OBSConnectionError as exc:
                return jsonify({"error": "OBS_COMMAND_BLOCKED", "message": str(exc)}), 409
        push_history(state)
        # Visibility is deliberately isolated from broadcast lifecycle and active selection.
        state["scorebug_visible"] = next_visible
        state["broadcast_id"] = active_broadcast_id
        save_state(state)
        return jsonify(state)

@app.post("/api/toggle-halftime")
@require_auth
def toggle_halftime():
    with lock:
        state = load_state()
        push_history(state)
        if state["broadcast_phase"] == "halftime":
            state["broadcast_phase"] = "live"
            state["quarter"] = "3"
            state["scorebug_visible"] = True
        else:
            state["broadcast_phase"] = "halftime"
            state["scorebug_visible"] = False
        save_state(state)
        return jsonify(state)

@app.post("/api/end-game")
@require_auth
def end_game():
    with lock:
        state = load_state()
        push_history(state)
        state["broadcast_phase"] = "final"
        state["scorebug_visible"] = False
        state["status"] = "completed"
        save_state(state)
        update_linked_broadcast_status(state.get("broadcast_id", ""), "completed", {"final_home_score":state.get("home_score",0),"final_visitor_score":state.get("visitor_score",0)})
        return jsonify(state)

@app.post("/api/reset-data")
@require_auth
def reset_data():
    with lock:
        current = load_state()
        reset = copy.deepcopy(DEFAULT_STATE)
        # Reset only game-operation data. Preserve the selected broadcast and
        # its schedule/identity so an accidentally completed game can resume.
        reset.update({
            "broadcast_created": bool(current.get("broadcast_id")),
            "broadcast_id": current.get("broadcast_id", ""),
            "sport": current.get("sport", "Football"),
            "season": current.get("season", ""),
            "week": current.get("week", "1"),
            "classification": current.get("classification", ""),
            "level": current.get("level", "Varsity"),
            "division": current.get("division", "Boys"),
            "home_team": current.get("home_team", "Caledonia"),
            "visitor_team": current.get("visitor_team", "Visitor"),
            "home_school_id": current.get("home_school_id", ""),
            "visitor_school_id": current.get("visitor_school_id", ""),
            "home_identity": current.get("home_identity", {}),
            "visitor_identity": current.get("visitor_identity", {}),
            "venue_id": current.get("venue_id", ""),
            "venue": current.get("venue", "Caledonia High School"),
            "date": current.get("date", ""),
            "scheduled_start": current.get("scheduled_start", ""),
            "visual_mode": current.get("visual_mode", "graphic"),
            "crew": current.get("crew", {}),
            "status": current.get("status", "planned"),
            "broadcast_phase": "final" if current.get("status") == "completed" else "pregame",
            "review_mode": current.get("status") == "completed",
            "scorebug_visible": False,
        })
        save_state(reset)
        return jsonify(reset)

@app.post("/api/new-broadcast")
@require_auth
def new_broadcast():
    with lock:
        state = copy.deepcopy(DEFAULT_STATE)
        save_state(state)
        return jsonify(state)



def spot_to_coord(value: Any) -> int:
    """Canonical field coordinate: 0=left goal line, 100=right goal line."""
    text = str(value or "").strip().lower()
    if text in {"left goal", "left_goal", "home goal", "home_goal", "0"}: return 0
    if text in {"right goal", "right_goal", "visitor goal", "visitor_goal", "100"}: return 100
    if text == "50": return 50
    match = re.match(r"^(left|right|home|visitor)\s*(\d{1,2})$", text)
    if match:
        side, yard = match.group(1), max(0, min(49, int(match.group(2))))
        return yard if side in {"left", "home"} else 100-yard
    try: return max(0, min(100, int(float(text))))
    except (TypeError, ValueError): return 50


def coord_to_spot(coord: int) -> str:
    coord=max(0,min(100,int(coord)))
    if coord==0: return "LEFT GOAL"
    if coord==100: return "RIGHT GOAL"
    if coord==50: return "50"
    return f"LEFT {coord}" if coord<50 else f"RIGHT {100-coord}"


def team_direction(state: dict[str, Any], team: str) -> int:
    direction=str(state.get(f"{team}_direction", "right" if team=="home" else "left")).lower()
    return 1 if direction=="right" else -1


def opposite(team: str) -> str:
    return "visitor" if team=="home" else "home"


def advance_down(down: str) -> str:
    order=["1st","2nd","3rd","4th"]
    try: return order[min(3,order.index(str(down))+1)]
    except ValueError: return "1st"


@app.post("/api/clock-control")
@require_auth
def clock_control():
    data=request.get_json(force=True) or {}
    with lock:
        state=load_state(); action=str(data.get("action","")).lower()
        seconds=max(0,min(3599,int(state.get("clock_seconds",720) or 0)))
        if action=="start": state["clock_running"]=True; state["clock_started_at"]=int(time.time())
        elif action=="stop": state["clock_running"]=False; state["clock_started_at"]=0
        elif action=="set": seconds=max(0,min(3599,int(data.get("seconds",seconds) or 0)))
        elif action=="adjust": seconds=max(0,min(3599,seconds+int(data.get("delta",0) or 0)))
        elif action=="reset": seconds=max(0,min(3599,int(data.get("seconds",720) or 720))); state["clock_running"]=False; state["clock_started_at"]=0
        state["clock_seconds"]=seconds
        if "visible" in data: state["clock_visible"]=bool(data.get("visible"))
        save_state(state); return jsonify(state)


@app.post("/api/field-direction")
@require_auth
def field_direction():
    data=request.get_json(force=True) or {}
    with lock:
        state=load_state()
        team=str(data.get("team") or "home").lower()
        direction=str(data.get("direction") or data.get("home_direction") or "right").lower()
        if team not in {"home","visitor"} or direction not in {"left","right"}: return jsonify({"error":"INVALID_DIRECTION"}),400
        state[f"{team}_direction"]=direction
        state[f"{opposite(team)}_direction"]="left" if direction=="right" else "right"
        save_state(state); return jsonify(state)


@app.post("/api/rules-play")
@require_auth
def rules_play():
    data=request.get_json(force=True) or {}
    team=str(data.get("team","")).lower(); kind=str(data.get("play_type","")).lower()
    if team not in {"home","visitor"} or kind not in {"run","pass","kickoff","punt"}:
        return jsonify({"error":"INVALID_PLAY"}),400
    with lock:
        state=load_state()
        if not state.get("broadcast_id"): return jsonify({"error":"NO_ACTIVE_BROADCAST"}),409
        if not game_data_source_allowed(state,"statistician"): return authority_rejection(state)
        push_history(state)
        before={k:copy.deepcopy(state.get(k)) for k in ("home_score","visitor_score","possession","down","distance","ball_spot","quarter","clock_seconds","clock_running","player_graphic")}
        start=spot_to_coord(data.get("start_spot") or state.get("ball_spot") or 50)
        end=spot_to_coord(data.get("end_spot") if data.get("end_spot") not in (None,"") else start)
        direction=team_direction(state,team); yards=(end-start)*direction
        old_down=str(state.get("down","1st")); old_distance=str(state.get("distance","10"))
        try: distance=10 if old_distance in {"Off","Goal",""} else max(1,int(old_distance))
        except ValueError: distance=10
        outcome=str(data.get("pass_outcome","")).lower()
        turnover=bool(data.get("fumble_lost")) or outcome=="interception"
        touchdown=(direction==1 and end==100) or (direction==-1 and end==0)
        safety=(direction==1 and end==0) or (direction==-1 and end==100)
        first_down=False
        label=kind.title(); result=""
        player_number=str(data.get("player_number","")).strip(); passer_number=str(data.get("passer_number","")).strip(); receiver_number=str(data.get("receiver_number","")).strip(); sacker_number=str(data.get("sacker_number","")).strip(); kicker_number=str(data.get("kicker_number","")).strip(); returner_number=str(data.get("returner_number","")).strip()
        player_ref=resolve_game_roster_player(state,team,player_number); passer_ref=resolve_game_roster_player(state,team,passer_number); receiver_ref=resolve_game_roster_player(state,team,receiver_number); sacker_ref=resolve_game_roster_player(state,opposite(team),sacker_number); kicker_ref=resolve_game_roster_player(state,team,kicker_number); returner_ref=resolve_game_roster_player(state,opposite(team),returner_number)
        player_name=player_ref.get('name') or str(data.get('player_name','')).strip(); passer_name=passer_ref.get('name') or str(data.get('passer_name','')).strip(); receiver_name=receiver_ref.get('name') or str(data.get('receiver_name','')).strip(); sacker_name=sacker_ref.get('name') or str(data.get('sacker_name','')).strip(); kicker_name=kicker_ref.get('name') or str(data.get('kicker_name','')).strip(); returner_name=returner_ref.get('name') or str(data.get('returner_name','')).strip()
        if kind=="run":
            kneel=bool(data.get("kneel")); label="Kneel" if kneel else "Run"
            runner_label=(f"#{player_number} {player_name}".strip() if player_number else player_name or '?'); result=f"{runner_label} {'kneel' if kneel else 'run'} for {yards} yards"
        elif kind=="pass":
            if outcome in {"incomplete","spike"}:
                end=start; yards=0; label="Spike" if outcome=="spike" else "Incomplete Pass"; passer_label=(f"#{passer_number} {passer_name}".strip() if passer_number else passer_name or '?'); result=f"{passer_label} pass incomplete" if outcome!="spike" else f"{passer_label} spike"
            elif outcome=="interception": label="Interception"; passer_label=(f"#{passer_number} {passer_name}".strip() if passer_number else passer_name or '?'); result=f"{passer_label} pass intercepted"
            elif outcome=="sack": label="Sack"; passer_label=(f"#{passer_number} {passer_name}".strip() if passer_number else passer_name or '?'); sacker_label=(f"#{sacker_number} {sacker_name}".strip() if sacker_number else sacker_name or '?'); result=f"{passer_label} sacked by {sacker_label} for {yards} yards"
            else: label="Pass"; passer_label=(f"#{passer_number} {passer_name}".strip() if passer_number else passer_name or '?'); receiver_label=(f"#{receiver_number} {receiver_name}".strip() if receiver_number else receiver_name or '?'); result=f"{passer_label} complete to {receiver_label} for {yards} yards"
        elif kind in {"kickoff","punt"}:
            receiving=opposite(team); state["possession"]=receiving
            landing=spot_to_coord(data.get("landing_spot") if data.get("landing_spot") not in (None,"") else end)
            touchback=bool(data.get("touchback")); fair=bool(data.get("fair_catch")); blocked=bool(data.get("blocked"))
            if touchback:
                # NFHS edition default: receiving team begins at its own 20.
                receiving_direction=team_direction(state, receiving)
                end=20 if receiving_direction==1 else 80
            kick_distance=abs(landing-start)
            return_direction=team_direction(state, receiving)
            return_yards=max(0,(end-landing)*return_direction)
            touchdown = (not touchback and not fair and returner_number and ((return_direction==1 and end==100) or (return_direction==-1 and end==0)))
            if touchdown:
                state[f"{receiving}_score"] = int(state.get(f"{receiving}_score", 0) or 0) + 6
            state["ball_spot"]=coord_to_spot(end); state["down"]="1st"; state["distance"]="10"; state["clock_running"]=False; state["clock_started_at"]=0
            label="Kickoff" if kind=="kickoff" else "Punt"
            result=f"{label} by #{kicker_number or '?'} landed at {coord_to_spot(landing)}"
            if returner_number and not fair and not touchback:
                returner_label=(f"#{returner_number} {returner_name}".strip() if returner_number else returner_name or '?')
                result += f", returned by {returner_label} for {return_yards} yards to {coord_to_spot(end)}"
            else: result += f", ball at {coord_to_spot(end)}"
            result += (" — touchback" if touchback else " — fair catch" if fair else " — blocked" if blocked else "")
            if touchdown:
                result += ", touchdown"
                label = "Kickoff Return Touchdown" if kind == "kickoff" else "Punt Return Touchdown"
                if returner_number or returner_name:
                    td_roster = {"id": returner_ref.get("roster_id", ""), "school_id": state.get(f"{receiving}_school_id", ""), "sport": str(state.get("sport") or "Football"), "players": []}
                    td_player = {"id": returner_ref.get("player_id", ""), "number": returner_number, "preferred_name": returner_name, "first_name": returner_name, "last_name": "", "position": "Returner"}
                    show_automation_player_graphic(state, td_roster, td_player, "touchdown", 8, eyebrow="TOUCHDOWN", play_detail=f"{return_yards}-yard {kind} return")
        if kind in {"run","pass"}:
            if touchdown:
                state[f"{team}_score"]=int(state.get(f"{team}_score",0))+6; state["down"]="1st"; state["distance"]="10"; state["clock_running"]=False; state["clock_started_at"]=0
                # Alpha.3e: a touchdown derived by the rules engine must trigger
                # the same player graphic path as a manual touchdown event.
                td_number = receiver_number if kind == "pass" and outcome == "complete" else player_number
                td_name = receiver_name if kind == "pass" and outcome == "complete" else player_name
                if td_number or td_name:
                    td_roster = {
                        "id": "", "school_id": state.get(f"{team}_school_id", ""),
                        "sport": str(state.get("sport") or "Football"), "players": [],
                    }
                    td_player = {"id": "", "number": td_number, "preferred_name": td_name,
                                 "first_name": td_name, "last_name": "", "position": ""}
                    td_detail = f"{yards}-yard touchdown " + ("reception" if kind == "pass" else "run")
                    show_automation_player_graphic(state, td_roster, td_player, "touchdown", 8,
                                                   eyebrow="TOUCHDOWN", play_detail=td_detail)
            elif safety:
                other=opposite(team); state[f"{other}_score"]=int(state.get(f"{other}_score",0))+2; state["possession"]=other; state["clock_running"]=False; state["clock_started_at"]=0
            elif turnover:
                state["possession"]=opposite(team); state["down"]="1st"; state["distance"]="10"; state["clock_running"]=False; state["clock_started_at"]=0
            else:
                first_down=yards>=distance
                if first_down: state["down"]="1st"; state["distance"]="10"
                else:
                    state["down"]=advance_down(old_down); state["distance"]=str(max(1,distance-yards))
                    if old_down=="4th": state["possession"]=opposite(team); state["down"]="1st"; state["distance"]="10"; state["clock_running"]=False; state["clock_started_at"]=0; turnover=True
                if outcome in {"incomplete","spike"} or bool(data.get("out_of_bounds")): state["clock_running"]=False; state["clock_started_at"]=0
            state["ball_spot"]=coord_to_spot(end)
        play_number=int(state.get("next_play_number",1) or 1); state["next_play_number"]=play_number+1
        token=re.sub(r"[^A-Za-z0-9]+","-",str(state.get("broadcast_id") or "GAME")).strip("-") or "GAME"
        play_id=f"{token}-{play_number:04d}"; event_id=f"evt-{int(time.time()*1000)}-{play_number}"
        if bool(data.get("fumble")): result += ", fumble" + (" lost" if bool(data.get("fumble_lost")) else " recovered")
        if touchdown and kind in {"run", "pass"}:
            result += ", touchdown"
            label = "Touchdown Pass" if kind == "pass" else "Touchdown Run"
        elif first_down:
            result += ", first down"
        scoring_team = opposite(team) if touchdown and kind in {"kickoff", "punt"} else team
        td_number = returner_number if touchdown and kind in {"kickoff", "punt"} else (receiver_number if kind == "pass" and outcome == "complete" else player_number)
        td_name = returner_name if touchdown and kind in {"kickoff", "punt"} else (receiver_name if kind == "pass" and outcome == "complete" else player_name)
        event={"id":event_id,"play_id":play_id,"play_number":play_number,"broadcast_id":state.get("broadcast_id",""),"team":scoring_team,"team_name":state.get(f"{scoring_team}_team",scoring_team.title()),"event":"PLAY","label":label,"description":result,"quarter":state.get("quarter","1"),"source":"statistician","created_at":int(time.time()),"score_delta":6 if touchdown else (2 if safety else 0),"before":before,"after":{k:copy.deepcopy(state.get(k)) for k in before},"automation":{"play_type":kind,"yards":str(yards),"pass_outcome":outcome,"fumble":bool(data.get("fumble")),"fumble_lost":bool(data.get("fumble_lost")),"turnover":turnover,"touchdown":touchdown,"safety":safety,"player_name":td_name if touchdown else (player_name or receiver_name),"player_number":td_number if touchdown else (player_number or receiver_number),"sacker_number":sacker_number,"landing_spot":coord_to_spot(landing) if kind in {"kickoff","punt"} else "","kick_distance":kick_distance if kind in {"kickoff","punt"} else 0,"return_yards":return_yards if kind in {"kickoff","punt"} else 0},"media_trigger":{"key":f"touchdown_{scoring_team}" if touchdown else "","assigned":bool(touchdown and (td_number or td_name)),"graphics":"player_touchdown" if touchdown and (td_number or td_name) else None,"audio":None,"video":None}}
        play={"play_id":play_id,"play_number":play_number,"event_id":event_id,"broadcast_id":state.get("broadcast_id",""),"quarter":str(state.get("quarter","1")),"clock":str(data.get("clock", "")),"offense":opposite(team) if kind in {"kickoff","punt"} else team,"defense":team if kind in {"kickoff","punt"} else opposite(team),"kicking_team":team if kind in {"kickoff","punt"} else "","down":old_down,"distance":old_distance,"ball_spot":coord_to_spot(start),"end_spot":coord_to_spot(end),"play_type":kind,"result":result,"yards":yards,"first_down":first_down,"touchdown":touchdown,"turnover":turnover,"safety":safety,"notes":str(data.get("notes","")),"created_by":"statistician","created_at":int(time.time()),"label":label,"player_number":returner_number if kind in {"kickoff","punt"} else (player_number or receiver_number),"player_name":returner_name if kind in {"kickoff","punt"} else (player_name or receiver_name),"passer_number":passer_number,"passer_name":passer_name,"receiver_number":receiver_number,"receiver_name":receiver_name,"sacker_number":sacker_number,"sacker_name":sacker_name,"kicker_number":kicker_number,"kicker_name":kicker_name,"returner_number":returner_number,"returner_name":returner_name,"unresolved_players":[role for role,ref in (("player",player_ref),("passer",passer_ref),("receiver",receiver_ref),("sacker",sacker_ref),("kicker",kicker_ref),("returner",returner_ref)) if ref.get("number") and not ref.get("resolved")],"landing_spot":coord_to_spot(landing) if kind in {"kickoff","punt"} else "","fumble":bool(data.get("fumble")),"fumble_lost":bool(data.get("fumble_lost")),"kneel":bool(data.get("kneel")),"undone":False}
        state["events"]=(list(state.get("events") or [])+[event])[-500:]; state["plays"]=(list(state.get("plays") or [])+[play])[-500:]; state["last_event"]=event
        state["status"]="live"; state["broadcast_phase"]="live"
        save_state(state); return jsonify({"state":state,"play":play})

@app.post("/api/undo")
@require_auth
def undo():
    with lock:
        state = load_state()
        events = list(state.get("events") or [])
        target = next((event for event in reversed(events) if not event.get("undone") and event.get("before")), None)
        if target:
            before = target.get("before") or {}
            state["home_score"] = int(before.get("home_score", state.get("home_score", 0)))
            state["visitor_score"] = int(before.get("visitor_score", state.get("visitor_score", 0)))
            state["possession"] = before.get("possession", state.get("possession", "home"))
            state["down"] = before.get("down", state.get("down", "1st"))
            state["distance"] = before.get("distance", state.get("distance", "10"))
            state["ball_spot"] = before.get("ball_spot", state.get("ball_spot", ""))
            state["quarter"] = before.get("quarter", state.get("quarter", "1"))
            state["clock_seconds"] = int(before.get("clock_seconds", state.get("clock_seconds", 720)) or 0)
            state["clock_running"] = bool(before.get("clock_running", state.get("clock_running", False)))
            append_correction(state, correction_entry("undo", "operator", target.get("after") or {}, before, target.get("id", ""), f"Undid {target.get('label', target.get('event', 'event'))}"))
            if "player_graphic" in before:
                state["player_graphic"] = copy.deepcopy(before.get("player_graphic") or DEFAULT_STATE["player_graphic"])
            # Operational undo removes the mistaken record so Play numbers remain aligned with film/Hudl.
            target_id = target.get("id", "")
            target_play_number = int(target.get("play_number", 0) or 0)
            state["events"] = [row for row in events if row.get("id") != target_id]
            state["plays"] = [row for row in list(state.get("plays") or []) if row.get("event_id") != target_id and row.get("play_id") != target.get("play_id")]
            if target_play_number:
                state["next_play_number"] = target_play_number
            remaining = [row for row in state["events"] if not row.get("undone")]
            state["last_event"] = remaining[-1] if remaining else {}
            save_state(state)
        else:
            history = state.get("history", [])
            if history:
                previous = history.pop()
                previous["history"] = history
                state = normalize_state(previous)
                save_state(state)
        return jsonify(state)

def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"

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
