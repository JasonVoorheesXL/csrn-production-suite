"""Roster/lineup ownership -- baseball and softball sub-engines (CSRN_NFHS_
Baseball_Softball_Rules_Engine_Spec_2026 Sec.5, Sec.8, Sec.9, Sec.10,
Sec.15.1). Owns player identity, batting slots, defensive positions, DH/DP/
FLEX, starter/substitute and re-entry history -- kept completely separate
from diamond_state_service (game situation: inning/count/bases/score),
matching the spec's own module boundary (Sec.2 "Roster/Lineup Service" is
its own row, distinct from "Game-State Reducer").

Sec.5: "Separate the player from the lineup slot. A slot is a persistent
offensive position in the batting order; a person may enter, leave, and
re-enter that slot. Defensive position is another independent assignment."

Ledger: lineup events (SUBSTITUTION, REENTRY, POSITION_CHANGE, DH_
TRANSITION, DP_FLEX_TRANSITION, COURTESY_RUNNER_ENTER/RETURN,
PLAYER_DEFENSIVE_MEETING, CHARGED_CONFERENCE) live on their own append-only
ledger (`lineup_events`), separate from diamond_state_service's
`diamond_events`. Spec Sec.2.1's ideal is one unified stream; two
independently-deterministic domain ledgers -- each replayable on its own,
each with its own structural interpreters -- is the pragmatic choice here,
avoiding a cross-module dispatch-table registration hack. diamond_event_
service (the operator-facing void/correct boundary) works across both.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

TEAMS: tuple[str, str] = ("home", "visitor")
DEFENSIVE_POSITIONS: tuple[str, ...] = ("P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF")

# Sec.5: SpecialRole enum.
ROLE_NONE = "NONE"
ROLE_BASEBALL_DH = "BASEBALL_DH"
ROLE_PLAYER_DH = "PLAYER_DH"
ROLE_SOFTBALL_DP = "SOFTBALL_DP"
ROLE_SOFTBALL_FLEX = "SOFTBALL_FLEX"
ROLE_COURTESY_RUNNER = "COURTESY_RUNNER"

DH_NONE = "NONE"
DH_TRADITIONAL = "TRADITIONAL_DH"
DH_PLAYER = "PLAYER_DH"


@dataclass(frozen=True)
class LineupMessage:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class LineupResult:
    code: str
    state: dict[str, Any]
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


def default_side_state() -> dict[str, Any]:
    return {
        "slots": {},  # "1".."10" -> {starter_player_id, active_player_id, entry_history:[...]}
        "defense": {},  # position -> player_id
        "roles": {},  # player_id -> SpecialRole string
        "dh_mode": DH_NONE,  # baseball only; softball leaves this at NONE
        "dp_flex": None,  # softball only -- see start_dp_flex()
        "defensive_meetings_this_half": 0,
        "charged_conferences": 0,
        "courtesy_runners": [],  # CourtesyRunnerAppearance dicts
        "batting_order_alerts": [],  # BattingOrderAlert dicts
        "pitching_appearances": [],  # entry/exit tracking only -- pitch-count POLICY is P4
    }


def default_state() -> dict[str, Any]:
    return {
        "lineup": {"home": default_side_state(), "visitor": default_side_state()},
        "lineup_events": [],
    }


class LineupService:
    # --- small internal accessors ---------------------------------------

    @classmethod
    def _side(cls, state: Mapping[str, Any], side: str) -> dict[str, Any]:
        if side not in TEAMS:
            raise ValueError(f"unknown side: {side}")
        lineup = state.get("lineup")
        if not isinstance(lineup, dict):
            raise ValueError("lineup state not initialized -- call start_lineup first")
        return lineup[side]

    @classmethod
    def _slot(cls, side_state: dict[str, Any], slot: int) -> dict[str, Any]:
        key = str(slot)
        return side_state["slots"].setdefault(
            key, {"starter_player_id": "", "active_player_id": "", "entry_history": []}
        )

    @classmethod
    def _current_appearance(cls, slot_state: Mapping[str, Any], player_id: str) -> dict[str, Any] | None:
        for appearance in reversed(slot_state.get("entry_history", [])):
            if appearance.get("player_id") == player_id and not appearance.get("exited_event_id"):
                return appearance
        return None

    @classmethod
    def _reentry_count(cls, slot_state: Mapping[str, Any], player_id: str) -> int:
        return sum(
            1
            for appearance in slot_state.get("entry_history", [])
            if appearance.get("player_id") == player_id and appearance.get("entry_type") == "REENTRY"
        )

    @classmethod
    def _has_ever_appeared(cls, slot_state: Mapping[str, Any], player_id: str) -> bool:
        return any(a.get("player_id") == player_id for a in slot_state.get("entry_history", []))

    @classmethod
    def _other_slots_with_history(cls, side_state: Mapping[str, Any], player_id: str, exclude_slot: int) -> list[int]:
        """Sec.9.1: re-entry must return to the SAME batting position --
        this finds any OTHER slot this player has appeared in, to catch an
        operator attempting to re-enter someone into the wrong slot."""
        found: list[int] = []
        for key, slot_state in side_state.get("slots", {}).items():
            if int(key) == exclude_slot:
                continue
            if cls._has_ever_appeared(slot_state, player_id):
                found.append(int(key))
        return found

    @classmethod
    def _append_event(cls, state: dict[str, Any], event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        events = state.setdefault("lineup_events", [])
        sequence = len(events) + 1
        event = {
            "event_id": f"lineup-evt-{sequence}",
            "sequence": sequence,
            "event_type": event_type,
            "payload": copy.deepcopy(dict(payload)),
            "voided": False,
        }
        events.append(event)
        return event

    # --- pregame lineup acceptance ---------------------------------------

    @classmethod
    def start_lineup(
        cls,
        state: dict[str, Any],
        side: str,
        starters: Mapping[int, str],
        defense: Mapping[str, str],
        *,
        sport: str = "baseball",
        dh_mode: str = DH_NONE,
    ) -> LineupResult:
        """Sec.5.1: pregame lineup input contract. Locks the DH mode once
        accepted (Sec.8.2: "Once the lineup card has been accepted, do not
        let the operator switch between traditional DH and player/DH modes
        as a mere edit -- require an official correction workflow")."""
        state.setdefault("lineup", {"home": default_side_state(), "visitor": default_side_state()})
        side_state = default_side_state()
        side_state["dh_mode"] = dh_mode if sport == "baseball" else DH_NONE
        for slot_number, player_id in starters.items():
            slot = cls._slot(side_state, int(slot_number))
            slot["starter_player_id"] = player_id
            slot["active_player_id"] = player_id
            slot["entry_history"].append(
                {
                    "player_id": player_id,
                    "slot": int(slot_number),
                    "entered_event_id": "",
                    "exited_event_id": "",
                    "entry_type": "STARTER",
                    "is_starter": True,
                }
            )
        side_state["defense"] = dict(defense)
        state["lineup"][side] = side_state
        event = cls._append_event(
            state, "LINEUP_ACCEPTED", {"side": side, "sport": sport, "dh_mode": side_state["dh_mode"]}
        )
        return LineupResult("OK", state, {"event": event})

    # --- baseball / shared re-entry state machine ------------------------

    @classmethod
    def substitute(
        cls,
        state: dict[str, Any],
        side: str,
        slot: int,
        incoming_player_id: str,
        *,
        sport: str = "baseball",
        event_id: str = "",
    ) -> LineupResult:
        """Sec.8.1 (baseball) / Sec.9.1 (softball) standard substitution:
        close the outgoing player's appearance, open the incoming player's,
        transfer active offensive occupancy. This is for a FRESH substitute
        entering for the first time -- an operator explicitly choosing
        "re-entry" for a player who has appeared before calls reenter()
        instead (Sec.13.3: the operator picks the transition type, the
        engine does not infer it)."""
        side_state = cls._side(state, side)
        slot_state = cls._slot(side_state, slot)
        outgoing_id = slot_state["active_player_id"]
        messages: list[LineupMessage] = []
        if cls._has_ever_appeared(slot_state, incoming_player_id):
            messages.append(
                LineupMessage(
                    "SOFT_WARNING",
                    "SUBSTITUTE_ALREADY_APPEARED",
                    f"{incoming_player_id} has already appeared in slot {slot} this game -- "
                    "use reenter() if this is a legal re-entry, or record_reality() to override.",
                )
            )
        current = cls._current_appearance(slot_state, outgoing_id)
        if current is not None:
            current["exited_event_id"] = event_id or "pending"
        slot_state["entry_history"].append(
            {
                "player_id": incoming_player_id,
                "slot": slot,
                "entered_event_id": event_id or "pending",
                "exited_event_id": "",
                "entry_type": "SUBSTITUTION",
                "is_starter": False,
            }
        )
        slot_state["active_player_id"] = incoming_player_id
        event = cls._append_event(
            state,
            "SUBSTITUTION",
            {"side": side, "slot": slot, "outgoing_player_id": outgoing_id, "incoming_player_id": incoming_player_id},
        )
        return LineupResult("OK", state, {"event": event, "messages": messages})

    @classmethod
    def reenter(
        cls,
        state: dict[str, Any],
        side: str,
        slot: int,
        player_id: str,
        *,
        sport: str = "baseball",
        event_id: str = "",
    ) -> LineupResult:
        """Sec.8.1: 'A starting player may be withdrawn and re-enter once in
        the same batting position. A substitute who is withdrawn does not
        receive an independent re-entry right.' Sec.9.1 (softball): ANY
        player (starter or substitute) may re-enter once, same batting
        position. Always records reality (Sec.1: 'the rules validator is
        advisory... it should not block the scorer from recording an
        action the game officials allowed') -- ineligibility surfaces as
        SOFT_WARNING/NEEDS_RULING, never a blocked commit."""
        side_state = cls._side(state, side)
        slot_state = cls._slot(side_state, slot)
        outgoing_id = slot_state["active_player_id"]
        messages: list[LineupMessage] = []

        other_slots = cls._other_slots_with_history(side_state, player_id, slot)
        if other_slots and not cls._has_ever_appeared(slot_state, player_id):
            # SB-02: re-entry must return to the SAME batting position --
            # this player's only history is in a different slot.
            messages.append(
                LineupMessage(
                    "SOFT_WARNING",
                    "REENTRY_WRONG_SLOT",
                    f"{player_id} previously appeared in slot(s) {other_slots}, not slot {slot} -- "
                    "re-entry must return to the same batting position. Recording as requested; "
                    "flag for umpire ruling if this needs enforcement.",
                )
            )

        is_starter = any(
            a.get("player_id") == player_id and a.get("is_starter") for a in slot_state["entry_history"]
        )
        prior_reentries = cls._reentry_count(slot_state, player_id)

        if sport == "baseball":
            if not is_starter:
                # Sec.8.1 BB-03: substitute re-entry attempt.
                messages.append(
                    LineupMessage(
                        "SOFT_WARNING",
                        "SUBSTITUTE_REENTRY_NOT_ORDINARILY_ALLOWED",
                        f"{player_id} is not the original starter in slot {slot} -- a baseball "
                        "substitute ordinarily has no re-entry right. Recording as requested; "
                        "flag for umpire ruling if this needs enforcement.",
                    )
                )
            elif prior_reentries >= 1:
                # BB-02: starter's second re-entry attempt.
                messages.append(
                    LineupMessage(
                        "SOFT_WARNING",
                        "STARTER_SECOND_REENTRY",
                        f"{player_id} has already used their one re-entry in slot {slot}. "
                        "Recording as requested (NEEDS_RULING if the umpire has not addressed it).",
                    )
                )
        else:  # softball: ANY player, one re-entry maximum, regardless of starter status
            if prior_reentries >= 1:
                messages.append(
                    LineupMessage(
                        "SOFT_WARNING",
                        "PLAYER_SECOND_REENTRY",
                        f"{player_id} has already used their one re-entry in slot {slot}.",
                    )
                )

        current = cls._current_appearance(slot_state, outgoing_id)
        if current is not None:
            current["exited_event_id"] = event_id or "pending"
        slot_state["entry_history"].append(
            {
                "player_id": player_id,
                "slot": slot,
                "entered_event_id": event_id or "pending",
                "exited_event_id": "",
                "entry_type": "REENTRY",
                "is_starter": is_starter,
            }
        )
        slot_state["active_player_id"] = player_id
        event = cls._append_event(
            state,
            "REENTRY",
            {"side": side, "slot": slot, "outgoing_player_id": outgoing_id, "player_id": player_id},
        )
        return LineupResult("OK", state, {"event": event, "messages": messages})

    @classmethod
    def position_change(
        cls, state: dict[str, Any], side: str, position: str, player_id: str, *, event_id: str = ""
    ) -> LineupResult:
        """Sec.8.1: 'Defensive position change only -- update defense map;
        do not alter batting slot occupancy.'"""
        if position not in DEFENSIVE_POSITIONS:
            raise ValueError(f"unknown defensive position: {position}")
        side_state = cls._side(state, side)
        previous = side_state["defense"].get(position, "")
        side_state["defense"][position] = player_id
        event = cls._append_event(
            state,
            "POSITION_CHANGE",
            {"side": side, "position": position, "previous_player_id": previous, "player_id": player_id},
        )
        return LineupResult("OK", state, {"event": event})

    # --- baseball DH modes (Sec.8.2) --------------------------------------

    @classmethod
    def replace_on_defense_only(
        cls, state: dict[str, Any], side: str, position: str, incoming_player_id: str, *, event_id: str = ""
    ) -> LineupResult:
        """BB-04: 'Player/DH replaced only on defense -> Player remains DH;
        defensive assignment changes.' A defensive position change alone
        never terminates the Player/DH role (Sec.8.2: 'A defensive position
        change for the player/DH does not by itself terminate the DH
        role')."""
        return cls.position_change(state, side, position, incoming_player_id, event_id=event_id)

    @classmethod
    def terminate_player_dh_role(
        cls, state: dict[str, Any], side: str, player_id: str, *, reason: str, event_id: str = ""
    ) -> LineupResult:
        """BB-05: 'Player/DH pinch-hit or pinch-run for -> DH role
        terminates; transition is persisted.' Sec.8.2: 'When the player/DH
        is pinch-hit or pinch-run for, mark the DH role ended for that game
        and apply the resulting lineup state.'"""
        side_state = cls._side(state, side)
        if side_state["roles"].get(player_id) == ROLE_PLAYER_DH:
            side_state["roles"][player_id] = ROLE_NONE
        event = cls._append_event(
            state, "DH_TRANSITION", {"side": side, "player_id": player_id, "transition": "PLAYER_DH_ENDED", "reason": reason}
        )
        return LineupResult("OK", state, {"event": event})

    @classmethod
    def assign_role(cls, state: dict[str, Any], side: str, player_id: str, role: str) -> None:
        side_state = cls._side(state, side)
        side_state["roles"][player_id] = role

    # --- baseball defensive meetings (Sec.8.4, BB-06) ---------------------

    @classmethod
    def record_defensive_meeting(cls, state: dict[str, Any], side: str, *, event_id: str = "") -> LineupResult:
        """Sec.8.4: PLAYER_DEFENSIVE_MEETING is modeled as a DISTINCT event
        type from CHARGED_CONFERENCE -- 'Do not automatically convert one to
        the other based solely on duration.' BB-06: a second meeting in the
        same half-inning is a count/warning, never auto-charged as a coach
        conference."""
        side_state = cls._side(state, side)
        side_state["defensive_meetings_this_half"] += 1
        count = side_state["defensive_meetings_this_half"]
        messages: list[LineupMessage] = []
        if count >= 2:
            messages.append(
                LineupMessage(
                    "SOFT_WARNING",
                    "SECOND_DEFENSIVE_MEETING",
                    f"This is the {count} recorded player-to-player defensive meeting this half-inning.",
                )
            )
        event = cls._append_event(
            state, "PLAYER_DEFENSIVE_MEETING", {"side": side, "ordinal_in_half_inning": count}
        )
        return LineupResult("OK", state, {"event": event, "messages": messages})

    @classmethod
    def record_charged_conference(cls, state: dict[str, Any], side: str, *, event_id: str = "") -> LineupResult:
        side_state = cls._side(state, side)
        side_state["charged_conferences"] += 1
        event = cls._append_event(
            state, "CHARGED_CONFERENCE", {"side": side, "count": side_state["charged_conferences"]}
        )
        return LineupResult("OK", state, {"event": event})

    @classmethod
    def reset_half_inning_meetings(cls, state: dict[str, Any]) -> None:
        """Called by inning_service at each half-inning close -- the
        defensive-meeting count is scoped to one half-inning (Sec.8.4)."""
        for side in TEAMS:
            cls._side(state, side)["defensive_meetings_this_half"] = 0

    # --- softball DP/FLEX (Sec.9.2/9.3) -----------------------------------

    @classmethod
    def start_dp_flex(
        cls, state: dict[str, Any], side: str, dp_player_id: str, dp_slot: int, flex_player_id: str
    ) -> LineupResult:
        """Sec.9.2: 'Team starts with DP/FLEX -> Lineup card contains 10
        players; DP occupies one of batting slots 1-9; FLEX occupies
        position 10 and is defense-only by default.' Sets the DP as the
        starting occupant of dp_slot (the pregame lineup card names the DP
        directly in that batting position -- this call is what establishes
        the DP/FLEX relationship on top of whatever start_lineup already
        seeded there)."""
        side_state = cls._side(state, side)
        side_state["dp_flex"] = {
            "dp_player_id": dp_player_id,
            "dp_slot": dp_slot,
            "flex_player_id": flex_player_id,
            "offense_occupant": "DP",  # DP bats in dp_slot; FLEX is defense-only
            "active_count": 10,
        }
        slot_state = cls._slot(side_state, dp_slot)
        slot_state["starter_player_id"] = dp_player_id
        slot_state["active_player_id"] = dp_player_id
        if not cls._has_ever_appeared(slot_state, dp_player_id):
            slot_state["entry_history"].append(
                {
                    "player_id": dp_player_id,
                    "slot": dp_slot,
                    "entered_event_id": "",
                    "exited_event_id": "",
                    "entry_type": "STARTER",
                    "is_starter": True,
                }
            )
        side_state["roles"][dp_player_id] = ROLE_SOFTBALL_DP
        side_state["roles"][flex_player_id] = ROLE_SOFTBALL_FLEX
        event = cls._append_event(
            state, "DP_FLEX_TRANSITION",
            {"side": side, "transition": "STARTED", "dp_player_id": dp_player_id, "flex_player_id": flex_player_id},
        )
        return LineupResult("OK", state, {"event": event})

    @classmethod
    def _require_dp_flex(cls, side_state: Mapping[str, Any]) -> dict[str, Any]:
        dp_flex = side_state.get("dp_flex")
        if not isinstance(dp_flex, dict):
            raise ValueError("DP/FLEX is not active for this side")
        return dp_flex

    @classmethod
    def dp_plays_defense_for_flex(cls, state: dict[str, Any], side: str, *, event_id: str = "") -> LineupResult:
        """SB-03 / Sec.9.3 row 1: FLEX leaves; DP remains offense+defense;
        active count 9. (DP_FLEX_TRANSITION: FLEX_EXIT_DEFENSE)"""
        side_state = cls._side(state, side)
        dp_flex = cls._require_dp_flex(side_state)
        if dp_flex["offense_occupant"] != "DP":
            return LineupResult(
                "HARD_ERROR", state,
                {"message": "FLEX is currently the offensive occupant -- DP cannot also take defense for FLEX from this state."},
            )
        dp_flex["active_count"] = 9
        event = cls._append_event(
            state, "DP_FLEX_TRANSITION",
            {"side": side, "transition": "FLEX_EXIT_DEFENSE", "dp_player_id": dp_flex["dp_player_id"]},
        )
        return LineupResult("OK", state, {"event": event})

    @classmethod
    def flex_bats_for_dp(cls, state: dict[str, Any], side: str, *, event_id: str = "") -> LineupResult:
        """SB-04 / Sec.9.3 row 2: DP leaves; FLEX remains defense+offense in
        the DP's batting slot; active count 9. (FLEX_FOR_DP_OFFENSE). This is
        the HARD invariant's enforcement point: FLEX cannot become the
        offensive occupant while DP still is (Sec.9.2: 'DP and FLEX on
        offense: Never simultaneously -- HARD invariant')."""
        side_state = cls._side(state, side)
        dp_flex = cls._require_dp_flex(side_state)
        if dp_flex["offense_occupant"] == "FLEX":
            return LineupResult(
                "HARD_ERROR", state,
                {"message": "FLEX is already the offensive occupant -- DP and FLEX can never both be active on offense."},
            )
        dp_flex["offense_occupant"] = "FLEX"
        dp_flex["active_count"] = 9
        slot = dp_flex["dp_slot"]
        slot_state = cls._slot(side_state, slot)
        outgoing = slot_state["active_player_id"]
        current = cls._current_appearance(slot_state, outgoing)
        if current is not None:
            current["exited_event_id"] = event_id or "pending"
        slot_state["entry_history"].append(
            {
                "player_id": dp_flex["flex_player_id"],
                "slot": slot,
                "entered_event_id": event_id or "pending",
                "exited_event_id": "",
                "entry_type": "DP_FLEX_TRANSITION",
                "is_starter": False,
            }
        )
        slot_state["active_player_id"] = dp_flex["flex_player_id"]
        event = cls._append_event(
            state, "DP_FLEX_TRANSITION",
            {"side": side, "transition": "FLEX_FOR_DP_OFFENSE", "flex_player_id": dp_flex["flex_player_id"], "slot": slot},
        )
        return LineupResult("OK", state, {"event": event})

    @classmethod
    def dp_reenters(cls, state: dict[str, Any], side: str, *, flex_resulting_state: str, event_id: str = "") -> LineupResult:
        """SB-05 / Sec.9.2 'DP re-enters: must return to original batting-
        order position; FLEX may return to position 10 or leave, depending
        on the transition.' Sec.9.3: 'Wizard must ask which legal
        configuration is being reported' -- flex_resulting_state is that
        explicit operator choice: "RETURNS_TO_TEN" or "LEAVES"."""
        if flex_resulting_state not in {"RETURNS_TO_TEN", "LEAVES"}:
            raise ValueError("flex_resulting_state must be RETURNS_TO_TEN or LEAVES")
        side_state = cls._side(state, side)
        dp_flex = cls._require_dp_flex(side_state)
        if dp_flex["offense_occupant"] != "FLEX":
            return LineupResult(
                "HARD_ERROR", state,
                {"message": "DP is already the offensive occupant -- nothing to re-enter."},
            )
        slot = dp_flex["dp_slot"]
        slot_state = cls._slot(side_state, slot)
        outgoing = slot_state["active_player_id"]
        current = cls._current_appearance(slot_state, outgoing)
        if current is not None:
            current["exited_event_id"] = event_id or "pending"
        slot_state["entry_history"].append(
            {
                "player_id": dp_flex["dp_player_id"],
                "slot": slot,
                "entered_event_id": event_id or "pending",
                "exited_event_id": "",
                "entry_type": "DP_FLEX_TRANSITION",
                "is_starter": False,
            }
        )
        slot_state["active_player_id"] = dp_flex["dp_player_id"]
        dp_flex["offense_occupant"] = "DP"
        dp_flex["active_count"] = 10 if flex_resulting_state == "RETURNS_TO_TEN" else 9
        if flex_resulting_state == "LEAVES":
            side_state["roles"].pop(dp_flex["flex_player_id"], None)
        event = cls._append_event(
            state, "DP_FLEX_TRANSITION",
            {"side": side, "transition": "DP_REENTERED", "flex_resulting_state": flex_resulting_state},
        )
        return LineupResult("OK", state, {"event": event})

    @classmethod
    def substitute_for_dp(cls, state: dict[str, Any], side: str, incoming_player_id: str, *, event_id: str = "") -> LineupResult:
        """Sec.9.3: 'Substitute enters for DP -> Sub assumes DP batting
        slot/role; FLEX status depends on current state. Track substitute
        re-entry separately.' Reuses the shared substitute() state machine
        on the DP's own slot."""
        side_state = cls._side(state, side)
        dp_flex = cls._require_dp_flex(side_state)
        result = cls.substitute(state, side, dp_flex["dp_slot"], incoming_player_id, sport="softball", event_id=event_id)
        if result.ok:
            dp_flex["dp_player_id"] = incoming_player_id
            side_state["roles"][incoming_player_id] = ROLE_SOFTBALL_DP
        return result

    @classmethod
    def substitute_for_flex(cls, state: dict[str, Any], side: str, incoming_player_id: str, *, event_id: str = "") -> LineupResult:
        """Sec.9.3: 'Substitute enters for FLEX -> New FLEX occupies #10
        defense role; preserve DP offensive slot.'"""
        side_state = cls._side(state, side)
        dp_flex = cls._require_dp_flex(side_state)
        outgoing = dp_flex["flex_player_id"]
        side_state["roles"].pop(outgoing, None)
        dp_flex["flex_player_id"] = incoming_player_id
        side_state["roles"][incoming_player_id] = ROLE_SOFTBALL_FLEX
        event = cls._append_event(
            state, "DP_FLEX_TRANSITION",
            {"side": side, "transition": "FLEX_SUBSTITUTED", "outgoing_player_id": outgoing, "incoming_player_id": incoming_player_id},
        )
        return LineupResult("OK", state, {"event": event})

    # --- courtesy runners (Sec.10) -----------------------------------------

    @classmethod
    def enter_courtesy_runner(
        cls,
        state: dict[str, Any],
        side: str,
        runner_player_id: str,
        for_player_id: str,
        for_role_at_time: str,
        *,
        eligible: bool = True,
        event_id: str = "",
    ) -> LineupResult:
        """Sec.10: 'Courtesy runner must be modeled as a special temporary
        role, not as an ordinary substitution -- prevents the engine from
        accidentally consuming re-entry rights or changing the batting-slot
        occupant... do not close the pitcher/catcher lineup appearance
        merely because the CR enters.' CR-01: lineup occupant unchanged;
        CR appearance created. CR-02: an ineligible CR is a warning, never
        an automatic block (Sec.10: 'do not auto-remove a runner from a
        live game')."""
        if for_role_at_time not in {"PITCHER", "CATCHER"}:
            raise ValueError("for_role_at_time must be PITCHER or CATCHER")
        side_state = cls._side(state, side)
        appearance = {
            "runner_player_id": runner_player_id,
            "for_player_id": for_player_id,
            "for_role_at_time": for_role_at_time,
            "entered_event_id": event_id or "pending",
            "ended_event_id": "",
            "eligibility_snapshot": {"was_unused_substitute": eligible, "restrictions": [] if eligible else ["INELIGIBLE_AT_ENTRY"]},
            "policy_version": 1,
        }
        side_state["courtesy_runners"].append(appearance)
        side_state["roles"][runner_player_id] = ROLE_COURTESY_RUNNER
        messages: list[LineupMessage] = []
        if not eligible:
            messages.append(
                LineupMessage(
                    "SOFT_WARNING",
                    "COURTESY_RUNNER_POSSIBLY_INELIGIBLE",
                    f"{runner_player_id} may not meet the courtesy-runner eligibility profile -- "
                    "recorded as entered; record the umpire's ruling if this is contested.",
                )
            )
        event = cls._append_event(
            state, "COURTESY_RUNNER_ENTER",
            {"side": side, "runner_player_id": runner_player_id, "for_player_id": for_player_id, "for_role_at_time": for_role_at_time},
        )
        return LineupResult("OK", state, {"event": event, "messages": messages})

    @classmethod
    def return_courtesy_runner(cls, state: dict[str, Any], side: str, runner_player_id: str, *, event_id: str = "") -> LineupResult:
        side_state = cls._side(state, side)
        for appearance in reversed(side_state["courtesy_runners"]):
            if appearance["runner_player_id"] == runner_player_id and not appearance["ended_event_id"]:
                appearance["ended_event_id"] = event_id or "pending"
                break
        if side_state["roles"].get(runner_player_id) == ROLE_COURTESY_RUNNER:
            side_state["roles"][runner_player_id] = ROLE_NONE
        event = cls._append_event(state, "COURTESY_RUNNER_RETURN", {"side": side, "runner_player_id": runner_player_id})
        return LineupResult("OK", state, {"event": event})

    # --- batting out of order (Sec.15.1) -----------------------------------

    @classmethod
    def record_batter(
        cls, state: dict[str, Any], side: str, expected_slot: int, actual_batter_id: str, *, event_id: str = ""
    ) -> LineupResult:
        """Sec.15.1: 'Detection is not enforcement. If CSRN sees a batter
        different from the expected slot, record the actual batter and
        raise a warning. Do not create an out or advance the lineup cursor
        according to an assumed penalty until the umpire rules on a proper
        appeal.' BOO-01: warning remains; engine does not auto-create an
        out."""
        side_state = cls._side(state, side)
        expected_player_id = cls._slot(side_state, expected_slot)["active_player_id"]
        messages: list[LineupMessage] = []
        alert = None
        if expected_player_id and actual_batter_id and expected_player_id != actual_batter_id:
            alert = {
                "expected_slot": expected_slot,
                "expected_player_id": expected_player_id,
                "actual_batter_id": actual_batter_id,
                "detected_at_event_id": event_id or "pending",
                "status": "OPEN",
            }
            side_state["batting_order_alerts"].append(alert)
            messages.append(
                LineupMessage(
                    "SOFT_WARNING",
                    "BATTING_ORDER_MISMATCH",
                    f"Slot {expected_slot} expected {expected_player_id}, but {actual_batter_id} batted. "
                    "Recorded as-is; no out or lineup-cursor change until an appeal is ruled on.",
                )
            )
        return LineupResult("OK", state, {"alert": alert, "messages": messages})

    @classmethod
    def apply_appeal_ruling(
        cls,
        state: dict[str, Any],
        side: str,
        alert_index: int,
        *,
        appeal_type: str,
        ruling_result: str,
        next_batter_slot: int,
        event_id: str = "",
    ) -> LineupResult:
        """BOO-02: 'Wrong batter appealed and umpire rules -> Apply
        APPEAL_RULING consequences and next-slot cursor explicitly.'
        outsAwarded/runnerAdjustments are the diamond engine's job (spec's
        UmpireRulingPayload, applied via at_bat_rules_service.record_
        ruling) -- this call only resolves the lineup-side bookkeeping: the
        alert's status and which slot bats next."""
        side_state = cls._side(state, side)
        alerts = side_state["batting_order_alerts"]
        if not (0 <= alert_index < len(alerts)):
            return LineupResult("ALERT_NOT_FOUND", state, {})
        alerts[alert_index]["status"] = "APPEAL_RULING_RECORDED"
        event = cls._append_event(
            state, "APPEAL_RULING",
            {
                "side": side, "appeal_type": appeal_type, "ruling_result": ruling_result,
                "next_batter_slot": next_batter_slot,
            },
        )
        return LineupResult("OK", state, {"event": event, "next_batter_slot": next_batter_slot})

    @classmethod
    def dismiss_alert_no_appeal(cls, state: dict[str, Any], side: str, alert_index: int) -> LineupResult:
        side_state = cls._side(state, side)
        alerts = side_state["batting_order_alerts"]
        if not (0 <= alert_index < len(alerts)):
            return LineupResult("ALERT_NOT_FOUND", state, {})
        alerts[alert_index]["status"] = "NO_APPEAL"
        return LineupResult("OK", state, {})
