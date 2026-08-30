from __future__ import annotations

import copy
import json
import hashlib
import os
import sys
import re
import secrets
import signal
import time
import shutil
import tempfile
from functools import wraps
from pathlib import Path
from datetime import date
from threading import Lock
from typing import Any, Callable, Mapping
from urllib.parse import urlparse, quote

from flask import Flask, current_app, jsonify, session
from application_factory import create_application
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
from core_repositories import (
    ConfigurationRepository,
    LocalMirroredStateRepository,
    StateRepository,
    SecurityRepository,
)
from security_service import SecurityService
from broadcast_package_service import BroadcastPackageService
from school_service import SchoolService
from roster_service import RosterService
from sponsor_service import SponsorService
from venue_service import VenueService
from broadcast_service import BroadcastService
from broadcaster_print_service import BroadcasterPrintService
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
from penalty_service import PenaltyService
from rules_service import RulesService
from statistics_service import StatisticsService
from game_operations_service import GameOperationsService
from support_media_service import SupportMediaService
from game_day_safety_service import GameDaySafetyService
from recovery_service import RecoveryService
from commissioning_service import HardwareOBSCommissioningService
from caption_service import CaptionService
from caption_worker import CaptionRuntime
from weather_service import VenueWeatherService
from operational_rehearsal_service import OperationalRehearsalService
from product_paths import resolve_product_paths
from entitlement_service import EntitlementService
from deployment_service import DeploymentService
from theme_service import GraphicsThemeService
from social_service import SocialPublishingService
from social_card_renderer import SocialCardRenderer
from social_asset_resolver import SocialAssetResolver
from social_platforms import default_adapter_registry
from facebook_connection_service import (
    FacebookConnectionService,
    FacebookCredentialVault,
)
from recap_service import GroundedGameRecapService
from broadcast_lifecycle_service import BroadcastLifecycleService
from routes.system_routes import (
    SystemRoutesDependencies,
    create_system_blueprint,
)
from routes.coin_toss_routes import create_coin_toss_blueprint
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
from routes.mhsaa_division_routes import create_mhsaa_division_blueprint
from routes.personnel_routes import (
    PersonnelRoutesDependencies,
    create_personnel_blueprint,
)
from routes.roster_routes import (
    RosterRoutesDependencies,
    create_roster_blueprint,
)
from routes.venue_routes import (
    VenueRoutesDependencies,
    create_venue_blueprint,
)
from routes.asset_routes import (
    AssetRoutesDependencies,
    create_asset_blueprint,
    start_isolated_media_server,
)
from routes.logo_routes import (
    LogoRoutesDependencies,
    create_logo_blueprint,
)
from routes.sponsor_routes import (
    SponsorRoutesDependencies,
    create_sponsor_blueprint,
)
from routes.broadcast_lifecycle_routes import (
    BroadcastLifecycleRoutesDependencies,
    create_broadcast_lifecycle_blueprint,
)
from routes.broadcast_package_routes import (
    BroadcastPackageRoutesDependencies,
    create_broadcast_package_blueprint,
)
from routes.broadcast_routes import (
    BroadcastRoutesDependencies,
    create_broadcast_blueprint,
)
from routes.graphics_routes import (
    GraphicsRoutesDependencies,
    create_graphics_blueprint,
)
from routes.obs_routes import (
    OBSRoutesDependencies,
    create_obs_blueprint,
)
from routes.live_game_routes import (
    LiveGameRoutesDependencies,
    create_live_game_blueprint,
)
from routes.page_routes import (
    PageRoutesDependencies,
    create_page_blueprint,
)
from routes.support_routes import (
    SupportRoutesDependencies,
    create_support_blueprint,
)
from routes.game_day_safety_routes import (
    GameDaySafetyRoutesDependencies,
    create_game_day_safety_blueprint,
)
from routes.recovery_routes import (
    RecoveryRoutesDependencies,
    create_recovery_blueprint,
)
from routes.commissioning_routes import (
    CommissioningRoutesDependencies,
    create_commissioning_blueprint,
)
from routes.caption_routes import (
    CaptionRoutesDependencies,
    create_caption_blueprint,
)
from routes.weather_routes import (
    WeatherRoutesDependencies,
    create_weather_blueprint,
)
from routes.rehearsal_routes import (
    RehearsalRoutesDependencies,
    create_rehearsal_blueprint,
)
from routes.deployment_routes import (
    DeploymentRoutesDependencies,
    create_deployment_blueprint,
)
from routes.theme_routes import (
    ThemeRoutesDependencies,
    create_theme_blueprint,
)
from routes.social_routes import (
    SocialRoutesDependencies,
    create_social_blueprint,
)
from routes.recap_routes import (
    RecapRoutesDependencies,
    create_recap_blueprint,
)
from association_import_service import AssociationImportService
from association_supplement_service import AssociationSupplementService
from association_profile_service import AssociationProfileService
from association_source_service import AssociationSourceService
from dragonfly_service import DragonFlyService
from dragonfly_sync_service import DragonFlySyncService
from association_workflow_service import AssociationWorkflowService
from school_repository import SchoolRepository
from roster_repository import RosterRepository
from sponsor_repository import SponsorRepository
from venue_repository import VenueRepository
from broadcast_repository import BroadcastRepository

# Phase 3 repository boundaries remain integrated below.

BASE_DIR = Path(__file__).resolve().parent
PRODUCT_PATHS = resolve_product_paths(
    BASE_DIR,
    frozen=bool(getattr(sys, "frozen", False) or "--installed" in sys.argv),
)
OVERLAY_SCHEMA_REVISION = "gate6-logo-fallback-v1"
PRODUCT_PATHS.ensure()
STATE_FILE = PRODUCT_PATHS.state_file
SECURITY_FILE = PRODUCT_PATHS.security_file
DATA_DIR = PRODUCT_PATHS.data_dir
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
GAME_DAY_BACKUP_DIR = DATA_DIR / "Backups" / "GameDay"
GAME_DAY_RECOVERY_DIR = DATA_DIR / "Backups" / "Recovery"
COMMISSIONING_FILE = DATA_DIR / "Settings" / "hardware_commissioning.json"
CAPTION_PROFILE_FILE = DATA_DIR / "Settings" / "caption_profile.json"
CAPTION_STATE_FILE = DATA_DIR / "Captions" / "caption_state.json"
CAPTION_TRANSCRIPTS_DIR = DATA_DIR / "Captions" / "Transcripts"
WEATHER_STATE_FILE = DATA_DIR / "Weather" / "weather_state.json"
REHEARSAL_STATE_FILE = DATA_DIR / "Rehearsals" / "rehearsals.json"
RELEASE_MANIFEST_FILE = DATA_DIR / "Releases" / "game_day_release_manifest.json"
THEME_STATE_FILE = DATA_DIR / "Themes" / "theme_state.json"
SOCIAL_STATE_FILE = DATA_DIR / "Social" / "social_state.json"
SOCIAL_CARDS_DIR = DATA_DIR / "Social" / "Cards"
FACEBOOK_CONNECTION_FILE = DATA_DIR / "Social" / "facebook_connection.json"
FACEBOOK_CREDENTIAL_FILE = DATA_DIR / "Social" / "facebook_credentials.dat"
RECAP_STATE_FILE = DATA_DIR / "Recaps" / "recaps.json"

APPLICATION_BLUEPRINTS: list[Any] = []
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
    "coin_toss": {"recorded": False},
    "second_half_receiving_team": "",
    "scorebug_visible": False,
    "visual_mode": "graphic",
    "broadcast_phase": "pregame",
    "crew": {"play_by_play": "", "color_analyst": "", "sideline_reporter": "", "statistician": "", "producer": ""},
    "broadcast_id": "",
    "season": "",
    "week": "1",
    "classification": "",
    "home_classification": "",
    "home_region": "",
    "visitor_classification": "",
    "visitor_region": "",
    "home_pregame_record": {"wins": 0, "losses": 0, "ties": 0},
    "home_pregame_region_record": {"wins": 0, "losses": 0, "ties": 0},
    "visitor_pregame_record": {"wins": 0, "losses": 0, "ties": 0},
    "visitor_pregame_region_record": {"wins": 0, "losses": 0, "ties": 0},
    "contest_type": "official",
    "record_policy": "official",
    "region_game": False,
    "special_designations": [],
    "record_tracking": {},
    "venue_id": "",
    "status": "planned",
    "history": [],
    "events": [],
    "plays": [],
    "last_event": {},
    "next_play_number": 1,
    "ball_spot": "",
    "ball_spot_visible": True,
    "correction_log": [],
    "game_data_authority": "broadcaster",
    "statistician_enabled": False,
    "ticker_visible": True,
    # "fast" == 189 px/s in csrn-production-theme-runtime.js tickerSpeed().
    # "slow" (36 px/s) read as a crawl on broadcast; operators can still pick
    # any preset from the Scroll Speed control. Existing broadcasts keep
    # whatever value their saved state already has -- flip the control to
    # change a game in progress.
    "ticker_speed": "fast",
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
        "passer_name": "",
        "eyebrow": "PLAYER PROFILE",
        "sponsor_id": "",
        "sponsor_lead_in": "",
        "sponsor_name": "",
        "sponsor_logo": "",
        "duration": 0,
        "expires_at": 0,
        "updated_at": 0
    },
    "player_highlight": {
        "visible": False,
        "roster_id": "",
        "player_id": "",
        "school_id": "",
        "full_name": "",
        "display_name": "",
        "number": "",
        "position": "",
        "grade": "",
        "team_logo": "",
        "team_name": "",
        "team_color": "#C9203B",
        "eyebrow": "PLAYER HIGHLIGHT",
        "detail": "",
        "media_asset_id": "",
        "media_name": "",
        "media_url": "",
        "media_type": "video",
        "duration": 0,
        "expires_at": 0,
        "updated_at": 0
    },
    "sponsor_spotlight": {
        "visible": False,
        "sponsor_id": "",
        "sponsor_name": "",
        "sponsor_logo": "",
        "lead_in": "SPONSOR SPOTLIGHT",
        "caption": "",
        "media_asset_id": "",
        "media_name": "",
        "media_url": "",
        "media_type": "image",
        "duration": 0,
        "expires_at": 0,
        "updated_at": 0
    },
    "graphics_queue": [],
}

DEFAULT_SECURITY: dict[str, Any] = {
    "pin_hash": "",
    "secret_key": secrets.token_hex(32),
    "failed_attempts": 0,
    "locked_until": 0,
}


RUNTIME_VERSION = (
    "Version 1.13.0-alpha.8f — Player Identity Repair and Source Alignment"
)
RUNTIME_BUILD = "V1.13A8F-SOURCE-ALIGNMENT"


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
        "refresh_seconds": 60,
        "stale_after_seconds": 180,
        "user_agent": "CSRN-Production-Suite/1.13 (operator-configurable)",
    },
    "licensing": {
        "provider": "",
        "enforcement_mode": "installed_only",
        "activation_endpoint": "",
    },
    "graphics_theme": {
        "active_preset": "modern_network",
        "school_color_adaptation": True,
        "season_lock": False,
    },
    "social": {
        "facebook": "",
        "youtube": "",
        "x": "",
        "website": "",
        "publishing": {
            "preview_first": True,
            "auto_create_drafts": False,
            "allow_auto_publish": False,
            "facebook_credential_ref": "CSRN_FACEBOOK_SECURE_PAGE_TOKEN",
            "facebook_api_version": "v25.0",
            "facebook_connection": "local_oauth_test",
            "x_mode": "assisted_manual",
            "x_oauth": False,
            "x_api": False,
            "x_auto_queue": False,
        },
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
    for name in ("Schools", "Venues", "Logos", "Sources", "Imports", "Broadcasts", "Rosters", "Personnel", "Assets", "Sponsors", "Statistics", "Logs", "Backups", "Settings", "Rehearsals", "Releases", "Themes", "Social", "Recaps"):
        (DATA_DIR / name).mkdir(parents=True, exist_ok=True)
    ASSOCIATION_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    HEADSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    PERSONNEL_HEADSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    SPONSOR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    SOCIAL_CARDS_DIR.mkdir(parents=True, exist_ok=True)

LEGACY_CORE_BACKUP_ROOT = DATA_DIR / "Backups"


def _core_backup_root() -> Path:
    """Local, non-synced home for JsonPersistenceEngine's rolling snapshots
    and quarantine copies.

    Those are written on every save (JsonPersistenceEngine._snapshot ->
    shutil.copy2) and had grown to hundreds of MB inside the Google-Drive-
    synced project tree, where Drive's uploader then churned through every
    one. Disaster-recovery backups do not need cloud redundancy in real
    time; keep them beside the local state authority instead.

    Override with CSRN_CORE_BACKUP_ROOT. Falls back to the old in-Data
    location only when there is no LOCALAPPDATA (non-Windows dev).
    """
    explicit = os.environ.get("CSRN_CORE_BACKUP_ROOT", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    root = os.environ.get("LOCALAPPDATA", "").strip()
    if root:
        return Path(root).expanduser() / "PossumFrog" / "CSRN Production Suite" / "Backups"
    return LEGACY_CORE_BACKUP_ROOT


CORE_BACKUP_ROOT = _core_backup_root()
CORE_BACKUP_DIR = CORE_BACKUP_ROOT / "Core"
CORE_QUARANTINE_DIR = CORE_BACKUP_ROOT / "Quarantine"
CORE_PERSISTENCE = JsonPersistenceEngine(CORE_BACKUP_DIR, CORE_QUARANTINE_DIR)


def legacy_core_backup_notice() -> str | None:
    """One-line startup notice if old snapshots still sit in the synced tree.

    Relocation is intentionally NOT automatic on the live save path -- run
    tools/migrate_core_backups.py --apply when convenient. New snapshots
    already go to CORE_BACKUP_ROOT.
    """
    try:
        if CORE_BACKUP_ROOT.resolve() == LEGACY_CORE_BACKUP_ROOT.resolve():
            return None
        total = 0
        for sub in ("Core", "Quarantine"):
            old_dir = LEGACY_CORE_BACKUP_ROOT / sub
            if not old_dir.is_dir():
                continue
            for f in old_dir.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
        if total <= 0:
            return None
        return (
            f"[note] {total / (1024 * 1024):.0f} MB of old core backups remain in "
            f"{LEGACY_CORE_BACKUP_ROOT} (Drive-synced). New snapshots now go to "
            f"{CORE_BACKUP_ROOT}. Run tools/migrate_core_backups.py --apply to relocate the old ones."
        )
    except OSError:
        return None
CONFIG_REPOSITORY = ConfigurationRepository(
    CORE_PERSISTENCE,
    CONFIG_FILE,
    DEFAULT_CONFIG,
    runtime_identity={
    "version": RUNTIME_VERSION,
    "build": RUNTIME_BUILD,
},
)

def _local_state_authority_path() -> Path:
    explicit = os.environ.get("CSRN_STATE_AUTHORITY_FILE", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    root = os.environ.get("LOCALAPPDATA", "").strip()
    base = Path(root).expanduser() if root else Path.home() / ".possumfrog"
    candidate = base / "PossumFrog" / "CSRN Production Suite" / "GameDay" / "state.json"
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError:
        return Path(tempfile.gettempdir()) / "CSRN" / "GameDay" / "state.json"


def _drive_backed_game_day_state() -> bool:
    explicit = os.environ.get("CSRN_GAME_DAY_LOCAL_STATE", "").strip().lower()
    if explicit in {"0", "false", "no", "off"}:
        return False
    if explicit in {"1", "true", "yes", "on"}:
        return True
    return any(part.lower() in {"my drive", "google drive"} for part in STATE_FILE.parts)


def authority_state_hardlink_warning(path: Any) -> str | None:
    """Return a warning string if the live state authority file has extra hard
    links (st_nlink > 1), else None.

    Tonight's stability incident traced partly to the Google Drive sync client
    hard-linking state.json into `.tmp.driveupload\\<id>` mid-write, which
    defeats the local-authority / Drive-mirror split and lets Drive lock the
    hot write path. A quiet startup check makes a recurrence obvious in the
    console instead of only showing up as mid-game write failures. Warn-only
    by design -- it must never stop CSRN from starting a broadcast.
    """

    try:
        candidate = Path(path)
        if not candidate.exists():
            return None
        nlink = candidate.stat().st_nlink
    except (OSError, TypeError, ValueError):
        return None
    if nlink and nlink > 1:
        return (
            f"[WARN] State authority file has {nlink} hard links: {candidate}. "
            "Something outside CSRN (usually Google Drive's sync client) is "
            "holding another link to the hot write path. Move the live state "
            "out of any synced folder; keep Drive for periodic snapshots only."
        )
    return None


def break_authority_mirror_hardlink(authority: Any, mirror: Any) -> str | None:
    """If the local state authority and the Drive mirror are literally the
    same file (hard-linked -> identical device+inode), rewrite the authority
    in place so the two become independent files. Returns a message when it
    acted, else None.

    A hard-linked pair defeats the whole authority/mirror split: a Drive
    lock on the mirror is a lock on the hot authority write. Every save
    already ``os.replace``s a fresh temp into place, which gives the
    authority a new inode -- this just does that eagerly at startup so the
    files are genuinely separate before the first write (and before the
    throttled mirror's possibly-delayed first write).

    Only a confirmed authority<->mirror pairing is touched. An authority
    whose extra link is Drive's transient ``.tmp.driveupload\\<id>`` is left
    alone; ``authority_state_hardlink_warning`` still surfaces that.
    """

    try:
        a = Path(authority)
        m = Path(mirror)
        if not (a.exists() and m.exists()):
            return None
        sa = a.stat()
        sm = m.stat()
        if not (sa.st_dev == sm.st_dev and sa.st_ino == sm.st_ino):
            return None
        payload = a.read_bytes()
        descriptor, raw_temp = tempfile.mkstemp(
            prefix=f".{a.name}.", suffix=".relink", dir=str(a.parent)
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(raw_temp, str(a))
            raw_temp = None
        finally:
            if raw_temp is not None:
                try:
                    os.unlink(raw_temp)
                except OSError:
                    pass
        return (
            f"[fix] State authority {a} was hard-linked to the Drive mirror "
            f"{m}; rewrote the authority so they are now independent files."
        )
    except OSError:
        return None


STATE_AUTHORITY_PATH = _local_state_authority_path()
DRIVE_BACKED_GAME_DAY_STATE = _drive_backed_game_day_state()


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "").strip() or default)
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except (TypeError, ValueError):
        return default


# The Drive mirror is game-day disaster recovery, not real-time redundancy:
# coalesce writes to at most one per interval / per N mutations so it stops
# contending with Drive's uploader on every play. Tune with
# CSRN_STATE_MIRROR_INTERVAL_SECONDS / CSRN_STATE_MIRROR_MAX_MUTATIONS.
STATE_MIRROR_INTERVAL_SECONDS = _env_float("CSRN_STATE_MIRROR_INTERVAL_SECONDS", 90.0)
STATE_MIRROR_MAX_MUTATIONS = _env_int("CSRN_STATE_MIRROR_MAX_MUTATIONS", 8)

STATE_REPOSITORY = (
    LocalMirroredStateRepository(
        CORE_PERSISTENCE,
        authority_path=STATE_AUTHORITY_PATH,
        mirror_path=STATE_FILE,
        defaults=DEFAULT_STATE,
        mirror_min_interval=STATE_MIRROR_INTERVAL_SECONDS,
        mirror_max_pending_mutations=STATE_MIRROR_MAX_MUTATIONS,
    )
    if DRIVE_BACKED_GAME_DAY_STATE
    else StateRepository(CORE_PERSISTENCE, STATE_FILE, DEFAULT_STATE)
)

if hasattr(STATE_REPOSITORY, "flush"):
    import atexit as _atexit

    _atexit.register(STATE_REPOSITORY.flush)
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

def save_schools(schools: list[dict[str, Any]], *, force: bool = False) -> None:
    ensure_data_architecture()
    SCHOOL_REPOSITORY.save(schools, force=force)


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


def save_venues(items: list[dict[str, Any]], *, force: bool = False) -> None:
    ensure_data_architecture()
    VENUE_REPOSITORY.save(items, force=force)


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


DRAGONFLY_SERVICE: DragonFlyService | None = None


def get_dragonfly_service() -> DragonFlyService:
    global DRAGONFLY_SERVICE

    if DRAGONFLY_SERVICE is None:
        DRAGONFLY_SERVICE = DragonFlyService()

    return DRAGONFLY_SERVICE


DRAGONFLY_SYNC_SERVICE: DragonFlySyncService | None = None


def get_dragonfly_sync_service() -> DragonFlySyncService:
    global DRAGONFLY_SYNC_SERVICE

    if DRAGONFLY_SYNC_SERVICE is None:
        DRAGONFLY_SYNC_SERVICE = DragonFlySyncService(
            dragonfly_service=get_dragonfly_service(),
            load_schools=load_schools,
            load_rosters=load_rosters,
            save_rosters=save_rosters,
        )

    return DRAGONFLY_SYNC_SERVICE


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


def save_sponsors(items: list[dict[str, Any]], *, force: bool = False) -> None:
    ensure_data_architecture()
    SPONSOR_REPOSITORY.save(items, force=force)


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
    *,
    force: bool = False,
) -> None:
    ensure_data_architecture()
    BROADCAST_REPOSITORY.save(items, force=force)


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



BROADCASTER_PRINT_SERVICE: BroadcasterPrintService | None = None


def get_broadcaster_print_service() -> BroadcasterPrintService:
    global BROADCASTER_PRINT_SERVICE

    if BROADCASTER_PRINT_SERVICE is None:
        BROADCASTER_PRINT_SERVICE = BroadcasterPrintService(
            load_broadcasts=load_broadcasts,
            load_rosters=load_rosters,
            load_packages=load_packages,
            get_school_logo_file=lambda school_id, filename: DATA_DIR / "Logos" / normalize_school_id(school_id) / filename,
        )

    return BROADCASTER_PRINT_SERVICE

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

def save_rosters(items: list[dict[str, Any]], *, force: bool = False) -> None:
    ensure_data_architecture()
    ROSTER_REPOSITORY.save(items, force=force)


ROSTER_SERVICE: RosterService | None = None


def get_roster_service() -> RosterService:
    global ROSTER_SERVICE

    if ROSTER_SERVICE is None:
        ROSTER_SERVICE = RosterService(
            load_rosters=load_rosters,
            save_rosters=save_rosters,
            load_schools=load_schools,
            pronunciation_dictionary_path=DATA_DIR / "Rosters" / "pronunciation_dictionary.json",
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
            load_assets=load_assets,
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
    snapshot = copy.deepcopy(normalized)
    # Runs on a dedicated background thread (StateService's async linked-
    # snapshot writer) whenever async_linked_snapshot=True, as it is for the
    # production STATE_SERVICE — never inline on a request thread that might
    # already hold `lock`. Taking `lock` here serializes this read-modify-
    # write of Data/Broadcasts/*.json against write_broadcast_final_archive()
    # below, which runs synchronously inside GameOperationsService's
    # already-held transaction lock (the same `lock` object).
    with lock:
        items = load_broadcasts()
        item = next(
            (row for row in items if row.get("broadcast_id") == broadcast_id),
            None,
        )
        if not item:
            return
        item["live_state"] = snapshot
        item["status"] = normalized.get(
            "status",
            item.get("status", "planned"),
        )
        item["updated_at"] = int(time.time())
        save_broadcasts(items)
        write_broadcast_detail(item)


def write_broadcast_final_archive(state: Mapping[str, Any]) -> bool:
    """Archive a completed broadcast's full state — including its play-by-play
    history — into Data/Broadcasts/<id>.json, and confirm the write by
    reading it back from disk before reporting success.

    Must be called while `lock` is already held (GameOperationsService runs
    this synchronously inside its transaction lock), so it can't race the
    background linked-snapshot writer above.

    Returns True only once the archive has been verified on disk to contain
    the expected history/events/plays. The caller (GameOperationsService)
    must not clear the live state unless this returns True.
    """
    broadcast_id = str(state.get("broadcast_id", "")).strip()
    if not broadcast_id:
        return False

    snapshot = copy.deepcopy(dict(state))
    expected_history = list(snapshot.get("history") or [])
    expected_events = list(snapshot.get("events") or [])
    expected_plays = list(snapshot.get("plays") or [])

    try:
        items = load_broadcasts()
        item = next(
            (row for row in items if row.get("broadcast_id") == broadcast_id),
            None,
        )
        if item is None:
            return False
        item["final_state_archive"] = snapshot
        item["final_state_archived_at"] = int(time.time())
        # Also bring the ongoing live-mirror up to the same, uncleared
        # snapshot right now — the regular async mirror will overwrite it
        # again shortly after with the (soon to be cleared) live state, which
        # is fine: final_state_archive above is the durable record, live_state
        # is only ever a reflection of whatever state.json currently holds.
        item["live_state"] = copy.deepcopy(snapshot)
        item["status"] = snapshot.get("status", item.get("status", "planned"))
        item["updated_at"] = int(time.time())
        save_broadcasts(items)
        write_broadcast_detail(item)
    except Exception:
        return False

    detail_path = DATA_DIR / "Broadcasts" / f"{broadcast_id}.json"
    try:
        written = json.loads(detail_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(written, dict):
        return False
    archive = written.get("final_state_archive")
    if not isinstance(archive, dict):
        return False
    if str(archive.get("broadcast_id", "")).strip() != broadcast_id:
        return False
    if (
        list(archive.get("history") or []) != expected_history
        or list(archive.get("events") or []) != expected_events
        or list(archive.get("plays") or []) != expected_plays
    ):
        return False
    return True


def load_final_state_archive(broadcast_id: str) -> dict[str, Any] | None:
    key = str(broadcast_id or "").strip()
    if not key:
        return None
    detail_path = DATA_DIR / "Broadcasts" / f"{key}.json"
    try:
        item = json.loads(detail_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(item, dict):
        return None
    archive = item.get("final_state_archive")
    return archive if isinstance(archive, dict) else None


def load_state_for_reporting() -> dict[str, Any]:
    """Read-only variant of load_state() for reporting consumers (recap
    generation, social drafting, the statistics and play-register endpoints)
    that may run after a broadcast has been finalized.

    GameOperationsService.end_game() clears history/events/plays from the
    live state.json once it has confirmed a full archive was written (see
    write_broadcast_final_archive above). A reporting request made after
    that point would otherwise see an empty game, so once state.json shows
    a completed broadcast with those fields empty, this transparently backs
    them from the archived snapshot in Data/Broadcasts/<id>.json.

    Never use this for state mutation — only load_state()/save_state() are
    the write path, and mutating a copy built from the archived fallback
    would write archived history back into "live" state.
    """
    state = load_state()
    if str(state.get("status", "")).strip().lower() != "completed":
        return state
    # events/plays are what statistics/recap/play-register actually consume
    # -- history is irrelevant to whether backfilling is needed. Checking
    # history here was the bug: a stray leftover history entry (e.g. from
    # set_control_source() running after end_game() -- see
    # StateService.push_history()'s completed-broadcast guard) made this
    # `or` trip and skip the archive fallback even though events/plays were
    # both genuinely empty.
    if state.get("events") or state.get("plays"):
        return state
    broadcast_id = str(state.get("broadcast_id", "") or "").strip()
    if not broadcast_id:
        return state
    archive = load_final_state_archive(broadcast_id)
    if not archive:
        return state
    result = dict(state)
    for key in ("history", "events", "plays"):
        if archive.get(key):
            result[key] = copy.deepcopy(archive[key])
    return result


def get_state_service() -> StateService:
    global STATE_SERVICE
    if STATE_SERVICE is None:
        STATE_SERVICE = StateService(
            load_raw=STATE_REPOSITORY.load,
            replace_raw=STATE_REPOSITORY.replace,
            default_state=lambda: copy.deepcopy(DEFAULT_STATE),
            persist_linked_snapshot=persist_linked_state_snapshot,
            async_linked_snapshot=True,
            cache_committed_state=True,
            resolve_player=resolve_game_roster_player,
            canonical_team_key=canonical_team_key,
            canonical_team_name=canonical_team_name,
        )
    return STATE_SERVICE


def load_state() -> dict[str, Any]:
    return get_state_service().load().data["state"]


def save_state(state: dict[str, Any]) -> None:
    get_state_service().save(state)
    try:
        from state_read_cache import invalidate_state_read_cache
        from runtime_state_cache import invalidate_runtime_state_cache

        invalidate_state_read_cache()
        invalidate_runtime_state_cache()
    except Exception:
        pass


def load_reconciled_state() -> dict[str, Any]:
    with lock:
        state = load_state()
        result = get_graphics_service().reconcile_queue(state)
        reconciled = result.data["state"]
        if result.data.get("changed"):
            save_state(reconciled)
        return reconciled


def _merge_opening_setup_state(result: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    for key in ("coin_toss", "second_half_receiving_team", "special_game_phase", "kicking_team", "receiving_team"):
        if key in state:
            result[key] = copy.deepcopy(state.get(key))
    return result


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    result = get_state_service().public(state).data["state"]
    _merge_opening_setup_state(result, state)
    result["overlay_revision"] = OVERLAY_SCHEMA_REVISION
    return result


def runtime_state(state: dict[str, Any]) -> dict[str, Any]:
    result = get_state_service().runtime_view(state).data["state"]
    _merge_opening_setup_state(result, state)
    result["overlay_revision"] = OVERLAY_SCHEMA_REVISION
    return result

def load_security() -> dict[str, Any]:
    return SECURITY_SERVICE.ensure_secret_key(
        lambda: secrets.token_hex(32)
    )


def save_security(sec: dict[str, Any]) -> None:
    SECURITY_REPOSITORY.save(sec)

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
    setattr(wrapper, "_csrn_requires_auth", True)
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


PAGE_ROUTES_BLUEPRINT = create_page_blueprint(
    PageRoutesDependencies(
        application_identity=lambda: application_identity(),
    )
)
APPLICATION_BLUEPRINTS.append(PAGE_ROUTES_BLUEPRINT)


BROADCAST_PACKAGE_ROUTES_BLUEPRINT = create_broadcast_package_blueprint(
    BroadcastPackageRoutesDependencies(
        require_auth=require_auth,
        get_package_service=get_broadcast_package_service,
        public_state=lambda state: public_state(state),
    )
)
APPLICATION_BLUEPRINTS.append(BROADCAST_PACKAGE_ROUTES_BLUEPRINT)


SPONSOR_ROUTES_BLUEPRINT = create_sponsor_blueprint(
    SponsorRoutesDependencies(
        require_auth=require_auth,
        get_sponsor_service=get_sponsor_service,
        load_sponsors=lambda: load_sponsors(),
        load_assets=lambda: load_assets(),
        save_assets=lambda items: save_assets(items),
        clean_asset_record=lambda payload, asset_id: clean_asset_record(
            payload,
            asset_id,
        ),
        asset_file_hash=lambda path: asset_file_hash(path),
        get_asset_upload_dir=lambda: ASSET_UPLOAD_DIR,
        get_sponsor_upload_dir=lambda: SPONSOR_UPLOAD_DIR,
        clock=lambda: time.time(),
        token_hex=lambda length: secrets.token_hex(length),
    )
)
APPLICATION_BLUEPRINTS.append(SPONSOR_ROUTES_BLUEPRINT)

ASSET_ROUTES_BLUEPRINT = create_asset_blueprint(
    AssetRoutesDependencies(
        require_auth=require_auth,
        get_asset_service=get_asset_service,
        get_upload_dir=lambda: ASSET_UPLOAD_DIR,
        extension_allowed=AssetService.extension_allowed,
        normalize_asset_id=AssetService.normalize_id,
        clock=lambda: time.time(),
        token_hex=lambda length: secrets.token_hex(length),
    )
)
APPLICATION_BLUEPRINTS.append(ASSET_ROUTES_BLUEPRINT)


PERSONNEL_ROUTES_BLUEPRINT = create_personnel_blueprint(
    PersonnelRoutesDependencies(
        require_auth=require_auth,
        get_personnel_service=get_personnel_service,
        get_headshots_dir=lambda: PERSONNEL_HEADSHOTS_DIR,
        normalize_personnel_id=PersonnelService.normalize_id,
    )
)
APPLICATION_BLUEPRINTS.append(PERSONNEL_ROUTES_BLUEPRINT)

ROSTER_ROUTES_BLUEPRINT = create_roster_blueprint(
    RosterRoutesDependencies(
        require_auth=require_auth,
        get_roster_service=get_roster_service,
    )
)
APPLICATION_BLUEPRINTS.append(ROSTER_ROUTES_BLUEPRINT)

VENUE_ROUTES_BLUEPRINT = create_venue_blueprint(
    VenueRoutesDependencies(
        require_auth=require_auth,
        get_venue_service=get_venue_service,
    )
)
APPLICATION_BLUEPRINTS.append(VENUE_ROUTES_BLUEPRINT)


SCHOOL_ROUTES_BLUEPRINT = create_school_blueprint(
    SchoolRoutesDependencies(
        require_auth=require_auth,
        get_school_service=get_school_service,
    )
)
APPLICATION_BLUEPRINTS.append(SCHOOL_ROUTES_BLUEPRINT)

ASSOCIATION_ROUTES_BLUEPRINT = create_association_blueprint(
    AssociationRoutesDependencies(
        require_auth=require_auth,
        get_profile_service=get_association_profile_service,
        get_workflow_service=get_association_workflow_service,
        get_import_service=get_association_import_service,
        get_supplement_service=get_association_supplement_service,
        get_dragonfly_service=get_dragonfly_service,
        get_dragonfly_sync_service=get_dragonfly_sync_service,
        get_school_service=get_school_service,
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
APPLICATION_BLUEPRINTS.append(ASSOCIATION_ROUTES_BLUEPRINT)

MHSAA_DIVISION_ROUTES_BLUEPRINT = create_mhsaa_division_blueprint(
    require_auth=require_auth,
    get_import_service=get_association_import_service,
    imports_dir=IMPORTS_DIR,
)
APPLICATION_BLUEPRINTS.append(MHSAA_DIVISION_ROUTES_BLUEPRINT)


def _hex(rgb: tuple[int, int, int]) -> str:
    return LogoService._hex(rgb)


def extract_logo_colors(image: Image.Image) -> list[str]:
    return LogoService.extract_colors(image)


def normalize_round_logo(source: Image.Image, size: int) -> Image.Image:
    return LogoService.normalize_round_logo(source, size)


LOGO_ROUTES_BLUEPRINT = create_logo_blueprint(
    LogoRoutesDependencies(
        require_auth=require_auth,
        get_logo_service=get_logo_service,
        get_base_dir=lambda: BASE_DIR,
        get_school_logo_dir=lambda school_id: (
            DATA_DIR / "Logos" / normalize_school_id(school_id)
        ),
        normalize_school_id=normalize_school_id,
    )
)
APPLICATION_BLUEPRINTS.append(LOGO_ROUTES_BLUEPRINT)


UPGRADE_SERVICE: UpgradeService | None = None


def activate_upgrade_secret_key(secret_key: str) -> None:
    current_app.secret_key = secret_key


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
APPLICATION_BLUEPRINTS.append(SECURITY_UPGRADE_ROUTES_BLUEPRINT)


OBS_ROUTES_BLUEPRINT = create_obs_blueprint(
    OBSRoutesDependencies(
        require_auth=require_auth,
        get_obs_service=lambda: get_obs_service(),
    )
)
APPLICATION_BLUEPRINTS.append(OBS_ROUTES_BLUEPRINT)


def command_scorebug_visibility(visible: bool) -> dict[str, Any]:
    result = get_obs_service().scorebug_visibility(visible)
    if not result.ok:
        raise OBSConnectionError(
            str(result.data.get("message", result.code))
        )
    return result.data["obs"]


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
        load_state=load_reconciled_state,
        load_runtime_state=load_state,
        public_state=public_state,
        runtime_state=runtime_state,
        readiness_payload=readiness_payload,
        load_build_journal=load_build_journal,
    )
)
APPLICATION_BLUEPRINTS.append(SYSTEM_ROUTES_BLUEPRINT)

COIN_TOSS_ROUTES_BLUEPRINT = create_coin_toss_blueprint(
    require_auth=require_auth,
    load_state=load_state,
    save_state=save_state,
    public_state=public_state,
    transaction_lock=lock,
    clock=time.time,
)
APPLICATION_BLUEPRINTS.append(COIN_TOSS_ROUTES_BLUEPRINT)


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


BROADCAST_LIFECYCLE_ROUTES_BLUEPRINT = create_broadcast_lifecycle_blueprint(
    BroadcastLifecycleRoutesDependencies(
        require_auth=require_auth,
        get_lifecycle_service=get_broadcast_lifecycle_service,
    )
)
APPLICATION_BLUEPRINTS.append(BROADCAST_LIFECYCLE_ROUTES_BLUEPRINT)

BROADCAST_ROUTES_BLUEPRINT = create_broadcast_blueprint(
    BroadcastRoutesDependencies(
        require_auth=require_auth,
        get_broadcast_service=get_broadcast_service,
        get_broadcaster_print_service=get_broadcaster_print_service,
    )
)
APPLICATION_BLUEPRINTS.append(BROADCAST_ROUTES_BLUEPRINT)


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
            archive_final_state=write_broadcast_final_archive,
            transaction_lock=lock,
        )
    return GAME_OPERATIONS_SERVICE


LIVE_GAME_ROUTES_BLUEPRINT = create_live_game_blueprint(
    LiveGameRoutesDependencies(
        require_auth=require_auth,
        get_game_operations_service=lambda: get_game_operations_service(),
        get_event_service=lambda: get_event_service(),
        get_rules_service=lambda: get_rules_service(),
        get_statistics_service=lambda: get_statistics_service(),
        load_state=lambda: load_state(),
        load_state_for_reporting=lambda: load_state_for_reporting(),
        load_rosters=lambda: load_rosters(),
    )
)
APPLICATION_BLUEPRINTS.append(LIVE_GAME_ROUTES_BLUEPRINT)


GAME_DAY_SAFETY_SERVICE: GameDaySafetyService | None = None


def get_game_day_safety_service() -> GameDaySafetyService:
    global GAME_DAY_SAFETY_SERVICE
    if GAME_DAY_SAFETY_SERVICE is None:
        GAME_DAY_SAFETY_SERVICE = GameDaySafetyService(
            base_dir=BASE_DIR,
            data_dir=DATA_DIR,
            backup_root=GAME_DAY_BACKUP_DIR,
            state_file=STATE_FILE,
            security_file=SECURITY_FILE,
            config_file=CONFIG_FILE,
            version_file=VERSION_FILE,
            clock=time.time,
        )
    return GAME_DAY_SAFETY_SERVICE


GAME_DAY_SAFETY_ROUTES_BLUEPRINT = create_game_day_safety_blueprint(
    GameDaySafetyRoutesDependencies(
        require_auth=require_auth,
        get_safety_service=lambda: get_game_day_safety_service(),
    )
)
APPLICATION_BLUEPRINTS.append(GAME_DAY_SAFETY_ROUTES_BLUEPRINT)


RECOVERY_SERVICE: RecoveryService | None = None


def get_recovery_service() -> RecoveryService:
    global RECOVERY_SERVICE
    if RECOVERY_SERVICE is None:
        RECOVERY_SERVICE = RecoveryService(
            safety_service=get_game_day_safety_service(),
            data_dir=DATA_DIR,
            backup_root=GAME_DAY_BACKUP_DIR,
            recovery_root=GAME_DAY_RECOVERY_DIR,
            state_file=STATE_FILE,
            security_file=SECURITY_FILE,
            version_file=VERSION_FILE,
            load_state=load_state,
            clock=time.time,
            transaction_lock=lock,
        )
    return RECOVERY_SERVICE


RECOVERY_ROUTES_BLUEPRINT = create_recovery_blueprint(
    RecoveryRoutesDependencies(
        require_auth=require_auth,
        get_recovery_service=lambda: get_recovery_service(),
    )
)
APPLICATION_BLUEPRINTS.append(RECOVERY_ROUTES_BLUEPRINT)


COMMISSIONING_SERVICE: HardwareOBSCommissioningService | None = None


def get_commissioning_service() -> HardwareOBSCommissioningService:
    global COMMISSIONING_SERVICE
    if COMMISSIONING_SERVICE is None:
        COMMISSIONING_SERVICE = HardwareOBSCommissioningService(
            profile_file=COMMISSIONING_FILE,
            load_config=load_config,
            validate_obs=lambda: get_obs_service().test_connection().data["obs"],
            clock=time.time,
        )
    return COMMISSIONING_SERVICE


COMMISSIONING_ROUTES_BLUEPRINT = create_commissioning_blueprint(
    CommissioningRoutesDependencies(
        require_auth=require_auth,
        get_commissioning_service=lambda: get_commissioning_service(),
    )
)
APPLICATION_BLUEPRINTS.append(COMMISSIONING_ROUTES_BLUEPRINT)


CAPTION_SERVICE: CaptionService | None = None
CAPTION_RUNTIME: CaptionRuntime | None = None


def get_caption_service() -> CaptionService:
    global CAPTION_SERVICE
    if CAPTION_SERVICE is None:
        CAPTION_SERVICE = CaptionService(
            profile_file=CAPTION_PROFILE_FILE,
            state_file=CAPTION_STATE_FILE,
            transcripts_dir=CAPTION_TRANSCRIPTS_DIR,
            clock=time.time,
        )
    return CAPTION_SERVICE


def current_caption_broadcast_id() -> str:
    return str(load_state().get("broadcast_id") or "unscheduled")


def _caption_active_rosters(state: dict[str, Any]) -> list[dict[str, Any]]:
    sport = str(state.get("sport") or "Football").strip().casefold()
    level = str(state.get("level") or "Varsity").strip().casefold()
    linked_ids = {str(value) for value in (state.get("package_roster_ids") or []) if str(value).strip()}
    school_ids = {
        str(state.get("home_school_id") or "").strip(),
        str(state.get("visitor_school_id") or "").strip(),
    }
    school_ids.discard("")
    team_names = {
        str(state.get("home_team") or "").strip().casefold(),
        str(state.get("visitor_team") or "").strip().casefold(),
    }
    team_names.discard("")

    def roster_school_name(roster: dict[str, Any]) -> str:
        school = get_school(str(roster.get("school_id", "") or ""))
        return str(
            (school or {}).get("broadcast_name")
            or (school or {}).get("official_name")
            or roster.get("school_id", "")
        ).strip().casefold()

    def is_candidate(roster: dict[str, Any]) -> bool:
        roster_id = str(roster.get("id", "") or "")
        if linked_ids and roster_id in linked_ids:
            return True
        roster_school_id = str(roster.get("school_id", "") or "").strip()
        school_match = roster_school_id in school_ids or roster_school_name(roster) in team_names
        sport_match = not roster.get("sport") or str(roster.get("sport", "")).strip().casefold() == sport
        return school_match and sport_match

    rosters = [roster for roster in load_rosters() if isinstance(roster, dict) and is_candidate(roster)]
    preferred = [
        roster
        for roster in rosters
        if str(roster.get("level", "") or "").strip().casefold() in {"", level, "varsity"}
    ]
    return preferred or rosters


def _caption_name_terms_from_rosters(state: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for roster in _caption_active_rosters(state):
        for player in roster.get("players", []) if isinstance(roster.get("players"), list) else []:
            if not isinstance(player, dict):
                continue
            if str(player.get("status", "active") or "active").strip().casefold() == "inactive":
                continue
            first = str(player.get("first_name") or "").strip()
            last = str(player.get("last_name") or "").strip()
            preferred = str(player.get("preferred_name") or "").strip()
            pronunciation = str(player.get("pronunciation") or "").strip()
            number = str(player.get("number") or "").strip()
            full_name = " ".join(part for part in (first, last) if part)
            display_name = " ".join(part for part in (preferred or first, last) if part)
            for value in (full_name, display_name, preferred, last, pronunciation):
                if value:
                    terms.append(value)
            if number and full_name:
                terms.append(f"number {number} {full_name}")
            if number and display_name and display_name != full_name:
                terms.append(f"number {number} {display_name}")
    return terms


def _caption_name_terms_from_personnel(state: dict[str, Any]) -> list[str]:
    school_ids = {
        str(state.get("home_school_id") or "").strip(),
        str(state.get("visitor_school_id") or "").strip(),
        "",
    }
    terms: list[str] = []
    for person in load_broadcasters():
        if not isinstance(person, dict):
            continue
        if str(person.get("status", "active") or "active").strip().casefold() == "inactive":
            continue
        school_id = str(person.get("school_id") or "").strip()
        category = str(person.get("category") or "").strip().casefold()
        role = str(person.get("role") or person.get("primary_role") or person.get("title") or "").strip().casefold()
        if school_id and school_id not in school_ids:
            continue
        if school_id or category in {"coach", "broadcast talent"} or "coach" in role or "play-by-play" in role or "analyst" in role:
            for key in ("full_name", "name", "preferred_name", "pronunciation"):
                value = str(person.get(key) or "").strip()
                if value:
                    terms.append(value)
            title = str(person.get("title") or person.get("role") or "").strip()
            name = str(person.get("full_name") or person.get("name") or "").strip()
            if title and name:
                terms.append(f"{title} {name}")
    return terms


def current_caption_prompt_terms() -> list[str]:
    state = load_state()
    terms: list[str] = []
    for side in ("home", "visitor"):
        terms.extend(
            [
                state.get(f"{side}_team", ""),
                state.get(f"{side}_identity", {}).get("broadcast_name", ""),
                state.get(f"{side}_identity", {}).get("official_name", ""),
                state.get(f"{side}_identity", {}).get("preferred_scorebug_name", ""),
                state.get(f"{side}_identity", {}).get("mascot", ""),
            ]
        )
    terms.extend(["Cavaliers", "first and ten", "yard line"])
    terms.extend(_caption_name_terms_from_rosters(state))
    terms.extend(_caption_name_terms_from_personnel(state))
    seen: set[str] = set()
    cleaned: list[str] = []
    for term in terms:
        value = " ".join(str(term or "").split())
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            cleaned.append(value)
    return cleaned


def get_caption_runtime() -> CaptionRuntime:
    global CAPTION_RUNTIME
    if CAPTION_RUNTIME is None:
        CAPTION_RUNTIME = CaptionRuntime(
            caption_service=get_caption_service(),
            load_broadcast_id=current_caption_broadcast_id,
            build_prompt_terms=current_caption_prompt_terms,
            clock=time.time,
        )
    return CAPTION_RUNTIME


CAPTION_ROUTES_BLUEPRINT = create_caption_blueprint(
    CaptionRoutesDependencies(
        require_auth=require_auth,
        get_caption_service=lambda: get_caption_service(),
        get_caption_runtime=lambda: get_caption_runtime(),
    )
)
APPLICATION_BLUEPRINTS.append(CAPTION_ROUTES_BLUEPRINT)


WEATHER_SERVICE: VenueWeatherService | None = None


def get_weather_service() -> VenueWeatherService:
    global WEATHER_SERVICE
    if WEATHER_SERVICE is None:
        WEATHER_SERVICE = VenueWeatherService(
            state_file=WEATHER_STATE_FILE,
            load_state=load_state,
            load_config=load_config,
            load_venues=load_venues,
            save_venues=save_venues,
            load_schools=load_schools,
            clock=time.time,
        )
    return WEATHER_SERVICE


WEATHER_ROUTES_BLUEPRINT = create_weather_blueprint(
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


ENTITLEMENT_SERVICE: EntitlementService | None = None


def get_entitlement_service() -> EntitlementService:
    global ENTITLEMENT_SERVICE
    if ENTITLEMENT_SERVICE is None:
        ENTITLEMENT_SERVICE = EntitlementService(
            paths=PRODUCT_PATHS,
            verifier=None,
            clock=time.time,
        )
    return ENTITLEMENT_SERVICE


DEPLOYMENT_SERVICE: DeploymentService | None = None


def get_deployment_service() -> DeploymentService:
    global DEPLOYMENT_SERVICE
    if DEPLOYMENT_SERVICE is None:
        DEPLOYMENT_SERVICE = DeploymentService(
            paths=PRODUCT_PATHS,
            version_file=VERSION_FILE,
            entitlement_service=get_entitlement_service(),
            create_snapshot=lambda **kwargs: get_game_day_safety_service().create_snapshot(**kwargs),
            clock=time.time,
        )
    return DEPLOYMENT_SERVICE


DEPLOYMENT_ROUTES_BLUEPRINT = create_deployment_blueprint(
    DeploymentRoutesDependencies(
        require_auth=require_auth,
        get_deployment_service=lambda: get_deployment_service(),
        get_entitlement_service=lambda: get_entitlement_service(),
    )
)
APPLICATION_BLUEPRINTS.append(DEPLOYMENT_ROUTES_BLUEPRINT)


THEME_SERVICE: GraphicsThemeService | None = None


def get_theme_service() -> GraphicsThemeService:
    global THEME_SERVICE
    if THEME_SERVICE is None:
        THEME_SERVICE = GraphicsThemeService(
            state_file=THEME_STATE_FILE,
            load_state=load_state,
            load_config=load_config,
            clock=time.time,
        )
    return THEME_SERVICE


THEME_ROUTES_BLUEPRINT = create_theme_blueprint(
    ThemeRoutesDependencies(
        require_auth=require_auth,
        get_theme_service=lambda: get_theme_service(),
    )
)
APPLICATION_BLUEPRINTS.append(THEME_ROUTES_BLUEPRINT)


SOCIAL_SERVICE: SocialPublishingService | None = None
FACEBOOK_CONNECTION_SERVICE: FacebookConnectionService | None = None
FACEBOOK_CREDENTIAL_VAULT = FacebookCredentialVault(FACEBOOK_CREDENTIAL_FILE)


def get_social_service() -> SocialPublishingService:
    global SOCIAL_SERVICE
    if SOCIAL_SERVICE is None:
        resolver = SocialAssetResolver(
            base_dir=BASE_DIR,
            data_dir=DATA_DIR,
            asset_upload_dir=ASSET_UPLOAD_DIR,
            headshots_dir=HEADSHOTS_DIR,
        )
        SOCIAL_SERVICE = SocialPublishingService(
            state_file=SOCIAL_STATE_FILE,
            renderer=SocialCardRenderer(
                output_dir=SOCIAL_CARDS_DIR,
                asset_resolver=resolver,
            ),
            adapters=default_adapter_registry(
                credential_resolver=FACEBOOK_CREDENTIAL_VAULT.resolve
            ),
            load_broadcast_state=load_state_for_reporting,
            load_config=load_config,
            load_rosters=load_rosters,
            load_sponsors=load_sponsors,
            active_sponsor_by_id=active_sponsor_by_id,
            get_theme_status=lambda: get_theme_service().status(),
            credential_available=FACEBOOK_CREDENTIAL_VAULT.available,
            clock=time.time,
        )
    return SOCIAL_SERVICE




def get_facebook_connection_service() -> FacebookConnectionService:
    global FACEBOOK_CONNECTION_SERVICE
    if FACEBOOK_CONNECTION_SERVICE is None:
        FACEBOOK_CONNECTION_SERVICE = FacebookConnectionService(
            settings_file=FACEBOOK_CONNECTION_FILE,
            vault=FACEBOOK_CREDENTIAL_VAULT,
            save_social_account=lambda payload: get_social_service().configure_account(payload),
            remove_social_account=lambda account_id, confirmation: get_social_service().remove_account(
                account_id, confirmation
            ),
            clock=time.time,
        )
    return FACEBOOK_CONNECTION_SERVICE

SOCIAL_ROUTES_BLUEPRINT = create_social_blueprint(
    SocialRoutesDependencies(
        require_auth=require_auth,
        get_social_service=lambda: get_social_service(),
        get_facebook_connection_service=lambda: get_facebook_connection_service(),
    )
)
APPLICATION_BLUEPRINTS.append(SOCIAL_ROUTES_BLUEPRINT)


RECAP_SERVICE: GroundedGameRecapService | None = None


def _create_recap_social_draft(recap: dict[str, Any]):
    summary = str(recap.get("social_summary") or recap.get("lead") or "").strip()
    return get_social_service().create_draft(
        "FINAL",
        payload={
            "headline": str(recap.get("headline") or "FINAL").strip(),
            "message": summary,
            "detail": summary,
            "postgame_summary": True,
            "recap_id": str(recap.get("id") or ""),
            "broadcast_id": str(recap.get("broadcast_id") or ""),
        },
        force_duplicate=True,
    )


def get_recap_service() -> GroundedGameRecapService:
    global RECAP_SERVICE
    if RECAP_SERVICE is None:
        RECAP_SERVICE = GroundedGameRecapService(
            state_file=RECAP_STATE_FILE,
            load_broadcast_state=load_state_for_reporting,
            create_social_draft=_create_recap_social_draft,
            clock=time.time,
        )
    return RECAP_SERVICE


RECAP_ROUTES_BLUEPRINT = create_recap_blueprint(
    RecapRoutesDependencies(
        require_auth=require_auth,
        get_recap_service=lambda: get_recap_service(),
    )
)
APPLICATION_BLUEPRINTS.append(RECAP_ROUTES_BLUEPRINT)


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


SUPPORT_ROUTES_BLUEPRINT = create_support_blueprint(
    SupportRoutesDependencies(
        require_auth=require_auth,
        get_support_media_service=lambda: get_support_media_service(),
        get_headshots_dir=lambda: HEADSHOTS_DIR,
        connection_port=5050,
    )
)
APPLICATION_BLUEPRINTS.append(SUPPORT_ROUTES_BLUEPRINT)


def activate_primary_graphic(state: dict[str, Any], active: str) -> None:
    """Keep the legacy mutating helper while delegating graphic rules."""
    updated = get_graphics_service().activate_primary(state, active)
    state.clear()
    state.update(updated)


GRAPHICS_ROUTES_BLUEPRINT = create_graphics_blueprint(
    GraphicsRoutesDependencies(
        require_auth=require_auth,
        get_graphics_service=lambda: get_graphics_service(),
        load_state=lambda: load_state(),
        save_state=lambda state: save_state(state),
        public_state=lambda state: public_state(state),
        transaction_lock=lock,
    )
)
APPLICATION_BLUEPRINTS.append(GRAPHICS_ROUTES_BLUEPRINT)


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


def _roster_player_by_school_and_number(school_id: str, number: str):
    """Best-effort lookup used to backfill a manually-entered player (typed
    number, no roster_id/player_id) with their real roster headshot -- the
    same kind of number-match already used for stat-rail headshot decoration
    in routes/live_game_routes.py, applied here for the player-spotlight path.
    """
    school_id = str(school_id or "").strip()
    number = str(number or "").strip()
    if not school_id or not number:
        return None
    candidates = [
        player
        for roster in load_rosters()
        if str(roster.get("school_id", "") or "") == school_id
        for player in roster.get("players", [])
        if isinstance(player, dict)
        and str(player.get("number", "") or "").strip() == number
        and str(player.get("status", "active") or "active").strip().casefold() != "inactive"
    ]
    return candidates[0] if candidates else None


def manual_automation_player(data, team_name, school_id=""):
    if not isinstance(data, dict) or not str(data.get("number", "")).strip():
        return None
    number = str(data.get("number", "")).strip()
    name = str(data.get("name", "")).strip() or f"{team_name} {number}"
    parts = name.split(" ", 1)
    result = {
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
    roster_match = _roster_player_by_school_and_number(school_id, number)
    if roster_match:
        result["headshot"] = str(roster_match.get("headshot", "") or "")
        for key in ("grade", "height", "weight"):
            if not result[key]:
                result[key] = str(roster_match.get(key, "") or "")
    return result

def show_automation_player_graphic(
    state,
    roster,
    player,
    graphic_type,
    duration,
    defensive=False,
    eyebrow="",
    play_detail="",
    sponsor_id="",
    passer_name="",
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
        sponsor_id=sponsor_id,
        passer_name=passer_name,
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
    return {
        "number": jersey,
        "name": name,
        "resolved": True,
        "roster_id": str(roster.get("id", "")),
        "player_id": str(player.get("id", "")),
        "headshot": str(player.get("headshot", "") or ""),
        "position": str(player.get("position", "") or ""),
        "grade": str(player.get("grade", "") or ""),
        "height": str(player.get("height", "") or ""),
        "weight": str(player.get("weight", "") or ""),
    }

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
    options = copy.deepcopy(state.get("_pending_penalty_options") or {})
    possession = str(state.get("possession", "home") or "home").lower()
    if category == "Defensive":
        default_selected_team = "visitor" if possession == "home" else "home"
    else:
        default_selected_team = possession
    selected_team = str(options.get("selected_team") or default_selected_team)
    requested_unit = str(options.get("requested_unit") or category)
    return PenaltyService.enforce(
        state,
        selected_team=selected_team,
        requested_unit=requested_unit,
        name=name,
        yards=yards,
        outcome=outcome,
        spot_to_coord=spot_to_coord,
        coord_to_spot=coord_to_spot,
        team_direction=team_direction,
        enforcement_spot=options.get("enforcement_spot", ""),
        half_distance=bool(options.get("half_distance")),
        automatic_first_down=bool(options.get("automatic_first_down")),
        loss_of_down=bool(options.get("loss_of_down")),
        untimed_down=bool(options.get("untimed_down")),
        retry_down=bool(options.get("retry_down")),
    )

def local_addresses() -> list[str]:
    return get_support_media_service().local_addresses()


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
            resolve_player=resolve_game_roster_player,
            on_event=lambda event: get_social_service().queue_event(event),
            transaction_lock=lock,
        )
    return EVENT_SERVICE


def game_data_source_allowed(state: dict[str, Any], source: str) -> bool:
    return EventService.source_allowed(state, source)


def authority_rejection(state: dict[str, Any]):
    return jsonify(EventService.locked_payload(state)), 409


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


def local_ip() -> str:
    return SupportMediaService.local_ip()


def create_app(
    config_overrides: dict[str, Any] | None = None,
) -> Flask:
    """Build a configured CSRN application from the consolidated Blueprints."""

    security = load_security()
    return create_application(
        __name__,
        blueprints=tuple(APPLICATION_BLUEPRINTS),
        secret_key=str(security["secret_key"]),
        session_seconds=SESSION_SECONDS,
        config_overrides=config_overrides,
    )


app = create_app()



# Gate 18.4 R11.7 - coalesce expensive public-state reads across concurrent clients.
from state_read_cache import install_state_read_cache
install_state_read_cache(app)
from runtime_state_cache import install_runtime_state_cache
install_runtime_state_cache(app)
from theme_public_state_cache import install_theme_public_state_cache
install_theme_public_state_cache(app)

# CSRN UNIVERSAL PREGAME DELAY R14
from pregame_presentation import install_pregame_presentation
install_pregame_presentation(app)

def _record_clean_shutdown_and_stop(signum, frame):
    """Handle a deliberate SIGINT/SIGTERM (e.g. Ctrl+C) by writing the clean
    shutdown marker before the process exits.

    This intentionally does NOT run on a force-kill (e.g. `taskkill /F`,
    which delivers no catchable signal) or on an unhandled crash — those
    cases must still leave the marker in place so the next startup reports
    UNCLEAN_SHUTDOWN_DETECTED.
    """
    try:
        signal_name = signal.Signals(signum).name
    except ValueError:
        signal_name = str(signum)
    try:
        get_recovery_service().mark_clean_shutdown()
        print(f"\nReceived {signal_name} — recording clean application shutdown...")
    except Exception as exc:
        print(f"[WARN] Could not record clean shutdown marker: {exc}")
    # Push the final state to the throttled Drive mirror before exit so the
    # last plays are not left only in the local authority.
    try:
        if hasattr(STATE_REPOSITORY, "flush"):
            STATE_REPOSITORY.flush()
    except Exception as exc:
        print(f"[WARN] Could not flush state mirror on shutdown: {exc}")
    # Re-raise so Waitress's own (SystemExit, KeyboardInterrupt) handling in
    # server.run() still gets a chance to close its sockets cleanly.
    raise SystemExit(0)


if __name__ == "__main__":
    ensure_data_architecture()
    load_config()
    from waitress import serve

    signal.signal(signal.SIGINT, _record_clean_shutdown_and_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _record_clean_shutdown_and_stop)

    ip = local_ip()
    media_directory = ASSET_UPLOAD_DIR.parent / "SponsorAdvertisements"
    try:
        media_port = start_isolated_media_server(media_directory, ASSET_UPLOAD_DIR)
    except OSError as exc:
        print(f"[FAIL] Isolated media server could not start on port 5051: {exc}")
        print("CSRN will not start in an unsafe mode that serves local video/audio media through Waitress.")
        raise SystemExit(1) from exc

    print("\nCSRN Production Suite — Command Center is running.")
    print(f"State authority: drive_backed={DRIVE_BACKED_GAME_DAY_STATE} mirror={STATE_FILE} authority={STATE_AUTHORITY_PATH}")
    print(f"Core backups: {CORE_BACKUP_ROOT}")
    if DRIVE_BACKED_GAME_DAY_STATE:
        _relink_fix = break_authority_mirror_hardlink(STATE_AUTHORITY_PATH, STATE_FILE)
        if _relink_fix:
            print(_relink_fix)
    _authority_hardlink_warning = authority_state_hardlink_warning(STATE_AUTHORITY_PATH)
    if _authority_hardlink_warning:
        print(_authority_hardlink_warning)
    _legacy_backup_notice = legacy_core_backup_notice()
    if _legacy_backup_notice:
        print(_legacy_backup_notice)
    print("Laptop: http://127.0.0.1:5050")
    print(f"Phone/iPad: http://{ip}:5050")
    print("OBS overlay: http://127.0.0.1:5050/overlay")
    print(f"Media server: http://127.0.0.1:{media_port} — READY")
    print("Server: Waitress production server — READY\n")
    serve(app, host="0.0.0.0", port=5050, threads=16)












