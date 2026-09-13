"""Canonical basketball game-state fields, pure mutators, and the
append-only event reducer (docs/BASKETBALL_ENGINE_SCOPING_PLAN.md Sec.3
"Canonical basketball game state" / Sec.5.2 "Responsibility split").
Mirrors diamond_state_service.DiamondStateFoundation's role for baseball/
softball -- and, like that module, mutates only the supplied state dict,
never touches ruleset_service, and has no persistence/history/source-
authority concerns (P4, once routes exist).

State lives under state["hoops"] (engine_router.py's hoops_view()/
commit_hoops_view() namespace, added alongside diamond's the same way --
see that module's own P0-addendum docstring). period/clock/possession/
home_score/visitor_score are explicitly SHARED with football/the rest of
the app (docs/HOOPS_OVERLAY_CONTRACT.md Sec.1: same wire field names
football already publishes) -- engine_router.hoops_view() puts those on
the flat view it hands to this module's callers, but THIS module's own
HOOPS_CANONICAL_FIELDS only lists the fields state["hoops"] itself owns
(mirrors DIAMOND_OWNED_KEYS vs diamond_state_service.CANONICAL_FIELDS: the
diamond precedent duplicates home_score/visitor_score into its own
namespace and projects them back out via sync_shared_fields(); basketball
never moved those off the top level in the first place, so there is
nothing to project -- see engine_router.py's own HOOPS_OWNED_KEYS comment
for the full asymmetry).

Sec.2 responsibility table: this module owns "canonical basketball
fields; pure readers... mutators... No I/O." The structural event
interpreters below (_apply_shot, _apply_foul, etc.) are the single place
each event type's effect on canonical state is computed -- a live
operator call and a later replay both call the same interpreter, so
"replay reproduces the live result" holds by construction (same
event-sourcing shape as diamond_state_service.rebuild(), Sec.2.1 of the
baseball spec this scoping doc's Sec.5.2 explicitly borrows).

Sec.3.2 "Auto vs recorded" -- this module computes automatically: score
arithmetic, team-foul/player-foul accumulation, bonus (a pure function of
team fouls + the ruleset's bonus rule -- see bonus_for_fouls()),
foul-out flagging once told a threshold is reached, possession-arrow
flips when told a held ball happened. It NEVER decides: whether a foul
was personal/shooting/technical/flagrant, how many free throws it awards,
made-vs-missed, or whether a basket counts -- those are recorded exactly
as the operator/official reports them (hoops_rules_service's payloads),
never officiated here.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

TEAMS: tuple[str, str] = ("home", "visitor")
BONUS_STATES: tuple[str, str, str] = ("NONE", "ONE_AND_ONE", "DOUBLE")

# Fields this reducer owns and replays deterministically -- state["hoops"]'s
# own contents. Shared fields (period/clock/possession/scores/...) live on
# the outer state dict; see module docstring.
HOOPS_CANONICAL_FIELDS: tuple[str, ...] = (
    "period_format",
    "period_length_seconds",
    "shot_clock_seconds",
    "shot_clock_visible",
    "shot_clock_running",
    "home_team_fouls",
    "visitor_team_fouls",
    "home_bonus",
    "visitor_bonus",
    "player_fouls",
    "disqualified",
    "possession_arrow",
    "home_timeouts",
    "visitor_timeouts",
    "home_on_floor",
    "visitor_on_floor",
    "tv_timeout",
    "game_end_candidate",
    "official_end_reason",
)

# Ledger bookkeeping -- part of canonical state but excluded from
# state_hash() (same rationale as diamond_state_service._LEDGER_FIELDS:
# the replay-determinism invariant is about the game SITUATION, not how
# many events it took to reach it).
_LEDGER_FIELDS: tuple[str, ...] = (
    "hoops_events",
    "last_applied_sequence",
    "last_snapshot_event_id",
)

# The shared, non-namespaced fields on the OUTER state dict that this
# module's structural interpreters also mutate (period/clock/possession/
# scores -- see module docstring). Diamond has no equivalent split: all of
# its fields live in one flat namespace. Because these fields are mutated
# by the same interpreters, they must be part of the same snapshot/replay
# unit as HOOPS_CANONICAL_FIELDS -- snapshot()/state_hash()/rebuild() below
# all take the FULL outer state and cover both tuples together, not just
# state["hoops"].
_SHARED_CANONICAL_FIELDS: tuple[str, ...] = (
    "period",
    "clock_seconds",
    "clock_running",
    "clock_started_at",
    "possession",
    "home_score",
    "visitor_score",
)


def default_shared_state() -> dict[str, Any]:
    """Defaults for the SHARED outer-state fields this module's
    interpreters mutate (_SHARED_CANONICAL_FIELDS). Not merged in by
    default_state() below -- hoops_period_service.start_game() sets these
    for real from the active ruleset before a game begins; this exists so
    rebuild() has a well-defined zero-state to seed from when no baseline
    snapshot is given."""
    return {
        "period": "",
        "clock_seconds": 0,
        "clock_running": False,
        "clock_started_at": 0,
        "possession": "",
        "home_score": 0,
        "visitor_score": 0,
    }


def default_state() -> dict[str, Any]:
    """The basketball-specific canonical fields, defaulted. Merge this
    onto a fresh state["hoops"] for a game whose sport is basketball --
    wiring that into the live app is P4, not this module. period/
    clock_seconds/possession/scores are NOT here -- they're shared fields
    on the outer state dict (see module docstring and
    default_shared_state()); hoops_period_service.start_game() sets their
    initial values from the active ruleset."""
    return {
        "period_format": "",
        "period_length_seconds": 0,
        "shot_clock_seconds": None,
        "shot_clock_visible": False,
        "shot_clock_running": False,
        "home_team_fouls": 0,
        "visitor_team_fouls": 0,
        "home_bonus": "NONE",
        "visitor_bonus": "NONE",
        "player_fouls": {},
        "disqualified": [],
        "possession_arrow": "",
        "home_timeouts": 0,
        "visitor_timeouts": 0,
        "home_on_floor": [],
        "visitor_on_floor": [],
        "tv_timeout": False,
        "game_end_candidate": None,
        "official_end_reason": None,
        "hoops_events": [],
        "last_applied_sequence": 0,
        "last_snapshot_event_id": "",
    }


class HoopsStateFoundation:
    # --- derived reads ----------------------------------------------------

    @classmethod
    def opposite(cls, team: str) -> str:
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        return "visitor" if team == "home" else "home"

    @classmethod
    def snapshot(cls, state: Mapping[str, Any]) -> dict[str, Any]:
        """Takes the FULL outer state (not just state["hoops"]) -- see
        _SHARED_CANONICAL_FIELDS' module-docstring note on why the
        snapshot/replay unit spans both namespaces. The returned dict is
        flat (hoops-owned and shared field names never collide) and is
        exactly what rebuild()'s `baseline` parameter expects back."""
        hoops = state.get("hoops") or {}
        combined: dict[str, Any] = {field: copy.deepcopy(hoops.get(field)) for field in HOOPS_CANONICAL_FIELDS}
        combined.update({field: copy.deepcopy(state.get(field)) for field in _SHARED_CANONICAL_FIELDS})
        return combined

    @classmethod
    def state_hash(cls, state: Mapping[str, Any]) -> str:
        """Same invariant as diamond_state_service.state_hash() (spec
        Sec.19.1 equivalent for basketball): replaying the same ordered
        ledger produces the same hash. Ledger bookkeeping fields are
        excluded. Takes the full outer state, same as snapshot()."""
        encoded = json.dumps(cls.snapshot(state), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def bonus_for_fouls(cls, team_fouls: int, bonus_rule: Mapping[str, Any]) -> str:
        """Sec.3.1: 'bonus is a pure function of team fouls + the profile
        bonus rule -- never set directly.' Only one bonus_rule shape has
        ever been encoded in a shipped ruleset (basketball/us-nfhs.json's
        P0 content: {type: "TWO_SHOT_ON_FIFTH_FOUL", threshold: 5}) --
        this function handles exactly that type and raises on anything
        else rather than guessing at the old NFHS one-and-one/double-bonus
        shape the scoping doc's Sec.4.2 says MHSAA might still retain
        (flagged there as an owner-confirmation item, not yet a real
        ruleset value to derive against)."""
        rule_type = str(bonus_rule.get("type", ""))
        if rule_type == "TWO_SHOT_ON_FIFTH_FOUL":
            threshold = int(bonus_rule.get("threshold", 5))
            return "DOUBLE" if team_fouls >= threshold else "NONE"
        raise ValueError(
            f"unrecognized bonus_rule.type {rule_type!r} -- no shipped ruleset "
            "produces this shape yet; see scoping doc Sec.4.2 before adding one."
        )

    # --- pure primitive mutators -------------------------------------------

    @classmethod
    def set_period_format(cls, hoops: dict[str, Any], period_format: str) -> None:
        if period_format not in ("quarters", "halves"):
            raise ValueError(f"unknown period_format: {period_format}")
        hoops["period_format"] = period_format

    @classmethod
    def set_period_length(cls, hoops: dict[str, Any], seconds: int) -> None:
        hoops["period_length_seconds"] = max(0, int(seconds))

    @classmethod
    def set_shot_clock(
        cls, hoops: dict[str, Any], seconds: int | None, *, running: bool | None = None, visible: bool | None = None,
    ) -> None:
        hoops["shot_clock_seconds"] = None if seconds is None else max(0, int(seconds))
        if running is not None:
            hoops["shot_clock_running"] = bool(running)
        if visible is not None:
            hoops["shot_clock_visible"] = bool(visible)

    @classmethod
    def score_points(cls, state: dict[str, Any], team: str, points: int) -> None:
        # Lives on the OUTER state (shared home_score/visitor_score field,
        # per module docstring) -- not state["hoops"].
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        key = f"{team}_score"
        state[key] = int(state.get(key, 0)) + int(points)

    @classmethod
    def record_team_foul(cls, hoops: dict[str, Any], team: str, *, count: int = 1) -> int:
        """Pure increment -- does NOT recompute bonus (mirrors diamond's
        record_out() not knowing about the 4-outs HARD_ERROR limit: the
        caller, hoops_rules_service.foul(), calls bonus_for_fouls() itself
        right after this and writes the result, so it can pass the
        ruleset's bonus_rule through explicitly without this module ever
        importing ruleset_service)."""
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        key = f"{team}_team_fouls"
        hoops[key] = int(hoops.get(key, 0)) + int(count)
        return hoops[key]

    @classmethod
    def set_bonus(cls, hoops: dict[str, Any], team: str, value: str) -> None:
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        if value not in BONUS_STATES:
            raise ValueError(f"unknown bonus state: {value}")
        hoops[f"{team}_bonus"] = value

    @classmethod
    def reset_team_fouls(cls, hoops: dict[str, Any], team: str | None = None) -> None:
        """Period-boundary reset (hoops_period_service, per the ruleset's
        fouls.team_foul_scope). Resets bonus back to NONE alongside the
        count it's derived from -- never leaves a stale DOUBLE bonus after
        the count that earned it is cleared."""
        targets = TEAMS if team is None else (team,)
        for t in targets:
            if t not in TEAMS:
                raise ValueError(f"unknown team: {t}")
            hoops[f"{t}_team_fouls"] = 0
            hoops[f"{t}_bonus"] = "NONE"

    @classmethod
    def record_player_foul(cls, hoops: dict[str, Any], player_id: str, *, count: int = 1) -> int:
        """Pure increment, keyed by player_id. Does NOT disqualify --
        mirrors record_team_foul(): the caller (hoops_rules_service.foul())
        knows the ruleset's foul-out threshold and calls disqualify_player()
        itself once this return value reaches it."""
        fouls = hoops.setdefault("player_fouls", {})
        fouls[player_id] = int(fouls.get(player_id, 0)) + int(count)
        return fouls[player_id]

    @classmethod
    def disqualify_player(cls, hoops: dict[str, Any], player_id: str) -> None:
        disqualified = hoops.setdefault("disqualified", [])
        if player_id not in disqualified:
            disqualified.append(player_id)

    @classmethod
    def set_possession_arrow(cls, hoops: dict[str, Any], team: str) -> None:
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        hoops["possession_arrow"] = team

    @classmethod
    def flip_possession_arrow(cls, hoops: dict[str, Any]) -> str:
        current = hoops.get("possession_arrow") or ""
        new_arrow = cls.opposite(current) if current in TEAMS else "home"
        hoops["possession_arrow"] = new_arrow
        return new_arrow

    @classmethod
    def set_possession(cls, state: dict[str, Any], team: str) -> None:
        # Shared outer-state field (docs/HOOPS_OVERLAY_CONTRACT.md Sec.1:
        # same "possession" field name football already publishes).
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        state["possession"] = team

    @classmethod
    def set_timeouts(cls, hoops: dict[str, Any], team: str, count: int) -> None:
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        hoops[f"{team}_timeouts"] = max(0, int(count))

    @classmethod
    def use_timeout(cls, hoops: dict[str, Any], team: str) -> bool:
        """False (a no-op) if the team has none remaining -- the caller
        (hoops_rules_service) is responsible for surfacing that as a
        HARD_ERROR ('negative timeouts', Sec.3.1) before this is ever
        called, same guard-then-mutate discipline as every other CSRN
        *_service."""
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        key = f"{team}_timeouts"
        remaining = int(hoops.get(key, 0))
        if remaining <= 0:
            return False
        hoops[key] = remaining - 1
        return True

    @classmethod
    def set_on_floor(cls, hoops: dict[str, Any], team: str, player_ids: list[str]) -> None:
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        hoops[f"{team}_on_floor"] = list(player_ids)

    # --- structural event interpreters -------------------------------------
    # Each of these is the ONLY place its event type's effect on canonical
    # state is computed -- called directly for a live operator action, and
    # by rebuild() for a replay. Same function, same result, always.

    @classmethod
    def apply_game_start(cls, state: dict[str, Any], hoops: dict[str, Any], payload: Mapping[str, Any]) -> None:
        """payload: {firstPeriod, periodFormat, periodLengthSeconds,
        shotClockSeconds, shotClockVisible, homeTimeouts, visitorTimeouts}.
        P2 finding (hoops_event_service's undo/redo needs a full
        DiamondStateFoundation-style rebuild from JUST the ledger, same as
        diamond's own undo/redo -- see diamond_event_service.py): unlike
        diamond, this module's ruleset-derived initial values
        (period_length_seconds, shot clock, timeouts) are NOT reproducible
        from default_state() alone, since they come from the active
        ruleset, not structural defaults. Without this as a real,
        replayable event, rebuild()-with-no-baseline (undo/redo's normal
        mode) would reset them to zero/blank on every correction.
        hoops_period_service.start_game() applies this AND appends it as
        the ledger's own first event, exactly like every other mutation --
        it does not special-case itself as an unlogged setup step."""
        state["period"] = str(payload.get("firstPeriod", ""))
        state["clock_seconds"] = int(payload.get("periodLengthSeconds", 0))
        state["clock_running"] = False
        state["clock_started_at"] = 0
        cls.set_period_format(hoops, str(payload.get("periodFormat", "quarters")))
        cls.set_period_length(hoops, int(payload.get("periodLengthSeconds", 0)))
        cls.set_shot_clock(
            hoops, payload.get("shotClockSeconds"),
            running=False, visible=bool(payload.get("shotClockVisible")),
        )
        cls.set_timeouts(hoops, "home", int(payload.get("homeTimeouts", 0)))
        cls.set_timeouts(hoops, "visitor", int(payload.get("visitorTimeouts", 0)))
        cls.reset_team_fouls(hoops)
        hoops["player_fouls"] = {}
        hoops["disqualified"] = []

    @classmethod
    def apply_shot(cls, state: dict[str, Any], hoops: dict[str, Any], payload: Mapping[str, Any]) -> None:
        """payload: {team, made: bool, points: 2|3, shooterId?, assistId?,
        andOne?}. Recorded exactly as reported (made/missed, 2-vs-3,
        whether it counts) -- Sec.3.2: this is never engine-officiated."""
        team = str(payload.get("team", ""))
        if payload.get("made"):
            cls.score_points(state, team, int(payload.get("points", 2)))

    @classmethod
    def apply_free_throw(cls, state: dict[str, Any], hoops: dict[str, Any], payload: Mapping[str, Any]) -> None:
        """payload: {team, made: bool, shooterId?, attemptNumber?, ofAttempts?}."""
        if payload.get("made"):
            cls.score_points(state, str(payload.get("team", "")), 1)

    @classmethod
    def apply_rebound(cls, state: dict[str, Any], hoops: dict[str, Any], payload: Mapping[str, Any]) -> None:
        """payload: {team, playerId?, kind: "offensive"|"defensive"|"team"}.
        A rebound's only canonical-state effect is possession -- the team
        that pulled it down has the ball next."""
        team = str(payload.get("team", ""))
        if team:
            cls.set_possession(state, team)

    @classmethod
    def apply_foul(cls, state: dict[str, Any], hoops: dict[str, Any], payload: Mapping[str, Any]) -> None:
        """payload: {team, playerId?, foulType, countsTowardTeam: bool,
        countsTowardPersonal: bool, teamFoulsAfter, bonusRule (the
        resolved ruleset dict), foulOutThreshold}. hoops_rules_service.foul()
        computes countsTowardTeam/countsTowardPersonal from foulType + the
        ruleset (e.g. NFHS: technical fouls don't count toward team fouls,
        DO count toward personal when technical_counts_toward_personal) --
        this interpreter only applies what it's told, same "record the
        ruling" discipline as diamond_state_service.apply_ruling()."""
        team = str(payload.get("team", ""))
        player_id = str(payload.get("playerId", ""))
        if payload.get("countsTowardTeam") and team:
            new_total = cls.record_team_foul(hoops, team, count=1)
            bonus_rule = payload.get("bonusRule") or {}
            if bonus_rule:
                # Bonus is charged to the FOULING team's opponent -- e.g.
                # the visitor's 5th team foul of the quarter sends the
                # HOME team into the bonus (home shoots free throws on the
                # visitor's next fouls), not the other way around.
                cls.set_bonus(hoops, cls.opposite(team), cls.bonus_for_fouls(new_total, bonus_rule))
        if payload.get("countsTowardPersonal") and player_id:
            new_count = cls.record_player_foul(hoops, player_id, count=1)
            threshold = payload.get("foulOutThreshold")
            if threshold is not None and new_count >= int(threshold):
                cls.disqualify_player(hoops, player_id)

    @classmethod
    def apply_held_ball(cls, state: dict[str, Any], hoops: dict[str, Any], payload: Mapping[str, Any]) -> None:
        """Sec.5.1 'Held ball / jump situation' -> flip the alternating-
        possession arrow and assign possession to whichever team the
        (now-flipped) arrow points to."""
        team = cls.flip_possession_arrow(hoops)
        cls.set_possession(state, team)

    @classmethod
    def apply_turnover(cls, state: dict[str, Any], hoops: dict[str, Any], payload: Mapping[str, Any]) -> None:
        """payload: {team (the team that turned it over), playerId?}.
        Possession passes to the other team -- straightforward, no
        judgment involved (the operator already decided it was a
        turnover; this just flips possession)."""
        team = str(payload.get("team", ""))
        if team in TEAMS:
            cls.set_possession(state, cls.opposite(team))

    @classmethod
    def apply_lineup_set(cls, state: dict[str, Any], hoops: dict[str, Any], payload: Mapping[str, Any]) -> None:
        """payload: {team, playerIds: [5 ids]}. hoops_lineup_service has
        already validated the count and disqualification-freedom before
        appending this -- this interpreter only applies it, same "record
        the ruling" split as every other event type here."""
        team = str(payload.get("team", ""))
        if team in TEAMS:
            cls.set_on_floor(hoops, team, list(payload.get("playerIds", [])))

    @classmethod
    def apply_substitution(cls, state: dict[str, Any], hoops: dict[str, Any], payload: Mapping[str, Any]) -> None:
        """payload: {team, outPlayerId, inPlayerId}. hoops_lineup_service
        validates the out-player is on the floor, the in-player isn't
        already, and the in-player isn't disqualified, before appending
        this -- this interpreter only applies the already-validated swap."""
        team = str(payload.get("team", ""))
        if team not in TEAMS:
            return
        out_id = str(payload.get("outPlayerId", ""))
        in_id = str(payload.get("inPlayerId", ""))
        on_floor = list(hoops.get(f"{team}_on_floor", []))
        hoops[f"{team}_on_floor"] = [in_id if p == out_id else p for p in on_floor]

    @classmethod
    def apply_period_transition(cls, state: dict[str, Any], hoops: dict[str, Any], payload: Mapping[str, Any]) -> None:
        """payload: {nextPeriod, nextPeriodLengthSeconds, resetTeamFouls: bool,
        shotClockSeconds, shotClockVisible}. Called by
        hoops_period_service.close_period() -- this interpreter only
        applies the already-decided transition (mirrors diamond's
        apply_half_inning_transition() being called by inning_service)."""
        state["period"] = str(payload.get("nextPeriod", ""))
        length = int(payload.get("nextPeriodLengthSeconds", hoops.get("period_length_seconds", 0)))
        hoops["period_length_seconds"] = length
        state["clock_seconds"] = length
        state["clock_running"] = False
        state["clock_started_at"] = 0
        if payload.get("resetTeamFouls"):
            cls.reset_team_fouls(hoops)
        # Shot clock resets to the profile's full length (if enabled)
        # entering every new period -- not left at whatever it happened to
        # read when the old period's clock hit 0.
        cls.set_shot_clock(hoops, payload.get("shotClockSeconds"), running=False, visible=bool(payload.get("shotClockVisible")))

    # --- event ledger -------------------------------------------------------

    @classmethod
    def append_event(
        cls, hoops: dict[str, Any], event_type: str, payload: Mapping[str, Any], *, event_id: str = "",
    ) -> dict[str, Any]:
        """Record that an event happened. Callers apply the corresponding
        structural interpreter THEMSELVES before or after calling this --
        append_event does not mutate game state, only the ledger, so a
        live-apply sequence and rebuild()'s replay sequence look identical
        from the ledger's point of view (same shape as
        diamond_state_service.append_event())."""
        events = hoops.setdefault("hoops_events", [])
        sequence = len(events) + 1
        event = {
            "event_id": event_id or f"evt-{sequence}",
            "sequence": sequence,
            "event_type": event_type,
            "payload": copy.deepcopy(dict(payload)),
            "voided": False,
        }
        events.append(event)
        hoops["last_applied_sequence"] = sequence
        return event

    @classmethod
    def void_event(cls, hoops: dict[str, Any], event_id: str) -> bool:
        """Spec-equivalent of diamond_state_service.void_event(): the
        original event stays in the ledger for audit; it simply no longer
        contributes when replayed."""
        for event in hoops.get("hoops_events", []):
            if event.get("event_id") == event_id:
                event["voided"] = True
                return True
        return False

    # --- replay -------------------------------------------------------------

    _INTERPRETERS = {
        "GAME_START": "apply_game_start",
        "SHOT": "apply_shot",
        "FREE_THROW": "apply_free_throw",
        "REBOUND": "apply_rebound",
        "FOUL": "apply_foul",
        "HELD_BALL": "apply_held_ball",
        "TURNOVER": "apply_turnover",
        "LINEUP_SET": "apply_lineup_set",
        "SUBSTITUTION": "apply_substitution",
        "PERIOD_TRANSITION": "apply_period_transition",
    }

    @classmethod
    def rebuild(
        cls,
        current_state: Mapping[str, Any],
        events: list[dict[str, Any]],
        *,
        baseline: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """AuthoritativeState = reduce(snapshot, eventsAfterSnapshot) --
        same event-sourcing shape as diamond_state_service.rebuild().
        Replays every non-voided event in sequence order through the same
        structural interpreter a live apply uses. `current_state` is the
        OUTER state dict (so shared fields -- period/clock/possession/
        scores -- can be replayed too, alongside state["hoops"] itself,
        per _SHARED_CANONICAL_FIELDS). `baseline` is a prior snapshot()
        result (covering BOTH namespaces -- not just state["hoops"]), or
        combined canonical defaults when absent."""
        rebuilt = copy.deepcopy(dict(current_state))
        rebuilt_hoops: dict[str, Any] = dict(rebuilt.get("hoops") or {})
        seed = dict(baseline) if baseline is not None else {**default_state(), **default_shared_state()}
        defaults = {**default_state(), **default_shared_state()}
        for field in HOOPS_CANONICAL_FIELDS:
            rebuilt_hoops[field] = copy.deepcopy(seed.get(field, defaults[field]))
        for field in _SHARED_CANONICAL_FIELDS:
            rebuilt[field] = copy.deepcopy(seed.get(field, defaults[field]))
        rebuilt["hoops"] = rebuilt_hoops

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
                getattr(cls, method_name)(rebuilt, rebuilt_hoops, event.get("payload") or {})
            event["after"] = cls.snapshot(rebuilt)
            applied.append(event)

        rebuilt_hoops["hoops_events"] = applied
        contributing = [e for e in applied if not e.get("voided")]
        rebuilt_hoops["last_applied_sequence"] = (
            max(int(e.get("sequence", 0) or 0) for e in contributing) if contributing else 0
        )
        rebuilt["hoops"] = rebuilt_hoops
        return rebuilt
