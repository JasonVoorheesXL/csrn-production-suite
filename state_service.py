from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class StateResult:
    code: str
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class StateService:
    """Application-state boundary independent of Flask and filesystem details."""

    VALID_PHASES = {"pregame", "live", "halftime", "postgame", "final"}
    VALID_POSSESSION = {"home", "visitor"}
    VALID_AUTHORITIES = {"broadcaster", "statistician"}
    SAFE_URL_PREFIXES = (
        "/",
        "data:image/svg+xml",
        "http://",
        "https://",
    )

    def __init__(
        self,
        *,
        load_raw: Callable[[], Mapping[str, Any]],
        replace_raw: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        default_state: Callable[[], Mapping[str, Any]],
        persist_linked_snapshot: Callable[[dict[str, Any]], None] | None = None,
        resolve_player: Callable[[dict[str, Any], str, Any], Mapping[str, Any]] | None = None,
        canonical_team_key: Callable[[dict[str, Any], Any], str] | None = None,
        canonical_team_name: Callable[[dict[str, Any], Any], str] | None = None,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._load_raw = load_raw
        self._replace_raw = replace_raw
        self._default_state = default_state
        self._persist_linked_snapshot = persist_linked_snapshot
        self._resolve_player = resolve_player
        self._canonical_team_key = canonical_team_key
        self._canonical_team_name = canonical_team_name
        self._now = now

    def normalize(self, state: Mapping[str, Any] | None) -> dict[str, Any]:
        merged = copy.deepcopy(dict(self._default_state()))
        merged.update(copy.deepcopy(dict(state or {})))

        if merged.get("broadcast_phase") not in self.VALID_PHASES:
            merged["broadcast_phase"] = "pregame"
        if merged.get("possession") not in self.VALID_POSSESSION:
            merged["possession"] = "home"

        for field in (
            "history",
            "events",
            "plays",
            "correction_log",
            "graphics_queue",
        ):
            if not isinstance(merged.get(field), list):
                merged[field] = []

        if not merged["plays"] and merged["events"]:
            merged["plays"] = self._migrate_events_to_plays(merged)

        try:
            merged["next_play_number"] = max(
                1,
                int(merged.get("next_play_number", 1) or 1),
            )
        except (TypeError, ValueError):
            merged["next_play_number"] = 1

        if merged.get("game_data_authority") not in self.VALID_AUTHORITIES:
            merged["game_data_authority"] = "broadcaster"
        merged["statistician_enabled"] = (
            merged.get("game_data_authority") == "statistician"
        )
        return merged

    def load(self) -> StateResult:
        state = self.normalize(self._load_raw())
        if state.get("clock_running"):
            now = int(self._now())
            try:
                started = int(state.get("clock_started_at", 0) or 0)
            except (TypeError, ValueError):
                started = 0

            changed = False
            if started:
                elapsed = max(0, now - started)
                if elapsed:
                    try:
                        remaining = int(state.get("clock_seconds", 0) or 0)
                    except (TypeError, ValueError):
                        remaining = 0
                    state["clock_seconds"] = max(0, remaining - elapsed)
                    state["clock_started_at"] = now
                    if state["clock_seconds"] <= 0:
                        state["clock_running"] = False
                        state["clock_started_at"] = 0
                    changed = True
            else:
                state["clock_started_at"] = now
                changed = True

            if changed:
                self._replace_raw(self.normalize(state))

        return StateResult("OK", {"state": copy.deepcopy(state)})

    def save(self, state: Mapping[str, Any]) -> StateResult:
        normalized = self.normalize(state)
        stored = self._replace_raw(normalized)
        result = self.normalize(stored)
        if (
            str(result.get("broadcast_id", "")).strip()
            and self._persist_linked_snapshot is not None
        ):
            self._persist_linked_snapshot(copy.deepcopy(result))
        return StateResult("OK", {"state": copy.deepcopy(result)})

    def apply_change(
        self,
        changes: Mapping[str, Any],
        *,
        save_undo: bool = True,
    ) -> StateResult:
        state = self.load().data["state"]
        if save_undo:
            self.push_history(state)
        state.update(copy.deepcopy(dict(changes)))
        return self.save(state)

    @staticmethod
    def push_history(state: dict[str, Any]) -> None:
        snapshot = {
            key: copy.deepcopy(value)
            for key, value in state.items()
            if key != "history"
        }
        history = state.setdefault("history", [])
        if not isinstance(history, list):
            history = []
        history.append(snapshot)
        state["history"] = history[-50:]

    def public(self, state: Mapping[str, Any]) -> StateResult:
        result = copy.deepcopy(dict(state))
        for key in ("home_identity", "visitor_identity"):
            identity = result.get(key)
            if isinstance(identity, dict):
                identity["logo"] = self._safe_media_value(identity.get("logo", ""))

        personnel = result.get("personnel_graphic")
        if isinstance(personnel, dict):
            for field in ("headshot", "logo", "sponsor_logo"):
                personnel[field] = self._safe_media_value(personnel.get(field, ""))

        graphic = result.get("player_graphic")
        if isinstance(graphic, dict):
            for field in ("headshot", "team_logo", "sponsor_logo"):
                graphic[field] = self._safe_media_value(graphic.get(field, ""))

        spotlight = result.get("sponsor_spotlight")
        if isinstance(spotlight, dict):
            for field in ("sponsor_logo", "media_url"):
                spotlight[field] = self._safe_media_value(
                    spotlight.get(field, "")
                )

        for item in result.get("graphics_queue", []):
            if not isinstance(item, dict):
                continue
            queued_graphic = item.get("graphic")
            if isinstance(queued_graphic, dict):
                for field in ("headshot", "team_logo", "sponsor_logo"):
                    queued_graphic[field] = self._safe_media_value(
                        queued_graphic.get(field, "")
                    )

        result["plays"] = [
            self._enrich_play(result, source)
            for source in list(result.get("plays") or [])
            if isinstance(source, dict)
        ]
        return StateResult("OK", {"state": result})

    def _migrate_events_to_plays(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        migrated: list[dict[str, Any]] = []
        for event in state.get("events", []):
            if not isinstance(event, dict):
                continue
            try:
                play_number = int(
                    event.get("play_number", len(migrated) + 1)
                    or len(migrated) + 1
                )
            except (TypeError, ValueError):
                play_number = len(migrated) + 1
            before = event.get("before") or {}
            after = event.get("after") or {}
            automation = event.get("automation") or {}
            team = event.get("team", "")
            migrated.append(
                {
                    "play_id": f"{state.get('broadcast_id') or 'GAME'}-{play_number:04d}",
                    "play_number": play_number,
                    "event_id": event.get("id", ""),
                    "broadcast_id": event.get(
                        "broadcast_id",
                        state.get("broadcast_id", ""),
                    ),
                    "quarter": str(
                        event.get(
                            "quarter",
                            after.get("quarter", state.get("quarter", "1")),
                        )
                    ),
                    "clock": str(event.get("clock", "")),
                    "offense": team or before.get("possession", ""),
                    "defense": (
                        "visitor"
                        if team == "home"
                        else "home"
                        if team == "visitor"
                        else ""
                    ),
                    "down": str(before.get("down", "")),
                    "distance": str(before.get("distance", "")),
                    "ball_spot": str(before.get("ball_spot", "")),
                    "play_type": automation.get("play_type")
                    or str(event.get("event", "")).lower(),
                    "result": event.get("description", ""),
                    "yards": automation.get("yards", ""),
                    "first_down": event.get("event") == "FIRST_DOWN",
                    "touchdown": event.get("event") == "TD"
                    or bool(automation.get("return_td")),
                    "turnover": event.get("event") == "TURNOVER",
                    "safety": event.get("event") == "SAFETY",
                    "notes": "",
                    "created_by": event.get("source", "broadcaster"),
                    "created_at": event.get("created_at", 0),
                    "label": event.get("label", event.get("event", "Play")),
                    "undone": bool(event.get("undone", False)),
                }
            )
        return migrated

    @classmethod
    def _safe_media_value(cls, value: Any) -> str:
        text = str(value or "")
        if not text or text.startswith(cls.SAFE_URL_PREFIXES):
            return text
        return ""

    def _enrich_play(
        self,
        state: dict[str, Any],
        source: dict[str, Any],
    ) -> dict[str, Any]:
        play = copy.deepcopy(source)
        offense = self._team_key(state, play.get("offense", ""))
        defense = self._team_key(state, play.get("defense", ""))
        play["offense_name"] = self._team_name(state, offense)
        play["defense_name"] = self._team_name(state, defense)

        role_specs = (
            ("player", offense),
            ("passer", offense),
            ("receiver", offense),
            ("kicker", offense),
            ("returner", defense),
            ("sacker", defense),
        )
        if self._resolve_player is not None:
            for role, team_key in role_specs:
                number_key = f"{role}_number"
                name_key = f"{role}_name"
                number = str(play.get(number_key, "") or "").strip()
                if number and not str(play.get(name_key, "") or "").strip():
                    resolved = self._resolve_player(state, team_key, number)
                    name = str(resolved.get("name", "") or "").strip()
                    if name:
                        play[name_key] = name

        kind = str(play.get("play_type", "") or "").lower()
        yards = play.get("yards", "")
        if kind == "run" and play.get("player_number") and play.get("player_name"):
            suffix = "kneel" if play.get("kneel") else "run"
            play["result"] = (
                f"#{play['player_number']} {play['player_name']} "
                f"{suffix} for {yards} yards"
            )
            if play.get("touchdown"):
                play["result"] += ", touchdown"
            elif play.get("first_down"):
                play["result"] += ", first down"
        elif kind == "pass":
            outcome = str(play.get("pass_outcome", "complete") or "complete").lower()
            passer = (
                f"#{play.get('passer_number', '')} "
                f"{play.get('passer_name', '')}"
            ).strip()
            receiver = (
                f"#{play.get('receiver_number', '')} "
                f"{play.get('receiver_name', '')}"
            ).strip()
            if outcome == "complete" and receiver:
                play["result"] = (
                    f"{passer} complete to {receiver} for {yards} yards"
                ).strip()
                if play.get("touchdown"):
                    play["result"] += ", touchdown"
            elif outcome == "incomplete":
                play["result"] = f"{passer} pass incomplete".strip()
        return play

    def _team_key(self, state: dict[str, Any], value: Any) -> str:
        if self._canonical_team_key is not None:
            return str(self._canonical_team_key(state, value))
        return str(value or "")

    def _team_name(self, state: dict[str, Any], value: Any) -> str:
        if self._canonical_team_name is not None:
            return str(self._canonical_team_name(state, value))
        return str(value or "")
