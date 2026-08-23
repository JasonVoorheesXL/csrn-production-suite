from __future__ import annotations

import copy
import re
from typing import Any, Callable, Mapping


class EligibilityService:
    """Derive in-game player availability from reversible canonical history."""

    VALID_TEAMS = {"home", "visitor"}

    @staticmethod
    def _norm(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip()).casefold()

    @classmethod
    def _number(cls, value: Any) -> str:
        text = str(value or "").strip()
        if text.startswith("#"):
            text = text[1:].strip()
        if text.isdigit():
            return str(int(text))
        return ""

    @classmethod
    def derive(
        cls,
        state: Mapping[str, Any],
        *,
        resolve_player: Callable[[dict[str, Any], str, Any], Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        result = {
            "home": {"ejected": []},
            "visitor": {"ejected": []},
        }
        for event in list(state.get("events") or []):
            if not isinstance(event, dict) or event.get("undone"):
                continue
            if str(event.get("event", "")).upper() != "EJECTION":
                continue
            team = str(event.get("team", "") or "").lower()
            if team not in cls.VALID_TEAMS:
                continue
            payload = event.get("ejection") if isinstance(event.get("ejection"), Mapping) else {}
            if str(payload.get("person_type", "") or "").strip().casefold() != "player":
                continue
            number = cls._number(payload.get("player_number") or payload.get("person_name"))
            player_id = str(payload.get("player_id", "") or "").strip()
            roster_id = str(payload.get("roster_id", "") or "").strip()
            display_name = str(payload.get("player_name") or payload.get("person_name") or "").strip()
            if resolve_player is not None and number and not player_id:
                try:
                    resolved = dict(resolve_player(dict(state), team, number) or {})
                except Exception:
                    resolved = {}
                if resolved.get("resolved"):
                    player_id = str(resolved.get("player_id", "") or "").strip()
                    roster_id = str(resolved.get("roster_id", "") or "").strip()
                    display_name = str(resolved.get("name", "") or display_name).strip()
            result[team]["ejected"].append({
                "event_id": str(event.get("id", "") or ""),
                "player_id": player_id,
                "roster_id": roster_id,
                "number": number,
                "name": display_name,
                "reason": str(payload.get("reason", "") or ""),
            })
        return result

    @classmethod
    def is_eligible(
        cls,
        state: Mapping[str, Any],
        team: str,
        *,
        player_id: Any = "",
        number: Any = "",
        name: Any = "",
        resolve_player: Callable[[dict[str, Any], str, Any], Mapping[str, Any]] | None = None,
    ) -> bool:
        team_key = str(team or "").lower()
        if team_key not in cls.VALID_TEAMS:
            return True
        derived = state.get("player_eligibility")
        if not isinstance(derived, Mapping):
            derived = cls.derive(state, resolve_player=resolve_player)
        entries = ((derived.get(team_key) or {}).get("ejected") or []) if isinstance(derived.get(team_key), Mapping) else []
        pid = str(player_id or "").strip()
        num = cls._number(number)
        normalized_name = cls._norm(name)
        for row in entries:
            if not isinstance(row, Mapping):
                continue
            if pid and str(row.get("player_id", "") or "").strip() == pid:
                return False
            if num and cls._number(row.get("number")) == num:
                return False
            row_name = cls._norm(row.get("name"))
            if normalized_name and row_name and normalized_name == row_name:
                return False
        return True

    @classmethod
    def public_copy(cls, state: Mapping[str, Any]) -> dict[str, Any]:
        value = state.get("player_eligibility")
        if isinstance(value, Mapping):
            return copy.deepcopy(dict(value))
        return cls.derive(state)
