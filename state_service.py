from __future__ import annotations

import copy
import threading
import time
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Mapping

from canonical_state_service import CanonicalStateFoundation
from ticker_policy_service import TickerPolicyService
from eligibility_service import EligibilityService
from live_command_service import LEDGER_FIELD, compact_recent_commands, current_revision
from runtime_diagnostics_service import get_runtime_diagnostics


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
    LIVE_ARRAY_LIMITS = {
        "history": 50,
        "events": 500,
        "plays": 500,
        "correction_log": 500,
        "redo_stack": 50,
        "graphics_queue": 100,
    }
    SAFE_URL_PREFIXES = (
        "/",
        "data:image/svg+xml",
        "http://",
        "https://",
    )
    LEGACY_MANAGED_URL_PREFIXES = (
        "asset-files/",
        "school-logos/",
        "roster-headshots/",
        "personnel-headshots/",
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
        async_linked_snapshot: bool = False,
        cache_committed_state: bool = False,
    ) -> None:
        self._load_raw = load_raw
        self._replace_raw = replace_raw
        self._default_state = default_state
        self._persist_linked_snapshot = persist_linked_snapshot
        self._resolve_player = resolve_player
        self._canonical_team_key = canonical_team_key
        self._canonical_team_name = canonical_team_name
        self._now = now
        self._async_linked_snapshot = bool(async_linked_snapshot)
        self._cache_committed_state = bool(cache_committed_state)
        self._committed_state_lock = threading.RLock()
        self._committed_state: dict[str, Any] | None = None
        self._linked_snapshot_lock = threading.Lock()
        self._linked_snapshot_pending: dict[str, Any] | None = None
        self._linked_snapshot_worker: threading.Thread | None = None

    def _read_committed_raw(self) -> Mapping[str, Any]:
        if not self._cache_committed_state:
            return self._load_raw()
        with self._committed_state_lock:
            if self._committed_state is not None:
                return copy.deepcopy(self._committed_state)
        loaded = copy.deepcopy(dict(self._load_raw()))
        with self._committed_state_lock:
            if self._committed_state is None:
                self._committed_state = copy.deepcopy(loaded)
            return copy.deepcopy(self._committed_state)

    def _remember_committed(self, state: Mapping[str, Any]) -> None:
        if not self._cache_committed_state:
            return
        with self._committed_state_lock:
            self._committed_state = copy.deepcopy(dict(state))

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
            "redo_stack",
            "graphics_queue",
        ):
            if not isinstance(merged.get(field), list):
                merged[field] = []
            merged[field] = merged[field][-self.LIVE_ARRAY_LIMITS[field] :]

        merged["state_revision"] = current_revision(merged)
        if not isinstance(merged.get(LEDGER_FIELD), dict):
            merged[LEDGER_FIELD] = {}
        compact_recent_commands(merged)

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
        # Gate 18.4 R7: eligibility is derived from reversible canonical history,
        # never persisted by mutating the master roster.
        merged["player_eligibility"] = EligibilityService.derive(
            merged,
            resolve_player=self._resolve_player,
        )
        return merged

    def load(self) -> StateResult:
        state = self.normalize(self._read_committed_raw())
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

            # Reading public state must never write the full state file. The
            # running clock is derived from its persisted baseline and is saved
            # only by an explicit mutation such as pause, reset, or game action.
            # Polling clients may call this method several times per second.
            # Writing here turns every viewer into a continuous disk writer and
            # can exhaust the WSGI worker pool on synchronized storage.

        return StateResult("OK", {"state": copy.deepcopy(state)})


    def _queue_linked_snapshot(self, state: Mapping[str, Any]) -> None:
        if self._persist_linked_snapshot is None:
            return
        snapshot = copy.deepcopy(dict(state))
        with self._linked_snapshot_lock:
            self._linked_snapshot_pending = snapshot
            worker = self._linked_snapshot_worker
            if worker is not None and worker.is_alive():
                return
            self._linked_snapshot_worker = threading.Thread(
                target=self._linked_snapshot_loop,
                name="csrn-linked-snapshot-writer",
                daemon=True,
            )
            self._linked_snapshot_worker.start()

    def _linked_snapshot_loop(self) -> None:
        while True:
            with self._linked_snapshot_lock:
                snapshot = self._linked_snapshot_pending
                self._linked_snapshot_pending = None
            if snapshot is None:
                with self._linked_snapshot_lock:
                    if self._linked_snapshot_pending is None:
                        self._linked_snapshot_worker = None
                        return
                continue
            started = perf_counter()
            try:
                assert self._persist_linked_snapshot is not None
                self._persist_linked_snapshot(snapshot)
                get_runtime_diagnostics().record(
                    "SERVER_LINKED_SNAPSHOT",
                    status="OK",
                    broadcast_id=str(snapshot.get("broadcast_id", "") or ""),
                    state_revision=current_revision(snapshot),
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    thread=threading.current_thread().name,
                )
            except Exception as exc:
                get_runtime_diagnostics().record(
                    "SERVER_LINKED_SNAPSHOT",
                    status="ERROR",
                    broadcast_id=str(snapshot.get("broadcast_id", "") or ""),
                    state_revision=current_revision(snapshot),
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    error_type=type(exc).__name__,
                    error_message=str(exc)[:240],
                    thread=threading.current_thread().name,
                )

    def save(self, state: Mapping[str, Any]) -> StateResult:
        started = perf_counter()
        normalized = self.normalize(state)
        incoming_revision = current_revision(normalized)
        stored_revision = 0
        load_ms = 0.0
        replace_ms = 0.0
        linked_snapshot_ms = 0.0
        linked_snapshot = False
        try:
            step_started = perf_counter()
            stored_revision = current_revision(self._read_committed_raw())
            load_ms = round((perf_counter() - step_started) * 1000, 2)
            if incoming_revision < stored_revision:
                normalized["state_revision"] = stored_revision

            step_started = perf_counter()
            stored = self._replace_raw(normalized)
            replace_ms = round((perf_counter() - step_started) * 1000, 2)
            result = self.normalize(stored)
            self._remember_committed(result)

            if (
                str(result.get("broadcast_id", "")).strip()
                and self._persist_linked_snapshot is not None
            ):
                linked_snapshot = True
                if self._async_linked_snapshot:
                    self._queue_linked_snapshot(result)
                else:
                    step_started = perf_counter()
                    self._persist_linked_snapshot(copy.deepcopy(result))
                    linked_snapshot_ms = round((perf_counter() - step_started) * 1000, 2)
        except Exception as exc:
            get_runtime_diagnostics().record(
                "SERVER_STATE_SAVE", status="ERROR", thread=threading.current_thread().name,
                state_revision_incoming=incoming_revision, state_revision_stored=stored_revision,
                load_ms=load_ms, replace_ms=replace_ms, linked_snapshot_ms=linked_snapshot_ms,
                linked_snapshot=linked_snapshot, total_ms=round((perf_counter() - started) * 1000, 2),
                error_type=type(exc).__name__, error_message=str(exc)[:240],
            )
            raise

        total_ms = round((perf_counter() - started) * 1000, 2)
        get_runtime_diagnostics().record(
            "SERVER_STATE_SAVE", status="OK", thread=threading.current_thread().name,
            broadcast_id=str(result.get("broadcast_id", "") or ""),
            state_revision_incoming=incoming_revision, state_revision_stored=stored_revision,
            state_revision_after=current_revision(result), load_ms=load_ms, replace_ms=replace_ms,
            linked_snapshot_ms=linked_snapshot_ms, linked_snapshot=linked_snapshot, linked_snapshot_async=self._async_linked_snapshot, total_ms=total_ms,
            slow_persistence=total_ms > 250,
        )
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
            if key not in {"history", LEDGER_FIELD}
        }
        history = state.setdefault("history", [])
        if not isinstance(history, list):
            history = []
        history.append(snapshot)
        state["history"] = history[-50:]

    def public(self, state: Mapping[str, Any]) -> StateResult:
        result = copy.deepcopy(dict(state))
        result.pop(LEDGER_FIELD, None)
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

        highlight = result.get("player_highlight")
        if isinstance(highlight, dict):
            for field in ("team_logo", "media_url"):
                highlight[field] = self._safe_media_value(
                    highlight.get(field, "")
                )

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
        # Gate 18.4 R1: every browser/overlay consumer receives one canonical
        # interpretation of field state and team roles. Existing public fields
        # remain unchanged for backward compatibility.
        result["team_roles"] = CanonicalStateFoundation.team_roles(result).as_dict()
        result["canonical_field_state"] = CanonicalStateFoundation.field_state(result)
        # Gate 18.4 R10: one backend-derived ticker lifecycle view is consumed
        # by both the legacy overlay and production-theme ticker adapter.
        result["ticker_items"] = TickerPolicyService.build(result)
        return StateResult("OK", {"state": result})

    def runtime_view(self, state: Mapping[str, Any]) -> StateResult:
        """Return the small live-browser state view without undo/history archives."""

        source = dict(state)
        excluded = {
            "history",
            "redo_stack",
            "events",
            "plays",
            "correction_log",
            "graphics_queue",
            LEDGER_FIELD,
        }
        runtime: dict[str, Any] = {
            key: copy.deepcopy(value)
            for key, value in source.items()
            if key not in excluded
            and not isinstance(value, (list, tuple, set))
            and not key.startswith("_")
        }

        for key in (
            "home_identity",
            "visitor_identity",
            "home_pregame_record",
            "home_pregame_region_record",
            "visitor_pregame_record",
            "visitor_pregame_region_record",
            "lower_third",
            "player_graphic",
            "player_highlight",
            "personnel_graphic",
            "sponsor_spotlight",
            "crew",
        ):
            if key in source and isinstance(source.get(key), dict):
                runtime[key] = copy.deepcopy(source[key])

        for key in ("home_identity", "visitor_identity"):
            identity = runtime.get(key)
            if isinstance(identity, dict):
                identity["logo"] = self._safe_media_value(identity.get("logo", ""))

        for key, fields in (
            ("personnel_graphic", ("headshot", "logo", "sponsor_logo")),
            ("player_graphic", ("headshot", "team_logo", "sponsor_logo")),
            ("player_highlight", ("team_logo", "media_url")),
            ("sponsor_spotlight", ("sponsor_logo", "media_url")),
        ):
            graphic = runtime.get(key)
            if isinstance(graphic, dict):
                for field in fields:
                    graphic[field] = self._safe_media_value(graphic.get(field, ""))

        runtime["team_roles"] = CanonicalStateFoundation.team_roles(runtime).as_dict()
        runtime["canonical_field_state"] = CanonicalStateFoundation.field_state(runtime)
        runtime["ticker_items"] = TickerPolicyService.build(source)
        runtime["runtime_view_schema"] = "csrn-runtime-state-v1"
        runtime["state_revision"] = current_revision(source)
        runtime["revision"] = runtime["state_revision"] or self._runtime_revision(source, runtime)
        return StateResult("OK", {"state": runtime})

    @staticmethod
    def _runtime_revision(
        source: Mapping[str, Any],
        runtime: Mapping[str, Any],
    ) -> int:
        candidates: list[int] = []
        for key in (
            "control_source_updated_at",
            "clock_started_at",
            "last_saved_at",
            "updated_at",
        ):
            try:
                candidates.append(int(source.get(key, 0) or 0))
            except (TypeError, ValueError):
                pass

        for key in (
            "lower_third",
            "player_graphic",
            "player_highlight",
            "personnel_graphic",
            "sponsor_spotlight",
            "last_event",
        ):
            value = source.get(key)
            if isinstance(value, Mapping):
                try:
                    candidates.append(int(value.get("updated_at", 0) or 0))
                except (TypeError, ValueError):
                    pass
                try:
                    candidates.append(int(value.get("created_at", 0) or 0))
                except (TypeError, ValueError):
                    pass

        for item in runtime.get("ticker_items", []) or []:
            if isinstance(item, Mapping):
                try:
                    candidates.append(int(item.get("created_at", 0) or 0))
                except (TypeError, ValueError):
                    pass
        return max(candidates or [0])

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
        text = str(value or "").strip()
        if not text or text.startswith(cls.SAFE_URL_PREFIXES):
            return text
        normalized = text.replace("\\", "/")
        if normalized.startswith(cls.LEGACY_MANAGED_URL_PREFIXES):
            return f"/{normalized}"
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


