"""External Identity Profile: the organization / broadcast-default / streaming
values that used to be hard-coded in app.py's DEFAULT_CONFIG.

The profile is a single JSON document resolved via product_paths (the same
dev-vs-installed pattern as state.json / security.json). It is seeded once:

* against an **existing** install (state.json or config.json already present)
  it is seeded with today's exact Caledonia/CSRN literals -- zero behaviour
  change, the current install keeps every value it had;
* on a **fresh** install it is seeded blank so a new customer starts on a
  template instead of inheriting Caledonia's identity.

app.py reads organization / broadcast_defaults from here; the launcher reads
the streaming block (Round 12 Task B).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping


# --- Today's exact literals (moved verbatim out of app.py DEFAULT_CONFIG /
#     CSRN_GAME_DAY_LAUNCHER.ps1). Used only to seed an existing install. ---
LEGACY_ORGANIZATION: dict[str, Any] = {
    "name": "Caledonia Sports Radio Network",
    "short_name": "CSRN",
    "logo_path": "static/csrn-logo.png",
    "primary_color": "#C9203B",
    "secondary_color": "#000000",
    "accent_color": "#FFFFFF",
}
LEGACY_BROADCAST_DEFAULTS: dict[str, Any] = {
    "venue": "Caledonia High School",
    "sport": "Football",
    "timezone": "America/Chicago",
    "theme": "CSRN Dark",
    "home_school_id": "caledonia",
    "visual_mode": "graphic",
}
LEGACY_STREAMING: dict[str, Any] = {
    "facebook_live": (
        "https://www.facebook.com/live/producer/v2/?target_id=100075470576573"
    ),
    "youtube_live": (
        "https://studio.youtube.com/channel/"
        "UCAZZRMpb3HnrSxCnDiQeH7Q/livestreaming"
    ),
}

# --- Fresh-install template: identity fields blank, structural defaults kept. ---
BLANK_ORGANIZATION: dict[str, Any] = {
    "name": "",
    "short_name": "",
    "logo_path": "",
    "primary_color": "#C9203B",
    "secondary_color": "#000000",
    "accent_color": "#FFFFFF",
}
BLANK_BROADCAST_DEFAULTS: dict[str, Any] = {
    "venue": "",
    "sport": "Football",
    "timezone": "America/Chicago",
    "theme": "CSRN Dark",
    "home_school_id": "",
    "visual_mode": "graphic",
}
BLANK_STREAMING: dict[str, Any] = {
    "facebook_live": "",
    "youtube_live": "",
}

_SECTIONS = ("organization", "broadcast_defaults", "streaming")


def _template(existing_install: bool) -> dict[str, Any]:
    if existing_install:
        return {
            "organization": copy.deepcopy(LEGACY_ORGANIZATION),
            "broadcast_defaults": copy.deepcopy(LEGACY_BROADCAST_DEFAULTS),
            "streaming": copy.deepcopy(LEGACY_STREAMING),
        }
    return {
        "organization": copy.deepcopy(BLANK_ORGANIZATION),
        "broadcast_defaults": copy.deepcopy(BLANK_BROADCAST_DEFAULTS),
        "streaming": copy.deepcopy(BLANK_STREAMING),
    }


def _normalize(raw: Mapping[str, Any] | None, existing_install: bool) -> dict[str, Any]:
    base = _template(existing_install)
    if isinstance(raw, Mapping):
        for section in _SECTIONS:
            value = raw.get(section)
            if isinstance(value, Mapping):
                base[section] = {**base[section], **{
                    str(k): v for k, v in value.items()
                }}
    return base


def load_identity_profile(
    identity_file: Path,
    *,
    existing_install: bool,
) -> dict[str, Any]:
    """Return the identity profile, seeding the file on first run.

    ``existing_install`` must be evaluated by the caller BEFORE any repository
    auto-creates config.json (which would make the check always true).
    """

    path = Path(identity_file)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = None
        return _normalize(raw, existing_install)

    seeded = _template(existing_install)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(seeded, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass
    return seeded


def save_identity_profile(
    identity_file: Path,
    profile: Mapping[str, Any],
    *,
    existing_install: bool = True,
) -> dict[str, Any]:
    """Persist a full identity profile, normalized to the known sections."""

    path = Path(identity_file)
    normalized = _normalize(profile, existing_install)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return normalized
