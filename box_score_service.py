"""Line score + batting/pitching boxes derived from the event ledger (CSRN_
NFHS_Baseball_Softball_Rules_Engine_Spec_2026 Sec.2 "Stat Engine": "Derives
baseball/softball statistics from authoritative events and scorer
classifications."). Read-only reporting layer -- never a second source of
truth: the line score (runs/hits/errors) comes straight from diamond_
state_service's own canonical fields, already correctly maintained by the
reducer; per-player attribution comes from each PLATE_APPEARANCE event's
own payload (batterId, pitcherId, resultCode -- spec Sec.7.2) plus the
`before` snapshot rebuild() stamps on every event, which is what makes it
possible to know who occupied a base at the moment it was scored from
without the payload itself needing to repeat that identity.

report(state) always rebuilds from the ledger first (DiamondStateFoundation.
rebuild(), same as any replay) rather than trusting whatever before/after
stamps a live-play event might or might not already carry -- so a box
score is correct whether it's requested mid-game or after a correction.
"""

from __future__ import annotations

from typing import Any, Mapping

from diamond_state_service import BASES, DiamondStateFoundation

# Sec.7.2 resultCode vocabulary this module understands for attribution.
# An unrecognised/absent resultCode still counts hits/runs/RBI correctly
# (those come from hits/runnerOutcomes, not the code) -- it just can't be
# classified into AB/BB/SO/HBP buckets.
_HIT_CODES = {"1B", "2B", "3B", "HR"}
_NON_AT_BAT_CODES = {"BB", "HBP", "SAC", "CI", "INT"}


def _empty_batting_line() -> dict[str, int]:
    return {"ab": 0, "h": 0, "r": 0, "rbi": 0, "bb": 0, "so": 0, "hbp": 0}


def _empty_pitching_line() -> dict[str, Any]:
    return {"outs_recorded": 0, "h": 0, "r": 0, "bb": 0, "so": 0}


class BoxScoreService:
    @classmethod
    def line_score(cls, state: Mapping[str, Any]) -> dict[str, Any]:
        line_score = state.get("line_score") or {}
        return {
            "home": {
                "innings": list(line_score.get("home") or []),
                "runs": int(state.get("home_score", 0) or 0),
                "hits": int(state.get("home_hits", 0) or 0),
                "errors": int(state.get("home_errors", 0) or 0),
            },
            "visitor": {
                "innings": list(line_score.get("visitor") or []),
                "runs": int(state.get("visitor_score", 0) or 0),
                "hits": int(state.get("visitor_hits", 0) or 0),
                "errors": int(state.get("visitor_errors", 0) or 0),
            },
        }

    @classmethod
    def _rebuilt_events(cls, state: Mapping[str, Any]) -> list[dict[str, Any]]:
        rebuilt = DiamondStateFoundation.rebuild(state, state.get("diamond_events", []))
        return [e for e in rebuilt.get("diamond_events", []) if not e.get("voided")]

    @classmethod
    def batting_box(cls, state: Mapping[str, Any]) -> dict[str, dict[str, int]]:
        box: dict[str, dict[str, int]] = {}
        for event in cls._rebuilt_events(state):
            if event.get("event_type") != "PLATE_APPEARANCE":
                continue
            payload = event.get("payload") or {}
            batter_id = str(payload.get("batterId", "")).strip()
            if not batter_id:
                continue
            line = box.setdefault(batter_id, _empty_batting_line())
            result = str(payload.get("resultCode", "")).upper()
            if result and result not in _NON_AT_BAT_CODES:
                line["ab"] += 1
            if result in _HIT_CODES:
                line["h"] += 1
            elif result == "BB":
                line["bb"] += 1
            elif result == "SO" or result == "K":
                line["so"] += 1
            elif result == "HBP":
                line["hbp"] += 1

            before = event.get("before") or {}
            before_runners = before.get("base_runners") or {}
            rbi_this_pa = 0
            for outcome in payload.get("runnerOutcomes") or []:
                if outcome.get("to") != "score":
                    continue
                src = str(outcome.get("from", ""))
                if src == "batter":
                    # the batter scored on their own play (e.g. a home run)
                    line["r"] += 1
                    rbi_this_pa += 1
                elif src in BASES:
                    occupant = (before_runners.get(src) or {}).get("player_id", "")
                    if occupant:
                        box.setdefault(occupant, _empty_batting_line())["r"] += 1
                    rbi_this_pa += 1
            if rbi_this_pa and result != "E":
                # spec/scorer convention: an error does not credit an RBI.
                line["rbi"] += rbi_this_pa
        return box

    @classmethod
    def pitching_box(cls, state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        box: dict[str, dict[str, Any]] = {}
        for event in cls._rebuilt_events(state):
            if event.get("event_type") != "PLATE_APPEARANCE":
                continue
            payload = event.get("payload") or {}
            pitcher_id = str(payload.get("pitcherId", "")).strip()
            if not pitcher_id:
                continue
            line = box.setdefault(pitcher_id, _empty_pitching_line())
            line["outs_recorded"] += int(payload.get("outsRecorded", 0) or 0)
            if payload.get("hits"):
                line["h"] += int(payload["hits"])
            result = str(payload.get("resultCode", "")).upper()
            if result == "BB":
                line["bb"] += 1
            elif result in {"SO", "K"}:
                line["so"] += 1
            runs_this_pa = sum(1 for o in payload.get("runnerOutcomes") or [] if o.get("to") == "score")
            line["r"] += runs_this_pa
        for line in box.values():
            whole, remainder = divmod(line.pop("outs_recorded"), 3)
            line["ip"] = f"{whole}.{remainder}"
        return box

    @classmethod
    def report(cls, state: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "line_score": cls.line_score(state),
            "batting": cls.batting_box(state),
            "pitching": cls.pitching_box(state),
            # Sec.2 "Stat Engine" honesty note: earned vs. unearned runs is
            # an official-scorer judgment call (Sec.1: "CSRN records the
            # ruling made by the umpire or official scorer... does not make
            # officiating judgment calls") this module does not attempt to
            # infer from errors alone. "r" above is runs ALLOWED, not
            # earned runs -- ER is not reported until a scorer-entered
            # earned/unearned determination exists on the ruling payload.
            "notes": {
                "earned_runs": "not distinguished from runs allowed -- requires an explicit scorer determination not yet modeled",
            },
        }
