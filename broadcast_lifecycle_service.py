from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import engine_router
import ruleset_service
from hoops_period_service import HoopsPeriodService
from hoops_rules_service import HoopsRulesService


@dataclass(frozen=True)
class BroadcastLifecycleResult:
    code: str
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class BroadcastLifecycleService:
    """Broadcast loading and live-lifecycle boundary independent of Flask."""

    def __init__(
        self,
        *,
        load_broadcasts: Callable[[], list[dict[str, Any]]],
        load_packages: Callable[[], list[dict[str, Any]]],
        load_state: Callable[[], Mapping[str, Any]],
        save_state: Callable[[Mapping[str, Any]], Any],
        normalize_state: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        default_state: Callable[[], Mapping[str, Any]],
        get_school: Callable[[str], Mapping[str, Any] | None],
        build_identity: Callable[[Mapping[str, Any] | None, str], Mapping[str, Any]],
        readiness: Callable[[], Mapping[str, Any]],
        update_linked_status: Callable[[str, str, dict[str, Any] | None], Any],
        load_config: Callable[[], Mapping[str, Any]],
        command_scorebug_visibility: Callable[[bool], Mapping[str, Any]],
        public_state: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        resume_record: Callable[[str], Any],
        transaction_lock: Any,
    ) -> None:
        self._load_broadcasts = load_broadcasts
        self._load_packages = load_packages
        self._load_state = load_state
        self._save_state = save_state
        self._normalize_state = normalize_state
        self._default_state = default_state
        self._get_school = get_school
        self._build_identity = build_identity
        self._readiness = readiness
        self._update_linked_status = update_linked_status
        self._load_config = load_config
        self._command_scorebug_visibility = command_scorebug_visibility
        self._public_state = public_state
        self._resume_record = resume_record
        self._transaction_lock = transaction_lock

    def load(self, broadcast_id: Any) -> BroadcastLifecycleResult:
        key = str(broadcast_id or "").strip()
        item = next(
            (
                row
                for row in self._load_broadcasts()
                if str(row.get("broadcast_id", "")) == key
                and not row.get("archived")
            ),
            None,
        )
        if item is None:
            return BroadcastLifecycleResult("NOT_FOUND", {})

        current = copy.deepcopy(dict(self._load_state()))
        if str(current.get("broadcast_id", "")) == key and (
            current.get("broadcast_created") or current.get("events") or current.get("plays")
        ):
            return BroadcastLifecycleResult("OK", {"state": current})

        snapshot = item.get("live_state")
        if isinstance(snapshot, Mapping):
            state = copy.deepcopy(dict(self._normalize_state(snapshot)))
        else:
            state = copy.deepcopy(dict(self._default_state()))
            state.update(self._state_from_record(item))

        package = next(
            (
                row
                for row in self._load_packages()
                if str(row.get("broadcast_id", "")) == key
            ),
            None,
        )
        if package is not None:
            state["broadcast_package_id"] = package.get(
                "id",
                state.get("broadcast_package_id", ""),
            )
            state["package_roster_ids"] = list(
                package.get("roster_ids")
                or state.get("package_roster_ids")
                or []
            )

        status = str(item.get("status", state.get("status", "planned")))
        state["status"] = status
        state["review_mode"] = status == "completed"
        state["broadcast_phase"] = self.phase_for_status(status)
        self._save_state(state)
        return BroadcastLifecycleResult(
            "OK",
            {
                "state": copy.deepcopy(state),
                "broadcast": copy.deepcopy(item),
            },
        )

    def initialize(self) -> BroadcastLifecycleResult:
        state = copy.deepcopy(dict(self._load_state()))
        if not str(state.get("broadcast_id", "")).strip():
            return BroadcastLifecycleResult("NO_ACTIVE_BROADCAST", {})
        return BroadcastLifecycleResult(
            "OK",
            {
                "state": state,
                "readiness": copy.deepcopy(dict(self._readiness())),
                "deprecated": True,
            },
        )

    def start(self) -> BroadcastLifecycleResult:
        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            broadcast_id = str(state.get("broadcast_id", "")).strip()
            if not broadcast_id:
                return BroadcastLifecycleResult("NO_ACTIVE_BROADCAST", {})

            state["status"] = "live"
            state["broadcast_phase"] = "live"
            state["scorebug_visible"] = True
            self._save_state(state)
            self._update_linked_status(broadcast_id, "live", None)

            obs_result: Mapping[str, Any] | None = None
            obs_config = dict(self._load_config()).get("obs", {})
            if isinstance(obs_config, Mapping) and obs_config.get(
                "controlled_commands",
                False,
            ):
                try:
                    obs_result = self._command_scorebug_visibility(True)
                except Exception as exc:  # injected hardware boundary
                    obs_result = {"error": str(exc)}

            record = next(
                (
                    row
                    for row in self._load_broadcasts()
                    if str(row.get("broadcast_id", "")) == broadcast_id
                ),
                None,
            )
            return BroadcastLifecycleResult(
                "OK",
                {
                    "state": copy.deepcopy(dict(self._public_state(state))),
                    "broadcast": copy.deepcopy(record),
                    "obs": copy.deepcopy(obs_result),
                },
            )

    def resume(self) -> BroadcastLifecycleResult:
        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            broadcast_id = str(state.get("broadcast_id", "")).strip()
            if not broadcast_id:
                return BroadcastLifecycleResult("NO_ACTIVE_BROADCAST", {})

            state["status"] = "live"
            state["broadcast_phase"] = "live"
            state["review_mode"] = False
            state["scorebug_visible"] = False
            self._save_state(state)
            self._resume_record(broadcast_id)
            return BroadcastLifecycleResult(
                "OK",
                {"state": copy.deepcopy(dict(self._public_state(state)))},
            )

    @staticmethod
    def phase_for_status(status: Any) -> str:
        normalized = str(status or "planned").strip().lower()
        if normalized == "completed":
            return "final"
        if normalized == "live":
            return "live"
        return "pregame"

    def _effective_profile_fields(
        self, sport: str, country: str, region: str, association: str
    ) -> dict[str, Any]:
        # RulesProfile versioning (CSRN_NFHS_Baseball_Softball_Rules_Engine_
        # Spec_2026 §3.2): "A game stores effectiveProfileId and
        # effectiveProfileVersion at creation. Changing a master profile
        # affects only future games unless an explicit migration is
        # performed." This is that stamp -- computed once, here, at the
        # moment a planned broadcast record becomes live state, not
        # re-resolved from country/region/association on every read the way
        # ruleset_service.active_ruleset() already does for in-game rules
        # lookups. A resumed live-state snapshot (the other branch of
        # load()) already carries whatever was stamped here previously and
        # is never re-stamped.
        profile_id = ruleset_service.resolve_id(
            country=country, region=region or None, association=association or None,
            sport=sport,
        )
        try:
            document = ruleset_service.load_ruleset(profile_id)
        except (FileNotFoundError, ValueError):
            document = {}
        # Existing football rulesets predate this field and carry none;
        # treat an undeclared version as 1 rather than requiring every
        # shipped document to be edited.
        version = document.get("version", 1)
        return {
            "effective_profile_id": profile_id,
            "effective_profile_version": version,
        }

    def _default_hoops_fields(
        self, sport: str, country: str, region: str, association: str
    ) -> dict[str, Any]:
        """Fresh period/clock/hoops sub-state for a newly-loaded basketball
        broadcast -- same "state is correct the moment it exists" standard
        as _state_from_record()'s diamond stamp above, but basketball's own
        initial values (period length, shot clock, timeouts) are
        ruleset-derived, unlike baseball's default_diamond_state() (which
        needs no ruleset at all). Resolves the ruleset once, here, via a
        throwaway probe dict passed to hoops_period_service.start_game()
        (the same call hoops_game_operations_service.initialize_hoops()
        makes), then returns just the fields it set -- period/clock_seconds/
        clock_running/clock_started_at (shared) plus hoops (namespaced) --
        for the caller to splat into the real state dict being built."""
        probe: dict[str, Any] = {
            "sport": sport, "country": country, "region": region, "association": association,
        }
        ruleset = HoopsRulesService.active_ruleset(probe)
        HoopsPeriodService.start_game(probe, ruleset)
        return {
            "period": probe["period"],
            "clock_seconds": probe["clock_seconds"],
            "clock_running": probe["clock_running"],
            "clock_started_at": probe["clock_started_at"],
            "hoops": probe["hoops"],
        }

    def _state_from_record(self, item: Mapping[str, Any]) -> dict[str, Any]:
        status = str(item.get("status", "planned"))
        sport = str(item.get("sport", "Football"))
        home_school_id = str(item.get("home_school_id", ""))
        visitor_school_id = str(item.get("visitor_school_id", ""))
        completed = status == "completed"
        country = str(item.get("country", "") or "").strip().upper() or "US"
        region = str(item.get("region", "") or "").strip().upper()
        association = str(item.get("association", "") or "").strip().upper()
        return {
            "broadcast_created": True,
            "broadcast_id": item.get("broadcast_id", ""),
            "sport": sport,
            # Jurisdiction the rules engine resolves against
            # (ruleset_service.active_ruleset). Absent on legacy records ->
            # "" -> the generic ruleset, identical engine behaviour to today.
            "country": country,
            "region": region,
            "association": association,
            **self._effective_profile_fields(sport, country, region, association),
            # P2 followup (2026-09-14, owner decision): narrow per-
            # broadcast override for baseball/softball's regulation length
            # -- game_end_evaluator._scheduled_innings() checks this before
            # falling back to the resolved ruleset's scheduledInnings.
            # None (absent) is the common case; harmless on a non-diamond
            # broadcast, since nothing else reads it.
            "regulation_innings_override": item.get("regulation_innings_override"),
            "season": item.get("season", ""),
            "week": item.get("week", "1"),
            "classification": item.get("classification", ""),
            "home_classification": item.get("home_classification", ""),
            "home_region": item.get("home_region", ""),
            "visitor_classification": item.get("visitor_classification", ""),
            "visitor_region": item.get("visitor_region", ""),
            "home_pregame_record": copy.deepcopy(item.get("home_pregame_record", {"wins": 0, "losses": 0, "ties": 0})),
            "home_pregame_region_record": copy.deepcopy(item.get("home_pregame_region_record", {"wins": 0, "losses": 0, "ties": 0})),
            "visitor_pregame_record": copy.deepcopy(item.get("visitor_pregame_record", {"wins": 0, "losses": 0, "ties": 0})),
            "visitor_pregame_region_record": copy.deepcopy(item.get("visitor_pregame_region_record", {"wins": 0, "losses": 0, "ties": 0})),
            "contest_type": item.get("contest_type", "official"),
            "record_policy": item.get("record_policy", "official"),
            "region_game": (
                bool(item.get("region_game", False))
                if str(item.get("contest_type", "official")).strip().lower() == "official"
                else False
            ),
            "special_designations": copy.deepcopy(item.get("special_designations", [])),
            "record_tracking": copy.deepcopy(item.get("record_tracking", {})),
            "level": item.get("level", "Varsity"),
            "division": item.get("division", "Boys"),
            "home_school_id": home_school_id,
            "visitor_school_id": visitor_school_id,
            "home_team": item.get("home_team", "Home"),
            "visitor_team": item.get("visitor_team", "Visitor"),
            "home_identity": item.get("home_identity")
            or self._build_identity(self._get_school(home_school_id), sport),
            "visitor_identity": item.get("visitor_identity")
            or self._build_identity(self._get_school(visitor_school_id), sport),
            "venue_id": item.get("venue_id", ""),
            "venue": item.get("venue", ""),
            "date": item.get("date", ""),
            "scheduled_start": item.get("scheduled_start", "07:00 PM"),
            "visual_mode": item.get("visual_mode", "graphic"),
            "crew": copy.deepcopy(item.get("crew", {})),
            "status": status,
            "broadcast_phase": self.phase_for_status(status),
            "scorebug_visible": False,
            "home_score": item.get("final_home_score", 0) if completed else 0,
            "visitor_score": item.get("final_visitor_score", 0)
            if completed
            else 0,
            # P5: a freshly-loaded baseball/softball broadcast gets a clean
            # namespaced diamond sub-state immediately (inning 1, TOP, 0-0,
            # empty lineups) rather than waiting on lazy creation at the
            # first diamond route call -- same "state is correct the moment
            # it exists" standard football's own fields above already get.
            # Only this branch (a fresh record, never a resumed live-state
            # snapshot -- see load()'s other branch) stamps it; a resumed
            # snapshot already carries whatever diamond state that game had.
            **(
                {"diamond": engine_router.default_diamond_state()}
                if engine_router.is_diamond_sport(sport)
                else {}
            ),
            # P5: a freshly-loaded basketball broadcast gets a clean period/
            # clock/hoops sub-state immediately (period 1, a full game
            # clock, zeroed fouls/timeouts from the ruleset) rather than
            # waiting on lazy creation at the first hoops route call. Same
            # fresh-record-only caveat as the diamond stamp above -- a
            # resumed live-state snapshot already carries whatever
            # basketball state that game had.
            **(
                self._default_hoops_fields(sport, country, region, association)
                if engine_router.is_hoops_sport(sport)
                else {}
            ),
        }
