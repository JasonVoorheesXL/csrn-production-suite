from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class StatisticsResult:
    code: str
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class StatisticsService:
    """Derive broadcast statistics from canonical events and Play Register rows."""

    NOTE = "Statistics are derived from canonical Play Register records and scoring events."

    def __init__(self, *, now: Callable[[], float] = time.time) -> None:
        self._now = now

    @staticmethod
    def canonical_team_key(state: Mapping[str, Any], value: Any) -> str:
        text = str(value or "").strip()
        lowered = text.lower()
        if lowered in {"home", str(state.get("home_team", "")).strip().lower()}:
            return "home"
        if lowered in {"visitor", "away", str(state.get("visitor_team", "")).strip().lower()}:
            return "visitor"
        return text

    @classmethod
    def canonical_team_name(cls, state: Mapping[str, Any], value: Any) -> str:
        key = cls.canonical_team_key(state, value)
        if key == "home":
            return str(state.get("home_team") or "Home")
        if key == "visitor":
            return str(state.get("visitor_team") or "Visitor")
        return str(value or "")

    @staticmethod
    def _safe_int(value: Any, fallback: int = 0) -> int:
        try:
            return int(str(value if value not in (None, "") else fallback))
        except (TypeError, ValueError):
            return fallback

    # UTF-8 text that was once decoded as Windows-1252 and re-saved leaves a
    # fixed mojibake signature (leading "â€"). The report is a
    # coach-facing document, so any historical play text carrying this is
    # repaired on the way out. The upstream root cause (a corrupted em-dash
    # literal in rules_service.py) is fixed separately; this covers already
    # persisted games.
    _MOJIBAKE_REPAIRS = {
        "â€”": "—",  # em dash
        "â€“": "–",  # en dash
        "â€™": "’",  # right single quote / apostrophe
        "â€˜": "‘",  # left single quote
        "â€œ": "“",  # left double quote
        "â€": "”",  # right double quote
        "â€¦": "…",  # ellipsis
    }

    @classmethod
    def _repair_text(cls, value: Any) -> Any:
        if not isinstance(value, str) or "â€" not in value:
            return value
        for bad, good in cls._MOJIBAKE_REPAIRS.items():
            value = value.replace(bad, good)
        return value

    @staticmethod
    def _active_rows(rows: Any, broadcast_id: str) -> list[dict[str, Any]]:
        if not isinstance(rows, list):
            return []
        active: list[dict[str, Any]] = []
        for source in rows:
            if not isinstance(source, dict) or source.get("undone"):
                continue
            row_broadcast = str(source.get("broadcast_id", "") or "")
            if broadcast_id and row_broadcast and row_broadcast != broadcast_id:
                continue
            active.append(source)
        return active

    @staticmethod
    def _team_row(name: Any, score: Any) -> dict[str, Any]:
        return {
            "name": str(name),
            "score": StatisticsService._safe_int(score),
            "touchdowns": 0,
            "field_goals": 0,
            "field_goal_attempts": 0,
            "extra_points": 0,
            "extra_point_attempts": 0,
            "two_point_conversions": 0,
            "two_point_attempts": 0,
            "turnovers_gained": 0,
            "interceptions_gained": 0,
            "fumble_recoveries": 0,
            "sacks": 0,
            "rushing_attempts": 0,
            "rushing_yards": 0,
            "pass_attempts": 0,
            "completions": 0,
            "passing_yards": 0,
            "interceptions": 0,
            "receptions": 0,
            "receiving_yards": 0,
            "kickoff_returns": 0,
            "kickoff_return_yards": 0,
            "punt_returns": 0,
            "punt_return_yards": 0,
            "kickoffs": 0,
            "punts": 0,
            "total_plays": 0,
            "total_yards": 0,
        }

    @staticmethod
    def _player_row(teams: Mapping[str, Mapping[str, Any]], team: str, name: Any, number: Any) -> dict[str, Any] | None:
        player_name = str(name or "").strip()
        player_number = str(number or "").strip()
        if not player_name and not player_number:
            return None
        return {
            "team": team,
            "team_name": str(teams.get(team, {}).get("name", "")),
            "name": player_name or f"Player {player_number}",
            "number": player_number,
            "touchdowns": 0,
            "rushing_touchdowns": 0,
            "receiving_touchdowns": 0,
            "return_touchdowns": 0,
            "passing_touchdowns": 0,
            "field_goals": 0,
            "field_goal_attempts": 0,
            "extra_points": 0,
            "extra_point_attempts": 0,
            "two_point_conversions": 0,
            "two_point_attempts": 0,
            "points": 0,
            "rushing_attempts": 0,
            "rushing_yards": 0,
            "pass_attempts": 0,
            "completions": 0,
            "passing_yards": 0,
            "receptions": 0,
            "receiving_yards": 0,
            "targets": 0,
            "interceptions_thrown": 0,
            "fumbles": 0,
            "fumbles_lost": 0,
            "kickoff_returns": 0,
            "kickoff_return_yards": 0,
            "punt_returns": 0,
            "punt_return_yards": 0,
            "kickoffs": 0,
            "punts": 0,
            "interceptions": 0,
            "defensive_interceptions": 0,
            "fumble_recoveries": 0,
            "muff_recoveries": 0,
            "turnover_return_yards": 0,
            "sacks": 0,
        }

    @staticmethod
    def _player_key(team: str, name: Any, number: Any) -> str:
        return f"{team}|{str(number or '').strip()}|{str(name or '').strip().casefold()}"

    @staticmethod
    def _player_sort_key(player: Mapping[str, Any]) -> tuple[Any, ...]:
        number = str(player.get("number", ""))
        number_key = int(number) if number.isdigit() else 999999
        return (str(player.get("team_name", "")), number_key, str(player.get("name", "")))

    def report(self, state: Mapping[str, Any] | None) -> StatisticsResult:
        source_state = dict(state or {})
        broadcast_id = str(source_state.get("broadcast_id", "") or "")
        events = self._active_rows(source_state.get("events"), broadcast_id)
        plays = self._active_rows(source_state.get("plays"), broadcast_id)
        event_by_id = {str(event.get("id", "")): event for event in events if str(event.get("id", ""))}

        teams: dict[str, dict[str, Any]] = {
            "home": self._team_row(source_state.get("home_team") or "Home", source_state.get("home_score", 0)),
            "visitor": self._team_row(source_state.get("visitor_team") or "Visitor", source_state.get("visitor_score", 0)),
        }
        players: dict[str, dict[str, Any]] = {}

        def player_row(team: str, name: Any, number: Any) -> dict[str, Any] | None:
            if team not in teams:
                return None
            key = self._player_key(team, name, number)
            if key not in players:
                row = self._player_row(teams, team, name, number)
                if row is None:
                    return None
                players[key] = row
            return players[key]

        scoring_summary: list[dict[str, Any]] = []
        touchdown_play_ids: set[str] = set()
        turnover_event_keys: set[str] = set()

        for event in events:
            team = self.canonical_team_key(source_state, event.get("team", ""))
            if team not in teams:
                continue
            code = str(event.get("event", "")).upper()
            automation = event.get("automation") if isinstance(event.get("automation"), dict) else {}
            delta = self._safe_int(event.get("score_delta", 0))
            conversion_outcome = str(event.get("conversion_outcome") or automation.get("conversion_outcome") or "").lower()
            kick_outcome = str(event.get("kick_outcome") or automation.get("kick_outcome") or "").lower()
            touchdown = bool(code == "TD" or (code == "TURNOVER" and automation.get("return_td")) or automation.get("touchdown"))

            if touchdown:
                teams[team]["touchdowns"] += 1
                play_id = str(event.get("play_id", "") or "")
                if play_id:
                    touchdown_play_ids.add(play_id)
            elif code == "FG":
                teams[team]["field_goal_attempts"] += 1
                if kick_outcome in {"", "made"} and delta == 3:
                    teams[team]["field_goals"] += 1
            elif code == "XP":
                teams[team]["extra_point_attempts"] += 1
                if conversion_outcome in {"", "good"} and delta == 1:
                    teams[team]["extra_points"] += 1
            elif code == "2PT":
                teams[team]["two_point_attempts"] += 1
                if conversion_outcome in {"", "good"} and delta == 2:
                    teams[team]["two_point_conversions"] += 1

            if code == "TURNOVER":
                key = str(event.get("id") or event.get("play_id") or id(event))
                turnover_event_keys.add(key)
                teams[team]["turnovers_gained"] += 1
                turnover_type = str(automation.get("turnover_type", "") or "").lower()
                if turnover_type == "interception":
                    teams[team]["interceptions_gained"] += 1
                elif turnover_type in {"fumble", "fumble_recovery", "muff_recovery"}:
                    teams[team]["fumble_recoveries"] += 1
                defender = player_row(team, automation.get("turnover_player_name", ""), automation.get("turnover_player_number", ""))
                if defender is not None:
                    if turnover_type == "interception":
                        defender["interceptions"] += 1
                        defender["defensive_interceptions"] += 1
                    elif turnover_type == "muff_recovery":
                        defender["muff_recoveries"] += 1
                    elif turnover_type in {"fumble", "fumble_recovery", "kicking_team_recovery"}:
                        defender["fumble_recoveries"] += 1
                    defender["turnover_return_yards"] += self._safe_int(
                        automation.get("return_yards", 0)
                    )

            scorer = player_row(team, automation.get("player_name", ""), automation.get("player_number", ""))
            if scorer is not None:
                scorer["points"] += delta
                if touchdown:
                    scorer["touchdowns"] += 1
                elif code == "FG":
                    scorer["field_goal_attempts"] += 1
                    if delta == 3:
                        scorer["field_goals"] += 1
                elif code == "XP":
                    scorer["extra_point_attempts"] += 1
                    if delta == 1:
                        scorer["extra_points"] += 1
                elif code == "2PT":
                    scorer["two_point_attempts"] += 1
                    if delta == 2:
                        scorer["two_point_conversions"] += 1

            if delta:
                after = event.get("after") if isinstance(event.get("after"), dict) else {}
                scoring_summary.append({
                    "quarter": str(event.get("quarter", "")),
                    "team": team,
                    "team_name": teams[team]["name"],
                    "label": str(event.get("label") or code),
                    "description": self._repair_text(str(event.get("description") or code)),
                    "points": delta,
                    "home_score": self._safe_int(after.get("home_score", 0)),
                    "visitor_score": self._safe_int(after.get("visitor_score", 0)),
                    "created_at": self._safe_int(event.get("created_at", 0)),
                })

        normalized_plays: list[dict[str, Any]] = []
        for source_play in plays:
            play = copy.deepcopy(source_play)
            offense = self.canonical_team_key(source_state, play.get("offense", ""))
            defense = self.canonical_team_key(source_state, play.get("defense", ""))
            play["offense"] = offense
            play["defense"] = defense
            play["offense_name"] = self.canonical_team_name(source_state, offense)
            play["defense_name"] = self.canonical_team_name(source_state, defense)
            for text_field in ("result", "description", "label"):
                if text_field in play:
                    play[text_field] = self._repair_text(play[text_field])
            normalized_plays.append(play)

            kind = str(play.get("play_type", "")).lower()
            yards = self._safe_int(play.get("yards", 0))
            linked = event_by_id.get(str(play.get("event_id", "")), {})
            linked_automation = linked.get("automation") if isinstance(linked.get("automation"), dict) else {}

            if kind in {"run", "pass"} and offense in teams:
                teams[offense]["total_plays"] += 1
                teams[offense]["total_yards"] += yards
                ball_carrier = player_row(offense, play.get("player_name", ""), play.get("player_number", ""))
                passer = player_row(offense, play.get("passer_name", ""), play.get("passer_number", ""))
                receiver = None

                if kind == "run":
                    teams[offense]["rushing_attempts"] += 1
                    teams[offense]["rushing_yards"] += yards
                    if ball_carrier is not None:
                        ball_carrier["rushing_attempts"] += 1
                        ball_carrier["rushing_yards"] += yards
                        if play.get("touchdown"):
                            ball_carrier["rushing_touchdowns"] += 1
                else:
                    outcome = str(play.get("pass_outcome") or linked_automation.get("pass_outcome") or "complete").lower()
                    if outcome == "complete":
                        receiver = player_row(
                            offense,
                            play.get("receiver_name") or play.get("player_name", ""),
                            play.get("receiver_number") or play.get("player_number", ""),
                        )
                    elif outcome == "incomplete":
                        receiver = player_row(
                            offense,
                            play.get("intended_receiver_name") or play.get("receiver_name", ""),
                            play.get("intended_receiver_number") or play.get("receiver_number", ""),
                        )
                    else:
                        receiver = player_row(offense, play.get("receiver_name", ""), play.get("receiver_number", ""))
                    # Sacks are team pass plays in the gamebook but not pass attempts.
                    if outcome not in {"sack"}:
                        teams[offense]["pass_attempts"] += 1
                        if passer is not None:
                            passer["pass_attempts"] += 1
                    if receiver is not None and outcome not in {"sack", "spike"}:
                        receiver["targets"] += 1
                    if outcome == "complete":
                        teams[offense]["completions"] += 1
                        teams[offense]["passing_yards"] += yards
                        teams[offense]["receptions"] += 1
                        teams[offense]["receiving_yards"] += yards
                        if passer is not None:
                            passer["completions"] += 1
                            passer["passing_yards"] += yards
                        if receiver is not None:
                            receiver["receptions"] += 1
                            receiver["receiving_yards"] += yards
                            if play.get("touchdown"):
                                receiver["receiving_touchdowns"] += 1
                        if play.get("touchdown") and passer is not None:
                            passer["passing_touchdowns"] += 1
                    elif outcome == "interception":
                        teams[offense]["interceptions"] += 1
                        if passer is not None:
                            passer["interceptions_thrown"] += 1
                    elif outcome == "sack" and defense in teams:
                        teams[defense]["sacks"] += 1
                        sacker = player_row(defense, play.get("sacker_name", ""), play.get("sacker_number", ""))
                        if sacker is not None:
                            sacker["sacks"] += 1

                if play.get("fumble") and ball_carrier is not None:
                    ball_carrier["fumbles"] += 1
                if play.get("fumble_lost") and ball_carrier is not None:
                    ball_carrier["fumbles_lost"] += 1

                play_id = str(play.get("play_id", "") or "")
                if play.get("touchdown") and play_id not in touchdown_play_ids:
                    teams[offense]["touchdowns"] += 1
                    td_player = receiver if kind == "pass" else ball_carrier
                    if td_player is not None:
                        td_player["touchdowns"] += 1

            elif kind in {"kickoff", "punt"}:
                receiving = offense
                kicking = self.canonical_team_key(source_state, play.get("kicking_team") or defense)
                return_yards = self._safe_int(play.get("return_yards", 0))
                fair_catch = "fair catch" in str(play.get("result", "")).lower()
                touchback = "touchback" in str(play.get("result", "")).lower()
                if kicking in teams:
                    teams[kicking]["kickoffs" if kind == "kickoff" else "punts"] += 1
                    kicker = player_row(kicking, play.get("kicker_name", ""), play.get("kicker_number", ""))
                    if kicker is not None:
                        kicker["kickoffs" if kind == "kickoff" else "punts"] += 1
                if receiving in teams and not fair_catch and not touchback and (play.get("returner_number") or play.get("returner_name")):
                    key = "kickoff_returns" if kind == "kickoff" else "punt_returns"
                    yards_key = "kickoff_return_yards" if kind == "kickoff" else "punt_return_yards"
                    teams[receiving][key] += 1
                    teams[receiving][yards_key] += return_yards
                    returner = player_row(receiving, play.get("returner_name", ""), play.get("returner_number", ""))
                    if returner is not None:
                        returner[key] += 1
                        returner[yards_key] += return_yards
                        if play.get("touchdown"):
                            returner["return_touchdowns"] += 1
                            if str(play.get("play_id", "")) not in touchdown_play_ids:
                                returner["touchdowns"] += 1

            if play.get("turnover") and defense in teams:
                linked_code = str(linked.get("event", "")).upper()
                # PLAY-based turnovers are not separate TURNOVER events. Count them once here.
                if linked_code != "TURNOVER":
                    teams[defense]["turnovers_gained"] += 1
                    turnover_type = str(play.get("turnover_type", "") or linked_automation.get("turnover_type", "")).lower()
                    defender = player_row(defense, play.get("turnover_player_name", ""), play.get("turnover_player_number", ""))
                    if turnover_type == "interception":
                        teams[defense]["interceptions_gained"] += 1
                        if defender is not None:
                            defender["interceptions"] += 1
                            defender["defensive_interceptions"] += 1
                    elif turnover_type == "muff_recovery":
                        teams[defense]["fumble_recoveries"] += 1
                        if defender is not None:
                            defender["muff_recoveries"] += 1
                    elif turnover_type in {"fumble", "fumble_recovery", "kicking_team_recovery"}:
                        teams[defense]["fumble_recoveries"] += 1
                        if defender is not None:
                            defender["fumble_recoveries"] += 1
                    if defender is not None:
                        defender["turnover_return_yards"] += self._safe_int(play.get("return_yards", 0))

        for team in teams.values():
            team["yards_per_play"] = round(team["total_yards"] / team["total_plays"], 1) if team["total_plays"] else 0

        player_rows = sorted(players.values(), key=self._player_sort_key)
        reconciliation = {
            "canonical_play_count": len(plays),
            "canonical_event_count": len(events),
            "team_rushing_yards": sum(self._safe_int(team["rushing_yards"]) for team in teams.values()),
            "player_rushing_yards": sum(self._safe_int(player["rushing_yards"]) for player in player_rows),
            "team_passing_yards": sum(self._safe_int(team["passing_yards"]) for team in teams.values()),
            "player_passing_yards": sum(self._safe_int(player["passing_yards"]) for player in player_rows),
            "team_receiving_yards": sum(self._safe_int(team["receiving_yards"]) for team in teams.values()),
            "player_receiving_yards": sum(self._safe_int(player["receiving_yards"]) for player in player_rows),
            "team_return_yards": sum(self._safe_int(team["kickoff_return_yards"]) + self._safe_int(team["punt_return_yards"]) for team in teams.values()),
            "player_return_yards": sum(self._safe_int(player["kickoff_return_yards"]) + self._safe_int(player["punt_return_yards"]) for player in player_rows),
        }
        reconciliation["rushing_reconciled"] = reconciliation["team_rushing_yards"] == reconciliation["player_rushing_yards"]
        reconciliation["passing_reconciled"] = reconciliation["team_passing_yards"] == reconciliation["player_passing_yards"]
        reconciliation["receiving_reconciled"] = reconciliation["team_receiving_yards"] == reconciliation["player_receiving_yards"]
        reconciliation["returns_reconciled"] = reconciliation["team_return_yards"] == reconciliation["player_return_yards"]
        reconciliation["all_reconciled"] = all(reconciliation[key] for key in ("rushing_reconciled", "passing_reconciled", "receiving_reconciled", "returns_reconciled"))

        report = {
            "broadcast_id": broadcast_id,
            "sport": str(source_state.get("sport") or "Football"),
            "season": source_state.get("season", ""),
            "date": source_state.get("date", ""),
            "venue": source_state.get("venue", ""),
            "quarter": str(source_state.get("quarter", "")),
            "status": str(source_state.get("status", "")),
            "teams": teams,
            "players": player_rows,
            "scoring_summary": scoring_summary,
            "play_register": normalized_plays,
            "event_count": len(events),
            "play_count": len(plays),
            "scoring_event_count": len(scoring_summary),
            "generated_at": int(self._now()),
            "reconciliation": reconciliation,
            "note": self.NOTE,
        }
        return StatisticsResult("OK", {"statistics": report})
