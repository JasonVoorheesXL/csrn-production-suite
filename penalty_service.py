from __future__ import annotations

import copy
from typing import Any, Mapping


class PenaltyService:
    """Canonical football penalty consequence engine.

    Keeps physical field movement, down/distance consequences, and audit metadata
    together so callers do not independently reconstruct penalty state.
    """

    RULES: dict[tuple[str, str], dict[str, Any]] = {
        ("Offensive", "False Start"): {"yards": 5, "dead_ball": True},
        ("Offensive", "Holding"): {"yards": 10},
        ("Offensive", "Illegal Formation"): {"yards": 5},
        ("Offensive", "Illegal Motion"): {"yards": 5},
        ("Offensive", "Illegal Shift"): {"yards": 5},
        ("Offensive", "Delay of Game"): {"yards": 5, "dead_ball": True},
        ("Offensive", "Intentional Grounding"): {"yards": 5, "loss_of_down": True},
        ("Offensive", "Ineligible Receiver Downfield"): {"yards": 5},
        ("Offensive", "Personal Foul"): {"yards": 15},
        ("Offensive", "Unsportsmanlike Conduct"): {"yards": 15},
        ("Defensive", "Offside"): {"yards": 5},
        ("Defensive", "Encroachment"): {"yards": 5, "dead_ball": True},
        ("Defensive", "Holding"): {"yards": 10, "automatic_first_down": True},
        ("Defensive", "Pass Interference"): {"yards": 15, "automatic_first_down": True},
        ("Defensive", "Roughing the Passer"): {"yards": 15, "automatic_first_down": True},
        ("Defensive", "Face Mask"): {"yards": 15},
        ("Defensive", "Personal Foul"): {"yards": 15, "automatic_first_down": True},
        ("Defensive", "Unsportsmanlike Conduct"): {"yards": 15, "automatic_first_down": True},
        ("Special Teams", "Kick Catch Interference"): {"yards": 15},
        ("Special Teams", "Illegal Block"): {"yards": 10},
        ("Special Teams", "Holding"): {"yards": 10},
        ("Special Teams", "Running Into the Kicker"): {"yards": 5},
        ("Special Teams", "Roughing the Kicker"): {"yards": 15, "automatic_first_down": True},
        ("Special Teams", "Personal Foul"): {"yards": 15},
    }

    # Penalty catalogue + down cycle come from ruleset_service.active_ruleset
    # (the game's jurisdiction, generic US base when absent -- identical
    # penalty yardages / down cycle to us-ms-mhsaa, so a no-op today). Every
    # derived value is cached keyed by the resolved ruleset id. RULES /
    # _DOWNS_SEQUENCE_FALLBACK above are the frozen anchor used only if the
    # ruleset engine raises. See tests/test_ruleset_golden.py.
    _penalty_rules_cache: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}

    @classmethod
    def _penalty_rules(
        cls, state: Mapping[str, Any] | None = None
    ) -> dict[tuple[str, str], dict[str, Any]]:
        import ruleset_service

        rid = ruleset_service.active_ruleset_id(state)
        if rid not in cls._penalty_rules_cache:
            try:
                resolved = ruleset_service.penalty_rules(
                    ruleset_service.active_ruleset(state)
                )
                # A ruleset that somehow lost its penalties falls back rather
                # than silently enforcing nothing.
                cls._penalty_rules_cache[rid] = resolved or dict(cls.RULES)
            except Exception:
                cls._penalty_rules_cache[rid] = dict(cls.RULES)
        return cls._penalty_rules_cache[rid]

    @staticmethod
    def opposite(team: str) -> str:
        return "visitor" if team == "home" else "home"

    @classmethod
    def infer_unit(cls, state: Mapping[str, Any], selected_team: str, requested: Any) -> str:
        requested_text = str(requested or "").strip()
        if requested_text in {"Special Teams", "General"}:
            return requested_text
        possession = str(state.get("possession", "home") or "home").lower()
        return "Offensive" if selected_team == possession else "Defensive"

    @staticmethod
    def _safe_int(value: Any, fallback: int = 0) -> int:
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return fallback

    _DOWNS_SEQUENCE_FALLBACK = ["1st", "2nd", "3rd", "4th"]
    _downs_sequence_cache: dict[str, list[str]] = {}

    @classmethod
    def _downs_sequence(cls, state: Mapping[str, Any] | None = None) -> list[str]:
        import ruleset_service

        rid = ruleset_service.active_ruleset_id(state)
        if rid not in cls._downs_sequence_cache:
            try:
                cls._downs_sequence_cache[rid] = (
                    ruleset_service.downs_sequence(ruleset_service.active_ruleset(state))
                    or list(cls._DOWNS_SEQUENCE_FALLBACK)
                )
            except Exception:
                cls._downs_sequence_cache[rid] = list(cls._DOWNS_SEQUENCE_FALLBACK)
        return cls._downs_sequence_cache[rid]

    @classmethod
    def _advance_down(cls, value: Any, state: Mapping[str, Any] | None = None) -> str:
        # wrap=False: a loss-of-down penalty on the final down leaves it on
        # the final down (it never manufactures a fresh series).
        import ruleset_service

        return ruleset_service.next_down(
            str(value or "1st"), cls._downs_sequence(state), wrap=False
        )

    @classmethod
    def enforce(
        cls,
        state: dict[str, Any],
        *,
        selected_team: str,
        requested_unit: Any,
        name: Any,
        yards: Any,
        outcome: Any,
        spot_to_coord,
        coord_to_spot,
        team_direction,
        enforcement_spot: Any = "",
        half_distance: bool = False,
        automatic_first_down: bool = False,
        loss_of_down: bool = False,
        untimed_down: bool = False,
        retry_down: bool = False,
    ) -> dict[str, Any]:
        before = {
            "possession": state.get("possession", "home"),
            "down": state.get("down", "1st"),
            "distance": state.get("distance", "10"),
            "ball_spot": state.get("ball_spot", "50"),
            "special_game_phase": state.get("special_game_phase", ""),
        }
        unit = cls.infer_unit(state, selected_team, requested_unit)
        name_text = str(name or "Penalty").strip() or "Penalty"
        outcome_text = str(outcome or "accepted").lower()
        rule = copy.deepcopy(cls._penalty_rules(state).get((unit, name_text), {}))
        configured_yards = max(0, min(99, cls._safe_int(yards, cls._safe_int(rule.get("yards"), 0))))

        result: dict[str, Any] = {
            "applied": False,
            "unit": unit,
            "name": name_text,
            "outcome": outcome_text,
            "yards": configured_yards,
            "enforced_yards": 0,
            "rule": rule,
            "automatic_first_down": False,
            "loss_of_down": False,
            "half_distance": False,
            "untimed_down": bool(untimed_down),
            "retry_down": bool(retry_down),
            "before": before,
        }

        if outcome_text in {"declined", "flag_picked_up"}:
            result["after"] = copy.deepcopy(before)
            return result
        if outcome_text == "offset":
            result["offsetting"] = True
            result["retry_down"] = True
            result["after"] = copy.deepcopy(before)
            return result
        if outcome_text != "accepted":
            result["after"] = copy.deepcopy(before)
            return result

        offense = str(state.get("possession", "home") or "home").lower()
        defense = cls.opposite(offense)
        direction = int(team_direction(state, offense))
        base_spot = enforcement_spot if str(enforcement_spot or "").strip() else state.get("ball_spot", "50")
        start_coord = max(0, min(100, int(spot_to_coord(base_spot))))

        against_offense = unit == "Offensive" or (unit in {"Special Teams", "General"} and selected_team == offense)
        against_defense = unit == "Defensive" or (unit in {"Special Teams", "General"} and selected_team == defense)
        move_sign = -direction if against_offense else direction if against_defense else 0
        target_coord = start_coord + (move_sign * configured_yards)

        requested_half = bool(half_distance)
        if move_sign:
            goal_coord = 0 if move_sign < 0 else 100
            distance_to_goal = abs(goal_coord - start_coord)
            if requested_half:
                enforced = max(1, distance_to_goal // 2) if distance_to_goal > 1 and configured_yards else 0
            else:
                enforced = min(configured_yards, distance_to_goal)
            target_coord = start_coord + (move_sign * enforced)
        else:
            enforced = 0

        target_coord = max(0, min(100, target_coord))
        if move_sign:
            state["ball_spot"] = coord_to_spot(target_coord)

        automatic = bool(rule.get("automatic_first_down")) or bool(automatic_first_down)
        loss = bool(rule.get("loss_of_down")) or bool(loss_of_down)
        old_down = str(before["down"] or "1st")
        old_distance_raw = str(before["distance"] or "10")
        old_distance = 10 if old_distance_raw in {"", "Off", "Goal"} else max(1, cls._safe_int(old_distance_raw, 10))

        if automatic:
            state["down"] = "1st"
            state["distance"] = "10"
        else:
            # Distance must move based on WHICH SIDE the foul is against, not
            # on move_sign (which also folds in team_direction -- the side of
            # the field the offense happens to be driving toward this half).
            # A foul against the offense always pushes the enforcement spot
            # away from the line-to-gain (distance increases) regardless of
            # which physical end zone that is; a foul against the defense
            # always pushes it toward the line-to-gain (distance decreases).
            # Keying this off move_sign instead inverted the result for
            # roughly half of all penalties -- whichever team/half currently
            # had team_direction=="left" (move_sign flips sign with
            # direction, but against_offense/against_defense do not).
            if against_offense:
                state["distance"] = str(min(99, old_distance + enforced))
            elif against_defense:
                remaining = old_distance - enforced
                if remaining <= 0:
                    state["down"] = "1st"
                    state["distance"] = "10"
                else:
                    state["distance"] = str(remaining)
            if loss:
                state["down"] = cls._advance_down(old_down, state)

        # Penalty administration never silently resolves scoring/special phases.
        # retry/untimed-down are canonical administration flags for the later
        # period/try enforcement layers.
        state["penalty_administration"] = {
            "untimed_down": bool(untimed_down),
            "retry_down": bool(retry_down or outcome_text == "offset"),
        }

        result.update(
            {
                "applied": True,
                "enforced_yards": enforced,
                "automatic_first_down": automatic,
                "loss_of_down": loss,
                "half_distance": requested_half,
                "enforcement_spot": coord_to_spot(start_coord),
                "result_spot": state.get("ball_spot", before["ball_spot"]),
                "after": {
                    "possession": state.get("possession", "home"),
                    "down": state.get("down", "1st"),
                    "distance": state.get("distance", "10"),
                    "ball_spot": state.get("ball_spot", "50"),
                    "special_game_phase": state.get("special_game_phase", ""),
                },
            }
        )
        return result
