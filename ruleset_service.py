"""Ruleset engine -- data-driven game rules keyed by (jurisdiction, sport).

Round 6 Task C found that every rule value in CSRN (penalty yardages,
kickoff / free-kick / try spots, quarter length, period structure,
classification scheme, reserved school IDs, timezone / association
defaults) was a hardcoded NFHS-football-with-Mississippi-identifiers
constant. This module replaces that with plain-JSON ruleset documents.

A ruleset lives in ``rulesets/<sport>/<id>.json`` (or, for a document meant
only as a shared extends-parent across sports, ``rulesets/<id>.json`` --
see ``bat-ball-base``) and may name a parent via ``"extends": "<id>"``.
``load_ruleset`` walks that chain and deep-merges parent-then-child: child
dicts merge recursively, child scalars / lists / explicit null replace the
parent value.

Shipped documents: ``football/us-nfhs`` (base) and ``football/us-ms-mhsaa``
(Round 6/Round 26/Round 27, US); ``football/ca-base`` and
``football/ca-cjfl-ofc`` (Round 26, Canadian); ``bat-ball-base`` (baseball
engine P0, the mechanics shared by both bat-and-ball sports -- never
resolved directly, only extended), ``baseball/us-nfhs`` and
``softball/us-nfhs`` (baseball engine P0, US NFHS-generic). State-specific
baseball/softball overlays (the ``us-ms-mhsaa`` equivalent) are a later
phase, gated on the owner's own MHSAA handbook confirmation.
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
    (("CA", "ON", "CJFL", "football"), "football/ca-cjfl-ofc"),
    (("CA", None, None, "football"), "football/ca-base"),
    # Baseball engine P0 -- NFHS-generic only. MHSAA state overlays land
    # once the owner confirms the 2026-27 handbook values (a later phase).
    (("US", None, "NFHS", "baseball"), "baseball/us-nfhs"),
    (("US", None, None, "baseball"), "baseball/us-nfhs"),
    (("US", None, "NFHS", "softball"), "softball/us-nfhs"),
    (("US", None, None, "softball"), "softball/us-nfhs"),
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


def resolve_id(
    *,
    country: str | None = "US",
    region: str | None = None,
    association: str | None = None,
    sport: str = "football",
) -> str:
    """The ruleset id a jurisdiction + sport maps to (no document load).
    Falls back to DEFAULT_RULESET_ID when nothing in the catalogue matches.

    Cheap -- a catalogue scan, no deep copy -- so callers that cache derived
    values keyed by ruleset id can check the key on every call and only
    load the document when the key is new.
    """
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
        return ruleset_id
    return DEFAULT_RULESET_ID


def resolve(
    *,
    country: str | None = "US",
    region: str | None = None,
    association: str | None = None,
    sport: str = "football",
) -> dict[str, Any]:
    """Map a jurisdiction + sport to a resolved ruleset. Falls back to
    DEFAULT_RULESET_ID when nothing matches."""
    return load_ruleset(
        resolve_id(
            country=country, region=region, association=association, sport=sport
        )
    )


def active_ruleset(
    state: Mapping[str, Any] | None = None, *, sport: str = "football"
) -> dict[str, Any]:
    """The resolved ruleset for the game described by *state*.

    Jurisdiction is taken from state's ``country`` / ``region`` /
    ``association`` -- the fields a Canadian broadcast will carry. When they
    are absent (every current broadcast) this falls back to the generic
    base, whose down / field / scoring / penalty / period values are
    identical to us-ms-mhsaa, so routing every engine consumer through here
    is a no-op today. It is the single place a future sport/jurisdiction
    picker wires into.
    """
    return load_ruleset(active_ruleset_id(state, sport=sport))


def active_ruleset_id(
    state: Mapping[str, Any] | None = None, *, sport: str = "football"
) -> str:
    """The ruleset id for *state*'s jurisdiction -- the cheap key a consumer
    checks before loading the document. See ``active_ruleset``."""
    s = state if isinstance(state, Mapping) else {}
    return resolve_id(
        country=s.get("country") or "US",
        region=s.get("region") or None,
        association=s.get("association") or None,
        sport=sport,
    )


def available_rulesets() -> list[dict[str, Any]]:
    """One entry per shipped ruleset document: ``id``, ``label``, ``sport``,
    and the ``country`` / ``region`` / ``association`` its ``jurisdiction``
    block declares (``region`` / ``association`` may be ``None``).

    This is what the broadcast-creation jurisdiction picker groups on. The
    jurisdiction is read from the raw document -- every shipped ruleset
    (us-nfhs, us-ms-mhsaa, ca-base, ca-cjfl-ofc) declares its own, so no
    ``extends`` resolution is needed here.
    """
    out: list[dict[str, Any]] = []
    root = rulesets_dir()
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*.json")):
        rel = path.relative_to(root).with_suffix("").as_posix()
        try:
            doc = _read_document(rel)
        except (FileNotFoundError, ValueError):
            continue
        jur = doc.get("jurisdiction") if isinstance(doc.get("jurisdiction"), Mapping) else {}
        out.append(
            {
                "id": rel,
                "label": str(doc.get("label", rel)),
                "sport": str(doc.get("sport", rel.split("/", 1)[0])),
                "country": (str(jur.get("country")).strip().upper() if jur.get("country") else None),
                "region": (str(jur.get("region")).strip().upper() if jur.get("region") else None),
                "association": (str(jur.get("association")).strip().upper() if jur.get("association") else None),
            }
        )
    return out


# --- helpers for consumers migrating off hardcoded constants ---------------

def field_spot_yardage(spec: str, length_yards: int = 100) -> tuple[str, int]:
    """A symbolic field spot ("own_40", "opp_3") -> (side, yard).

    side is "own" or "opp". yard is clamped to the field's half-way point
    (50 on a 100-yard field, 55 on a 110-yard Canadian field) -- pass the
    ruleset's field.length_yards so a Canadian midfield spec ("own_55")
    isn't silently pulled back to 50. Consumers have _team_own_yard_spot /
    _opponent_yard_spot helpers that take a yard int.
    """
    side, _, raw = str(spec or "").strip().lower().partition("_")
    if side not in {"own", "opp"}:
        raise ValueError(f"bad field spot spec: {spec!r}")
    try:
        midpoint = max(1, int(length_yards) // 2)
    except (TypeError, ValueError):
        midpoint = 50
    try:
        yard = max(0, min(midpoint, int(raw)))
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


# --- down / field / scoring shape (Round 26) ------------------------------
#
# canonical_state_service, rules_service and penalty_service each hardcode
# the same three shapes today: the ["1st".."4th"] down cycle, the bare
# 0-100 field coordinate scale, and the point value of every scoring play.
# These helpers read those from the ruleset instead so a 3-down / 110-yard
# / rouge-scoring document (ca-base) can express Canadian football without
# any consumer branching on jurisdiction. For every current US ruleset they
# return exactly the values above -- see tests/test_ruleset_golden.py.

_DOWN_ORDINALS: tuple[str, ...] = ("1st", "2nd", "3rd", "4th", "5th", "6th")

_FIELD_GEOMETRY_DEFAULTS: dict[str, int] = {
    "length_yards": 100,
    "end_zone_depth_yards": 10,
    "red_zone_yards": 20,
}

_SCORING_DEFAULTS: dict[str, int] = {
    "touchdown": 6,
    "field_goal": 3,
    "safety": 2,
    "convert_kick": 1,
    "convert_major": 2,
    "single": 1,
}


def downs_sequence(ruleset: Mapping[str, Any]) -> list[str]:
    """Ordered down labels for one series -- ``["1st", "2nd", "3rd", "4th"]``
    for NFHS, ``["1st", "2nd", "3rd"]`` for Canadian.

    Length is ``period.downs_per_set`` (default 4), clamped to the ordinals
    this module knows how to name.
    """
    raw = ((ruleset.get("period") or {}).get("downs_per_set", 4))
    try:
        count = int(raw)
    except (TypeError, ValueError):
        count = 4
    count = max(1, min(count, len(_DOWN_ORDINALS)))
    return list(_DOWN_ORDINALS[:count])


def next_down(down: str, sequence: list[str], *, wrap: bool = True) -> str:
    """The down after *down* within *sequence*. An unrecognised *down* resets
    to the first entry.

    ``wrap=True`` (default) sends the last down back to the first -- the
    ``"4th" -> "1st"`` cycle canonical_state_service uses before it applies
    turnover-on-downs. ``wrap=False`` keeps the last down where it is -- the
    clamp rules_service / penalty_service apply so a loss-of-down on the
    final down never reads as a fresh series.
    """
    if not sequence:
        return down
    try:
        idx = sequence.index(down)
    except ValueError:
        return sequence[0]
    if idx + 1 < len(sequence):
        return sequence[idx + 1]
    return sequence[0] if wrap else sequence[-1]


def is_terminal_down(down: str, sequence: list[str]) -> bool:
    """True when *down* is the last of the series -- failing to convert it is
    a turnover on downs (the consumers' ``if old_down == "4th"`` check)."""
    return bool(sequence) and down == sequence[-1]


def field_geometry(ruleset: Mapping[str, Any]) -> dict[str, int]:
    """``{length_yards, end_zone_depth_yards, red_zone_yards}`` for the
    ruleset, each defaulting to today's hardcoded value when absent."""
    field = ruleset.get("field") or {}
    out = dict(_FIELD_GEOMETRY_DEFAULTS)
    for key in out:
        if key in field:
            try:
                out[key] = int(field[key])
            except (TypeError, ValueError):
                pass
    return out


def scoring_values(ruleset: Mapping[str, Any]) -> dict[str, int]:
    """Point value of every scoring play, ruleset values merged over the
    current NFHS defaults (TD 6 / FG 3 / safety 2 / convert-kick 1 /
    convert-major 2 / single 1)."""
    scoring = ruleset.get("scoring") or {}
    out = dict(_SCORING_DEFAULTS)
    for key, value in scoring.items():
        try:
            out[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return out


def no_fair_catch(ruleset: Mapping[str, Any]) -> bool:
    """True when the ruleset abolishes the fair catch (Canadian football).
    NFHS keeps it, so this is False for every current US ruleset."""
    return bool((ruleset.get("field") or {}).get("no_fair_catch", False))


def single_restart_spot(ruleset: Mapping[str, Any]) -> str:
    """The spec ("own_35") the team scored upon restarts from after
    conceding a single / rouge, or "" when the ruleset has no single
    (NFHS). The value for Canadian amateur play is unverified -- see
    ca-base.json's _source_notes."""
    return str((ruleset.get("field") or {}).get("single_restart_spot") or "")


def no_yards_halo(ruleset: Mapping[str, Any]) -> int:
    """The restraining-zone ("no yards") radius, in yards, the kicking team
    must give a punt returner. 0 means the rule does not apply -- NFHS has
    no such rule, so this is 0 for every current US ruleset. Canadian
    rulesets set it (commonly 5 for a bouncing ball); the exact amateur /
    CJFL value is carried in the ruleset's own _source_notes pending a
    rulebook check.
    """
    try:
        return max(0, int((ruleset.get("field") or {}).get("no_yards_halo_yards", 0) or 0))
    except (TypeError, ValueError):
        return 0


_BASE_PLAY_TYPES: frozenset[str] = frozenset({"run", "pass", "kickoff", "punt"})


def valid_play_types(ruleset: Mapping[str, Any]) -> set[str]:
    """The play types the rules engine accepts for this ruleset.

    Always the four scrimmage/kick types RulesService has always allowed;
    a ruleset that sets ``field.field_goal_play`` true additionally allows
    ``"field_goal"`` as a distinct, returnable place-kick (Canadian rules,
    where a missed field goal is live). NFHS omits the flag, so the set is
    unchanged for every current US ruleset.
    """
    out = set(_BASE_PLAY_TYPES)
    if bool((ruleset.get("field") or {}).get("field_goal_play", False)):
        out.add("field_goal")
    return out
