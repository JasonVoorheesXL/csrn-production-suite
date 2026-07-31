from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Mapping


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
        if (
            str(current.get("broadcast_id", "")) == key
            and current.get("broadcast_created")
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

    def _state_from_record(self, item: Mapping[str, Any]) -> dict[str, Any]:
        status = str(item.get("status", "planned"))
        sport = str(item.get("sport", "Football"))
        home_school_id = str(item.get("home_school_id", ""))
        visitor_school_id = str(item.get("visitor_school_id", ""))
        completed = status == "completed"
        return {
            "broadcast_created": True,
            "broadcast_id": item.get("broadcast_id", ""),
            "sport": sport,
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
        }
