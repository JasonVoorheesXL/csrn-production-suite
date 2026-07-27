from __future__ import annotations

import copy
import re
import time
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Callable, Mapping


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
        self._on_event = on_event
        self._transaction_lock = transaction_lock
        self._now = now

    def _lock(self):
        return self._transaction_lock if self._transaction_lock is not None else nullcontext()

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

    def set_control_source(self, authority: Any) -> EventResult:
        authority_text = str(authority or "").lower()
        if authority_text not in self.VALID_AUTHORITIES:
            return EventResult("INVALID_CONTROL_SOURCE", {})
        with self._lock():
            state = copy.deepcopy(dict(self._load_state()))
            self._push_history(state)
            state["game_data_authority"] = authority_text
            state["statistician_enabled"] = authority_text == "statistician"
            state["control_source_updated_at"] = int(self._now())
            self._save_state(state)
        return EventResult(
            "OK",
            {"state": copy.deepcopy(dict(self._public_state(state)))},
        )

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
            source = str(
                incoming.get("source", "broadcaster") or "broadcaster"
            ).lower()
            if not self.source_allowed(state, source):
                return EventResult(
                    "CONTROL_SOURCE_LOCKED",
                    self.locked_payload(state),
                )

            self._push_history(state)
            score_key = "home_score" if team == "home" else "visitor_score"
            before = {
                "home_score": int(state.get("home_score", 0)),
                "visitor_score": int(state.get("visitor_score", 0)),
                "possession": state.get("possession", "home"),
                "down": state.get("down", "1st"),
                "distance": state.get("distance", "10"),
                "ball_spot": state.get("ball_spot", ""),
                "quarter": state.get("quarter", "1"),
                "player_graphic": copy.deepcopy(
                    state.get("player_graphic") or {}
                ),
            }
            return_td = bool(incoming.get("return_td")) and str(
                incoming.get("turnover_type", "")
            ) != "downs"
            delta = (
                6
                if event_code == "TD" or (event_code == "TURNOVER" and return_td)
                else 3
                if event_code == "FG"
                else 2
                if event_code == "2PT"
                else 1
                if event_code == "XP"
                else 0
            )
            if delta:
                state[score_key] = max(
                    0,
                    int(state.get(score_key, 0)) + delta,
                )
            if event_code == "TURNOVER":
                state["possession"] = team
            if event_code == "FIRST_DOWN":
                state["down"] = "1st"
                state["distance"] = "10"

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
                penalty_enforcement = self._apply_penalty(
                    state,
                    category,
                    name,
                    yards_value,
                    outcome,
                )

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
            if (event_code in {"TD", "2PT"} or return_td) and player:
                eyebrow = (
                    "TWO-POINT CONVERSION"
                    if event_code == "2PT"
                    else "DEFENSIVE TOUCHDOWN"
                    if return_td
                    else "TOUCHDOWN"
                )
                self._show_player_graphic(
                    state,
                    roster,
                    player,
                    "two_point" if event_code == "2PT" else "touchdown",
                    duration,
                    defensive=(event_code == "TURNOVER" and return_td),
                    eyebrow=eyebrow,
                    play_detail=description,
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
            self._save_state(state)

        if self._on_event is not None:
            try:
                self._on_event(copy.deepcopy(payload))
            except Exception:
                # Social draft creation can never invalidate the game event.
                pass

        return EventResult(
            "OK",
            {
                "state": copy.deepcopy(dict(self._public_state(state))),
                "trigger": copy.deepcopy(payload),
                "media_assigned": bool(payload["media_trigger"]["assigned"]),
                "message": description + (f" (+{delta})" if delta else ""),
            },
        )

    def quick_correction(self, data: Mapping[str, Any] | None) -> EventResult:
        incoming = dict(data or {})
        with self._lock():
            state = copy.deepcopy(dict(self._load_state()))
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
            self._save_state(state)
        return EventResult(
            "OK",
            {"state": copy.deepcopy(dict(self._public_state(state)))},
        )

    def edit(self, event_id: str, data: Mapping[str, Any] | None) -> EventResult:
        incoming = dict(data or {})
        with self._lock():
            state = copy.deepcopy(dict(self._load_state()))
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
                        f"{yards}-yard "
                        + (
                            description[0].lower() + description[1:]
                            if description
                            else "play"
                        )
                    )
            for field in ("description", "quarter"):
                if field in incoming:
                    event[field] = str(incoming.get(field, ""))[:300]
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
                if "description" in incoming:
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
            state["last_event"] = event
            self._save_state(state)
        return EventResult(
            "OK",
            {
                "state": copy.deepcopy(dict(self._public_state(state))),
                "event": copy.deepcopy(event),
            },
        )

    def corrections(self) -> EventResult:
        state = dict(self._load_state())
        return EventResult(
            "OK",
            {"corrections": copy.deepcopy(list(reversed(state.get("correction_log") or [])))},
        )

    def undo(self) -> EventResult:
        with self._lock():
            state = copy.deepcopy(dict(self._load_state()))
            events = list(state.get("events") or [])
            target = next(
                (
                    event
                    for event in reversed(events)
                    if not event.get("undone") and event.get("before")
                ),
                None,
            )
            if target:
                before = target.get("before") or {}
                state["home_score"] = int(
                    before.get("home_score", state.get("home_score", 0))
                )
                state["visitor_score"] = int(
                    before.get("visitor_score", state.get("visitor_score", 0))
                )
                for field, fallback in (
                    ("possession", "home"),
                    ("down", "1st"),
                    ("distance", "10"),
                    ("ball_spot", ""),
                    ("quarter", "1"),
                ):
                    state[field] = before.get(field, state.get(field, fallback))
                state["clock_seconds"] = int(
                    before.get(
                        "clock_seconds",
                        state.get("clock_seconds", 720),
                    )
                    or 0
                )
                state["clock_running"] = bool(
                    before.get(
                        "clock_running",
                        state.get("clock_running", False),
                    )
                )
                self._append_correction(
                    state,
                    self._correction_entry(
                        "undo",
                        "operator",
                        target.get("after") or {},
                        before,
                        str(target.get("id", "")),
                        f"Undid {target.get('label', target.get('event', 'event'))}",
                    ),
                )
                if "player_graphic" in before:
                    state["player_graphic"] = copy.deepcopy(
                        before.get("player_graphic")
                        or dict(self._default_player_graphic())
                    )
                target_id = target.get("id", "")
                target_play_number = self._clamp_int(
                    target.get("play_number", 0),
                    0,
                    1_000_000,
                    0,
                )
                state["events"] = [
                    row for row in events if row.get("id") != target_id
                ]
                state["plays"] = [
                    row
                    for row in list(state.get("plays") or [])
                    if row.get("event_id") != target_id
                    and row.get("play_id") != target.get("play_id")
                ]
                if target_play_number:
                    state["next_play_number"] = target_play_number
                remaining = [
                    row for row in state["events"] if not row.get("undone")
                ]
                state["last_event"] = remaining[-1] if remaining else {}
                self._save_state(state)
            else:
                history = state.get("history", [])
                if history:
                    previous = history.pop()
                    previous["history"] = history
                    state = copy.deepcopy(dict(self._normalize_state(previous)))
                    self._save_state(state)
        return EventResult("OK", {"state": copy.deepcopy(state)})

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
                description = f"{yards}-yard {description[0].lower() + description[1:]}"
            return label, description

        if event_code == "TURNOVER":
            kind = {
                "interception": "Interception",
                "fumble_recovery": "Fumble recovery",
                "downs": "Turnover on downs",
                "other": "Turnover",
            }.get(turnover_type, "Turnover")
            label = "Defensive Touchdown" if return_td else kind
            description = f"{scorer_name or team_name} {kind.lower()}"
            if return_td:
                description += " returned for a touchdown"
            if yards and return_td:
                description = f"{yards}-yard {description.lower()}"
            return label, description

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
            description = f"{scorer_name or team_name} field goal"
            if yards:
                description = f"{yards}-yard field goal by {scorer_name or team_name}"
            return "Field Goal", description

        return "Extra Point", f"Extra point by {scorer_name or team_name}"

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
                "person_type": str(
                    incoming.get("ejection_person_type", "") or ""
                ),
                "person_name": str(
                    incoming.get("ejection_person_name", "") or ""
                ),
                "reason": str(incoming.get("ejection_reason", "") or ""),
            },
            "after": {
                "home_score": int(state.get("home_score", 0)),
                "visitor_score": int(state.get("visitor_score", 0)),
                "possession": state.get("possession", "home"),
                "down": state.get("down", "1st"),
                "distance": state.get("distance", "10"),
                "ball_spot": state.get("ball_spot", ""),
                "quarter": state.get("quarter", "1"),
            },
            "automation": {
                "mode": (
                    "statistician"
                    if bool(incoming.get("statistician_mode"))
                    else "quick"
                ),
                "play_type": values["play_type"],
                "turnover_type": values["turnover_type"],
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
            "turnover": (
                event_code == "TURNOVER"
                or bool(incoming.get("turnover"))
                or bool(incoming.get("fumble_lost"))
                or str(incoming.get("pass_outcome", "")).lower()
                == "interception"
            ),
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
