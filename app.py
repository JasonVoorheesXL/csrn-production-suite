from __future__ import annotations

import copy
import io
import json
import os
import re
import secrets
import socket
import time
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import Any, Callable
from urllib.parse import urlparse, quote

from flask import Flask, jsonify, render_template, request, session, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
from PIL import Image, ImageChops
from obs_client import (
    OBSConnectionError,
    set_program_visual_mode,
    set_scorebug_visibility,
    validate_obs_read_only,
)
from upgrade_manager import inspect_candidate, migrate

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
VENUES_FILE = DATA_DIR / "Venues" / "venues.json"
LOGOS_FILE = DATA_DIR / "Logos" / "logos.json"
IMPORTS_DIR = DATA_DIR / "Imports"
MHSAA_5A_FILE = IMPORTS_DIR / "mhsaa_2025_27_football_5a.json"
MHSAA_5A_ENRICHMENT_FILE = IMPORTS_DIR / "mhsaa_5a_enrichment.json"
MHSAA_5A_BRANDING_FILE = IMPORTS_DIR / "mhsaa_5a_branding.json"
BROADCAST_INDEX_FILE = DATA_DIR / "Broadcasts" / "broadcasts.json"
BUILD_JOURNAL_FILE = DATA_DIR / "Logs" / "build_journal.json"
VERSION_FILE = BASE_DIR / "VERSION.txt"

app = Flask(__name__)
lock = Lock()
obs_status_lock = Lock()
upgrade_lock = Lock()
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
    "last_event": {},
    "ticker_visible": True,
    "ticker_speed": "normal",
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
        "eyebrow": "COACH", "sponsor_lead_in": "", "sponsor_name": "", "sponsor_logo": "", "duration": 0,
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
        "eyebrow": "PLAYER PROFILE",
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


DEFAULT_CONFIG: dict[str, Any] = {'organization': {'name': 'Caledonia Sports Radio Network', 'short_name': 'CSRN', 'logo_path': 'static/csrn-logo.png', 'primary_color': '#C9203B', 'secondary_color': '#000000', 'accent_color': '#FFFFFF'}, 'broadcast_defaults': {'venue': 'Caledonia High School', 'sport': 'Football', 'timezone': 'America/Chicago', 'theme': 'CSRN Dark', 'home_school_id': 'caledonia', 'visual_mode': 'graphic'}, 'folders': {'graphics': 'Graphics', 'assets': 'Assets', 'obs': 'OBS', 'broadcast_archive': 'Data/Broadcasts', 'exports': 'Exports', 'backups': 'Data/Backups'}, 'obs': {'websocket_enabled': False, 'controlled_commands': False, 'host': '127.0.0.1', 'port': 4455, 'password': '', 'scene_collection': 'CSRN Master', 'profile': 'CSRN Production', 'required_scene': '10.01 - FOOTBALL SCOREBUG', 'browser_source': 'BRWSR - Football Scorebug', 'program_visual_scene': '10.02 - PROGRAM VISUAL', 'graphic_source': 'IMG - Broadcast Background', 'camera_source': 'CAM - Primary Camera'}, 'weather': {'use_home_venue_address': True, 'default_alert_radius_miles': 25}, 'social': {'facebook': '', 'youtube': '', 'x': '', 'website': ''}, 'application': {'version': 'Version 1.4 Alpha — Player Graphics Engine v1', 'build': 'V1.4A-PLAYERGRAPHICS1', 'automatic_backup': True, 'auto_save': True, 'operator_timeout_hours': 12, 'upgrade_manager_enabled': True, 'last_migration_status': ''}}

SESSION_SECONDS = 12 * 60 * 60
MAX_ATTEMPTS = 3
LOCKOUT_SECONDS = 60


def ensure_data_architecture() -> None:
    for name in ("Schools", "Venues", "Logos", "Sources", "Imports", "Broadcasts", "Rosters", "Personnel", "Statistics", "Logs", "Backups", "Settings"):
        (DATA_DIR / name).mkdir(parents=True, exist_ok=True)
    HEADSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    PERSONNEL_HEADSHOTS_DIR.mkdir(parents=True, exist_ok=True)

def load_config() -> dict[str, Any]:
    ensure_data_architecture()
    if not CONFIG_FILE.exists():
        save_json(CONFIG_FILE, DEFAULT_CONFIG)
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        loaded = copy.deepcopy(DEFAULT_CONFIG)
        save_json(CONFIG_FILE, loaded)
    merged = copy.deepcopy(DEFAULT_CONFIG)
    for section, values in loaded.items():
        if isinstance(values, dict) and isinstance(merged.get(section), dict):
            merged[section].update(values)
        else:
            merged[section] = values
    # Application identity always follows the running package, including after migration.
    merged.setdefault("application", {})["version"] = "Version 1.6 Alpha — Graphics Library v1"
    merged["application"]["build"] = "V1.6A-GRAPHICSLIB1"
    return merged

def save_config(config: dict[str, Any]) -> None:
    ensure_data_architecture()
    save_json(CONFIG_FILE, config)



def application_identity() -> dict[str, str]:
    """Return package identity from VERSION.txt with safe config fallbacks."""
    cfg = load_config()
    version = cfg.get("application", {}).get("version", "Version 1.6 Alpha — Graphics Library v1")
    build = cfg.get("application", {}).get("build", "V1.6A-GRAPHICSLIB1")
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

def load_schools() -> list[dict[str, Any]]:
    ensure_data_architecture()
    if not SCHOOLS_FILE.exists():
        save_json(SCHOOLS_FILE, {"schools": []})
    raw = load_json(SCHOOLS_FILE, {"schools": []})
    if isinstance(raw, list):
        schools = raw
    else:
        schools = raw.get("schools", [])
    if not isinstance(schools, list):
        return []
    changed = reconcile_5a_csrn_ids(schools)
    for school in schools:
        before = json.dumps(school, sort_keys=True)
        ensure_school_schema(school, schools)
        changed = changed or before != json.dumps(school, sort_keys=True)
    if changed:
        save_schools(schools)
    return schools

def save_schools(schools: list[dict[str, Any]]) -> None:
    ensure_data_architecture()
    SCHOOLS_FILE.write_text(json.dumps(schools, indent=2), encoding="utf-8")


def load_venues() -> list[dict[str, Any]]:
    ensure_data_architecture()
    if not VENUES_FILE.exists():
        save_json(VENUES_FILE, [])
    data = load_json(VENUES_FILE, [])
    return data if isinstance(data, list) else data.get("venues", [])

def save_venues(items: list[dict[str, Any]]) -> None:
    save_json(VENUES_FILE, items)

def load_logos() -> list[dict[str, Any]]:
    ensure_data_architecture()
    if not LOGOS_FILE.exists():
        save_json(LOGOS_FILE, [])
    data = load_json(LOGOS_FILE, [])
    return data if isinstance(data, list) else data.get("logos", [])

def save_logos(items: list[dict[str, Any]]) -> None:
    save_json(LOGOS_FILE, items)

def load_broadcasts() -> list[dict[str, Any]]:
    ensure_data_architecture()
    if not BROADCAST_INDEX_FILE.exists():
        save_json(BROADCAST_INDEX_FILE, [])
    data = load_json(BROADCAST_INDEX_FILE, [])
    items = data if isinstance(data, list) else data.get("broadcasts", [])
    if not isinstance(items, list):
        return []
    changed = False
    for item in items:
        # Prepared was removed from the operator lifecycle in Version 1.0 Alpha Hotfix 2.
        if str(item.get("status", "")).lower() == "prepared":
            item["status"] = "planned"
            changed = True
        live_state = item.get("live_state")
        if isinstance(live_state, dict) and str(live_state.get("status", "")).lower() == "prepared":
            live_state["status"] = "planned"
            changed = True
    if changed:
        save_json(BROADCAST_INDEX_FILE, items)
    return items

def save_broadcasts(items: list[dict[str, Any]]) -> None:
    save_json(BROADCAST_INDEX_FILE, items)


def normalize_roster_id(value: str) -> str:
    return normalize_school_id(value)

def normalize_player_id(value: str) -> str:
    return normalize_school_id(value)

def load_rosters() -> list[dict[str, Any]]:
    ensure_data_architecture()
    if not ROSTERS_FILE.exists():
        save_json(ROSTERS_FILE, [])
    data = load_json(ROSTERS_FILE, [])
    items = data if isinstance(data, list) else data.get("rosters", [])
    if not isinstance(items, list):
        return []
    changed = False
    for roster in items:
        roster.setdefault("id", normalize_roster_id(f"{roster.get('school_id','school')}-{roster.get('sport','football')}-{roster.get('season','season')}-{roster.get('level','varsity')}-{roster.get('division','boys')}"))
        roster.setdefault("school_id", "")
        roster.setdefault("sport", "Football")
        roster.setdefault("season", "")
        roster.setdefault("level", "Varsity")
        roster.setdefault("division", "Boys")
        roster.setdefault("players", [])
        for player in roster["players"]:
            player.setdefault("id", normalize_player_id(f"{player.get('number','')}-{player.get('first_name','')}-{player.get('last_name','')}"))
            player.setdefault("preferred_name", "")
            player.setdefault("position", "")
            player.setdefault("secondary_position", "")
            player.setdefault("grade", "")
            player.setdefault("height", "")
            player.setdefault("weight", "")
            player.setdefault("captain", False)
            player.setdefault("starter", False)
            player.setdefault("status", "active")
            player.setdefault("headshot", "")
            player.setdefault("pronunciation", "")
            player.setdefault("pronunciation_verified", False)
        changed = True
    if changed:
        save_rosters(items)
    return items

def save_rosters(items: list[dict[str, Any]]) -> None:
    save_json(ROSTERS_FILE, items)

def roster_summary(roster: dict[str, Any]) -> dict[str, Any]:
    school = next((s for s in load_schools() if str(s.get("id")) == str(roster.get("school_id"))), {})
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

def venue_for_school(school: dict[str, Any] | None) -> dict[str, Any] | None:
    if not school:
        return None
    venue_id = str(school.get("venue_id", ""))
    venues=load_venues()
    if venue_id:
        found=next((v for v in venues if str(v.get("id")) == venue_id), None)
        if found: return found
    school_id=str(school.get("id", ""))
    return next((v for v in venues if str(v.get("school_id", "")) == school_id), None)

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
    return normalize_state(load_json(STATE_FILE, DEFAULT_STATE))

def save_state(state: dict[str, Any]) -> None:
    normalized = normalize_state(state)
    save_json(STATE_FILE, normalized)
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
    return result

def load_security() -> dict[str, Any]:
    sec = load_json(SECURITY_FILE, DEFAULT_SECURITY)
    changed = False
    for key, value in DEFAULT_SECURITY.items():
        if key not in sec:
            sec[key] = value
            changed = True
    if not sec.get("secret_key"):
        sec["secret_key"] = secrets.token_hex(32)
        changed = True
    if changed:
        save_json(SECURITY_FILE, sec)
    return sec

security = load_security()
app.secret_key = security["secret_key"]
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=False,
    PERMANENT_SESSION_LIFETIME=SESSION_SECONDS,
)

def pin_is_configured() -> bool:
    return bool(load_security().get("pin_hash"))

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
    if pin_is_configured():
        return jsonify({"error": "PIN_ALREADY_CONFIGURED"}), 409
    data = request.get_json(force=True)
    pin = str(data.get("pin", ""))
    confirm = str(data.get("confirm", ""))
    if not (pin.isdigit() and len(pin) == 6):
        return jsonify({"error": "PIN_MUST_BE_6_DIGITS"}), 400
    if pin != confirm:
        return jsonify({"error": "PIN_MISMATCH"}), 400

    sec = load_security()
    sec["pin_hash"] = generate_password_hash(pin, method="scrypt")
    sec["failed_attempts"] = 0
    sec["locked_until"] = 0
    save_json(SECURITY_FILE, sec)

    session.clear()
    session.permanent = True
    session["authenticated"] = True
    return jsonify({"ok": True})

@app.post("/api/login")
def login():
    sec = load_security()
    now = time.time()
    locked_until = float(sec.get("locked_until", 0))
    if now < locked_until:
        return jsonify({"error": "LOCKED", "locked_seconds": int(locked_until - now)}), 429

    data = request.get_json(force=True)
    pin = str(data.get("pin", ""))
    if check_password_hash(sec.get("pin_hash", ""), pin):
        sec["failed_attempts"] = 0
        sec["locked_until"] = 0
        save_json(SECURITY_FILE, sec)
        session.clear()
        session.permanent = True
        session["authenticated"] = True
        return jsonify({"ok": True})

    sec["failed_attempts"] = int(sec.get("failed_attempts", 0)) + 1
    if sec["failed_attempts"] >= MAX_ATTEMPTS:
        sec["failed_attempts"] = 0
        sec["locked_until"] = int(now + LOCKOUT_SECONDS)
        save_json(SECURITY_FILE, sec)
        return jsonify({"error": "LOCKED", "locked_seconds": LOCKOUT_SECONDS}), 429

    remaining = MAX_ATTEMPTS - sec["failed_attempts"]
    save_json(SECURITY_FILE, sec)
    return jsonify({"error": "INVALID_PIN", "attempts_remaining": remaining}), 401

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
    return jsonify([roster_summary(r) for r in load_rosters()])

@app.post("/api/rosters")
@require_auth
def create_roster():
    incoming = request.get_json(force=True) or {}
    school_id = str(incoming.get("school_id", "")).strip()
    sport = str(incoming.get("sport", "Football")).strip() or "Football"
    season = str(incoming.get("season", "")).strip()
    level = str(incoming.get("level", "Varsity")).strip() or "Varsity"
    division = str(incoming.get("division", "Boys")).strip() or "Boys"
    if not school_id or not season:
        return jsonify({"error":"SCHOOL_AND_SEASON_REQUIRED"}), 400
    items = load_rosters()
    duplicate = next((r for r in items if str(r.get("school_id"))==school_id and str(r.get("sport")).lower()==sport.lower() and str(r.get("season"))==season and str(r.get("level")).lower()==level.lower() and str(r.get("division")).lower()==division.lower()), None)
    if duplicate:
        return jsonify({"error":"ROSTER_ALREADY_EXISTS", "roster":roster_summary(duplicate)}), 409
    roster_id = normalize_roster_id(f"{school_id}-{sport}-{season}-{level}-{division}")
    base=roster_id; n=2
    while any(r.get("id")==roster_id for r in items):
        roster_id=f"{base}-{n}"; n+=1
    record={"id":roster_id,"school_id":school_id,"sport":sport,"season":season,"level":level,"division":division,"players":[],"created_at":int(time.time()),"updated_at":int(time.time())}
    items.append(record); save_rosters(items)
    return jsonify(roster_summary(record)), 201

@app.put("/api/rosters/<roster_id>")
@require_auth
def update_roster(roster_id: str):
    incoming=request.get_json(force=True) or {}; items=load_rosters()
    roster=next((r for r in items if r.get("id")==roster_id),None)
    if not roster: return jsonify({"error":"ROSTER_NOT_FOUND"}),404
    for field in ("school_id","sport","season","level","division"):
        if field in incoming: roster[field]=str(incoming[field]).strip()
    roster["updated_at"]=int(time.time()); save_rosters(items)
    return jsonify(roster_summary(roster))

@app.delete("/api/rosters/<roster_id>")
@require_auth
def delete_roster(roster_id: str):
    items=load_rosters()
    if not any(r.get("id")==roster_id for r in items): return jsonify({"error":"ROSTER_NOT_FOUND"}),404
    save_rosters([r for r in items if r.get("id")!=roster_id])
    return jsonify({"ok":True})

@app.post("/api/rosters/<roster_id>/players")
@require_auth
def create_roster_player(roster_id: str):
    incoming=request.get_json(force=True) or {}; items=load_rosters(); roster=next((r for r in items if r.get("id")==roster_id),None)
    if not roster: return jsonify({"error":"ROSTER_NOT_FOUND"}),404
    first=str(incoming.get("first_name","")).strip(); last=str(incoming.get("last_name","")).strip(); number=str(incoming.get("number","")).strip()
    if not first and not last: return jsonify({"error":"PLAYER_NAME_REQUIRED"}),400
    player_id=normalize_player_id(incoming.get("id") or f"{number}-{first}-{last}"); base=player_id; n=2
    while any(p.get("id")==player_id for p in roster.get("players",[])): player_id=f"{base}-{n}"; n+=1
    duplicate_number=bool(number and any(str(p.get("number","")).strip()==number for p in roster.get("players",[])))
    player={"id":player_id,"number":number,"first_name":first,"last_name":last,"preferred_name":str(incoming.get("preferred_name","")).strip(),"position":str(incoming.get("position","")).strip(),"secondary_position":str(incoming.get("secondary_position","")).strip(),"grade":str(incoming.get("grade","")).strip(),"height":str(incoming.get("height","")).strip(),"weight":str(incoming.get("weight","")).strip(),"captain":bool(incoming.get("captain",False)),"starter":bool(incoming.get("starter",False)),"status":"inactive" if str(incoming.get("status", "active")).lower()=="inactive" else "active","pronunciation":str(incoming.get("pronunciation","")).strip(),"pronunciation_verified":bool(incoming.get("pronunciation_verified",False)),"headshot":str(incoming.get("headshot","")).strip()}
    roster.setdefault("players",[]).append(player); roster["updated_at"]=int(time.time()); save_rosters(items)
    return jsonify({"player":player,"warning":"DUPLICATE_JERSEY_NUMBER" if duplicate_number else ""}),201

@app.put("/api/rosters/<roster_id>/players/<player_id>")
@require_auth
def update_roster_player(roster_id: str, player_id: str):
    incoming=request.get_json(force=True) or {}; items=load_rosters(); roster=next((r for r in items if r.get("id")==roster_id),None)
    if not roster: return jsonify({"error":"ROSTER_NOT_FOUND"}),404
    player=next((p for p in roster.get("players",[]) if p.get("id")==player_id),None)
    if not player: return jsonify({"error":"PLAYER_NOT_FOUND"}),404
    number=str(incoming.get("number",player.get("number",''))).strip(); duplicate_number=bool(number and any(p.get("id")!=player_id and str(p.get("number","")).strip()==number for p in roster.get("players",[])))
    for field in ("number","first_name","last_name","preferred_name","position","secondary_position","grade","height","weight","pronunciation","headshot"):
        if field in incoming: player[field]=str(incoming[field]).strip()
    for field in ("captain","starter","pronunciation_verified"):
        if field in incoming: player[field]=bool(incoming[field])
    if "status" in incoming: player["status"]="inactive" if str(incoming["status"]).lower()=="inactive" else "active"
    roster["updated_at"]=int(time.time()); save_rosters(items)
    return jsonify({"player":player,"warning":"DUPLICATE_JERSEY_NUMBER" if duplicate_number else ""})

@app.delete("/api/rosters/<roster_id>/players/<player_id>")
@require_auth
def delete_roster_player(roster_id: str, player_id: str):
    items=load_rosters(); roster=next((r for r in items if r.get("id")==roster_id),None)
    if not roster: return jsonify({"error":"ROSTER_NOT_FOUND"}),404
    before=len(roster.get("players",[])); roster["players"]=[p for p in roster.get("players",[]) if p.get("id")!=player_id]
    if len(roster["players"])==before: return jsonify({"error":"PLAYER_NOT_FOUND"}),404
    roster["updated_at"]=int(time.time()); save_rosters(items); return jsonify({"ok":True})

@app.post("/api/rosters/<roster_id>/players/import")
@require_auth
def import_roster_players(roster_id: str):
    incoming=request.get_json(force=True) or {}; rows=incoming.get("players",[])
    if not isinstance(rows,list): return jsonify({"error":"INVALID_PLAYER_LIST"}),400
    items=load_rosters(); roster=next((r for r in items if r.get("id")==roster_id),None)
    if not roster: return jsonify({"error":"ROSTER_NOT_FOUND"}),404
    added=0; warnings=[]
    for row in rows:
        if not isinstance(row,dict): continue
        first=str(row.get("first_name","")).strip(); last=str(row.get("last_name","")).strip()
        if not first and not last: continue
        number=str(row.get("number","")).strip()
        if number and any(str(p.get("number","")).strip()==number for p in roster.get("players",[])): warnings.append(f"Duplicate jersey number {number}")
        pid=normalize_player_id(f"{number}-{first}-{last}"); base=pid; n=2
        while any(p.get("id")==pid for p in roster.get("players",[])): pid=f"{base}-{n}"; n+=1
        roster.setdefault("players",[]).append({"id":pid,"number":number,"first_name":first,"last_name":last,"preferred_name":str(row.get("preferred_name","")).strip(),"position":str(row.get("position","")).strip(),"secondary_position":str(row.get("secondary_position","")).strip(),"grade":str(row.get("grade","")).strip(),"height":str(row.get("height","")).strip(),"weight":str(row.get("weight","")).strip(),"captain":str(row.get("captain","")).lower() in ("1","true","yes","y"),"starter":str(row.get("starter","")).lower() in ("1","true","yes","y"),"status":"inactive" if str(row.get("status","")).lower()=="inactive" else "active","pronunciation":str(row.get("pronunciation","")).strip(),"pronunciation_verified":str(row.get("pronunciation_verified","")).lower() in ("1","true","yes","y"),"headshot":str(row.get("headshot","")).strip()}); added+=1
    roster["updated_at"]=int(time.time()); save_rosters(items)
    return jsonify({"added":added,"warnings":warnings,"roster":roster_summary(roster)})


@app.get("/api/schools")
@require_auth
def list_schools():
    return jsonify([school_display_payload(s) for s in load_schools()])

@app.get("/api/schools/<school_id>")
@require_auth
def read_school(school_id: str):
    school = get_school(school_id)
    if not school:
        return jsonify({"error": "SCHOOL_NOT_FOUND"}), 404
    return jsonify(school)

@app.post("/api/schools")
@require_auth
def create_school():
    incoming = request.get_json(force=True)
    official_name = str(incoming.get("official_name", "")).strip()
    broadcast_name = str(incoming.get("broadcast_name", "")).strip()
    if not official_name or not broadcast_name:
        return jsonify({"error": "SCHOOL_NAME_REQUIRED"}), 400

    duplicates = school_duplicate_candidates(incoming)
    if duplicates and not bool(incoming.get("confirm_duplicate", False)):
        return jsonify({"error": "LIKELY_DUPLICATE", "matches": duplicates}), 409

    schools = load_schools()
    school_id = normalize_school_id(incoming.get("id") or broadcast_name)
    base_id = school_id
    suffix = 2
    while any(s.get("id") == school_id for s in schools):
        school_id = f"{base_id}-{suffix}"
        suffix += 1

    general_social, social_errors = normalize_social_block(incoming.get("general_social") or {})
    if social_errors:
        return jsonify({"error": "INVALID_SOCIAL_URL", "fields": social_errors}), 400

    programs = incoming.get("programs") or {}
    if "Football" in programs:
        football_social, football_errors = normalize_social_block(programs.get("Football") or {})
        if football_errors:
            return jsonify({"error": "INVALID_SOCIAL_URL", "fields": football_errors}), 400
        programs["Football"].update(football_social)

    school = {
        "id": school_id,
        "csrn_id": str(incoming.get("csrn_id", "")).strip() or next_csrn_school_id(str(incoming.get("state", "MS")), str(incoming.get("classification", "")), schools),
        "official_name": official_name,
        "broadcast_name": broadcast_name,
        "nickname": str(incoming.get("nickname", "")).strip(),
        "short_name": str(incoming.get("short_name", broadcast_name)).strip(),
        "city": str(incoming.get("city", "")).strip(),
        "county": str(incoming.get("county", "")).strip(),
        "active": bool(incoming.get("active", True)),
        "preferred_scorebug_name": str(incoming.get("preferred_scorebug_name", broadcast_name)).strip(),
        "pronunciation_guide": str(incoming.get("pronunciation_guide", "")).strip(),
        "venue_id": str(incoming.get("venue_id", "")).strip(),
        "primary_color": incoming.get("primary_color", "#C9203B"),
        "secondary_color": incoming.get("secondary_color", "#FFFFFF"),
        "primary_logo": str(incoming.get("primary_logo", "")).strip(),
        "alternate_logo": str(incoming.get("alternate_logo", "")).strip(),
        "general_social": general_social,
        "venues": incoming.get("venues") or [],
        "programs": programs,
        "state": str(incoming.get("state", "MS")).strip() or "MS",
        "classification": str(incoming.get("classification", "")).strip(),
        "region": str(incoming.get("region", "")).strip(),
        "district": str(incoming.get("district", "")).strip(),
        "mhsaa_id": str(incoming.get("mhsaa_id", "")).strip(),
        "source_data": incoming.get("source_data") or {"provider": "Manual", "source_url": "", "retrieved_at": "", "district": ""},
        "user_overrides": incoming.get("user_overrides") or {},
        "verification_status": str(incoming.get("verification_status", "unverified")),
        "default_broadcast_logo_id": str(incoming.get("default_broadcast_logo_id", "")).strip(),
        "logo_status": str(incoming.get("logo_status", "candidate")),
        "logo_metadata": incoming.get("logo_metadata") or {"source_url": "", "transparent_background_status": "unknown", "approval_status": "candidate", "shape_standard": "round", "master_canvas": "1024x1024-round", "safe_area": "circle-90-percent", "scorebug_derivative": "256x256-round"},
        "notes": str(incoming.get("notes", "")).strip()
    }

    schools.append(school)
    save_schools(schools)
    return jsonify(school), 201

@app.put("/api/schools/<school_id>")
@require_auth
def update_school(school_id: str):
    incoming = request.get_json(force=True)
    schools = load_schools()
    index = next((i for i, s in enumerate(schools) if s.get("id") == school_id), None)
    if index is None:
        return jsonify({"error": "SCHOOL_NOT_FOUND"}), 404

    school = schools[index]
    if "general_social" in incoming:
        normalized_social, social_errors = normalize_social_block(incoming.get("general_social") or {})
        if social_errors:
            return jsonify({"error": "INVALID_SOCIAL_URL", "fields": social_errors}), 400
        incoming["general_social"] = normalized_social
    if "programs" in incoming and "Football" in incoming["programs"]:
        normalized_football, football_errors = normalize_social_block(incoming["programs"].get("Football") or {})
        if football_errors:
            return jsonify({"error": "INVALID_SOCIAL_URL", "fields": football_errors}), 400
        incoming["programs"]["Football"].update(normalized_football)

    school = schools[index]
    for key in (
        "official_name", "broadcast_name", "nickname", "mascot", "short_name", "city", "county", "active", "school_address", "phone", "website", "preferred_scorebug_name", "pronunciation_guide", "venue_id", "csrn_id", "primary_color",
        "secondary_color", "primary_logo", "alternate_logo",
        "general_social", "venues", "programs", "state", "classification", "region", "district", "mhsaa_id", "source_data", "user_overrides", "verification_status", "default_broadcast_logo_id", "logo_status", "logo_metadata", "notes"
    ):
        if key in incoming:
            school[key] = incoming[key]

    schools[index] = school
    save_schools(schools)
    linked_logo_id = str(school.get("default_broadcast_logo_id", "") or "").strip()
    if linked_logo_id:
        logos = load_logos()
        linked = next((row for row in logos if str(row.get("id", "")) == linked_logo_id), None)
        if linked is not None:
            linked["approval_status"] = str(school.get("logo_status", linked.get("approval_status", "candidate")))
            if school.get("primary_logo"):
                linked["round_master_path"] = school.get("primary_logo")
            save_logos(logos)
    return jsonify(school)

@app.delete("/api/schools/<school_id>")
@require_auth
def delete_school(school_id: str):
    schools = load_schools()
    school = next((s for s in schools if s.get("id") == school_id), None)
    if not school:
        return jsonify({"error": "SCHOOL_NOT_FOUND"}), 404
    save_schools([s for s in schools if s.get("id") != school_id])
    return jsonify({"ok": True})



@app.post("/api/schools/duplicate-check")
@require_auth
def duplicate_check():
    incoming = request.get_json(force=True)
    return jsonify({"matches": school_duplicate_candidates(incoming, str(incoming.get("exclude_id", "")))})

@app.get("/api/imports/mhsaa/5A/analyze")
@require_auth
def analyze_mhsaa_5a():
    manifest = load_json(MHSAA_5A_FILE, {"schools": []})
    existing = load_schools()
    results = []
    for candidate in manifest.get("schools", []):
        matches = school_duplicate_candidates(candidate)
        exact = next((s for s in existing if str(s.get("official_name", "")).casefold() == str(candidate.get("official_name", "")).casefold()), None)
        results.append({**candidate, "status": "existing" if exact else ("possible_duplicate" if matches else "new"), "matches": matches})
    return jsonify({
        "classification": "5A",
        "source": manifest.get("source", {}),
        "found": len(results),
        "new": sum(1 for r in results if r["status"] == "new"),
        "existing": sum(1 for r in results if r["status"] == "existing"),
        "possible_duplicates": sum(1 for r in results if r["status"] == "possible_duplicate"),
        "schools": results,
    })

@app.post("/api/imports/mhsaa/5A")
@require_auth
def import_mhsaa_5a():
    options = request.get_json(silent=True) or {}
    manifest = load_json(MHSAA_5A_FILE, {"schools": []})
    schools = load_schools()
    venues = load_venues()
    imported = 0
    skipped = 0
    created_ids: list[str] = []
    for candidate in manifest.get("schools", []):
        exact = next((s for s in schools if str(s.get("official_name", "")).casefold() == str(candidate.get("official_name", "")).casefold()), None)
        if exact:
            # Enrich the authoritative classification/region without replacing user customization.
            exact["classification"] = "5A"
            exact["region"] = str(candidate.get("region", ""))
            exact.setdefault("state", "MS")
            exact.setdefault("csrn_id", next_csrn_school_id("MS", "5A", schools))
            exact.setdefault("source_data", {}).update(candidate.get("source_data", {}))
            ensure_school_schema(exact, schools)
            skipped += 1
            continue
        school_id = normalize_school_id(candidate["broadcast_name"])
        base_id, suffix = school_id, 2
        while any(s.get("id") == school_id for s in schools):
            school_id = f"{base_id}-{suffix}"; suffix += 1
        venue_id = f"{school_id}-football"
        school = {
            "id": school_id,
            "csrn_id": next_csrn_school_id("MS", "5A", schools),
            "official_name": candidate["official_name"],
            "broadcast_name": candidate["broadcast_name"],
            "short_name": candidate["broadcast_name"],
            "preferred_scorebug_name": candidate["broadcast_name"],
            "nickname": "", "city": "", "county": "", "state": "MS", "active": True,
            "classification": "5A", "region": str(candidate.get("region", "")), "district": "", "mhsaa_id": "",
            "primary_color": "#808080", "secondary_color": "#FFFFFF",
            "primary_logo": "", "alternate_logo": "", "default_broadcast_logo_id": "", "logo_status": "candidate",
            "logo_metadata": {"source_url": "", "transparent_background_status": "unknown", "approval_status": "candidate", "shape_standard": "round", "master_canvas": "1024x1024-round", "safe_area": "circle-90-percent", "scorebug_derivative": "256x256-round"},
            "general_social": {"facebook": "", "x": "", "instagram": "", "youtube": "", "website": ""},
            "venue_id": venue_id if options.get("create_venues", True) else "",
            "venues": [{"id": venue_id, "name": f"{candidate['broadcast_name']} Football Venue", "address1": "", "address2": "", "city": "", "state": "MS", "postal_code": "", "weather_radius_miles": 25}] if options.get("create_venues", True) else [],
            "programs": {"Football": {"facebook": "", "x": "", "instagram": "", "youtube": "", "website": "", "venue_id": venue_id if options.get("create_venues", True) else "", "notes": ""}},
            "source_data": candidate.get("source_data", {}), "user_overrides": {}, "verification_status": "candidate",
            "pronunciation_guide": "", "notes": "Imported as a 5A candidate record; complete identity, venue, colors, logo and social fields during review."
        }
        schools.append(school)
        if options.get("create_venues", True):
            venues.append({"id": venue_id, "school_id": school_id, "csrn_school_id": school["csrn_id"], "sport": "Football", "name": f"{candidate['broadcast_name']} Football Venue", "address1": "", "address2": "", "city": "", "state": "MS", "postal_code": "", "latitude": None, "longitude": None, "approval_status": "candidate", "broadcast_notes": ""})
        imported += 1
        created_ids.append(school["csrn_id"])
    save_schools(schools)
    save_venues(venues)
    return jsonify({"imported": imported, "skipped_existing": skipped, "created_ids": created_ids, "total_schools": len(schools)})



@app.get("/api/imports/mhsaa/5A/branding/analyze")
@require_auth
def analyze_mhsaa_5a_branding():
    manifest = load_json(MHSAA_5A_BRANDING_FILE, {"schools": []})
    schools = load_schools()
    results = []
    for candidate in manifest.get("schools", []):
        school = next((s for s in schools if str(s.get("official_name", "")).casefold() == str(candidate.get("official_name", "")).casefold()), None)
        if not school:
            status = "school_missing"
        elif school.get("primary_logo") or str(school.get("branding_status", "")).lower() in {"approved", "manual"}:
            status = "preserved"
        else:
            status = "ready"
        results.append({**candidate, "status": status, "school_id": school.get("id", "") if school else ""})
    return jsonify({
        "found": len(results),
        "ready": sum(1 for r in results if r["status"] == "ready"),
        "preserved": sum(1 for r in results if r["status"] == "preserved"),
        "school_missing": sum(1 for r in results if r["status"] == "school_missing"),
        "schools": results,
        "source": manifest.get("source", {}),
    })

@app.post("/api/imports/mhsaa/5A/branding")
@require_auth
def import_mhsaa_5a_branding():
    manifest = load_json(MHSAA_5A_BRANDING_FILE, {"schools": []})
    schools = load_schools()
    updated = 0
    preserved = 0
    missing = []
    for candidate in manifest.get("schools", []):
        school = next((s for s in schools if str(s.get("official_name", "")).casefold() == str(candidate.get("official_name", "")).casefold()), None)
        if not school:
            missing.append(candidate.get("official_name", ""))
            continue
        # Existing processed logos/colors are considered user-reviewed and are never overwritten.
        if school.get("primary_logo") or str(school.get("branding_status", "")).lower() in {"approved", "manual"}:
            preserved += 1
            continue
        school["primary_color"] = candidate.get("primary_color", school.get("primary_color", "#808080"))
        school["secondary_color"] = candidate.get("secondary_color", school.get("secondary_color", "#FFFFFF"))
        school["accent_color"] = candidate.get("accent_color", "")
        school["branding_status"] = "candidate"
        school["branding_source"] = {
            "provider": candidate.get("source_provider", "CSRN research seed"),
            "source_url": candidate.get("source_url", ""),
            "checked_at": manifest.get("source", {}).get("checked_at", ""),
            "verification_status": "candidate",
            "notes": candidate.get("notes", "Candidate colors require visual approval."),
        }
        updated += 1
    save_schools(schools)
    return jsonify({"updated": updated, "preserved": preserved, "missing_schools": missing})

@app.get("/api/imports/mhsaa/5A/enrichment/analyze")
@require_auth
def analyze_mhsaa_5a_enrichment():
    manifest = load_json(MHSAA_5A_ENRICHMENT_FILE, {"schools": []})
    schools = load_schools()
    results = []
    for candidate in manifest.get("schools", []):
        school = next((s for s in schools if str(s.get("official_name", "")).casefold() == str(candidate.get("official_name", "")).casefold()), None)
        missing = []
        if not school:
            status = "school_missing"
        else:
            status = "ready"
            for key in ("mascot", "phone", "website"):
                if not candidate.get(key): missing.append(key)
            address = candidate.get("school_address", {})
            if not address.get("address1"): missing.append("school_address")
        results.append({"official_name": candidate.get("official_name"), "status": status, "missing_source_fields": missing})
    return jsonify({
        "classification": "5A", "found": len(results),
        "ready": sum(1 for r in results if r["status"] == "ready"),
        "school_missing": sum(1 for r in results if r["status"] == "school_missing"),
        "source": manifest.get("source", {}), "schools": results
    })

@app.post("/api/imports/mhsaa/5A/enrichment")
@require_auth
def enrich_mhsaa_5a():
    manifest = load_json(MHSAA_5A_ENRICHMENT_FILE, {"schools": []})
    schools = load_schools(); venues = load_venues(); logos = load_logos()
    updated = 0; missing_schools = []; missing_mascot = 0; missing_address = 0; missing_website = 0; venue_verification_needed = 0; logo_pending = 0
    for candidate in manifest.get("schools", []):
        school = next((s for s in schools if str(s.get("official_name", "")).casefold() == str(candidate.get("official_name", "")).casefold()), None)
        if not school:
            missing_schools.append(candidate.get("official_name", "")); continue
        overrides = school.get("user_overrides") or {}
        mascot = candidate.get("mascot", "")
        if mascot and not overrides.get("mascot"):
            school["mascot"] = mascot; school["nickname"] = school.get("nickname") or mascot
        elif not mascot: missing_mascot += 1
        address = candidate.get("school_address", {})
        if address.get("address1"):
            school["school_address"] = address
            school["city"] = school.get("city") or address.get("city", "")
        else: missing_address += 1
        if candidate.get("phone") and not overrides.get("phone"): school["phone"] = candidate.get("phone")
        if candidate.get("website") and not overrides.get("website"):
            school["website"] = candidate.get("website")
            school.setdefault("general_social", {})["website"] = school.get("general_social", {}).get("website") or candidate.get("website")
        elif not candidate.get("website"): missing_website += 1
        school.setdefault("source_data", {}).update({"provider":"MHSAA School Directory","directory_source_url":candidate.get("source_url", ""),"directory_checked_at":manifest.get("source", {}).get("checked_at", "")})
        school["verification_status"] = "candidate_enriched"
        school.setdefault("logo_metadata", {}).update({"source_url":candidate.get("source_url", ""),"approval_status":"candidate","shape_standard":"round","master_canvas":"1024x1024-round","scorebug_derivative":"256x256-round"})
        school["logo_status"] = school.get("logo_status") or "candidate"
        logo_pending += 1
        venue_id = school.get("venue_id") or f"{school.get('id')}-football"
        school["venue_id"] = venue_id
        venue = next((v for v in venues if v.get("id") == venue_id or v.get("school_id") == school.get("id")), None)
        venue_payload = {"id": venue_id, "school_id": school.get("id"), "csrn_school_id": school.get("csrn_id", ""), "sport":"Football", "name":f"{school.get('broadcast_name') or candidate.get('official_name')} Football Stadium", **address, "latitude":None, "longitude":None, "on_campus_assumed":True, "venue_address_source":"school_address", "venue_verified":False, "approval_status":"candidate", "broadcast_notes":"Defaulted to school address; verify whether the stadium is off campus."}
        if venue: venue.update({k:v for k,v in venue_payload.items() if k not in ("broadcast_notes",) or not venue.get(k)})
        else: venues.append(venue_payload)
        school["venues"] = [venue_payload if v.get("id") == venue_id else v for v in school.get("venues", [])] or [venue_payload]
        school.setdefault("programs", {}).setdefault("Football", {})["venue_id"] = venue_id
        venue_verification_needed += 1; updated += 1
    save_schools(schools); save_venues(venues); save_logos(logos)
    return jsonify({"updated":updated,"missing_schools":missing_schools,"missing_mascot":missing_mascot,"missing_address":missing_address,"missing_website":missing_website,"logo_pending_approval":logo_pending,"venue_verification_needed":venue_verification_needed})



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
    return jsonify(load_venues())

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
    current["application"]["version"] = "Version 1.6 Alpha — Graphics Library v1"
    current["application"]["build"] = "V1.6A-GRAPHICSLIB1"
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
    venues=load_venues(); changed=False
    for venue in venues:
        name=str(venue.get("name", ""))
        if name.endswith(" Football Venue"):
            school=name[:-len(" Football Venue")].strip()
            venue["name"]=f"{school} HS Football Field"; changed=True
        elif name.endswith(" Football Stadium"):
            school=name[:-len(" Football Stadium")].strip()
            venue["name"]=f"{school} HS Football Field"; changed=True
    if changed: save_venues(venues)

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
    venue = venue_for_school(home_school)
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
    data = request.get_json(force=True)
    allowed = {"quarter", "down", "distance", "clock_visible", "possession", "scorebug_visible", "broadcast_phase", "ticker_visible", "ticker_speed"}
    changes = {k: v for k, v in data.items() if k in allowed}
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
            for key in ("graphic_type", "roster_id", "player_id", "eyebrow", "sponsor_lead_in", "sponsor_name", "sponsor_logo"):
                if key in data:
                    graphic[key] = str(data.get(key, ""))[:240]
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
                graphic["visible"] = bool(data.get("visible", action == "show"))
                if graphic["visible"] and graphic["duration"] > 0:
                    graphic["expires_at"] = int(time.time()) + graphic["duration"]
                elif graphic["visible"]:
                    graphic["expires_at"] = 0
            graphic["updated_at"] = int(time.time())
        state["player_graphic"] = graphic
        save_state(state)
    return jsonify(public_state(state))

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
            for key in ("graphic_type","eyebrow","sponsor_lead_in","sponsor_name","sponsor_logo"):
                if key in data: graphic[key]=str(data.get(key,""))[:240]
            try: graphic["duration"]=max(0,min(120,int(data.get("duration",graphic.get("duration",0)) or 0)))
            except: graphic["duration"]=0
            if action=="hide": graphic["visible"]=False; graphic["expires_at"]=0
            elif action in {"show","update"}:
                if not graphic.get("personnel_id"): return jsonify({"error":"PERSONNEL_REQUIRED"}),400
                graphic["visible"]=True
                graphic["expires_at"]=int(time.time())+graphic["duration"] if graphic["duration"] else 0
            graphic["updated_at"]=int(time.time())
        state["personnel_graphic"]=graphic; save_state(state)
    return jsonify(public_state(state))

@app.post("/api/event-trigger")
@require_auth
def event_trigger():
    data = request.get_json(force=True)
    team = str(data.get("team", "")).lower()
    event = str(data.get("event", "")).upper()
    if team not in {"home", "visitor"} or event not in {"TD", "FG", "TURNOVER"}:
        return jsonify({"error": "INVALID_EVENT"}), 400
    with lock:
        state = load_state()
        if not state.get("broadcast_id"):
            return jsonify({"error": "NO_ACTIVE_BROADCAST"}), 409
        push_history(state)
        score_key = "home_score" if team == "home" else "visitor_score"
        before = {
            "home_score": int(state.get("home_score", 0)),
            "visitor_score": int(state.get("visitor_score", 0)),
            "possession": state.get("possession", "home"),
        }
        delta = 6 if event == "TD" else 3 if event == "FG" else 0
        if delta:
            state[score_key] = max(0, int(state.get(score_key, 0)) + delta)
        if event == "TURNOVER":
            state["possession"] = team
        if state.get("status") != "live":
            state["status"] = "live"
            state["broadcast_phase"] = "live"
            update_linked_broadcast_status(state.get("broadcast_id", ""), "live")
        team_name = state.get("home_team") if team == "home" else state.get("visitor_team")
        label = {"TD": "Touchdown", "FG": "Field Goal", "TURNOVER": "Turnover"}[event]
        payload = {
            "id": f"EV-{int(time.time() * 1000)}",
            "team": team,
            "team_name": team_name,
            "event": event,
            "label": label,
            "score_delta": delta,
            "created_at": int(time.time()),
            "quarter": str(state.get("quarter", "1") or "1"),
            "broadcast_id": state.get("broadcast_id", ""),
            "before": before,
            "after": {
                "home_score": int(state.get("home_score", 0)),
                "visitor_score": int(state.get("visitor_score", 0)),
                "possession": state.get("possession", "home"),
            },
            "media_trigger": {
                "key": f"{event.lower()}_{team}",
                "assigned": False,
                "graphics": None,
                "audio": None,
                "video": None,
            },
        }
        state["last_event"] = payload
        events = list(state.get("events") or [])
        events.append(payload)
        state["events"] = events[-200:]
        save_state(state)
    return jsonify({
        "state": public_state(state),
        "trigger": payload,
        "media_assigned": False,
        "message": f"{label}: {team_name}" + (f" (+{delta})" if delta else " — possession updated"),
    })

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
            target["undone"] = True
            target["undone_at"] = int(time.time())
            state["events"] = events
            state["last_event"] = {
                "id": f"UNDO-{int(time.time() * 1000)}",
                "event": "UNDO",
                "label": f"Undo: {target.get('label', target.get('event', 'Event'))}",
                "team": target.get("team", ""),
                "team_name": target.get("team_name", ""),
                "score_delta": 0,
                "created_at": int(time.time()),
                "quarter": str(state.get("quarter", "1") or "1"),
                "broadcast_id": state.get("broadcast_id", ""),
                "target_event_id": target.get("id", ""),
            }
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
