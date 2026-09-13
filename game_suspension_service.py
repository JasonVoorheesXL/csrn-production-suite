"""Suspension snapshot/resume (CSRN_NFHS_Baseball_Softball_Rules_Engine_
Spec_2026 Sec.11.4). Persist at suspension exactly what SUS-01 requires:
inning/half, outs, count, batter and batting-order cursor; all base
runners and their origin/responsible-pitcher metadata; active lineups,
re-entry history, DH/DP/FLEX state; pitcher/catcher, pitch counts, charged
conferences/player meetings; score and inning lines; rules-profile
version -- "resumption must not silently adopt a newer profile."

A resumed game must be state-equivalent immediately before the next event
(spec Sec.19.1's own property test). DiamondStateFoundation.snapshot()
already covers every diamond-side canonical field; lineup_service's
per-side dict is already a complete, self-contained structure (slots,
defense, roles, dp_flex, courtesy runners, batting-order alerts). This
module's only job is to snapshot BOTH together, plus the profile stamp, at
one moment, and restore all of it atomically.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from diamond_state_service import DiamondStateFoundation


@dataclass(frozen=True)
class SuspensionResult:
    code: str
    state: dict[str, Any]
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class GameSuspensionService:
    @classmethod
    def suspend(cls, state: dict[str, Any], *, reason: str = "") -> SuspensionResult:
        if state.get("status") == "suspended":
            return SuspensionResult("ALREADY_SUSPENDED", state, {})
        snapshot = {
            "diamond": DiamondStateFoundation.snapshot(state),
            "lineup": copy.deepcopy(state.get("lineup", {})),
            "effective_profile_id": state.get("effective_profile_id", ""),
            "effective_profile_version": state.get("effective_profile_version"),
            "status_before_suspension": state.get("status", ""),
        }
        state["suspension"] = {"suspended": True, "reason": reason, "snapshot": snapshot}
        state["status"] = "suspended"
        return SuspensionResult("OK", state, {"snapshot": copy.deepcopy(snapshot)})

    @classmethod
    def resume(cls, state: dict[str, Any]) -> SuspensionResult:
        """Sec.11.4: 'rules-profile version -- Resumption must not silently
        adopt a newer profile.' Restores the exact effective_profile_id/
        version captured at suspension, even if the live ruleset catalog
        has changed since (mirrors the same 'stamped once, never silently
        re-resolved' guarantee P0's BroadcastLifecycleService stamp
        established)."""
        suspension = state.get("suspension")
        if not isinstance(suspension, Mapping) or not suspension.get("suspended"):
            return SuspensionResult("NOT_SUSPENDED", state, {})
        snapshot = suspension["snapshot"]
        for field, value in snapshot["diamond"].items():
            state[field] = copy.deepcopy(value)
        state["lineup"] = copy.deepcopy(snapshot["lineup"])
        state["effective_profile_id"] = snapshot["effective_profile_id"]
        state["effective_profile_version"] = snapshot["effective_profile_version"]
        state["status"] = snapshot["status_before_suspension"] or "live"
        state["suspension"] = {"suspended": False, "reason": "", "snapshot": None}
        return SuspensionResult("OK", state, {})
