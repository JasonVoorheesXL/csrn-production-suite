"""Authoritative production-template persistence for CSRN Gate 16.6."""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

from product_paths import resolve_product_paths

SCHEMA = "csrn-production-template-state-v1"
DEFAULT_PACKAGE_ID = "legacy"
APPROVED_PACKAGE_IDS = frozenset(
    {
        "legacy",
        "friday_night_stadium",
        "eight_bit_gameday",
        "heritage_press",
        "digital_neon",
        "collegiate_traditional",
    }
)

# Temporarily hidden from the operator's theme picker. All Neon code
# (engines, renderer, adapter entries) is intentionally left intact -- this
# is a hide, not a removal, and it is coming back.
#   TO RE-ENABLE NEON: delete "digital_neon" from this one set (and from the
#   matching DISABLED set in static/csrn-pregame-theme-selector.js). Nothing
#   else needs to change.
DISABLED_PACKAGE_IDS = frozenset({"digital_neon"})

# What the picker may actually select / persist right now.
SELECTABLE_PACKAGE_IDS = APPROVED_PACKAGE_IDS - DISABLED_PACKAGE_IDS
_LOCK = threading.RLock()
_BASE_DIR = Path(__file__).resolve().parent


def _default_state_path() -> Path:
    # Same CSRN_DATA_ROOT/CSRN_RUNTIME_ROOT/CSRN_INSTALLED-aware resolution
    # app.py uses for DATA_DIR, so this file lands in the same Data/ root as
    # everything else -- and, critically, so an isolated CSRN_DATA_ROOT set
    # for tests/simulations actually isolates this module too, instead of
    # silently falling back to the process's launch directory.
    paths = resolve_product_paths(
        _BASE_DIR,
        frozen=bool(getattr(sys, "frozen", False) or "--installed" in sys.argv),
    )
    return paths.data_dir / "production_template_state.json"


def state_path() -> Path:
    override = os.environ.get("CSRN_PRODUCTION_TEMPLATE_STATE_PATH", "").strip()
    if override:
        return Path(override)
    return _default_state_path()


def _normalize(value: Any) -> str:
    candidate = str(value or "").strip()
    # A stale state file naming a now-disabled package degrades to the
    # default rather than persisting a hidden selection.
    return candidate if candidate in SELECTABLE_PACKAGE_IDS else DEFAULT_PACKAGE_ID


def default_state() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "package_id": DEFAULT_PACKAGE_ID,
        "authoritative": True,
        "render_binding_enabled": True,
    }


def read_production_template_state() -> dict[str, Any]:
    path = state_path()
    with _LOCK:
        if not path.exists():
            return default_state()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return default_state()

    state = default_state()
    state["package_id"] = _normalize(payload.get("package_id"))
    return state


def write_production_template_state(package_id: Any) -> dict[str, Any]:
    requested = str(package_id or "").strip()
    if requested not in SELECTABLE_PACKAGE_IDS:
        # Covers both genuinely unknown ids and temporarily-disabled ones
        # (e.g. digital_neon) -- neither can be made the live selection.
        raise ValueError("invalid_production_template")

    state = default_state()
    state["package_id"] = requested
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    encoded = json.dumps(state, indent=2, sort_keys=True) + "\n"

    with _LOCK:
        temp.write_text(encoded, encoding="utf-8")
        os.replace(temp, path)

    return state


def enrich_theme_public_state_response(response, request_path: str):
    if request_path != "/api/themes/public-state":
        return response
    if not getattr(response, "is_json", False):
        return response

    payload = response.get_json(silent=True)
    if not isinstance(payload, dict):
        return response

    state = read_production_template_state()
    payload["production_template_package_id"] = state["package_id"]
    payload["production_template_authoritative"] = True
    payload["production_template_render_binding_enabled"] = True
    response.set_data(json.dumps(payload, separators=(",", ":")))
    response.content_type = "application/json"
    return response
