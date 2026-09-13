"""Overlay-state serializer -- the engine's OUTPUT side of docs/DIAMOND_
OVERLAY_CONTRACT.md, the field-level contract T1/Phase C's rendering layer
already committed to consuming. Projects diamond_state_service's canonical
fields onto the flat wire shape the (already-shipped) renderer reads, and
closes the one gap that contract document flagged as a P1 leftover:
regulation_innings now comes from the active ruleset's real regulation
length instead of the renderer's own hardcoded-9 fallback (correct for a
7-inning NFHS/MHSAA game; the renderer's shrink/roll math was silently
wrong between innings 7-9 until this existed).

Player NAMES (pitcher_name/batter_name/batter_position) are not resolved
here -- this module only knows player IDs (diamond_state_service's
current_batter_id/current_pitcher_id, lineup_service's slots). Name
resolution against a roster is the caller's job (P4's routes layer, which
has roster_service available); pass them in, or they default to "".
"""

from __future__ import annotations

from typing import Any, Mapping

import ruleset_service
from diamond_state_service import DiamondStateFoundation


class OverlaySerializer:
    @classmethod
    def regulation_innings(cls, state: Mapping[str, Any]) -> int:
        sport = str(state.get("sport", "baseball") or "baseball").lower()
        ruleset = ruleset_service.active_ruleset(state, sport=sport)
        return int(ruleset.get("regulation", {}).get("scheduledInnings", 9))

    @classmethod
    def serialize(
        cls,
        state: Mapping[str, Any],
        *,
        pitcher_name: str = "",
        batter_name: str = "",
        batter_position: str = "",
    ) -> dict[str, Any]:
        line_score = state.get("line_score") or {}
        return {
            "inning": state.get("inning", 1),
            "inning_half": state.get("inning_half", "TOP"),
            "balls": state.get("balls", 0),
            "strikes": state.get("strikes", 0),
            "outs": state.get("outs", 0),
            "bases": DiamondStateFoundation.bases_occupied(state),
            "pitcher_name": pitcher_name,
            "batter_name": batter_name,
            "batter_position": batter_position,
            "home_hits": state.get("home_hits", 0),
            "visitor_hits": state.get("visitor_hits", 0),
            "home_errors": state.get("home_errors", 0),
            "visitor_errors": state.get("visitor_errors", 0),
            "line_score": {
                "home": list(line_score.get("home") or []),
                "visitor": list(line_score.get("visitor") or []),
            },
            "home_score": state.get("home_score", 0),
            "visitor_score": state.get("visitor_score", 0),
            "regulation_innings": cls.regulation_innings(state),
            "sport": str(state.get("sport", "baseball") or "baseball").lower(),
        }
