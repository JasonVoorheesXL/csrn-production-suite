from __future__ import annotations

import copy
import re
import time
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Callable, Mapping


from canonical_state_service import CanonicalStateFoundation
from eligibility_service import EligibilityService
from live_command_service import (
    assign_next_revision,
    attach_metadata,
    command_result_state,
    command_id_from,
    command_metadata,
    current_revision,
    duplicate_result,
    remember_command,
)


@dataclass(frozen=True)
class EventResult:
    code: str
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class EventService:
    """Live-event and correction boundary independent of Flask."""

    VALID_TEAMS = {"home", "visitor"}
    VALID_EVENTS = {
        "TD",
        "FG",
        "XP",
        "2PT",
        "TURNOVER",
        "FIRST_DOWN",
        "PENALTY",
        "EJECTION",
        "PLAY",
        "KICKOFF",
    }
    VALID_AUTHORITIES = {"broadcaster", "statistician"}
    VALID_DOWNS = {"1st", "2nd", "3rd", "4th", "Off"}

    def __init__(
        self,
        *,
        load_state: Callable[[], Mapping[str, Any]],
        save_state: Callable[[Mapping[str, Any]], Any],
        public_state: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        push_history: Callable[[dict[str, Any]], None],
        update_linked_status: Callable[[str, str, dict[str, Any] | None], None],
        automation_player: Callable[[str, str], tuple[Any, Any]],
        manual_player: Callable[[Any, str], Any],
        player_display: Callable[[Any], str],
        show_player_graphic: Callable[..., None],
        apply_penalty: Callable[[dict[str, Any], str, str, int, str], Mapping[str, Any]],
        spot_to_coord: Callable[[Any], int],
        team_direction: Callable[[dict[str, Any], str], int],
        normalize_state: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        default_player_graphic: Callable[[], Mapping[str, Any]],
        resolve_player: Callable[[dict[str, Any], str, Any], Mapping[str, Any]] | None = None,
        on_event: Callable[[Mapping[str, Any]], Any] | None = None,
        transaction_lock: Any | None = None,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._load_state = load_state
        self._save_state = save_state
        self._public_state = public_state
        self._push_history = push_history
        self._update_linked_status = update_linked_status
        self._automation_player = automation_player
        self._manual_player = manual_player
        self._player_display = player_display
        self._show_player_graphic = show_player_graphic
        self._apply_penalty = apply_penalty
        self._spot_to_coord = spot_to_coord
        self._team_direction = team_direction
        self._normalize_state = normalize_state
        self._default_player_graphic = default_player_graphic
        self._resolve_player = resolve_player
        self._on_event = on_event
        self._transaction_lock = transaction_lock
        self._now = now

    def _lock(self):
        return self._transaction_lock if self._transaction_lock is not None else nullcontext()

    @staticmethod
    def _player_matches_submitted_number(player: Any, submitted: Any) -> bool:
        if not player or not isinstance(submitted, Mapping):
            return True
        number = str(submitted.get("number", "") or "").strip()
        if not number:
            return True
        return str(player.get("number", "") or "").strip() == number

    @staticmethod
    def _coord_to_spot(coord: Any) -> str:
        try:
            value = max(0, min(100, int(coord)))
        except (TypeError, ValueError):
            value = 50
        if value == 0:
            return "LEFT GOAL"
        if value == 100:
            return "RIGHT GOAL"
        if value == 50:
            return "50"
        return f"LEFT {value}" if value < 50 else f"RIGHT {100 - value}"

    @staticmethod
    def source_allowed(state: Mapping[str, Any], source: Any) -> bool:
        authority = str(
            state.get("game_data_authority", "broadcaster") or "broadcaster"
        ).lower()
        return str(source or "broadcaster").lower() == authority

    @staticmethod
    def locked_payload(state: Mapping[str, Any]) -> dict[str, Any]:
        authority = str(
            state.get("game_data_authority", "broadcaster") or "broadcaster"
        )
        return {
            "error": "CONTROL_SOURCE_LOCKED",
            "authority": authority,
            "message": f"Game data is controlled by the {authority} console.",
        }

    def set_control_source(
        self,
        authority: Any,
        payload: Mapping[str, Any] | None = None,
    ) -> EventResult:
        incoming = dict(payload or {})
        authority_text = str(authority or "").lower()
        if authority_text not in self.VALID_AUTHORITIES:
            return EventResult("INVALID_CONTROL_SOURCE", {})
        with self._lock():
            state = copy.deepcopy(dict(self._load_state()))
            command_id = command_id_from(incoming)
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return EventResult("OK", duplicate)
            self._push_history(state)
            state["game_data_authority"] = authority_text
            state["statistician_enabled"] = authority_text == "statistician"
            state["control_source_updated_at"] = int(self._now())
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming,
                action="set_control_source",
                state_revision=revision,
            )
            result_data = attach_metadata(
                {"state": copy.deepcopy(dict(self._public_state(state)))},
                metadata,
            )
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
        return EventResult("OK", result_data)

    def trigger(self, data: Mapping[str, Any] | None) -> EventResult:
        incoming = dict(data or {})
        team = str(incoming.get("team", "")).lower()
        event_code = str(incoming.get("event", "")).upper()
        if team not in self.VALID_TEAMS or event_code not in self.VALID_EVENTS:
            return EventResult("INVALID_EVENT", {})

        with self._lock():
            state = copy.deepcopy(dict(self._load_state()))
            if not state.get("broadcast_id"):
                return EventResult("NO_ACTIVE_BROADCAST", {})
            command_id = command_id_from(incoming)
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return EventResult("OK", duplicate)
            phase = str(state.get("special_game_phase", "") or "").lower()
            resolving_pending_try = phase == "pending_try"

            # Try events are legal only while a try is actually pending.
            if event_code in {"XP", "2PT"} and phase != "pending_try":
                return EventResult(
                    "TRY_ALREADY_RESOLVED",
                    {
                        "phase": phase,
                        "team": str(state.get("possession", "") or ""),
                    },
                )

            # A pending try belongs only to the team that just scored.
            # enter_pending_try() preserves that scoring team as possession.
            if event_code in {"XP", "2PT"} and phase == "pending_try":
                scoring_team = str(state.get("possession", "") or "").lower()
                if scoring_team in self.VALID_TEAMS and team != scoring_team:
                    return EventResult(
                        "INVALID_TRY_TEAM",
                        {
                            "phase": phase,
                            "team": team,
                            "scoring_team": scoring_team,
                        },
                    )

            # KICKOFF is the minimal canonical resolution event shared by the
            # broadcaster quick control and detailed special-teams workflows.
            if event_code == "KICKOFF" and phase not in {"kickoff", "free_kick"}:
                return EventResult("KICKOFF_NOT_PENDING", {"phase": phase})

            if phase == "pending_try" and event_code not in {"XP", "2PT", "PENALTY", "EJECTION"}:
                return EventResult(
                    "SPECIAL_PHASE_REQUIRES_TRY",
                    {
                        "phase": phase,
                        "team": str(state.get("possession", "") or ""),
                    },
                )
            if (
                phase in {"kickoff", "free_kick"}
                and event_code not in {"KICKOFF", "PENALTY", "EJECTION"}
            ):
                return EventResult(
                    "SPECIAL_PHASE_REQUIRES_KICK",
                    {
                        "phase": phase,
                        "kicking_team": str(state.get("kicking_team", "") or ""),
                        "receiving_team": str(state.get("receiving_team", "") or ""),
                    },
                )
            source = str(
                incoming.get("source", "broadcaster") or "broadcaster"
            ).lower()
            if not self.source_allowed(state, source):
                return EventResult(
                    "CONTROL_SOURCE_LOCKED",
                    self.locked_payload(state),
                )
            roles = CanonicalStateFoundation.team_roles(state)
            requested_play_type = str(incoming.get("play_type", "") or "").lower()
            if event_code == "PLAY" and requested_play_type in {"run", "pass"} and team != roles.offense:
                return EventResult(
                    "TEAM_ROLE_MISMATCH",
                    {
                        "message": "Offensive plays must be entered for the team in possession.",
                        "submitted_team": team,
                        "offense": roles.offense,
                        "defense": roles.defense,
                    },
                )
            if event_code == "TURNOVER":
                current_possession = str(state.get("possession", "home") or "home").lower()
                if team == current_possession:
                    return EventResult(
                        "INVALID_TURNOVER_TEAM",
                        {"message": "Turnover recovery team must be the non-possessing team."},
                    )
            if event_code == "EJECTION" and str(incoming.get("ejection_person_type", "Player") or "Player").strip().casefold() == "player":
                token = str(incoming.get("ejection_person_name", "") or "").strip()
                incoming.setdefault("ejection_player_number", token.lstrip("#") if token.lstrip("#").isdigit() else "")
                if self._resolve_player is not None and incoming.get("ejection_player_number"):
                    resolved = dict(self._resolve_player(state, team, incoming.get("ejection_player_number")) or {})
                    if resolved.get("resolved"):
                        incoming["ejection_player_id"] = str(resolved.get("player_id", "") or "")
                        incoming["ejection_roster_id"] = str(resolved.get("roster_id", "") or "")
                        incoming["ejection_player_name"] = str(resolved.get("name", "") or token)

            ledger = state.pop("recent_commands", None)
            self._push_history(state)
            if isinstance(state.get("history"), list):
                state["history"] = state["history"][-50:]
            if ledger is not None:
                state["recent_commands"] = ledger
            score_key = "home_score" if team == "home" else "visitor_score"
            before = CanonicalStateFoundation.snapshot(state)
            before.update({
                "player_graphic": copy.deepcopy(state.get("player_graphic") or {}),
                "player_highlight": copy.deepcopy(state.get("player_highlight") or {}),
                "sponsor_spotlight": copy.deepcopy(state.get("sponsor_spotlight") or {}),
                "graphics_queue": copy.deepcopy(state.get("graphics_queue") or []),
            })
            return_td = bool(incoming.get("return_td")) and str(
                incoming.get("turnover_type", "")
            ) != "downs"
            conversion_outcome = str(
                incoming.get("conversion_outcome", "good") or "good"
            ).lower()
            kick_outcome = str(incoming.get("kick_outcome", "made") or "made").lower()
            if event_code == "XP" and conversion_outcome not in {"good", "no_good", "blocked", "retry"}:
                return EventResult("INVALID_CONVERSION_OUTCOME", {})
            if event_code == "2PT" and conversion_outcome not in {"good", "failed", "blocked", "retry"}:
                return EventResult("INVALID_CONVERSION_OUTCOME", {})
            if event_code == "FG" and kick_outcome not in {"made", "no_good", "missed", "blocked"}:
                return EventResult("INVALID_KICK_OUTCOME", {})
            conversion_good = conversion_outcome == "good"
            delta = (
                6
                if event_code == "TD" or (event_code == "TURNOVER" and return_td)
                else 3
                if event_code == "FG" and kick_outcome == "made"
                else 2
                if event_code == "2PT" and conversion_good
                else 1
                if event_code == "XP" and conversion_good
                else 0
            )
            if delta:
                state[score_key] = max(
                    0,
                    int(state.get(score_key, 0)) + delta,
                )

            if event_code == "KICKOFF":
                kicking = str(state.get("kicking_team", "") or team).lower()
                if kicking not in self.VALID_TEAMS:
                    kicking = team
                receiving = str(
                    state.get("receiving_team", "")
                    or CanonicalStateFoundation.opposite(kicking)
                ).lower()
                if receiving not in self.VALID_TEAMS:
                    receiving = CanonicalStateFoundation.opposite(kicking)
                if team != kicking:
                    return EventResult(
                        "INVALID_KICKOFF_TEAM",
                        {
                            "kicking_team": kicking,
                            "submitted_team": team,
                        },
                    )

                touchback = bool(incoming.get("kick_touchback") or incoming.get("touchback"))
                requested_spot = str(
                    incoming.get("kick_result_spot")
                    or incoming.get("result_spot")
                    or incoming.get("ball_spot")
                    or ""
                ).strip()
                if touchback:
                    result_spot = CanonicalStateFoundation._team_own_yard_spot(
                        state,
                        receiving,
                        20,
                    )
                elif requested_spot:
                    result_spot = self._coord_to_spot(self._spot_to_coord(requested_spot))
                else:
                    return EventResult(
                        "KICKOFF_RESULT_SPOT_REQUIRED",
                        {
                            "kicking_team": kicking,
                            "receiving_team": receiving,
                        },
                    )

                state["possession"] = receiving
                state["down"] = "1st"
                state["distance"] = "10"
                state["ball_spot"] = result_spot
                state["clock_running"] = False
                state["clock_started_at"] = 0
                incoming["kickoff_receiving_team"] = receiving
                incoming["kickoff_result_spot"] = result_spot
                incoming["kickoff_touchback"] = touchback
                CanonicalStateFoundation.clear_special_phase(state)

            if event_code == "TURNOVER":
                state["possession"] = team
                state["down"] = "1st"
                state["distance"] = "10"
                turnover_spot_value = (
                    incoming.get("turnover_spot")
                    or incoming.get("recovery_spot")
                    or incoming.get("interception_spot")
                    or state.get("ball_spot")
                    or "50"
                )
                return_end_value = incoming.get("return_end_spot")
                final_spot = return_end_value if return_end_value not in (None, "") else turnover_spot_value
                if return_td:
                    direction = self._team_direction(state, team)
                    final_spot = "RIGHT GOAL" if direction == 1 else "LEFT GOAL"
                state["ball_spot"] = self._coord_to_spot(self._spot_to_coord(final_spot))
                state["clock_running"] = False
                state["clock_started_at"] = 0
            if event_code == "FIRST_DOWN":
                state["down"] = "1st"
                state["distance"] = "10"

            if event_code == "TD" or (event_code == "TURNOVER" and return_td):
                CanonicalStateFoundation.enter_pending_try(state, team)
            elif event_code in {"XP", "2PT"}:
                if resolving_pending_try and conversion_outcome != "retry":
                    CanonicalStateFoundation.enter_kickoff(state, team)
            elif event_code == "FG":
                if kick_outcome == "made":
                    CanonicalStateFoundation.enter_kickoff(state, team)
                else:
                    receiving = CanonicalStateFoundation.opposite(team)
                    CanonicalStateFoundation.clear_special_phase(state)
                    state["possession"] = receiving
                    state["down"] = "1st"
                    state["distance"] = "10"
                    if bool(incoming.get("kick_touchback")):
                        state["ball_spot"] = CanonicalStateFoundation._team_own_yard_spot(state, receiving, 20)
                    elif str(incoming.get("kick_result_spot", "") or "").strip():
                        state["ball_spot"] = self._coord_to_spot(self._spot_to_coord(incoming.get("kick_result_spot")))
                    state["clock_running"] = False
                    state["clock_started_at"] = 0

            penalty_enforcement: Mapping[str, Any] = {}
            if event_code == "PENALTY":
                category = str(incoming.get("penalty_category", "") or "")
                name = str(incoming.get("penalty_name", "Penalty") or "Penalty")
                outcome = str(
                    incoming.get("penalty_outcome", "accepted") or "accepted"
                ).lower()
                try:
                    yards_value = int(incoming.get("penalty_yards", 0) or 0)
                except (TypeError, ValueError):
                    yards_value = 0
                yards_value = max(0, min(99, yards_value))
                if category not in {"Special Teams", "General"}:
                    category = CanonicalStateFoundation.penalty_unit(state, team)
                incoming["penalty_category"] = category
                state["_pending_penalty_options"] = {
                    "selected_team": team,
                    "requested_unit": category,
                    "enforcement_spot": incoming.get("penalty_enforcement_spot", ""),
                    "half_distance": bool(incoming.get("penalty_half_distance")),
                    "automatic_first_down": bool(incoming.get("penalty_automatic_first_down")),
                    "loss_of_down": bool(incoming.get("penalty_loss_of_down")),
                    "untimed_down": bool(incoming.get("penalty_untimed_down")),
                    "retry_down": bool(incoming.get("penalty_retry_down")),
                }
                try:
                    penalty_enforcement = self._apply_penalty(
                        state, category, name, yards_value, outcome
                    ) or {}
                finally:
                    state.pop("_pending_penalty_options", None)
                category = str(penalty_enforcement.get("unit") or category)
                incoming["penalty_category"] = category

            if state.get("status") != "live":
                state["status"] = "live"
                state["broadcast_phase"] = "live"
                self._update_linked_status(
                    str(state.get("broadcast_id", "")),
                    "live",
                    None,
                )

            team_name = str(
                state.get("home_team")
                if team == "home"
                else state.get("visitor_team")
            )
            roster, player = self._automation_player(
                str(incoming.get("roster_id", "")),
                str(incoming.get("player_id", "")),
            )
            _, passer = self._automation_player(
                str(incoming.get("roster_id", "")),
                str(incoming.get("passer_id", "")),
            )
            if not self._player_matches_submitted_number(
                player,
                incoming.get("manual_player"),
            ):
                player = None
                incoming["player_id"] = ""
            if not self._player_matches_submitted_number(
                passer,
                incoming.get("manual_passer"),
            ):
                passer = None
                incoming["passer_id"] = ""
            player = player or self._manual_player(
                incoming.get("manual_player"),
                team_name,
            )
            passer = passer or self._manual_player(
                incoming.get("manual_passer"),
                team_name,
            )
            if player and not roster:
                roster = {
                    "id": "",
                    "school_id": (
                        state.get("home_school_id")
                        if team == "home"
                        else state.get("visitor_school_id")
                    ),
                    "sport": "Football",
                    "players": [],
                }

            if player:
                if not EligibilityService.is_eligible(
                    state, team,
                    player_id=(player.get("id", "") if isinstance(player, Mapping) else ""),
                    number=(player.get("number", "") if isinstance(player, Mapping) else ""),
                    name=self._player_display(player),
                    resolve_player=self._resolve_player,
                ):
                    return EventResult("PLAYER_INELIGIBLE", {"message": "Selected player is unavailable because of a recorded ejection.", "team": team})
            if passer:
                if not EligibilityService.is_eligible(
                    state, team,
                    player_id=(passer.get("id", "") if isinstance(passer, Mapping) else ""),
                    number=(passer.get("number", "") if isinstance(passer, Mapping) else ""),
                    name=self._player_display(passer),
                    resolve_player=self._resolve_player,
                ):
                    return EventResult("PLAYER_INELIGIBLE", {"message": "Selected passer is unavailable because of a recorded ejection.", "team": team})

            scorer_name = self._player_display(player)
            passer_name = self._player_display(passer)
            yards = (
                str(incoming.get("yards", "")).strip()
                if bool(incoming.get("statistician_mode")) or event_code == "PLAY"
                else ""
            )
            play_type = str(incoming.get("play_type", "")).lower()
            if (
                event_code == "TD"
                and not yards
                and play_type in {"rush", "reception", "return"}
            ):
                start_coord = self._spot_to_coord(state.get("ball_spot") or 50)
                direction = self._team_direction(state, team)
                goal_coord = 100 if direction == 1 else 0
                yards = str(abs(goal_coord - start_coord))
            turnover_type = str(incoming.get("turnover_type", "")).lower()

            label, description = self._describe_event(
                state,
                incoming,
                team,
                team_name,
                event_code,
                play_type,
                turnover_type,
                return_td,
                scorer_name,
                passer_name,
                yards,
            )

            duration = self._clamp_int(
                incoming.get("graphic_duration", 0),
                0,
                30,
                0,
            )
            sack = (
                event_code == "PLAY"
                and play_type == "pass"
                and str(incoming.get("pass_outcome", "")).lower() == "sack"
            )
            turnover_spotlight = event_code == "TURNOVER" and not return_td
            first_down_spotlight = event_code == "FIRST_DOWN"
            if (
                (
                    event_code in {"TD", "2PT"}
                    or return_td
                    or sack
                    or turnover_spotlight
                    or first_down_spotlight
                )
                and player
                and str(player.get("id", "") or "").strip()
            ):
                eyebrow = (
                    "TWO-POINT CONVERSION"
                    if event_code == "2PT"
                    else "DEFENSIVE TOUCHDOWN"
                    if return_td
                    else "TOUCHDOWN"
                    if event_code == "TD"
                    else "SACK"
                    if sack
                    else "TURNOVER"
                    if turnover_spotlight
                    else "FIRST DOWN"
                )
                graphic_type = (
                    "two_point"
                    if event_code == "2PT"
                    else "sack"
                    if sack
                    else "turnover"
                    if turnover_spotlight
                    else "first_down"
                    if first_down_spotlight
                    else "touchdown"
                )
                self._show_player_graphic(
                    state,
                    roster,
                    player,
                    graphic_type,
                    duration,
                    defensive=(
                        (event_code == "TURNOVER" and return_td)
                        or sack
                        or turnover_spotlight
                    ),
                    eyebrow=eyebrow,
                    play_detail=description,
                    sponsor_id=str(incoming.get("sponsor_id", "") or "").strip(),
                )

            play_number = self._clamp_int(
                state.get("next_play_number", 1),
                1,
                1_000_000,
                1,
            )
            state["next_play_number"] = play_number + 1
            timestamp_ms = int(self._now() * 1000)
            event_id = f"EV-{timestamp_ms}"
            broadcast_token = (
                re.sub(
                    r"[^A-Za-z0-9]+",
                    "-",
                    str(state.get("broadcast_id") or "GAME"),
                )
                .strip("-")
                .upper()
                or "GAME"
            )
            play_id = f"{broadcast_token}-{play_number:04d}"
            created_at = int(self._now())

            payload = self._event_payload(
                state=state,
                incoming=incoming,
                team=team,
                team_name=team_name,
                event_code=event_code,
                label=label,
                description=description,
                delta=delta,
                before=before,
                source=source,
                penalty_enforcement=penalty_enforcement,
                play_type=play_type,
                turnover_type=turnover_type,
                player=player,
                passer=passer,
                scorer_name=scorer_name,
                passer_name=passer_name,
                yards=yards,
                return_td=return_td,
                duration=duration,
                event_id=event_id,
                play_id=play_id,
                play_number=play_number,
                created_at=created_at,
            )
            play_record = self._play_record(
                state=state,
                incoming=incoming,
                team=team,
                team_name=team_name,
                event_code=event_code,
                label=label,
                description=description,
                before=before,
                source=source,
                play_type=play_type,
                player=player,
                passer=passer,
                scorer_name=scorer_name,
                passer_name=passer_name,
                yards=yards,
                return_td=return_td,
                event_id=event_id,
                play_id=play_id,
                play_number=play_number,
                created_at=created_at,
            )

            state["last_event"] = payload
            state["events"] = (list(state.get("events") or []) + [payload])[-200:]
            state["plays"] = (list(state.get("plays") or []) + [play_record])[-500:]
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming,
                action=f"event_trigger:{event_code}",
                state_revision=revision,
            )
            result_data = attach_metadata(
                {
                    "state": command_result_state(self._public_state(state)),
                    "trigger": copy.deepcopy(payload),
                    "media_assigned": bool(payload["media_trigger"]["assigned"]),
                    "message": description + (f" (+{delta})" if delta else ""),
                },
                metadata,
            )
            remember_command(
                state,
                command_id,
                metadata=metadata,
                result=result_data,
            )
            self._save_state(state)

        if self._on_event is not None:
            try:
                self._on_event(copy.deepcopy(payload))
            except Exception:
                # Social draft creation can never invalidate the game event.
                pass

        return EventResult("OK", result_data)

    def quick_correction(self, data: Mapping[str, Any] | None) -> EventResult:
        incoming = dict(data or {})
        with self._lock():
            state = copy.deepcopy(dict(self._load_state()))
            command_id = command_id_from(incoming)
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return EventResult("OK", duplicate)
            source = str(
                incoming.get("source", "statistician") or "statistician"
            ).lower()
            if not self.source_allowed(state, source):
                return EventResult(
                    "CONTROL_SOURCE_LOCKED",
                    self.locked_payload(state),
                )
            before = {
                key: copy.deepcopy(state.get(key))
                for key in ("down", "distance", "ball_spot", "possession", "quarter")
            }
            down = str(incoming.get("down", state.get("down", "1st")))
            if down not in self.VALID_DOWNS:
                return EventResult("INVALID_DOWN", {})
            possession = str(
                incoming.get("possession", state.get("possession", "home"))
            )
            if possession not in self.VALID_TEAMS:
                return EventResult("INVALID_POSSESSION", {})
            state["down"] = down
            state["distance"] = (
                "Off"
                if down == "Off"
                else str(
                    self._clamp_int(
                        incoming.get(
                            "distance",
                            self._distance(state.get("distance"), 10),
                        ),
                        1,
                        99,
                        10,
                    )
                )
            )
            state["ball_spot"] = str(
                incoming.get("ball_spot", state.get("ball_spot", ""))
            )[:40]
            state["possession"] = possession
            state["quarter"] = str(
                incoming.get("quarter", state.get("quarter", "1"))
            )[:10]
            after = {key: copy.deepcopy(state.get(key)) for key in before}
            self._append_correction(
                state,
                self._correction_entry(
                    "quick_correction",
                    source,
                    before,
                    after,
                    note=str(incoming.get("note", ""))[:200],
                ),
            )
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming,
                action="quick_correction",
                state_revision=revision,
            )
            result_data = attach_metadata(
                {"state": copy.deepcopy(dict(self._public_state(state)))},
                metadata,
            )
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
        return EventResult("OK", result_data)

    def edit(self, event_id: str, data: Mapping[str, Any] | None) -> EventResult:
        incoming = dict(data or {})
        with self._lock():
            state = copy.deepcopy(dict(self._load_state()))
            command_id = command_id_from(incoming)
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return EventResult("OK", duplicate)
            source = str(
                incoming.get("source", "statistician") or "statistician"
            ).lower()
            if not self.source_allowed(state, source):
                return EventResult(
                    "CONTROL_SOURCE_LOCKED",
                    self.locked_payload(state),
                )
            events = list(state.get("events") or [])
            event = next(
                (row for row in events if row.get("id") == event_id),
                None,
            )
            if not event:
                return EventResult("EVENT_NOT_FOUND", {})
            before = copy.deepcopy(event)
            if "yards" in incoming:
                yards_int = self._clamp_int(
                    incoming.get("yards", 0),
                    -100,
                    100,
                    0,
                )
                yards = str(yards_int)
                event.setdefault("automation", {})["yards"] = yards
                description = str(event.get("description", ""))
                description = re.sub(
                    r"^-?\d+-yard\s+",
                    "",
                    description,
                    flags=re.I,
                )
                if yards not in {"", "0"}:
                    event["description"] = (
                        f"{yards}-yard {description}" if description else f"{yards}-yard play"
                    )
            for field in ("description", "quarter"):
                if field in incoming:
                    event[field] = str(incoming.get(field, ""))[:300]
            if str(event.get("event", "")).upper() == "EJECTION":
                eject = event.setdefault("ejection", {})
                edit_map = {
                    "ejection_person_type": "person_type",
                    "ejection_person_name": "person_name",
                    "ejection_reason": "reason",
                    "ejection_player_id": "player_id",
                    "ejection_roster_id": "roster_id",
                    "ejection_player_number": "player_number",
                    "ejection_player_name": "player_name",
                }
                for incoming_key, event_key in edit_map.items():
                    if incoming_key in incoming:
                        eject[event_key] = str(incoming.get(incoming_key, "") or "")[:200]
            after_state = event.setdefault("after", {})
            for field in ("down", "distance", "ball_spot", "possession"):
                if field in incoming:
                    after_state[field] = str(incoming.get(field, ""))[:40]
            if "down" in incoming:
                state["down"] = after_state["down"]
            if "distance" in incoming:
                state["distance"] = after_state["distance"]
            if "ball_spot" in incoming:
                state["ball_spot"] = after_state["ball_spot"]
            if (
                "possession" in incoming
                and after_state["possession"] in self.VALID_TEAMS
            ):
                state["possession"] = after_state["possession"]
            play = next(
                (
                    row
                    for row in list(state.get("plays") or [])
                    if row.get("event_id") == event_id
                    or row.get("play_id") == event.get("play_id")
                ),
                None,
            )
            if play:
                if "yards" in incoming:
                    play["yards"] = self._clamp_int(
                        incoming.get("yards", 0),
                        -100,
                        100,
                        0,
                    )
                if "start_spot" in incoming:
                    play["ball_spot"] = str(incoming.get("start_spot", ""))[:40]
                if "end_spot" in incoming:
                    play["end_spot"] = str(incoming.get("end_spot", ""))[:40]
                if "description" in incoming or "yards" in incoming:
                    play["result"] = event.get(
                        "description",
                        play.get("result", ""),
                    )
                if "quarter" in incoming:
                    play["quarter"] = event.get(
                        "quarter",
                        play.get("quarter", ""),
                    )
                if "down" in incoming:
                    play["resulting_down"] = after_state.get("down", "")
                if "distance" in incoming:
                    play["resulting_distance"] = after_state.get("distance", "")
            self._append_correction(
                state,
                self._correction_entry(
                    "event_edit",
                    source,
                    before,
                    copy.deepcopy(event),
                    event_id,
                    str(incoming.get("note", ""))[:200],
                ),
            )
            state["events"] = events
            # A prior edit is a canonical-history change. Rebuild dependent game
            # state and rewrite before/after snapshots instead of patching only
            # the currently visible controls.
            base_revision = current_revision(state)
            baseline = (events[0].get("before") if events else {}) or {}
            state = CanonicalStateFoundation.rebuild(
                state,
                events,
                list(state.get("plays") or []),
                baseline=baseline,
            )
            state["state_revision"] = base_revision
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming,
                action="event_edit",
                state_revision=revision,
            )
            result_data = attach_metadata(
                {
                    "state": copy.deepcopy(dict(self._public_state(state))),
                    "event": copy.deepcopy(event),
                },
                metadata,
            )
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
        return EventResult("OK", result_data)

    def corrections(self) -> EventResult:
        state = dict(self._load_state())
        return EventResult(
            "OK",
            {"corrections": copy.deepcopy(list(reversed(state.get("correction_log") or [])))},
        )

    @staticmethod
    def _restore_entry_available(state: Mapping[str, Any], entry: Mapping[str, Any]) -> bool:
        event = entry.get("event") if isinstance(entry, Mapping) else None
        if not isinstance(event, Mapping):
            return False
        event_id = str(event.get("id", ""))
        play_id = str(event.get("play_id", ""))
        try:
            play_number = int(event.get("play_number", 0) or 0)
            next_play_number = int(state.get("next_play_number", 1) or 1)
        except (TypeError, ValueError):
            return False
        if play_number < 1 or next_play_number != play_number:
            return False
        if event_id and any(str(row.get("id", "")) == event_id for row in list(state.get("events") or [])):
            return False
        if play_id and any(str(row.get("play_id", "")) == play_id for row in list(state.get("plays") or [])):
            return False
        return True

    def undo(self, payload: Mapping[str, Any] | None = None) -> EventResult:
        incoming = dict(payload or {})
        with self._lock():
            state = copy.deepcopy(dict(self._load_state()))
            command_id = command_id_from(incoming)
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return EventResult("OK", duplicate)
            base_revision = current_revision(state)
            result_data: dict[str, Any] | None = None
            events = list(state.get("events") or [])
            target = next(
                (event for event in reversed(events) if not event.get("undone") and event.get("before")),
                None,
            )
            if target:
                target_id = str(target.get("id", ""))
                target_play_id = str(target.get("play_id", ""))
                target_play = next(
                    (copy.deepcopy(row) for row in list(state.get("plays") or [])
                     if str(row.get("event_id", "")) == target_id
                     or (target_play_id and str(row.get("play_id", "")) == target_play_id)),
                    None,
                )
                redo_stack = list(state.get("redo_stack") or [])
                redo_stack.append({
                    "event": copy.deepcopy(target),
                    "play": target_play,
                    "undone_at": int(self._now()),
                })
                state["redo_stack"] = redo_stack[-20:]
                remaining_events = [row for row in events if str(row.get("id", "")) != target_id]
                remaining_plays = [
                    row for row in list(state.get("plays") or [])
                    if str(row.get("event_id", "")) != target_id
                    and str(row.get("play_id", "")) != target_play_id
                ]
                self._append_correction(
                    state,
                    self._correction_entry(
                        "undo",
                        "operator",
                        target.get("after") or {},
                        target.get("before") or {},
                        target_id,
                        f"Undid {target.get('label', target.get('event', 'event'))}",
                    ),
                )
                baseline = (remaining_events[0].get("before") if remaining_events else target.get("before")) or {}
                state = CanonicalStateFoundation.rebuild(
                    state,
                    remaining_events,
                    remaining_plays,
                    baseline=baseline,
                )
                state["state_revision"] = base_revision
                if not remaining_events:
                    saved_redo = copy.deepcopy(list(state.get("redo_stack") or []))
                    saved_corrections = copy.deepcopy(list(state.get("correction_log") or []))
                    for key, value in dict(target.get("before") or {}).items():
                        if key not in {"events", "plays", "history", "redo_stack", "correction_log"}:
                            state[key] = copy.deepcopy(value)
                    state["events"] = []
                    state["plays"] = []
                    state["last_event"] = {}
                    state["next_play_number"] = int(target.get("play_number", 1) or 1)
                    state["redo_stack"] = saved_redo
                    state["correction_log"] = saved_corrections
                revision = assign_next_revision(state)
                metadata = command_metadata(
                    incoming,
                    action="undo",
                    state_revision=revision,
                )
                result_data = attach_metadata(
                    {"state": copy.deepcopy(dict(self._public_state(state)))},
                    metadata,
                )
                remember_command(state, command_id, metadata=metadata, result=result_data)
                self._save_state(state)
            else:
                history = state.get("history", [])
                if history:
                    previous = history.pop()
                    previous["history"] = history
                    state = copy.deepcopy(dict(self._normalize_state(previous)))
                    state["state_revision"] = base_revision
                    revision = assign_next_revision(state)
                    metadata = command_metadata(
                        incoming,
                        action="undo",
                        state_revision=revision,
                    )
                    result_data = attach_metadata(
                        {"state": copy.deepcopy(dict(self._public_state(state)))},
                        metadata,
                    )
                    remember_command(state, command_id, metadata=metadata, result=result_data)
                    self._save_state(state)
            if result_data is None:
                result_data = {"state": copy.deepcopy(dict(self._public_state(state)))}
        return EventResult("OK", result_data)

    def restore(self, payload: Mapping[str, Any] | None = None) -> EventResult:
        incoming = dict(payload or {})
        with self._lock():
            state = copy.deepcopy(dict(self._load_state()))
            command_id = command_id_from(incoming)
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return EventResult("OK", duplicate)
            redo_stack = list(state.get("redo_stack") or [])
            entry = redo_stack[-1] if redo_stack else None
            if not entry or not self._restore_entry_available(state, entry):
                return EventResult(
                    "RESTORE_UNAVAILABLE",
                    {
                        "state": copy.deepcopy(dict(self._public_state(state))),
                        "message": "No safely restorable undone event is available.",
                    },
                )
            event = copy.deepcopy(dict(entry.get("event") or {}))
            play = copy.deepcopy(entry.get("play")) if isinstance(entry.get("play"), Mapping) else None
            events = list(state.get("events") or []) + [event]
            plays = list(state.get("plays") or [])
            if play is not None:
                plays.append(play)
            state["redo_stack"] = redo_stack[:-1]
            self._append_correction(
                state,
                self._correction_entry(
                    "restore",
                    "operator",
                    event.get("before") or {},
                    event.get("after") or {},
                    str(event.get("id", "")),
                    f"Restored {event.get('label', event.get('event', 'event'))}",
                ),
            )
            baseline = (events[0].get("before") if events else event.get("before")) or {}
            base_revision = current_revision(state)
            state = CanonicalStateFoundation.rebuild(state, events, plays, baseline=baseline)
            state["state_revision"] = base_revision
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming,
                action="restore",
                state_revision=revision,
            )
            result_data = attach_metadata(
                {"state": copy.deepcopy(dict(self._public_state(state)))},
                metadata,
            )
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
        return EventResult("OK", result_data)

    def _describe_event(
        self,
        state: dict[str, Any],
        incoming: dict[str, Any],
        team: str,
        team_name: str,
        event_code: str,
        play_type: str,
        turnover_type: str,
        return_td: bool,
        scorer_name: str,
        passer_name: str,
        yards: str,
    ) -> tuple[str, str]:
        if event_code == "PLAY":
            play_kind = str(incoming.get("play_type", "run") or "run").lower()
            outcome = str(
                incoming.get("pass_outcome", "complete") or "complete"
            ).lower()
            fumble = bool(incoming.get("fumble"))
            fumble_lost = bool(incoming.get("fumble_lost"))
            turnover = (
                bool(incoming.get("turnover"))
                or fumble_lost
                or outcome == "interception"
            )
            if play_kind == "pass":
                if outcome == "incomplete":
                    label = "Incomplete Pass"
                    description = f"{passer_name or team_name} pass incomplete"
                elif outcome == "interception":
                    label = "Interception"
                    description = f"{passer_name or team_name} pass intercepted"
                elif outcome == "sack":
                    label = "Sack"
                    description = f"{passer_name or team_name} sacked"
                else:
                    label = "Pass"
                    description = (
                        f"{passer_name or team_name} pass complete to "
                        f"{scorer_name or team_name}"
                    )
            else:
                label = "Run"
                description = f"{scorer_name or team_name} run"
            if yards not in {"", "0"}:
                description += f" for {yards} yards"
            elif yards == "0":
                description += " for no gain"
            if fumble:
                description += ", fumble" + (
                    " lost" if fumble_lost else " recovered"
                )
            if bool(incoming.get("first_down")):
                description += ", first down"
                state["down"] = "1st"
                state["distance"] = "10"
            if turnover:
                state["possession"] = "visitor" if team == "home" else "home"
            return label, description

        if event_code in {"TD", "2PT"}:
            conversion = event_code == "2PT"
            conversion_outcome = str(incoming.get("conversion_outcome", "good") or "good").lower()
            if conversion and conversion_outcome == "failed":
                return "Two-Point Conversion Failed", f"Two-point conversion failed for {team_name}"
            label = "Two-Point Conversion" if conversion else "Touchdown"
            phrase = "two-point conversion" if conversion else "touchdown"
            if play_type == "reception":
                description = f"{scorer_name or team_name} {phrase} reception"
                if passer_name:
                    description += f" from {passer_name}"
            elif play_type == "rush":
                description = f"{scorer_name or team_name} {phrase} run"
            elif play_type == "return":
                description = f"{scorer_name or team_name} {phrase} return"
            else:
                description = f"{scorer_name or team_name} {phrase}"
            if yards:
                description = f"{yards}-yard {description}"
            return label, description

        if event_code == "TURNOVER":
            kind = {
                "interception": "Interception",
                "fumble_recovery": "Fumble recovery",
                "muff_recovery": "Muff recovery",
                "kicking_team_recovery": "Kicking-team recovery",
                "downs": "Turnover on downs",
                "other": "Turnover",
            }.get(turnover_type, "Turnover")
            label = "Defensive Touchdown" if return_td else kind
            description = f"{scorer_name or team_name} {kind.lower()}"
            turnover_spot = str(
                incoming.get("turnover_spot")
                or incoming.get("recovery_spot")
                or incoming.get("interception_spot")
                or ""
            ).strip()
            return_end = str(incoming.get("return_end_spot", "") or "").strip()
            if turnover_spot:
                description += f" at {turnover_spot}"
            if return_end and not return_td:
                description += f", returned to {return_end}"
            if return_td:
                description += " returned for a touchdown"
            if yards and return_td:
                description = f"{yards}-yard {description}"
            return label, description

        if event_code == "KICKOFF":
            receiving = str(incoming.get("kickoff_receiving_team", "") or "").lower()
            receiving_name = str(
                state.get("home_team")
                if receiving == "home"
                else state.get("visitor_team")
                if receiving == "visitor"
                else "receiving team"
            )
            result_spot = str(incoming.get("kickoff_result_spot", "") or "").strip()
            if bool(incoming.get("kickoff_touchback")):
                return "Kickoff", f"{team_name} kickoff — touchback to {receiving_name}"
            return "Kickoff", f"{team_name} kickoff — {receiving_name} ball at {result_spot}"

        if event_code == "FIRST_DOWN":
            method = str(
                incoming.get("first_down_method", "manual") or "manual"
            ).title()
            description = f"{team_name} first down"
            if method != "Manual":
                description += f" ({method})"
            return "1st Down", description

        if event_code == "PENALTY":
            name = str(incoming.get("penalty_name", "Penalty") or "Penalty")
            yards_text = str(incoming.get("penalty_yards", "") or "").strip()
            category = str(incoming.get("penalty_category", "") or "").strip()
            outcome = str(
                incoming.get("penalty_outcome", "accepted") or "accepted"
            ).lower()
            if outcome == "flag_picked_up":
                return (
                    "Flag Picked Up",
                    f"Flag picked up — no penalty on {team_name}",
                )
            if outcome == "offset":
                return "Offsetting Penalties", "Offsetting penalties — replay down"
            if outcome == "declined":
                description = f"Penalty declined, {team_name}"
                if name:
                    description += f" — {name}"
                return "Penalty Declined", description
            description = f"Penalty, {team_name}"
            if yards_text:
                description += f", {yards_text} yards"
            if name:
                description += f" — {name}"
            if category:
                description += f" ({category})"
            return "Penalty", description

        if event_code == "EJECTION":
            person_type = str(
                incoming.get("ejection_person_type", "Player") or "Player"
            )
            person_name = str(
                incoming.get("ejection_person_name", "") or ""
            ).strip()
            reason = str(incoming.get("ejection_reason", "Other") or "Other")
            description = "Person ejected"
            description = f"{person_type} ejected"
            description += f": {person_name}" if person_name else f" — {team_name}"
            if reason:
                description += f" ({reason})"
            return f"{person_type} Ejected", description

        if event_code == "FG":
            kick_outcome = str(incoming.get("kick_outcome", "made") or "made").lower()
            base = f"{yards}-yard field goal by {scorer_name or team_name}" if yards else f"{scorer_name or team_name} field goal"
            if kick_outcome == "made":
                return "Field Goal", base + " good"
            if kick_outcome == "blocked":
                return "Field Goal Blocked", base + " blocked"
            return "Field Goal No Good", base + " no good"

        conversion_outcome = str(incoming.get("conversion_outcome", "good") or "good").lower()
        if event_code == "2PT":
            if conversion_outcome == "good":
                return "Two-Point Conversion", f"Two-point conversion good for {team_name}"
            if conversion_outcome == "retry":
                return "Two-Point Try Retry", f"Two-point try to be retried for {team_name}"
            return "Two-Point Conversion Failed", f"Two-point conversion failed for {team_name}"
        if conversion_outcome == "retry":
            return "Extra Point Retry", f"Extra point to be retried for {team_name}"
        if conversion_outcome == "blocked":
            return "Extra Point Blocked", f"Extra point blocked for {team_name}"
        if conversion_outcome == "no_good":
            return "Extra Point No Good", f"Extra point no good for {team_name}"
        return "Extra Point", f"Extra point good by {scorer_name or team_name}"

    def _event_payload(self, **values: Any) -> dict[str, Any]:
        state = values["state"]
        incoming = values["incoming"]
        player = values["player"]
        passer = values["passer"]
        event_code = values["event_code"]
        team = values["team"]
        return {
            "id": values["event_id"],
            "play_id": values["play_id"],
            "play_number": values["play_number"],
            "team": team,
            "team_name": values["team_name"],
            "event": event_code,
            "label": values["label"],
            "description": values["description"],
            "score_delta": values["delta"],
            "conversion_outcome": (
                str(incoming.get("conversion_outcome", "good") or "good").lower()
                if event_code in {"XP", "2PT"}
                else ""
            ),
            "kick_outcome": str(incoming.get("kick_outcome", "made") or "made").lower() if event_code == "FG" else "",
            "created_at": values["created_at"],
            "quarter": str(state.get("quarter", "1") or "1"),
            "broadcast_id": state.get("broadcast_id", ""),
            "before": values["before"],
            "source": values["source"],
            "first_down_method": str(incoming.get("first_down_method", "") or ""),
            "penalty": {
                "category": str(incoming.get("penalty_category", "") or ""),
                "name": str(incoming.get("penalty_name", "") or ""),
                "yards": str(incoming.get("penalty_yards", "") or ""),
                "outcome": str(
                    incoming.get("penalty_outcome", "accepted") or "accepted"
                ),
                "enforcement": dict(values["penalty_enforcement"]),
            },
            "ejection": {
                "person_type": str(incoming.get("ejection_person_type", "") or ""),
                "person_name": str(incoming.get("ejection_person_name", "") or ""),
                "reason": str(incoming.get("ejection_reason", "") or ""),
                "player_id": str(incoming.get("ejection_player_id", "") or ""),
                "roster_id": str(incoming.get("ejection_roster_id", "") or ""),
                "player_number": str(incoming.get("ejection_player_number", "") or ""),
                "player_name": str(incoming.get("ejection_player_name", "") or ""),
            },
            "after": {
                "home_score": int(state.get("home_score", 0)),
                "visitor_score": int(state.get("visitor_score", 0)),
                "possession": state.get("possession", "home"),
                "down": state.get("down", "1st"),
                "distance": state.get("distance", "10"),
                "ball_spot": state.get("ball_spot", ""),
                "quarter": state.get("quarter", "1"),
                "special_game_phase": state.get("special_game_phase", ""),
                "kicking_team": state.get("kicking_team", ""),
                "receiving_team": state.get("receiving_team", ""),
            },
            "automation": {
                "mode": (
                    "statistician"
                    if bool(incoming.get("statistician_mode"))
                    else "quick"
                ),
                "play_type": values["play_type"],
                "turnover_type": values["turnover_type"],
                "turnover_team": team if event_code == "TURNOVER" else "",
                "turnover_spot": str(incoming.get("turnover_spot") or incoming.get("recovery_spot") or incoming.get("interception_spot") or ""),
                "return_end_spot": str(incoming.get("return_end_spot", "") or ""),
                "return_yards": str(incoming.get("return_yards", values["yards"]) or ""),
                "turnover_player_id": str(incoming.get("player_id", "")) if event_code == "TURNOVER" else "",
                "turnover_player_name": values["scorer_name"] if event_code == "TURNOVER" else "",
                "turnover_player_number": str(player.get("number", "")) if event_code == "TURNOVER" and player else "",
                "player_id": str(incoming.get("player_id", "")),
                "player_name": values["scorer_name"],
                "player_number": str(player.get("number", "")) if player else "",
                "passer_id": str(incoming.get("passer_id", "")),
                "passer_name": values["passer_name"],
                "passer_number": str(passer.get("number", "")) if passer else "",
                "manual_player": incoming.get("manual_player"),
                "manual_passer": incoming.get("manual_passer"),
                "yards": values["yards"],
                "return_td": values["return_td"],
                "graphic_duration": values["duration"],
                "pass_outcome": str(incoming.get("pass_outcome", "") or ""),
                "fumble": bool(incoming.get("fumble")),
                "fumble_lost": bool(incoming.get("fumble_lost")),
                "first_down": bool(incoming.get("first_down")),
                "conversion_outcome": (
                    str(incoming.get("conversion_outcome", "good") or "good").lower()
                    if event_code in {"XP", "2PT"}
                    else ""
                ),
                "kick_outcome": str(incoming.get("kick_outcome", "made") or "made").lower() if event_code == "FG" else "",
                "kick_result_spot": str(incoming.get("kick_result_spot", "") or ""),
                "kick_touchback": bool(incoming.get("kick_touchback")),
                "turnover": (
                    bool(incoming.get("turnover"))
                    or bool(incoming.get("fumble_lost"))
                    or str(incoming.get("pass_outcome", "")).lower()
                    == "interception"
                ),
            },
            "media_trigger": {
                "key": f"{event_code.lower()}_{team}",
                "assigned": bool(player and values["duration"]),
                "graphics": (
                    "player_touchdown"
                    if player and values["duration"]
                    else None
                ),
                "audio": None,
                "video": None,
            },
        }

    def _play_record(self, **values: Any) -> dict[str, Any]:
        state = values["state"]
        incoming = values["incoming"]
        team = values["team"]
        player = values["player"]
        passer = values["passer"]
        event_code = values["event_code"]
        return {
            "play_id": values["play_id"],
            "play_number": values["play_number"],
            "event_id": values["event_id"],
            "broadcast_id": state.get("broadcast_id", ""),
            "quarter": str(state.get("quarter", "1") or "1"),
            "clock": str(incoming.get("clock", "") or ""),
            "offense": team,
            "offense_name": values["team_name"],
            "defense": "visitor" if team == "home" else "home",
            "defense_name": (
                state.get("visitor_team")
                if team == "home"
                else state.get("home_team")
            ),
            "down": str(values["before"].get("down", "")),
            "distance": str(values["before"].get("distance", "")),
            "ball_spot": str(values["before"].get("ball_spot", "")),
            "play_type": values["play_type"] or event_code.lower(),
            "result": values["description"],
            "yards": values["yards"],
            "first_down": event_code == "FIRST_DOWN" or bool(incoming.get("first_down")),
            "touchdown": event_code == "TD" or values["return_td"],
            "kick_outcome": str(incoming.get("kick_outcome", "made") or "made").lower() if event_code == "FG" else "",
            "conversion_outcome": str(incoming.get("conversion_outcome", "good") or "good").lower() if event_code in {"XP", "2PT"} else "",
            "turnover": (
                event_code == "TURNOVER"
                or bool(incoming.get("turnover"))
                or bool(incoming.get("fumble_lost"))
                or str(incoming.get("pass_outcome", "")).lower()
                == "interception"
            ),
            "turnover_type": str(incoming.get("turnover_type", "") or "") if event_code == "TURNOVER" else "",
            "turnover_team": team if event_code == "TURNOVER" else "",
            "turnover_spot": str(incoming.get("turnover_spot") or incoming.get("recovery_spot") or incoming.get("interception_spot") or values["before"].get("ball_spot", "")) if event_code == "TURNOVER" else "",
            "return_end_spot": str(incoming.get("return_end_spot", "") or "") if event_code == "TURNOVER" else "",
            "return_yards": str(incoming.get("return_yards", values["yards"]) or "") if event_code == "TURNOVER" else "",
            "turnover_player_name": values["scorer_name"] if event_code == "TURNOVER" else "",
            "turnover_player_number": str(player.get("number", "")) if event_code == "TURNOVER" and player else "",
            "fumble": bool(incoming.get("fumble")),
            "fumble_lost": bool(incoming.get("fumble_lost")),
            "pass_outcome": str(incoming.get("pass_outcome", "") or ""),
            "player_name": values["scorer_name"],
            "player_number": (
                str(player.get("number", ""))
                if player
                else str((incoming.get("manual_player") or {}).get("number", ""))
            ),
            "passer_name": values["passer_name"],
            "passer_number": (
                str(passer.get("number", ""))
                if passer
                else str((incoming.get("manual_passer") or {}).get("number", ""))
            ),
            "safety": False,
            "notes": str(incoming.get("notes", "") or ""),
            "created_by": values["source"],
            "created_at": values["created_at"],
            "label": values["label"],
            "undone": False,
            "statistics_hooks": [],
            "drive_id": "",
        }

    def _correction_entry(
        self,
        kind: str,
        operator: str,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        event_id: str = "",
        note: str = "",
    ) -> dict[str, Any]:
        return {
            "id": f"COR-{int(self._now() * 1000)}",
            "kind": kind,
            "operator": operator,
            "event_id": event_id,
            "before": copy.deepcopy(dict(before)),
            "after": copy.deepcopy(dict(after)),
            "note": note,
            "created_at": int(self._now()),
        }

    @staticmethod
    def _append_correction(state: dict[str, Any], entry: dict[str, Any]) -> None:
        rows = list(state.get("correction_log") or [])
        rows.append(entry)
        state["correction_log"] = rows[-500:]

    @staticmethod
    def _distance(value: Any, fallback: int = 10) -> int:
        try:
            return max(1, min(99, int(str(value))))
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _clamp_int(
        value: Any,
        minimum: int,
        maximum: int,
        fallback: int,
    ) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = fallback
        return max(minimum, min(maximum, number))
