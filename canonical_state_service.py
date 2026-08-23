from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from eligibility_service import EligibilityService


CANONICAL_FIELDS = (
    "home_score",
    "visitor_score",
    "possession",
    "down",
    "distance",
    "ball_spot",
    "home_direction",
    "visitor_direction",
    "quarter",
    "clock_seconds",
    "clock_visible",
    "clock_running",
    "clock_started_at",
    "broadcast_phase",
    "special_game_phase",
    "kicking_team",
    "receiving_team",
)


@dataclass(frozen=True)
class TeamRoles:
    possessing_team: str
    non_possessing_team: str
    offense: str
    defense: str
    home: str = "home"
    visitor: str = "visitor"
    kicking_team: str = ""
    receiving_team: str = ""
    special_teams_phase: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "possessing_team": self.possessing_team,
            "non_possessing_team": self.non_possessing_team,
            "offense": self.offense,
            "defense": self.defense,
            "home": self.home,
            "visitor": self.visitor,
            "kicking_team": self.kicking_team,
            "receiving_team": self.receiving_team,
            "special_teams_phase": self.special_teams_phase,
        }


class CanonicalStateFoundation:
    """Gate 18.4 R1 canonical team-role and field-state primitives.

    This helper is intentionally framework-free so Flask routes, services, tests,
    and browser serialization can share the same state interpretation.
    """

    VALID_TEAMS = {"home", "visitor"}
    SCRIMMAGE_ROLES = {"player", "ball_carrier", "passer", "receiver"}
    DEFENSIVE_ROLES = {"interceptor", "sacker", "forced_fumble", "defensive_recovery"}

    @classmethod
    def opposite(cls, team: Any) -> str:
        return "visitor" if str(team or "home").lower() == "home" else "home"

    @classmethod
    def team_roles(cls, state: Mapping[str, Any]) -> TeamRoles:
        possession = str(state.get("possession", "home") or "home").lower()
        if possession not in cls.VALID_TEAMS:
            possession = "home"
        other = cls.opposite(possession)
        phase = str(
            state.get("special_game_phase")
            or state.get("special_teams_phase")
            or ""
        ).strip().lower()
        kicking = ""
        receiving = ""
        if phase in {"kickoff", "punt", "free_kick", "try_kick"}:
            candidate = str(state.get("kicking_team", "") or "").lower()
            kicking = candidate if candidate in cls.VALID_TEAMS else possession
            receiving = cls.opposite(kicking)
        return TeamRoles(
            possessing_team=possession,
            non_possessing_team=other,
            offense=possession,
            defense=other,
            kicking_team=kicking,
            receiving_team=receiving,
            special_teams_phase=phase,
        )

    @classmethod
    def field_state(cls, state: Mapping[str, Any]) -> dict[str, Any]:
        roles = cls.team_roles(state)
        return {
            "ball_spot": str(state.get("ball_spot", "") or ""),
            "possession": roles.possessing_team,
            "offense": roles.offense,
            "defense": roles.defense,
            "down": str(state.get("down", "1st") or "1st"),
            "distance": str(state.get("distance", "10") or "10"),
            "drive_direction": str(
                state.get(f"{roles.possessing_team}_direction", "right") or "right"
            ),
            "home_direction": str(state.get("home_direction", "right") or "right"),
            "visitor_direction": str(state.get("visitor_direction", "left") or "left"),
            "quarter": str(state.get("quarter", "1") or "1"),
            "clock_seconds": int(state.get("clock_seconds", 0) or 0),
            "clock_visible": bool(state.get("clock_visible", False)),
            "clock_running": bool(state.get("clock_running", False)),
            "clock_started_at": int(state.get("clock_started_at", 0) or 0),
            "home_score": int(state.get("home_score", 0) or 0),
            "visitor_score": int(state.get("visitor_score", 0) or 0),
            "broadcast_phase": str(state.get("broadcast_phase", "pregame") or "pregame"),
            "special_game_phase": roles.special_teams_phase,
            "kicking_team": roles.kicking_team,
            "receiving_team": roles.receiving_team,
        }

    @classmethod
    def snapshot(cls, state: Mapping[str, Any]) -> dict[str, Any]:
        return {field: copy.deepcopy(state.get(field)) for field in CANONICAL_FIELDS}

    @classmethod
    def penalty_unit(cls, state: Mapping[str, Any], selected_team: Any) -> str:
        selected = str(selected_team or "").lower()
        roles = cls.team_roles(state)
        if selected == roles.offense:
            return "Offensive"
        if selected == roles.defense:
            return "Defensive"
        return "General"

    @classmethod
    def permitted_team_for_role(cls, state: Mapping[str, Any], role: str) -> str:
        roles = cls.team_roles(state)
        role_key = str(role or "").lower()
        if role_key in cls.SCRIMMAGE_ROLES:
            return roles.offense
        if role_key in cls.DEFENSIVE_ROLES:
            return roles.defense
        if role_key == "kicker":
            return roles.kicking_team or roles.offense
        if role_key == "returner":
            return roles.receiving_team or roles.defense
        return ""

    @staticmethod
    def _spot_to_coord(value: Any) -> int:
        text = str(value or "").strip().upper()
        if text in {"LEFT GOAL", "HOME GOAL", "0"}:
            return 0
        if text in {"RIGHT GOAL", "VISITOR GOAL", "100"}:
            return 100
        if text == "50":
            return 50
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            yard = max(0, min(50, int(parts[1])))
            if parts[0] in {"LEFT", "HOME"}:
                return yard
            if parts[0] in {"RIGHT", "VISITOR"}:
                return 100 - yard
        try:
            return max(0, min(100, int(float(text))))
        except (TypeError, ValueError):
            return 50

    @staticmethod
    def _coord_to_spot(coord: Any) -> str:
        try:
            value = max(0, min(100, int(round(float(coord)))))
        except (TypeError, ValueError):
            value = 50
        if value == 0:
            return "LEFT GOAL"
        if value == 100:
            return "RIGHT GOAL"
        if value == 50:
            return "50"
        return f"LEFT {value}" if value < 50 else f"RIGHT {100 - value}"


    @classmethod
    def _team_own_yard_spot(cls, state: Mapping[str, Any], team: str, yard: int) -> str:
        direction = str(state.get(f"{team}_direction", "right" if team == "home" else "left") or "right").lower()
        coord = yard if direction == "right" else 100 - yard
        return cls._coord_to_spot(coord)

    @classmethod
    def _opponent_yard_spot(cls, state: Mapping[str, Any], team: str, yard: int) -> str:
        direction = str(state.get(f"{team}_direction", "right" if team == "home" else "left") or "right").lower()
        coord = 100 - yard if direction == "right" else yard
        return cls._coord_to_spot(coord)

    @classmethod
    def enter_pending_try(cls, state: dict[str, Any], scoring_team: str) -> None:
        scoring = scoring_team if scoring_team in cls.VALID_TEAMS else str(state.get("possession", "home"))
        state["possession"] = scoring
        state["special_game_phase"] = "pending_try"
        state["kicking_team"] = ""
        state["receiving_team"] = ""
        state["down"] = "Off"
        state["distance"] = "Off"
        state["ball_spot"] = cls._opponent_yard_spot(state, scoring, 3)
        state["clock_running"] = False
        state["clock_started_at"] = 0

    @classmethod
    def enter_kickoff(cls, state: dict[str, Any], scoring_team: str) -> None:
        kicking = scoring_team if scoring_team in cls.VALID_TEAMS else str(state.get("possession", "home"))
        receiving = cls.opposite(kicking)
        state["possession"] = kicking
        state["special_game_phase"] = "kickoff"
        state["kicking_team"] = kicking
        state["receiving_team"] = receiving
        state["down"] = "Off"
        state["distance"] = "Off"
        state["ball_spot"] = cls._team_own_yard_spot(state, kicking, 40)
        state["clock_running"] = False
        state["clock_started_at"] = 0

    @classmethod
    def enter_free_kick(cls, state: dict[str, Any], kicking_team: str) -> None:
        kicking = kicking_team if kicking_team in cls.VALID_TEAMS else str(state.get("possession", "home"))
        receiving = cls.opposite(kicking)
        state["possession"] = receiving
        state["special_game_phase"] = "free_kick"
        state["kicking_team"] = kicking
        state["receiving_team"] = receiving
        state["down"] = "Off"
        state["distance"] = "Off"
        state["ball_spot"] = cls._team_own_yard_spot(state, kicking, 20)
        state["clock_running"] = False
        state["clock_started_at"] = 0

    @classmethod
    def clear_special_phase(cls, state: dict[str, Any]) -> None:
        state["special_game_phase"] = ""
        state["kicking_team"] = ""
        state["receiving_team"] = ""

    @classmethod
    def _apply_scrimmage_play(
        cls,
        state: dict[str, Any],
        play: dict[str, Any],
    ) -> None:
        team = str(play.get("offense", state.get("possession", "home")) or "home").lower()
        if team not in cls.VALID_TEAMS:
            team = cls.team_roles(state).offense
        kind = str(play.get("play_type", "") or "").lower()
        if kind not in {"run", "pass"}:
            return
        direction = -1 if str(state.get(f"{team}_direction", "right")) == "left" else 1
        start = cls._spot_to_coord(state.get("ball_spot") or play.get("ball_spot") or 50)
        try:
            yards = int(play.get("yards", 0) or 0)
        except (TypeError, ValueError):
            yards = 0
        outcome = str(play.get("pass_outcome", "") or "").lower()
        if kind == "pass" and outcome in {"incomplete", "spike"}:
            yards = 0
        end = max(0, min(100, start + (yards * direction)))
        play["ball_spot"] = cls._coord_to_spot(start)
        play["end_spot"] = cls._coord_to_spot(end)

        old_down = str(state.get("down", "1st") or "1st")
        old_distance_text = str(state.get("distance", "10") or "10")
        try:
            distance = 10 if old_distance_text in {"Off", "Goal", ""} else max(1, int(old_distance_text))
        except ValueError:
            distance = 10
        touchdown = (direction == 1 and end == 100) or (direction == -1 and end == 0)
        safety = (direction == 1 and end == 0) or (direction == -1 and end == 100)
        turnover = bool(play.get("turnover"))
        turnover_type = str(play.get("turnover_type", "") or "").lower()
        if turnover:
            turnover_spot = cls._spot_to_coord(
                play.get("turnover_spot") or play.get("end_spot") or cls._coord_to_spot(end)
            )
            return_end = cls._spot_to_coord(
                play.get("return_end_spot") or play.get("end_spot") or cls._coord_to_spot(turnover_spot)
            )
            end = return_end
            play["turnover_spot"] = cls._coord_to_spot(turnover_spot)
            play["return_end_spot"] = cls._coord_to_spot(return_end)
            gaining_team = str(play.get("turnover_team", "") or cls.opposite(team)).lower()
            if gaining_team not in cls.VALID_TEAMS:
                gaining_team = cls.opposite(team)
            play["turnover_team"] = gaining_team
            play["turnover_type"] = turnover_type or (
                "interception" if outcome == "interception" else "fumble_recovery"
            )
            return_direction = -1 if str(state.get(f"{gaining_team}_direction", "left")) == "left" else 1
            play["return_yards"] = max(0, (return_end - turnover_spot) * return_direction)
            turnover_touchdown = bool(play.get("touchdown")) or (
                (return_direction == 1 and return_end == 100)
                or (return_direction == -1 and return_end == 0)
            )
            touchdown = turnover_touchdown
            safety = False
        if turnover and touchdown:
            state[f"{play['turnover_team']}_score"] = int(state.get(f"{play['turnover_team']}_score", 0) or 0) + 6
            cls.enter_pending_try(state, play["turnover_team"])
        elif touchdown:
            state[f"{team}_score"] = int(state.get(f"{team}_score", 0) or 0) + 6
            cls.enter_pending_try(state, team)
        elif safety:
            other = cls.opposite(team)
            state[f"{other}_score"] = int(state.get(f"{other}_score", 0) or 0) + 2
            cls.enter_free_kick(state, team)
        elif turnover:
            state["possession"] = str(play.get("turnover_team") or cls.opposite(team))
            state["down"] = "1st"
            state["distance"] = "10"
        else:
            first_down = yards >= distance
            if first_down:
                state["down"] = "1st"
                state["distance"] = "10"
            else:
                order = {"1st": "2nd", "2nd": "3rd", "3rd": "4th", "4th": "1st"}
                state["down"] = order.get(old_down, "1st")
                state["distance"] = str(max(1, distance - yards))
                if old_down == "4th":
                    state["possession"] = cls.opposite(team)
                    state["down"] = "1st"
                    state["distance"] = "10"
                    turnover = True
                    play["turnover_type"] = "downs"
                    play["turnover_team"] = cls.opposite(team)
                    play["turnover_spot"] = cls._coord_to_spot(end)
                    play["return_end_spot"] = cls._coord_to_spot(end)
                    play["return_yards"] = 0
            play["first_down"] = first_down
        state["ball_spot"] = cls._coord_to_spot(end)
        play["touchdown"] = touchdown
        play["safety"] = safety
        play["turnover"] = turnover
        play["resulting_down"] = str(state.get("down", ""))
        play["resulting_distance"] = str(state.get("distance", ""))

    @classmethod
    def rebuild(
        cls,
        current_state: Mapping[str, Any],
        events: list[dict[str, Any]],
        plays: list[dict[str, Any]],
        *,
        baseline: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Rebuild dependent canonical game state from ordered canonical history.

        Supported scrimmage PLAY records are reduced from their canonical fields;
        other event types retain their recorded after-state until their dedicated
        Gate 18.4 repair batches replace those higher-level workflows.
        """
        rebuilt = copy.deepcopy(dict(current_state))
        ordered_events = [row for row in events if isinstance(row, dict) and not row.get("undone")]
        ordered_events.sort(key=lambda row: (int(row.get("play_number", 0) or 0), int(row.get("created_at", 0) or 0)))
        play_by_event = {
            str(row.get("event_id", "")): row
            for row in plays
            if isinstance(row, dict) and not row.get("undone")
        }
        play_by_id = {
            str(row.get("play_id", "")): row
            for row in plays
            if isinstance(row, dict) and not row.get("undone")
        }
        seed = dict(baseline or (ordered_events[0].get("before") if ordered_events else {}) or {})
        for field in CANONICAL_FIELDS:
            if field in seed:
                rebuilt[field] = copy.deepcopy(seed[field])
        for event in ordered_events:
            event["before"] = cls.snapshot(rebuilt)
            play = play_by_event.get(str(event.get("id", ""))) or play_by_id.get(str(event.get("play_id", "")))
            if str(event.get("event", "")).upper() == "PLAY" and play and str(play.get("play_type", "")).lower() in {"run", "pass"}:
                cls._apply_scrimmage_play(rebuilt, play)
            else:
                recorded_before = event.get("before") if isinstance(event.get("before"), Mapping) else {}
                after = event.get("after") if isinstance(event.get("after"), Mapping) else {}
                # Replay only the canonical fields this event actually changed.
                # This prevents a later score-only event from reintroducing an
                # obsolete ball spot/down value after an earlier play is edited.
                for field in CANONICAL_FIELDS:
                    if field in after and (field not in recorded_before or after.get(field) != recorded_before.get(field)):
                        rebuilt[field] = copy.deepcopy(after[field])
            event["after"] = cls.snapshot(rebuilt)
        rebuilt["events"] = ordered_events
        rebuilt["plays"] = [row for row in plays if isinstance(row, dict) and not row.get("undone")]
        rebuilt["player_eligibility"] = EligibilityService.derive(rebuilt)
        rebuilt["last_event"] = copy.deepcopy(ordered_events[-1]) if ordered_events else {}
        if ordered_events:
            rebuilt["next_play_number"] = max(int(row.get("play_number", 0) or 0) for row in ordered_events) + 1
        else:
            rebuilt["next_play_number"] = 1
        return rebuilt
