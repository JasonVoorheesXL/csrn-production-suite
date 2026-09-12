"""Canonical baseball/softball game-state fields, pure mutators, and the
append-only event reducer (CSRN_NFHS_Baseball_Softball_Rules_Engine_Spec_
2026 Sec.2 "Core architecture" / Sec.4 "Canonical game state"). Mirrors
CanonicalStateFoundation's role for football: mutates only the supplied
state dict, no persistence/history/source-authority concerns (that stays
GameOperationsService's job once P4 wires routes -- this module, per the
baseball engine scoping plan's P1 row, is deliberately "No UI").

Sec.2.1 "Event-sourcing recommendation": AuthoritativeState = reduce(
snapshot, eventsAfterSnapshot). The structural event interpreters below
(_apply_plate_appearance, _apply_half_inning_transition, etc.) are the
single place that logic lives -- both a live operator action and a later
replay call the same interpreter, so "replay reproduces the live result"
holds by construction rather than by keeping two code paths in sync (a
different, slightly more defensive choice than canonical_state_service.
rebuild()'s own football precedent, which diff-replays a recorded after-
snapshot for anything that isn't its one structurally-interpreted PLAY
event type -- baseball has no equivalent legacy history to accommodate,
so there was no reason to take on that same fallback's risk).

See docs/DIAMOND_OVERLAY_CONTRACT.md for how the fields here relate to
what the (already-shipped) rendering layer reads off the live state wire --
short version: home_score/visitor_score/line_score/home_hits/visitor_hits/
home_errors/visitor_errors/inning/inning_half/balls/strikes/outs are the
same flat names the wire contract uses; base_runners/current_*_id are
richer internal-only fields the overlay serializer (P3) will project down
to the wire's plain bases:[bool,bool,bool] shape.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

BASES: tuple[str, str, str] = ("first", "second", "third")
TEAMS: tuple[str, str] = ("home", "visitor")

# Fields this reducer owns and replays deterministically. Everything else on
# the shared CSRN state dict (team identity, crew, ticker, effective_profile_*,
# ...) is untouched scaffold state the diamond engine shares with every sport.
CANONICAL_FIELDS: tuple[str, ...] = (
    "inning",
    "inning_half",
    "outs",
    "balls",
    "strikes",
    "base_runners",
    "current_batter_id",
    "current_pitcher_id",
    "current_catcher_id",
    "plate_appearance_id",
    "at_bat_sequence",
    "home_score",
    "visitor_score",
    "line_score",
    "home_hits",
    "visitor_hits",
    "home_errors",
    "visitor_errors",
    "left_on_base",
    "ball_status",
    "pending_ruling",
    "game_end_candidate",
    "official_game_end_reason",
)

# Ledger bookkeeping fields -- part of canonical state but excluded from
# state_hash() (Sec.19.1's replay-determinism invariant is about the GAME
# SITUATION, not how many events it took to reach it).
_LEDGER_FIELDS: tuple[str, ...] = (
    "diamond_events",
    "last_applied_sequence",
    "last_snapshot_event_id",
)


def default_state() -> dict[str, Any]:
    """The baseball/softball-specific canonical fields, defaulted. Merge
    this onto the shared CSRN state dict for a game whose sport is baseball/
    softball -- wiring that merge into the live app (DEFAULT_STATE, app.py)
    is P4, not this module."""
    return {
        "inning": 1,
        "inning_half": "TOP",
        "outs": 0,
        "balls": 0,
        "strikes": 0,
        "base_runners": {base: None for base in BASES},
        "current_batter_id": "",
        "current_pitcher_id": "",
        "current_catcher_id": "",
        "plate_appearance_id": "",
        "at_bat_sequence": 0,
        "home_score": 0,
        "visitor_score": 0,
        "line_score": {"home": [], "visitor": []},
        "home_hits": 0,
        "visitor_hits": 0,
        "home_errors": 0,
        "visitor_errors": 0,
        "left_on_base": {"home": [], "visitor": []},
        "ball_status": "LIVE",
        "pending_ruling": None,
        "game_end_candidate": None,
        "official_game_end_reason": None,
        "diamond_events": [],
        "last_applied_sequence": 0,
        "last_snapshot_event_id": "",
    }


class DiamondStateFoundation:
    # --- derived reads --------------------------------------------------

    @classmethod
    def batting_team(cls, state: Mapping[str, Any]) -> str:
        return "visitor" if str(state.get("inning_half", "TOP")).upper().startswith("T") else "home"

    @classmethod
    def fielding_team(cls, state: Mapping[str, Any]) -> str:
        return "home" if cls.batting_team(state) == "visitor" else "visitor"

    @classmethod
    def opposite(cls, team: str) -> str:
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        return "visitor" if team == "home" else "home"

    @classmethod
    def bases_occupied(cls, state: Mapping[str, Any]) -> list[bool]:
        """DIAMOND_OVERLAY_CONTRACT wire projection: [first, second, third]
        occupied booleans, stripped of runner identity."""
        runners = state.get("base_runners") or {}
        return [bool(runners.get(base)) for base in BASES]

    @classmethod
    def snapshot(cls, state: Mapping[str, Any]) -> dict[str, Any]:
        return {field: copy.deepcopy(state.get(field)) for field in CANONICAL_FIELDS}

    @classmethod
    def state_hash(cls, state: Mapping[str, Any]) -> str:
        """Sec.19.1: 'Replaying the same ordered ledger produces the same
        state hash.' Ledger bookkeeping fields are excluded so two states
        that reached the same game situation by equivalent-but-differently-
        shaped history still hash equal."""
        payload = {field: state.get(field) for field in CANONICAL_FIELDS}
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    # --- pure primitive mutators -----------------------------------------

    @classmethod
    def set_count(cls, state: dict[str, Any], *, balls: int | None = None, strikes: int | None = None) -> None:
        if balls is not None:
            state["balls"] = max(0, min(3, int(balls)))
        if strikes is not None:
            state["strikes"] = max(0, min(2, int(strikes)))

    @classmethod
    def reset_count(cls, state: dict[str, Any]) -> None:
        state["balls"] = 0
        state["strikes"] = 0

    @classmethod
    def record_out(cls, state: dict[str, Any], count: int = 1) -> None:
        # Spec Sec.14.1 HARD_ERROR: "Four outs stored in an active half-
        # inning." Clamp, don't raise -- the caller (at_bat_rules_service)
        # is responsible for deciding a 4th recorded out is a HARD_ERROR
        # before it ever reaches this mutator; this is the structural
        # backstop, not the operator-facing message.
        state["outs"] = max(0, min(3, int(state.get("outs", 0)) + count))

    @classmethod
    def reset_outs(cls, state: dict[str, Any]) -> None:
        state["outs"] = 0

    @classmethod
    def place_runner(
        cls, state: dict[str, Any], base: str, player_id: str, *, reason: str, event_id: str = ""
    ) -> None:
        if base not in BASES:
            raise ValueError(f"unknown base: {base}")
        runners = state.setdefault("base_runners", {b: None for b in BASES})
        runners[base] = {"player_id": player_id, "reason": reason, "event_id": event_id}

    @classmethod
    def clear_base(cls, state: dict[str, Any], base: str) -> dict[str, Any] | None:
        if base not in BASES:
            raise ValueError(f"unknown base: {base}")
        runners = state.setdefault("base_runners", {b: None for b in BASES})
        occupant = runners.get(base)
        runners[base] = None
        return occupant

    @classmethod
    def move_runner(cls, state: dict[str, Any], from_base: str, to_base: str) -> None:
        occupant = cls.clear_base(state, from_base)
        if occupant is not None:
            runners = state.setdefault("base_runners", {b: None for b in BASES})
            runners[to_base] = occupant

    @classmethod
    def clear_bases(cls, state: dict[str, Any]) -> None:
        state["base_runners"] = {b: None for b in BASES}

    @classmethod
    def score_run(cls, state: dict[str, Any], team: str, *, count: int = 1) -> None:
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        key = f"{team}_score"
        state[key] = int(state.get(key, 0)) + count
        cls._add_inning_runs(state, team, int(state.get("inning", 1)), count)

    @classmethod
    def _add_inning_runs(cls, state: dict[str, Any], team: str, inning: int, runs: int) -> None:
        line_score = state.setdefault("line_score", {"home": [], "visitor": []})
        column = line_score.setdefault(team, [])
        while len(column) < inning:
            column.append(0)
        column[inning - 1] = int(column[inning - 1]) + runs

    @classmethod
    def record_hit(cls, state: dict[str, Any], team: str, count: int = 1) -> None:
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        key = f"{team}_hits"
        state[key] = int(state.get(key, 0)) + count

    @classmethod
    def record_error(cls, state: dict[str, Any], team: str, count: int = 1) -> None:
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        key = f"{team}_errors"
        state[key] = int(state.get(key, 0)) + count

    @classmethod
    def record_left_on_base(cls, state: dict[str, Any], team: str, count: int) -> None:
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        lob = state.setdefault("left_on_base", {"home": [], "visitor": []})
        lob.setdefault(team, []).append(int(count))

    @classmethod
    def runners_left_on_base(cls, state: Mapping[str, Any]) -> int:
        runners = state.get("base_runners") or {}
        return sum(1 for base in BASES if runners.get(base))

    # --- structural event interpreters -----------------------------------
    # Each of these is the ONLY place its event type's effect on canonical
    # state is computed -- called directly for a live operator action, and
    # by rebuild() for a replay. Same function, same result, always.

    @classmethod
    def apply_plate_appearance(cls, state: dict[str, Any], payload: Mapping[str, Any]) -> None:
        """Sec.7.2 plate-appearance output contract. payload:
        {battingTeam, runnerOutcomes: [{from: "batter"|base, to: base|"out"|
        "score", runId?}], outsRecorded, hits?, errors?}. Runner movement is
        applied base-to-base from HOME side first (third -> home) so a
        chain advance (single scores the runner from third, moves 1st to
        2nd) never double-occupies a base mid-application."""
        team = str(payload.get("battingTeam") or cls.batting_team(state))
        outcomes = list(payload.get("runnerOutcomes") or [])

        def _apply_one(outcome: Mapping[str, Any]) -> None:
            src = str(outcome.get("from", ""))
            dst = str(outcome.get("to", ""))
            if dst == "out":
                if src in BASES:
                    cls.clear_base(state, src)
                return
            if dst == "score":
                if src in BASES:
                    cls.clear_base(state, src)
                cls.score_run(state, team)
                return
            if dst in BASES:
                if src == "batter":
                    cls.place_runner(state, dst, str(outcome.get("playerId", "")), reason="PLATE_APPEARANCE")
                elif src in BASES:
                    cls.move_runner(state, src, dst)

        # Order third->home first so scoring a run from third never
        # collides with a later batter-to-first placement.
        order = {"third": 0, "second": 1, "first": 2, "batter": 3}
        for outcome in sorted(outcomes, key=lambda o: order.get(str(o.get("from", "")), 9)):
            _apply_one(outcome)

        outs_recorded = int(payload.get("outsRecorded", 0) or 0)
        if outs_recorded:
            cls.record_out(state, outs_recorded)
        if payload.get("hits"):
            cls.record_hit(state, team, int(payload["hits"]))
        if payload.get("errors"):
            cls.record_error(state, cls.opposite(team), int(payload["errors"]))
        cls.reset_count(state)
        state["at_bat_sequence"] = int(state.get("at_bat_sequence", 0)) + 1

    @classmethod
    def apply_half_inning_transition(cls, state: dict[str, Any], payload: Mapping[str, Any]) -> None:
        """Sec.7.1: at three outs, close the half-inning, persist LOB,
        swap offense/defense, advance the inning number after the bottom
        half. payload carries the LOB count the caller (inning_service)
        already computed from base_runners BEFORE clearing them, so replay
        doesn't need to re-derive it from a base state this event itself
        is about to clear."""
        closing_team = cls.batting_team(state)
        lob = int(payload.get("leftOnBase", cls.runners_left_on_base(state)))
        cls.record_left_on_base(state, closing_team, lob)
        cls.clear_bases(state)
        cls.reset_count(state)
        cls.reset_outs(state)
        half = str(state.get("inning_half", "TOP")).upper()
        if half.startswith("T"):
            state["inning_half"] = "BOTTOM"
        else:
            state["inning_half"] = "TOP"
            state["inning"] = int(state.get("inning", 1)) + 1

    @classmethod
    def apply_tiebreaker_runner_placed(cls, state: dict[str, Any], payload: Mapping[str, Any]) -> None:
        """Sec.11.3: seeded-runner placement must be a first-class event,
        not a silent mutation of second base."""
        base = str(payload.get("base", "second"))
        player_id = str(payload.get("playerId", ""))
        cls.place_runner(state, base, player_id, reason="TIEBREAKER_RUNNER_PLACED")

    @classmethod
    def apply_ruling(cls, state: dict[str, Any], payload: Mapping[str, Any]) -> None:
        """Sec.6.2 UmpireRulingPayload, applied exactly as recorded -- no
        engine judgment of the deserved outcome (spec: 'moves runner to
        third; no engine judgment of deserved base')."""
        for award in payload.get("baseAwards") or []:
            src = str(award.get("fromBase", ""))
            dst = str(award.get("toBase", ""))
            if src in BASES and dst == "score":
                cls.clear_base(state, src)
                cls.score_run(state, cls.batting_team(state))
            elif src in BASES and dst in BASES:
                cls.move_runner(state, src, dst)
            elif src == "batter" and dst in BASES:
                cls.place_runner(state, dst, str(award.get("playerId", "")), reason="UMPIRE_RULING")
        outs_awarded = payload.get("outsAwarded") or []
        if outs_awarded:
            cls.record_out(state, len(outs_awarded))
        state["pending_ruling"] = None
        state["ball_status"] = str(payload.get("ballStatus", "LIVE"))

    # --- event ledger -----------------------------------------------------

    @classmethod
    def append_event(
        cls, state: dict[str, Any], event_type: str, payload: Mapping[str, Any], *, event_id: str = ""
    ) -> dict[str, Any]:
        """Record that an event happened (spec Sec.6 GameEvent). Callers
        apply the corresponding structural interpreter THEMSELVES before or
        after calling this -- append_event does not mutate game state, only
        the ledger, so a live-apply call sequence and rebuild()'s replay
        sequence look identical from the ledger's point of view."""
        events = state.setdefault("diamond_events", [])
        sequence = len(events) + 1
        event = {
            "event_id": event_id or f"evt-{sequence}",
            "sequence": sequence,
            "event_type": event_type,
            "payload": copy.deepcopy(dict(payload)),
            "voided": False,
        }
        events.append(event)
        state["last_applied_sequence"] = sequence
        return event

    @classmethod
    def void_event(cls, state: dict[str, Any], event_id: str) -> bool:
        """Spec Sec.15.2 EVENT_VOIDED: the original event stays in the
        ledger for audit; it simply no longer contributes when replayed.
        The full operator-facing correction workflow (EVENT_CORRECTED,
        replacement payloads, ruling/admin source requirements) is
        diamond_event_service, P2 -- this is the reducer-level primitive
        P2's void/correct commands build on."""
        for event in state.get("diamond_events", []):
            if event.get("event_id") == event_id:
                event["voided"] = True
                return True
        return False

    # --- replay -------------------------------------------------------

    _INTERPRETERS = {
        "PLATE_APPEARANCE": "apply_plate_appearance",
        "HALF_INNING_END": "apply_half_inning_transition",
        "TIEBREAKER_RUNNER_PLACED": "apply_tiebreaker_runner_placed",
        "RULING": "apply_ruling",
    }

    @classmethod
    def rebuild(
        cls,
        current_state: Mapping[str, Any],
        events: list[dict[str, Any]],
        *,
        baseline: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Sec.2.1: AuthoritativeState = reduce(snapshot, eventsAfterSnapshot).
        Replays every non-voided event in sequence order through the same
        structural interpreter a live apply uses, from `baseline` (a prior
        snapshot) or the canonical defaults when absent. Sec.19.1 invariants
        this exists to satisfy: replaying the same ledger reproduces the
        same state_hash; voiding an event and replaying reproduces the same
        result as a clean ledger without it, except audit metadata (the
        voided event itself stays visible in diamond_events)."""
        rebuilt = copy.deepcopy(dict(current_state))
        seed = dict(baseline) if baseline is not None else default_state()
        for field in CANONICAL_FIELDS:
            rebuilt[field] = copy.deepcopy(seed.get(field, default_state()[field]))

        ordered = sorted(
            (e for e in events if isinstance(e, dict)),
            key=lambda e: int(e.get("sequence", 0) or 0),
        )
        applied = []
        for event in ordered:
            event = copy.deepcopy(event)
            if event.get("voided"):
                applied.append(event)
                continue
            event["before"] = cls.snapshot(rebuilt)
            method_name = cls._INTERPRETERS.get(str(event.get("event_type", "")).upper())
            if method_name:
                getattr(cls, method_name)(rebuilt, event.get("payload") or {})
            event["after"] = cls.snapshot(rebuilt)
            applied.append(event)

        rebuilt["diamond_events"] = applied
        contributing = [e for e in applied if not e.get("voided")]
        rebuilt["last_applied_sequence"] = (
            max(int(e.get("sequence", 0) or 0) for e in contributing) if contributing else 0
        )
        return rebuilt
