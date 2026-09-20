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
import hashlib
import json
import logging
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Mapping

import layout_builder_service


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
    # Round 23 quick-launch toolbar (Command Center). Blank even on the
    # existing install -- new per-install operator conveniences, never
    # hard-coded anywhere before.
    "broadcast_software_path": "",
    "youtube_url": "",
    "facebook_url": "",
}
# Placeholder team/venue shown by DEFAULT_STATE before any broadcast is loaded
# (Round 13 Task A -- same class of literal as the two blocks above).
LEGACY_STATE_DEFAULTS: dict[str, Any] = {
    "home_team": "Caledonia",
    "venue": "Caledonia High School",
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
    "broadcast_software_path": "",
    "youtube_url": "",
    "facebook_url": "",
}
BLANK_STATE_DEFAULTS: dict[str, Any] = {
    "home_team": "",
    "venue": "",
}

_SECTIONS = ("organization", "broadcast_defaults", "streaming", "state_defaults")

# Round 22: scalar flags carried alongside the sections. `onboarding_complete`
# gates the first-run wizard -- an existing install is never onboarded (it
# already has its identity), a fresh one is, and the wizard's Finish/Skip
# writes True so it never re-triggers.
_FLAG_DEFAULTS: dict[str, Any] = {"onboarding_complete": False}


def _template(existing_install: bool) -> dict[str, Any]:
    # Layout Builder P0 (docs/LAYOUT_BUILDER_RECONCILIATION.md): the same
    # empty "default" preset regardless of existing-install vs fresh --
    # there is no legacy layout to seed from (layouts are new; every
    # broadcast up to now rendered with no layout system at all, which is
    # exactly what an empty "default" preset reproduces).
    if existing_install:
        return {
            "organization": copy.deepcopy(LEGACY_ORGANIZATION),
            "broadcast_defaults": copy.deepcopy(LEGACY_BROADCAST_DEFAULTS),
            "streaming": copy.deepcopy(LEGACY_STREAMING),
            "state_defaults": copy.deepcopy(LEGACY_STATE_DEFAULTS),
            "layouts": layout_builder_service.default_layouts_document(),
            "onboarding_complete": True,
        }
    return {
        "organization": copy.deepcopy(BLANK_ORGANIZATION),
        "broadcast_defaults": copy.deepcopy(BLANK_BROADCAST_DEFAULTS),
        "streaming": copy.deepcopy(BLANK_STREAMING),
        "state_defaults": copy.deepcopy(BLANK_STATE_DEFAULTS),
        "layouts": layout_builder_service.default_layouts_document(),
        "onboarding_complete": False,
    }


def onboarding_complete(profile: Mapping[str, Any] | None) -> bool:
    """True once first-run onboarding has been finished or skipped."""
    return bool(isinstance(profile, Mapping) and profile.get("onboarding_complete"))


def branding_logo(organization: Mapping[str, Any] | None) -> str:
    """The configured network/organization logo path, or "" -- never a
    hard-coded csrn-logo.png fallback. Accepts any of the historical key
    spellings (logo_path / logo / logo_url)."""
    if not isinstance(organization, Mapping):
        return ""
    return str(
        organization.get("logo_path")
        or organization.get("logo")
        or organization.get("logo_url")
        or ""
    ).strip()


def _normalize(raw: Mapping[str, Any] | None, existing_install: bool) -> dict[str, Any]:
    base = _template(existing_install)
    if isinstance(raw, Mapping):
        for section in _SECTIONS:
            value = raw.get(section)
            if isinstance(value, Mapping):
                base[section] = {**base[section], **{
                    str(k): v for k, v in value.items()
                }}
        # "layouts" is deeply nested (presets -> scene -> base_family ->
        # element), unlike the other sections' flat key/value shape, so it
        # gets layout_builder_service's own normalization rather than the
        # shallow merge above (which would silently drop everything below
        # the first level).
        base["layouts"] = layout_builder_service.normalize_layouts(raw.get("layouts"))
        for flag in _FLAG_DEFAULTS:
            if flag in raw:
                base[flag] = bool(raw[flag])
    return base


# --- Load-problem reporting --------------------------------------------------
#
# An identity_profile.json that is present but unreadable/unparseable has always
# been survivable on purpose: this runs live broadcasts, and a startup crash on
# a corrupted file is worse than a fallback. But the fallback used to be
# SILENT -- the app quietly ran on the built-in seed (for an existing install,
# Caledonia's own identity) and nobody could tell. It is still survivable; it
# is now loud: logged with enough detail to diagnose, the bad file is kept
# aside (a later save would otherwise overwrite it), and the problem is exposed
# through load_issue() to /api/diagnostics and /api/readiness.

LOGGER = logging.getLogger("csrn.identity")

_ISSUES: dict[str, dict[str, Any]] = {}
_ISSUES_LOCK = threading.Lock()


def _issue_key(path: Path) -> str:
    return str(path.resolve()) if path.exists() else str(path.absolute())


def load_issue(identity_file: Path | str) -> dict[str, Any] | None:
    """The unresolved problem found the last time ``identity_file`` was loaded
    (a copy), or None when the last load was clean. Cleared as soon as the file
    loads or is saved cleanly again."""

    with _ISSUES_LOCK:
        issue = _ISSUES.get(_issue_key(Path(identity_file)))
        return copy.deepcopy(issue) if issue else None


def _clear_issue(path: Path) -> None:
    with _ISSUES_LOCK:
        cleared = _ISSUES.pop(_issue_key(path), None)
    if cleared:
        LOGGER.warning(
            "Identity profile %s loads cleanly again; the earlier %s problem is resolved.",
            path, cleared.get("kind"),
        )


def _preserve_bad_file(path: Path, data: bytes) -> str | None:
    """Keep a copy of the unparseable file next to it, named by content hash so
    repeated loads do not pile up copies. Best effort; returns the path or None."""

    target = path.with_name(f"{path.name}.corrupt-{hashlib.sha256(data).hexdigest()[:8]}")
    try:
        if not target.exists():
            shutil.copyfile(path, target)
        return str(target)
    except OSError:
        return None


def _record_issue(path: Path, kind: str, error: str, *, data: bytes | None,
                  line: int | None = None, column: int | None = None,
                  existing_install: bool) -> None:
    fingerprint = hashlib.sha256(data).hexdigest()[:12] if data is not None else ""
    key = _issue_key(path)
    with _ISSUES_LOCK:
        known = _ISSUES.get(key)
        if (known and known.get("kind") == kind and known.get("fingerprint") == fingerprint
                and known.get("error") == error):
            return  # same problem as last load: already logged, keep first_seen
        backup = _preserve_bad_file(path, data) if data else None
        issue = {
            "path": str(path),
            "kind": kind,
            "error": error,
            "line": line,
            "column": column,
            "size_bytes": len(data) if data is not None else None,
            "detected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "backup": backup,
            "fallback": "existing-install seed (Caledonia values)" if existing_install else "blank new-install seed",
            "fingerprint": fingerprint,
        }
        _ISSUES[key] = issue
    where = f" at line {line}, column {column}" if line else ""
    LOGGER.error(
        "Identity profile %s is unusable (%s%s: %s). The app is continuing on the %s "
        "-- graphics will show those values until the file is fixed. %s",
        path, kind, where, error, issue["fallback"],
        f"A copy of the bad file was kept at {backup}." if backup else "No copy of the bad file could be kept.",
    )


def load_identity_profile(
    identity_file: Path,
    *,
    existing_install: bool,
) -> dict[str, Any]:
    """Return the identity profile, seeding the file on first run.

    ``existing_install`` must be evaluated by the caller BEFORE any repository
    auto-creates config.json (which would make the check always true).

    A present-but-unusable file never raises (see "Load-problem reporting"
    above): the result is the seed, and load_issue(identity_file) says why.
    """

    path = Path(identity_file)
    if path.exists():
        raw = None
        data: bytes | None = None
        try:
            data = path.read_bytes()
            text = data.decode("utf-8-sig")
            raw = json.loads(text)
        except OSError as exc:
            _record_issue(path, "unreadable", f"{type(exc).__name__}: {exc}", data=data,
                          existing_install=existing_install)
        except UnicodeDecodeError as exc:
            _record_issue(path, "invalid_json", f"not valid UTF-8 text ({exc})", data=data,
                          existing_install=existing_install)
        except ValueError as exc:
            _record_issue(path, "invalid_json", getattr(exc, "msg", str(exc)), data=data,
                          line=getattr(exc, "lineno", None), column=getattr(exc, "colno", None),
                          existing_install=existing_install)
        else:
            if isinstance(raw, Mapping):
                _clear_issue(path)
            else:
                _record_issue(path, "not_an_object",
                              f"the top level must be a JSON object, found {type(raw).__name__}",
                              data=data, existing_install=existing_install)
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
    _clear_issue(path)  # what is on disk now is valid by construction
    return normalized
