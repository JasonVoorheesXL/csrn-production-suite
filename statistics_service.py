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
        if lowered in {
            "home",
            str(state.get("home_team", "")).strip().lower(),
        }:
            return "home"
        if lowered in {
            "visitor",
            "away",
            str(state.get("visitor_team", "")).strip().lower(),
        }:
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
            return int(str(value or fallback))
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _active_rows(
        rows: Any,
        broadcast_id: str,
    ) -> list[dict[str, Any]]:
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
            "extra_points": 0,
            "two_point_conversions": 0,
            "turnovers_gained": 0,
            "rushing_attempts": 0,
            "rushing_yards": 0,
            "pass_attempts": 0,
            "completions": 0,
            "passing_yards": 0,
            "interceptions": 0,
            "total_plays": 0,
            "total_yards": 0,
        }

    @staticmethod
    def _player_row(
        teams: Mapping[str, Mapping[str, Any]],
        team: str,
        name: Any,
        number: Any,
    ) -> dict[str, Any] | None:
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
            "passing_touchdowns": 0,
            "field_goals": 0,
            "extra_points": 0,
            "two_point_conversions": 0,
            "points": 0,
            "rushing_attempts": 0,
            "rushing_yards": 0,
            "pass_attempts": 0,
            "completions": 0,
            "passing_yards": 0,
            "receptions": 0,
            "receiving_yards": 0,
            "interceptions_thrown": 0,
            "fumbles": 0,
            "fumbles_lost": 0,
        }

    @staticmethod
    def _player_key(team: str, name: Any, number: Any) -> str:
        return (
            f"{team}|{str(number or '').strip()}|"
            f"{str(name or '').strip().casefold()}"
        )

    @staticmethod
    def _player_sort_key(player: Mapping[str, Any]) -> tuple[Any, ...]:
        number = str(player.get("number", ""))
        number_key = int(number) if number.isdigit() else 999999
        return (
            str(player.get("team_name", "")),
            number_key,
            str(player.get("name", "")),
        )

    def report(self, state: Mapping[str, Any] | None) -> StatisticsResult:
        source_state = dict(state or {})
        broadcast_id = str(source_state.get("broadcast_id", "") or "")
        events = self._active_rows(source_state.get("events"), broadcast_id)
        plays = self._active_rows(source_state.get("plays"), broadcast_id)
        event_by_id = {
            str(event.get("id", "")): event
            for event in events
            if str(event.get("id", ""))
        }

        teams: dict[str, dict[str, Any]] = {
            "home": self._team_row(
                source_state.get("home_team") or "Home",
                source_state.get("home_score", 0),
            ),
            "visitor": self._team_row(
                source_state.get("visitor_team") or "Visitor",
                source_state.get("visitor_score", 0),
            ),
        }
        players: dict[str, dict[str, Any]] = {}

        def player_row(team: str, name: Any, number: Any) -> dict[str, Any] | None:
            key = self._player_key(team, name, number)
            if key not in players:
                row = self._player_row(teams, team, name, number)
                if row is None:
                    return None
                players[key] = row
            return players[key]

        scoring_summary: list[dict[str, Any]] = []
        touchdown_play_ids: set[str] = set()

        for event in events:
            team = self.canonical_team_key(source_state, event.get("team", ""))
            if team not in teams:
                continue
            code = str(event.get("event", "")).upper()
            automation = (
                event.get("automation")
                if isinstance(event.get("automation"), dict)
                else {}
            )
            delta = self._safe_int(event.get("score_delta", 0))
            touchdown = bool(
                code == "TD"
                or (code == "TURNOVER" and automation.get("return_td"))
                or automation.get("touchdown")
            )
            if touchdown:
                teams[team]["touchdowns"] += 1
                play_id = str(event.get("play_id", "") or "")
                if play_id:
                    touchdown_play_ids.add(play_id)
            elif code == "FG":
                teams[team]["field_goals"] += 1
            elif code == "XP":
                teams[team]["extra_points"] += 1
            elif code == "2PT":
                teams[team]["two_point_conversions"] += 1

            if code == "TURNOVER":
                teams[team]["turnovers_gained"] += 1

            scorer = player_row(
                team,
                automation.get("player_name", ""),
                automation.get("player_number", ""),
            )
            if scorer is not None:
                scorer["points"] += delta
                if touchdown:
                    scorer["touchdowns"] += 1
                elif code == "FG":
                    scorer["field_goals"] += 1
                elif code == "XP":
                    scorer["extra_points"] += 1
                elif code == "2PT":
                    scorer["two_point_conversions"] += 1

            if delta:
                after = (
                    event.get("after")
                    if isinstance(event.get("after"), dict)
                    else {}
                )
                scoring_summary.append(
                    {
                        "quarter": str(event.get("quarter", "")),
                        "team": team,
                        "team_name": teams[team]["name"],
                        "label": str(event.get("label") or code),
                        "description": str(event.get("description") or code),
                        "points": delta,
                        "home_score": self._safe_int(after.get("home_score", 0)),
                        "visitor_score": self._safe_int(
                            after.get("visitor_score", 0)
                        ),
                        "created_at": self._safe_int(event.get("created_at", 0)),
                    }
                )

        normalized_plays: list[dict[str, Any]] = []
        for source_play in plays:
            play = copy.deepcopy(source_play)
            offense = self.canonical_team_key(
                source_state,
                play.get("offense", ""),
            )
            defense = self.canonical_team_key(
                source_state,
                play.get("defense", ""),
            )
            play["offense"] = offense
            play["defense"] = defense
            play["offense_name"] = self.canonical_team_name(
                source_state,
                offense,
            )
            play["defense_name"] = self.canonical_team_name(
                source_state,
                defense,
            )
            normalized_plays.append(play)

            kind = str(play.get("play_type", "")).lower()
            if offense not in teams or kind not in {"run", "pass"}:
                if play.get("turnover") and defense in teams:
                    linked = event_by_id.get(str(play.get("event_id", "")), {})
                    if str(linked.get("event", "")).upper() != "TURNOVER":
                        teams[defense]["turnovers_gained"] += 1
                continue

            yards = self._safe_int(play.get("yards", 0))
            teams[offense]["total_plays"] += 1
            teams[offense]["total_yards"] += yards
            ball_carrier = player_row(
                offense,
                play.get("player_name", ""),
                play.get("player_number", ""),
            )
            passer = player_row(
                offense,
                play.get("passer_name", ""),
                play.get("passer_number", ""),
            )

            if kind == "run":
                teams[offense]["rushing_attempts"] += 1
                teams[offense]["rushing_yards"] += yards
                if ball_carrier is not None:
                    ball_carrier["rushing_attempts"] += 1
                    ball_carrier["rushing_yards"] += yards
            else:
                linked = event_by_id.get(str(play.get("event_id", "")), {})
                linked_automation = (
                    linked.get("automation")
                    if isinstance(linked.get("automation"), dict)
                    else {}
                )
                outcome = str(
                    play.get("pass_outcome")
                    or linked_automation.get("pass_outcome")
                    or "complete"
                ).lower()
                teams[offense]["pass_attempts"] += 1
                if passer is not None:
                    passer["pass_attempts"] += 1
                if outcome == "complete":
                    teams[offense]["completions"] += 1
                    teams[offense]["passing_yards"] += yards
                    if passer is not None:
                        passer["completions"] += 1
                        passer["passing_yards"] += yards
                    if ball_carrier is not None:
                        ball_carrier["receptions"] += 1
                        ball_carrier["receiving_yards"] += yards
                    if play.get("touchdown") and passer is not None:
                        passer["passing_touchdowns"] += 1
                elif outcome == "interception":
                    teams[offense]["interceptions"] += 1
                    if passer is not None:
                        passer["interceptions_thrown"] += 1

            if play.get("fumble") and ball_carrier is not None:
                ball_carrier["fumbles"] += 1
            if play.get("fumble_lost") and ball_carrier is not None:
                ball_carrier["fumbles_lost"] += 1

            if play.get("turnover") and defense in teams:
                linked = event_by_id.get(str(play.get("event_id", "")), {})
                if str(linked.get("event", "")).upper() != "TURNOVER":
                    teams[defense]["turnovers_gained"] += 1

            play_id = str(play.get("play_id", "") or "")
            if play.get("touchdown") and play_id not in touchdown_play_ids:
                teams[offense]["touchdowns"] += 1
                touchdown_player = ball_carrier
                if touchdown_player is not None:
                    touchdown_player["touchdowns"] += 1

        for team in teams.values():
            team["yards_per_play"] = (
                round(team["total_yards"] / team["total_plays"], 1)
                if team["total_plays"]
                else 0
            )

        report = {
            "broadcast_id": broadcast_id,
            "sport": str(source_state.get("sport") or "Football"),
            "season": source_state.get("season", ""),
            "date": source_state.get("date", ""),
            "venue": source_state.get("venue", ""),
            "quarter": str(source_state.get("quarter", "")),
            "status": str(source_state.get("status", "")),
            "teams": teams,
            "players": sorted(players.values(), key=self._player_sort_key),
            "scoring_summary": scoring_summary,
            "play_register": normalized_plays,
            "event_count": len(events),
            "play_count": len(plays),
            "scoring_event_count": len(scoring_summary),
            "generated_at": int(self._now()),
            "note": self.NOTE,
        }
        return StatisticsResult("OK", {"statistics": report})
