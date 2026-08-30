"""Ruleset engine -- data-driven game rules keyed by (jurisdiction, sport).

Round 6 Task C found that every rule value in CSRN (penalty yardages,
kickoff / free-kick / try spots, quarter length, period structure,
classification scheme, reserved school IDs, timezone / association
defaults) was a hardcoded NFHS-football-with-Mississippi-identifiers
constant. This module replaces that with plain-JSON ruleset documents.

A ruleset lives in ``rulesets/<sport>/<id>.json`` and may name a parent via
``"extends": "<sport>/<parent-id>"``. ``load_ruleset`` walks that chain and
deep-merges parent-then-child: child dicts merge recursively, child
scalars / lists / explicit null replace the parent value.

This round ships exactly two documents -- ``football/us-nfhs`` (base) and
``football/us-ms-mhsaa`` (extends it, adds MS classification + timezone /
association) -- which together reproduce every currently-hardcoded value.
No other sports or jurisdictions.
"""

from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path
from typing import Any, Mapping

_BASE_DIR = Path(__file__).resolve().parent
_LOCK = threading.RLock()
_CACHE: dict[str, dict[str, Any]] = {}

# (country, region, association, sport) -> ruleset id. region/association may
# be None to mean "any". First matching, most-specific-first, wins.
_CATALOG: tuple[tuple[tuple[str | None, str | None, str | None, str], str], ...] = (
    (("US", "MS", "MHSAA", "football"), "football/us-ms-mhsaa"),
    (("US", None, "NFHS", "football"), "football/us-nfhs"),
    (("US", None, None, "football"), "football/us-nfhs"),
)

# What resolve() falls back to when nothing in the catalogue matches. Keep
# this the generic base, never a jurisdiction-specific document.
DEFAULT_RULESET_ID = "football/us-nfhs"


def rulesets_dir() -> Path:
    override = os.environ.get("CSRN_RULESETS_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return _BASE_DIR / "rulesets"


def _read_document(ruleset_id: str) -> dict[str, Any]:
    path = rulesets_dir() / f"{ruleset_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"ruleset not found: {ruleset_id} ({path})")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"ruleset {ruleset_id} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"ruleset {ruleset_id} must be a JSON object")
    return data


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = copy.deepcopy(dict(base))
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], Mapping)
            and isinstance(value, Mapping)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _resolve_document(ruleset_id: str, _seen: tuple[str, ...] = ()) -> dict[str, Any]:
    if ruleset_id in _seen:
        raise ValueError(f"ruleset extends cycle: {' -> '.join((*_seen, ruleset_id))}")
    document = _read_document(ruleset_id)
    parent_id = document.get("extends")
    if parent_id:
        parent = _resolve_document(str(parent_id), (*_seen, ruleset_id))
        resolved = _deep_merge(parent, document)
    else:
        resolved = copy.deepcopy(document)
    resolved.pop("extends", None)
    resolved["id"] = ruleset_id
    return resolved


def load_ruleset(ruleset_id: str) -> dict[str, Any]:
    """Return the fully-resolved ruleset for *ruleset_id* (extends chain
    walked, parent-then-child deep-merged). Cached; a deep copy is returned
    so callers cannot mutate the cache."""
    with _LOCK:
        if ruleset_id not in _CACHE:
            _CACHE[ruleset_id] = _resolve_document(ruleset_id)
        return copy.deepcopy(_CACHE[ruleset_id])


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()


def resolve(
    *,
    country: str | None = "US",
    region: str | None = None,
    association: str | None = None,
    sport: str = "football",
) -> dict[str, Any]:
    """Map a jurisdiction + sport to a resolved ruleset. Falls back to
    DEFAULT_RULESET_ID when nothing matches."""
    country_n = (country or "").strip().upper() or None
    region_n = (region or "").strip().upper() or None
    association_n = (association or "").strip().upper() or None
    sport_n = (sport or "football").strip().lower()

    for (c, r, a, s), ruleset_id in _CATALOG:
        if s != sport_n:
            continue
        if c is not None and c != country_n:
            continue
        if r is not None and r != region_n:
            continue
        if a is not None and a != association_n:
            continue
        return load_ruleset(ruleset_id)
    return load_ruleset(DEFAULT_RULESET_ID)


def available_rulesets() -> list[dict[str, str]]:
    """{id, label, sport} for every shipped ruleset document -- for a future
    location/sport picker. Purely informational this round."""
    out: list[dict[str, str]] = []
    root = rulesets_dir()
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*.json")):
        rel = path.relative_to(root).with_suffix("").as_posix()
        try:
            doc = _read_document(rel)
        except (FileNotFoundError, ValueError):
            continue
        out.append(
            {
                "id": rel,
                "label": str(doc.get("label", rel)),
                "sport": str(doc.get("sport", rel.split("/", 1)[0])),
            }
        )
    return out


# --- helpers for consumers migrating off hardcoded constants ---------------

def field_spot_yardage(spec: str) -> tuple[str, int]:
    """A symbolic field spot ("own_40", "opp_3") -> (side, yard).

    side is "own" or "opp"; yard is 0-50. Consumers already have
    _team_own_yard_spot / _opponent_yard_spot helpers that take a yard int.
    """
    side, _, raw = str(spec or "").strip().lower().partition("_")
    if side not in {"own", "opp"}:
        raise ValueError(f"bad field spot spec: {spec!r}")
    try:
        yard = max(0, min(50, int(raw)))
    except ValueError as exc:
        raise ValueError(f"bad field spot spec: {spec!r}") from exc
    return side, yard


def penalty_rules(ruleset: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Ruleset ``penalties`` ("Unit/Name" keys) -> PenaltyService's
    (unit, name) tuple-keyed shape."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for key, value in (ruleset.get("penalties") or {}).items():
        unit, _, name = str(key).partition("/")
        if unit and name and isinstance(value, Mapping):
            out[(unit, name)] = dict(value)
    return out
