from __future__ import annotations

import copy
from typing import Any, Mapping


class TickerPolicyService:
    """Derive the broadcast ticker view from canonical event history.

    Gate 18.4 R10 keeps ticker policy out of overlay/theme JavaScript so every
    browser surface consumes the same lifecycle decisions.
    """

    NONPERSISTENT_WINDOW = 8
    CLOSE_GAME_MARGIN = 8

    TRY_TYPES = {"XP", "EXTRA_POINT", "EXTRA POINT", "2PT", "TWO_POINT", "TWO POINT"}
    TOUCHDOWN_TYPES = {"TD", "TOUCHDOWN"}
    TURNOVER_TYPES = {"TURNOVER", "INTERCEPTION", "FUMBLE", "FUMBLE_RECOVERY", "MUFF_RECOVERY", "TURNOVER_ON_DOWNS"}

    @classmethod
    def build(cls, state: Mapping[str, Any]) -> list[dict[str, Any]]:
        events = [copy.deepcopy(e) for e in list(state.get("events") or []) if isinstance(e, dict) and not e.get("undone")]
        stories: list[dict[str, Any]] = []
        index = 0
        while index < len(events):
            event = events[index]
            kind = cls._kind(event)
            if kind in cls.TOUCHDOWN_TYPES:
                story = cls._item(event)
                story["persistent"] = True
                story["lifecycle"] = "scoring"
                story["repeat_count"] = 1
                source_ids = [str(event.get("id") or event.get("event_id") or "")]
                # A try belongs to the immediately preceding touchdown story when
                # it is the same scoring team and no unrelated canonical event intervenes.
                if index + 1 < len(events):
                    nxt = events[index + 1]
                    if cls._kind(nxt) in cls.TRY_TYPES and cls._same_team(event, nxt):
                        source_ids.append(str(nxt.get("id") or nxt.get("event_id") or ""))
                        td_text = cls._action(event)
                        try_text = cls._action(nxt)
                        story["description"] = " · ".join(x for x in (td_text, try_text) if x)
                        story["after"] = copy.deepcopy(nxt.get("after") or story.get("after") or {})
                        story["try_outcome"] = str(nxt.get("outcome") or nxt.get("result") or nxt.get("label") or "")
                        index += 1
                story["source_ids"] = [x for x in source_ids if x]
                stories.append(story)
            else:
                item = cls._item(event)
                scoring = cls._is_scoring(event)
                close_q4_turnover = cls._is_close_q4_turnover(event)
                important = cls._is_important(event)
                item["persistent"] = bool(scoring or close_q4_turnover)
                item["lifecycle"] = "scoring" if scoring else ("persistent_turnover" if close_q4_turnover else ("important" if important else "routine"))
                item["repeat_count"] = 1 if item["persistent"] else (2 if important else 1)
                item["source_ids"] = [str(event.get("id") or event.get("event_id") or "")]
                stories.append(item)
            index += 1

        persistent = [item for item in stories if item.get("persistent")]
        transient = [item for item in stories if not item.get("persistent")][-cls.NONPERSISTENT_WINDOW :]
        keep_ids = {id(item) for item in persistent + transient}
        kept = [item for item in stories if id(item) in keep_ids]

        return kept

    @classmethod
    def _item(cls, event: Mapping[str, Any]) -> dict[str, Any]:
        item = copy.deepcopy(dict(event))
        item["description"] = cls._action(event)
        return item

    @staticmethod
    def _action(event: Mapping[str, Any]) -> str:
        text = str(event.get("description") or event.get("result") or "").strip()
        if text:
            return text
        label = str(event.get("label") or event.get("event") or event.get("play_type") or "Play").strip()
        delta = event.get("score_delta")
        if delta not in (None, "", 0, "0"):
            return f"{label} +{delta}"
        return label

    @classmethod
    def _kind(cls, event: Mapping[str, Any]) -> str:
        return str(event.get("event") or event.get("label") or event.get("play_type") or "").strip().upper().replace("-", "_")

    @staticmethod
    def _same_team(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
        return str(a.get("team") or a.get("scoring_team") or "") == str(b.get("team") or b.get("scoring_team") or "")

    @classmethod
    def _is_scoring(cls, event: Mapping[str, Any]) -> bool:
        kind = cls._kind(event)
        if kind in cls.TOUCHDOWN_TYPES | cls.TRY_TYPES | {"FG", "FIELD_GOAL", "FIELD GOAL", "SAFETY"}:
            # Failed try/FG records are important but are not persistent scoring stories on their own.
            outcome = str(event.get("outcome") or event.get("result_type") or "").lower()
            if kind in cls.TRY_TYPES | {"FG", "FIELD_GOAL", "FIELD GOAL"} and outcome in {"missed", "no_good", "no-good", "blocked", "failed"}:
                return False
            return True
        try:
            return int(event.get("score_delta") or 0) > 0
        except (TypeError, ValueError):
            return False

    @classmethod
    def _is_important(cls, event: Mapping[str, Any]) -> bool:
        kind = cls._kind(event)
        if kind in cls.TURNOVER_TYPES:
            return True
        if bool(event.get("turnover") or event.get("first_down") or event.get("touchdown") or event.get("safety")):
            return True
        try:
            return abs(int(event.get("yards") or 0)) >= 20
        except (TypeError, ValueError):
            return False

    @classmethod
    def _is_close_q4_turnover(cls, event: Mapping[str, Any]) -> bool:
        if cls._kind(event) not in cls.TURNOVER_TYPES and not bool(event.get("turnover")):
            return False
        quarter = str(event.get("quarter") or (event.get("after") or {}).get("quarter") or "").upper().replace("Q", "")
        if quarter != "4":
            return False
        after = event.get("after") or {}
        try:
            margin = abs(int(after.get("home_score", 0) or 0) - int(after.get("visitor_score", 0) or 0))
        except (TypeError, ValueError):
            return False
        return margin <= cls.CLOSE_GAME_MARGIN

