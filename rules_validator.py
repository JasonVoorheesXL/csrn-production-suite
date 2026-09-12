"""Severity-tagged validation (CSRN_NFHS_Baseball_Softball_Rules_Engine_
Spec_2026 Sec.14): "Validation should have severity and should explain what
it knows. Do not use a single 'illegal' boolean." HARD_ERROR blocks commit
(internal impossibility / corrupt state); SOFT_WARNING/NEEDS_RULING allow
commit with acknowledgment/a ruling workflow; INFO is informational only.

This module never officiates (Sec.1: "The rules validator is advisory at
the point of data entry... It should not block the scorer from recording an
action that the game officials allowed"). It validates only the STRUCTURAL
invariants that are meaningful without a lineup (Sec.14.1's "two active
offensive occupants in one batting slot" / "DP and FLEX both active on
offense" and every lineup-dependent SOFT_WARNING in Sec.14.2 need
lineup_service, P2, and are not implemented here)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from diamond_state_service import BASES, DiamondStateFoundation

SEVERITIES = ("HARD_ERROR", "SOFT_WARNING", "NEEDS_RULING", "INFO")


@dataclass(frozen=True)
class ValidationMessage:
    severity: str
    code: str
    message: str


class RulesValidator:
    @classmethod
    def validate_outs(cls, state: Mapping[str, Any], outs_to_record: int) -> list[ValidationMessage]:
        # Sec.14.1: "Four outs stored in an active half-inning."
        current = int(state.get("outs", 0))
        if current + int(outs_to_record) > 3:
            return [
                ValidationMessage(
                    "HARD_ERROR",
                    "FOUR_OUTS",
                    f"Recording {outs_to_record} out(s) would bring the half-inning to "
                    f"{current + int(outs_to_record)} outs; at most 3 are possible.",
                )
            ]
        return []

    @classmethod
    def validate_runner_placement(
        cls, state: Mapping[str, Any], base: str, player_id: str
    ) -> list[ValidationMessage]:
        # Sec.14.1: "Same player identity simultaneously assigned to two
        # bases." A player already occupying a DIFFERENT base cannot also
        # be placed on this one without first being cleared from the other.
        if not player_id:
            return []
        runners = state.get("base_runners") or {}
        for occupied_base in BASES:
            if occupied_base == base:
                continue
            occupant = runners.get(occupied_base)
            if isinstance(occupant, Mapping) and occupant.get("player_id") == player_id:
                return [
                    ValidationMessage(
                        "HARD_ERROR",
                        "RUNNER_ON_TWO_BASES",
                        f"Player {player_id} already occupies {occupied_base}; "
                        f"cannot also be placed on {base} without clearing it first.",
                    )
                ]
        return []

    @classmethod
    def validate_plate_appearance(
        cls, state: Mapping[str, Any], payload: Mapping[str, Any]
    ) -> list[ValidationMessage]:
        """Structural pre-check for an about-to-be-applied PLATE_APPEARANCE
        payload (see diamond_state_service.apply_plate_appearance for the
        shape). Returns every HARD_ERROR found; an empty list means the
        payload is structurally safe to apply (it does not mean the
        scorer's call is correct -- that judgment stays with the umpire /
        official scorer per Sec.1's "record reality first" policy)."""
        messages: list[ValidationMessage] = []
        outs_recorded = int(payload.get("outsRecorded", 0) or 0)
        if outs_recorded:
            messages.extend(cls.validate_outs(state, outs_recorded))
        for outcome in payload.get("runnerOutcomes") or []:
            dst = str(outcome.get("to", ""))
            if dst in BASES and str(outcome.get("from", "")) == "batter":
                messages.extend(
                    cls.validate_runner_placement(state, dst, str(outcome.get("playerId", "")))
                )
        return messages

    @classmethod
    def validate_replay_integrity(
        cls, events: list[Mapping[str, Any]]
    ) -> list[ValidationMessage]:
        # Sec.14.1: "Duplicate event sequence... indicating ledger
        # corruption."
        seen: set[int] = set()
        messages: list[ValidationMessage] = []
        for event in events:
            sequence = int(event.get("sequence", 0) or 0)
            if sequence in seen:
                messages.append(
                    ValidationMessage(
                        "HARD_ERROR",
                        "DUPLICATE_SEQUENCE",
                        f"Event sequence {sequence} appears more than once in the ledger.",
                    )
                )
            seen.add(sequence)
        return messages

    @classmethod
    def has_hard_error(cls, messages: list[ValidationMessage]) -> bool:
        return any(message.severity == "HARD_ERROR" for message in messages)
