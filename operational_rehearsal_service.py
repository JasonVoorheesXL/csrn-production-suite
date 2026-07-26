from __future__ import annotations

import copy
import json
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Callable


Clock = Callable[[], float]
TokenFactory = Callable[[], str]
SystemGateLoader = Callable[[], dict[str, Any]]
SnapshotCreator = Callable[..., Any]
KnownGoodRegistrar = Callable[..., Any]


@dataclass(frozen=True)
class RehearsalResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code in {
            "OK",
            "REHEARSAL_CREATED",
            "DRILL_UPDATED",
            "BLOCKER_ADDED",
            "BLOCKER_UPDATED",
            "REHEARSAL_COMPLETED",
            "REHEARSAL_REOPENED",
            "RELEASE_FROZEN",
            "RELEASE_UNFROZEN",
        }


class OperationalRehearsalService:
    """Persistent rehearsal evidence and guarded game-day release freeze."""

    SCHEMA = 1
    REQUIRED_REHEARSALS = 2
    COMPLETE_CONFIRMATION = "COMPLETE REHEARSAL"
    REOPEN_CONFIRMATION = "REOPEN REHEARSAL"
    FREEZE_CONFIRMATION = "FREEZE GAME DAY RELEASE"
    UNFREEZE_CONFIRMATION = "UNFREEZE GAME DAY RELEASE"
    COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")

    DRILLS: tuple[dict[str, Any], ...] = (
        {
            "key": "pregame.preflight",
            "label": "Pregame preflight, login, and safety snapshot",
            "category": "pregame",
            "required_each": True,
            "required_series": False,
        },
        {
            "key": "audio.multitrack",
            "label": "P4next isolated channels and multitrack recording",
            "category": "audio",
            "required_each": True,
            "required_series": False,
        },
        {
            "key": "audio.headphone_mix",
            "label": "Independent headphone mixes without clipping or hum",
            "category": "audio",
            "required_each": True,
            "required_series": False,
        },
        {
            "key": "obs.scene_contract",
            "label": "OBS profile, scenes, browser sources, and local recording",
            "category": "obs",
            "required_each": True,
            "required_series": False,
        },
        {
            "key": "network.primary_stream",
            "label": "Primary network and private stream path",
            "category": "network",
            "required_each": True,
            "required_series": False,
        },
        {
            "key": "captions.live_workflow",
            "label": "Channel-separated captions, correction, clear, and overlay",
            "category": "captions",
            "required_each": True,
            "required_series": False,
        },
        {
            "key": "weather.live_workflow",
            "label": "Venue weather refresh, overlay preview, and stale indicator",
            "category": "weather",
            "required_each": True,
            "required_series": False,
        },
        {
            "key": "game.full_workflow",
            "label": "Complete scoring, possession, clock, graphics, undo, and event workflow",
            "category": "game",
            "required_each": True,
            "required_series": False,
        },
        {
            "key": "game.halftime",
            "label": "Halftime state, graphics, recording, and return to play",
            "category": "game",
            "required_each": True,
            "required_series": False,
        },
        {
            "key": "game.postgame",
            "label": "Final score, postgame graphics, archive, and transcript export",
            "category": "postgame",
            "required_each": True,
            "required_series": False,
        },
        {
            "key": "shutdown.clean",
            "label": "Clean application, OBS, recorder, and hardware shutdown",
            "category": "shutdown",
            "required_each": True,
            "required_series": False,
        },
        {
            "key": "failure.obs_disconnect",
            "label": "OBS disconnect and controlled recovery",
            "category": "failure",
            "required_each": False,
            "required_series": True,
        },
        {
            "key": "failure.network_loss",
            "label": "Primary network loss and backup or local-recording response",
            "category": "failure",
            "required_each": False,
            "required_series": True,
        },
        {
            "key": "failure.application_restart",
            "label": "Application termination, restart, and live-state recovery",
            "category": "failure",
            "required_each": False,
            "required_series": True,
        },
        {
            "key": "failure.caption_worker",
            "label": "Caption worker loss without Command Center failure",
            "category": "failure",
            "required_each": False,
            "required_series": True,
        },
        {
            "key": "failure.weather_stale",
            "label": "Weather fetch failure and last-known stale-data behavior",
            "category": "failure",
            "required_each": False,
            "required_series": True,
        },
        {
            "key": "failure.mixer_disconnect",
            "label": "Mixer or USB audio disconnect and recovery",
            "category": "failure",
            "required_each": False,
            "required_series": True,
        },
        {
            "key": "recovery.snapshot_restore",
            "label": "Verified snapshot restore rehearsal",
            "category": "recovery",
            "required_each": False,
            "required_series": True,
        },
        {
            "key": "weather.alert_delay_lightning",
            "label": "Alert approval, weather delay, lightning timer, and official resumption",
            "category": "weather",
            "required_each": False,
            "required_series": True,
        },
    )

    CHECKLISTS: dict[str, tuple[str, ...]] = {
        "pregame": (
            "Confirm game, venue, rosters, crew, sponsors, and kickoff time.",
            "Run game-day preflight and create or verify a recent safety snapshot.",
            "Verify P4next power, SD card, isolated channels, levels, and local recording.",
            "Verify OBS profile, scene collection, browser sources, stream, and local recording.",
            "Verify captions, weather monitoring, phone control, and primary/backup internet.",
        ),
        "halftime": (
            "Confirm score, quarter, possession, event history, and recording health.",
            "Clear or replace temporary graphics and verify caption/weather overlays.",
            "Check audio levels, storage, network stability, and backup recording.",
        ),
        "postgame": (
            "Confirm final score and complete the broadcast lifecycle.",
            "Export or verify recordings, transcript, event history, and statistics.",
            "Record defects, blockers, corrections, and rehearsal evidence.",
            "Perform a clean shutdown and verify recovery markers.",
        ),
        "emergency": (
            "Follow school and venue officials; software does not declare conditions safe.",
            "Use sponsor-free emergency or weather-delay graphics.",
            "Preserve local recording and last-known verified information during outages.",
            "Document the failure, operator action, recovery, and final disposition.",
        ),
    }

    DEFAULT_STATE: dict[str, Any] = {
        "schema": SCHEMA,
        "rehearsals": [],
        "release_freeze": {
            "frozen": False,
            "frozen_at": 0,
            "operator": "",
            "release_version": "",
            "commit": "",
            "manifest_path": "",
            "snapshot_id": "",
            "rehearsal_ids": [],
            "notes": "",
        },
        "history": [],
        "updated_at": 0,
    }

    def __init__(
        self,
        *,
        state_file: Path,
        release_manifest_file: Path,
        version_file: Path,
        load_system_gates: SystemGateLoader,
        create_snapshot: SnapshotCreator | None = None,
        register_known_good: KnownGoodRegistrar | None = None,
        clock: Clock = time.time,
        token_factory: TokenFactory | None = None,
    ) -> None:
        self.state_file = Path(state_file)
        self.release_manifest_file = Path(release_manifest_file)
        self.version_file = Path(version_file)
        self._load_system_gates = load_system_gates
        self._create_snapshot = create_snapshot
        self._register_known_good = register_known_good
        self._clock = clock
        self._token_factory = token_factory or (lambda: secrets.token_hex(3))
        self._lock = Lock()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.release_manifest_file.parent.mkdir(parents=True, exist_ok=True)

    def catalog(self) -> RehearsalResult:
        return RehearsalResult(
            "OK",
            {
                "drills": copy.deepcopy(list(self.DRILLS)),
                "checklists": {key: list(value) for key, value in self.CHECKLISTS.items()},
                "required_rehearsals": self.REQUIRED_REHEARSALS,
            },
        )

    def status(self) -> RehearsalResult:
        with self._lock:
            state = self._load()
            return RehearsalResult(
                "OK",
                {
                    "rehearsal": copy.deepcopy(state),
                    "readiness": self._readiness(state),
                    "catalog": self.catalog().data,
                },
            )

    def create_rehearsal(self, payload: Any) -> RehearsalResult:
        if not isinstance(payload, dict):
            return RehearsalResult("REHEARSAL_REQUIRED")
        with self._lock:
            state = self._load()
            if state["release_freeze"].get("frozen"):
                return RehearsalResult("RELEASE_FROZEN")
            name = str(payload.get("name", "")).strip()[:160]
            operator = str(payload.get("operator", "")).strip()[:120]
            if not name:
                return RehearsalResult("NAME_REQUIRED")
            if not operator:
                return RehearsalResult("OPERATOR_REQUIRED")
            now = int(self._clock())
            rehearsal_id = self._new_id(state, now)
            rehearsal = {
                "id": rehearsal_id,
                "name": name,
                "operator": operator,
                "scheduled_for": str(payload.get("scheduled_for", "")).strip()[:80],
                "broadcast_id": str(payload.get("broadcast_id", "")).strip()[:120],
                "status": "planned",
                "created_at": now,
                "started_at": 0,
                "completed_at": 0,
                "signoff": "",
                "notes": str(payload.get("notes", "")).strip()[:4000],
                "drills": [
                    {
                        **copy.deepcopy(drill),
                        "result": "not_run",
                        "note": "",
                        "evidence": "",
                        "updated_at": 0,
                    }
                    for drill in self.DRILLS
                ],
                "blockers": [],
            }
            state["rehearsals"].append(rehearsal)
            self._history(state, "rehearsal_created", {"rehearsal_id": rehearsal_id})
            self._write(state)
            return RehearsalResult("REHEARSAL_CREATED", {"rehearsal": copy.deepcopy(rehearsal)})

    def update_drill(self, rehearsal_id: str, drill_key: str, payload: Any) -> RehearsalResult:
        if not isinstance(payload, dict):
            return RehearsalResult("DRILL_UPDATE_REQUIRED")
        with self._lock:
            state = self._load()
            if state["release_freeze"].get("frozen"):
                return RehearsalResult("RELEASE_FROZEN")
            rehearsal = self._find_rehearsal(state, rehearsal_id)
            if rehearsal is None:
                return RehearsalResult("REHEARSAL_NOT_FOUND")
            if rehearsal.get("status") == "completed":
                return RehearsalResult("REHEARSAL_COMPLETED_LOCKED")
            drill = next(
                (item for item in rehearsal["drills"] if item.get("key") == str(drill_key)),
                None,
            )
            if drill is None:
                return RehearsalResult("DRILL_NOT_FOUND")
            result = str(payload.get("result", "")).strip().lower()
            if result not in {"not_run", "passed", "failed"}:
                return RehearsalResult("DRILL_RESULT_INVALID")
            note = str(payload.get("note", "")).strip()[:1000]
            evidence = str(payload.get("evidence", "")).strip()[:2000]
            if result in {"passed", "failed"} and not note:
                return RehearsalResult("DRILL_NOTE_REQUIRED")
            now = int(self._clock())
            if not rehearsal.get("started_at") and result != "not_run":
                rehearsal["started_at"] = now
                rehearsal["status"] = "in_progress"
            drill.update(
                {
                    "result": result,
                    "note": note,
                    "evidence": evidence,
                    "updated_at": now,
                }
            )
            self._history(
                state,
                "drill_updated",
                {"rehearsal_id": rehearsal["id"], "drill_key": drill["key"], "result": result},
            )
            self._write(state)
            return RehearsalResult("DRILL_UPDATED", {"rehearsal": copy.deepcopy(rehearsal), "drill": copy.deepcopy(drill)})

    def add_blocker(self, rehearsal_id: str, payload: Any) -> RehearsalResult:
        if not isinstance(payload, dict):
            return RehearsalResult("BLOCKER_REQUIRED")
        with self._lock:
            state = self._load()
            if state["release_freeze"].get("frozen"):
                return RehearsalResult("RELEASE_FROZEN")
            rehearsal = self._find_rehearsal(state, rehearsal_id)
            if rehearsal is None:
                return RehearsalResult("REHEARSAL_NOT_FOUND")
            description = str(payload.get("description", "")).strip()[:1000]
            if not description:
                return RehearsalResult("BLOCKER_DESCRIPTION_REQUIRED")
            severity = str(payload.get("severity", "blocking")).strip().lower()
            if severity not in {"blocking", "advisory"}:
                return RehearsalResult("BLOCKER_SEVERITY_INVALID")
            now = int(self._clock())
            blocker = {
                "id": f"blocker-{now}-{self._token_factory()}",
                "description": description,
                "severity": severity,
                "status": "open",
                "resolution": "",
                "created_at": now,
                "resolved_at": 0,
            }
            rehearsal["blockers"].append(blocker)
            self._history(state, "blocker_added", {"rehearsal_id": rehearsal["id"], "blocker_id": blocker["id"]})
            self._write(state)
            return RehearsalResult("BLOCKER_ADDED", {"blocker": copy.deepcopy(blocker)})

    def update_blocker(self, rehearsal_id: str, blocker_id: str, payload: Any) -> RehearsalResult:
        if not isinstance(payload, dict):
            return RehearsalResult("BLOCKER_UPDATE_REQUIRED")
        with self._lock:
            state = self._load()
            if state["release_freeze"].get("frozen"):
                return RehearsalResult("RELEASE_FROZEN")
            rehearsal = self._find_rehearsal(state, rehearsal_id)
            if rehearsal is None:
                return RehearsalResult("REHEARSAL_NOT_FOUND")
            blocker = next((item for item in rehearsal["blockers"] if item.get("id") == blocker_id), None)
            if blocker is None:
                return RehearsalResult("BLOCKER_NOT_FOUND")
            status = str(payload.get("status", "")).strip().lower()
            if status not in {"open", "resolved"}:
                return RehearsalResult("BLOCKER_STATUS_INVALID")
            resolution = str(payload.get("resolution", "")).strip()[:1000]
            if status == "resolved" and not resolution:
                return RehearsalResult("BLOCKER_RESOLUTION_REQUIRED")
            blocker["status"] = status
            blocker["resolution"] = resolution if status == "resolved" else ""
            blocker["resolved_at"] = int(self._clock()) if status == "resolved" else 0
            self._history(state, "blocker_updated", {"rehearsal_id": rehearsal["id"], "blocker_id": blocker_id, "status": status})
            self._write(state)
            return RehearsalResult("BLOCKER_UPDATED", {"blocker": copy.deepcopy(blocker)})

    def complete_rehearsal(self, rehearsal_id: str, payload: Any) -> RehearsalResult:
        if not isinstance(payload, dict):
            return RehearsalResult("COMPLETION_REQUIRED")
        with self._lock:
            state = self._load()
            if state["release_freeze"].get("frozen"):
                return RehearsalResult("RELEASE_FROZEN")
            rehearsal = self._find_rehearsal(state, rehearsal_id)
            if rehearsal is None:
                return RehearsalResult("REHEARSAL_NOT_FOUND")
            if str(payload.get("confirmation", "")) != self.COMPLETE_CONFIRMATION:
                return RehearsalResult("CONFIRMATION_REQUIRED")
            signoff = str(payload.get("signoff", "")).strip()[:160]
            if not signoff:
                return RehearsalResult("SIGNOFF_REQUIRED")
            missing = [
                drill["key"]
                for drill in rehearsal["drills"]
                if drill.get("required_each") and drill.get("result") != "passed"
            ]
            blockers = [
                item["id"]
                for item in rehearsal["blockers"]
                if item.get("severity") == "blocking" and item.get("status") == "open"
            ]
            if missing or blockers:
                return RehearsalResult("REHEARSAL_INCOMPLETE", {"missing_drills": missing, "open_blockers": blockers})
            rehearsal.update(
                {
                    "status": "completed",
                    "completed_at": int(self._clock()),
                    "signoff": signoff,
                }
            )
            self._history(state, "rehearsal_completed", {"rehearsal_id": rehearsal["id"], "signoff": signoff})
            self._write(state)
            return RehearsalResult("REHEARSAL_COMPLETED", {"rehearsal": copy.deepcopy(rehearsal), "readiness": self._readiness(state)})

    def reopen_rehearsal(self, rehearsal_id: str, payload: Any) -> RehearsalResult:
        if not isinstance(payload, dict) or str(payload.get("confirmation", "")) != self.REOPEN_CONFIRMATION:
            return RehearsalResult("CONFIRMATION_REQUIRED")
        with self._lock:
            state = self._load()
            if state["release_freeze"].get("frozen"):
                return RehearsalResult("RELEASE_FROZEN")
            rehearsal = self._find_rehearsal(state, rehearsal_id)
            if rehearsal is None:
                return RehearsalResult("REHEARSAL_NOT_FOUND")
            rehearsal.update({"status": "in_progress", "completed_at": 0, "signoff": ""})
            self._history(state, "rehearsal_reopened", {"rehearsal_id": rehearsal["id"]})
            self._write(state)
            return RehearsalResult("REHEARSAL_REOPENED", {"rehearsal": copy.deepcopy(rehearsal)})

    def readiness(self) -> RehearsalResult:
        with self._lock:
            state = self._load()
            readiness = self._readiness(state)
            return RehearsalResult("OK" if readiness["ready"] else "RELEASE_NOT_READY", {"readiness": readiness})

    def freeze_release(self, payload: Any) -> RehearsalResult:
        if not isinstance(payload, dict):
            return RehearsalResult("FREEZE_REQUIRED")
        with self._lock:
            state = self._load()
            if state["release_freeze"].get("frozen"):
                return RehearsalResult("RELEASE_ALREADY_FROZEN", {"release_freeze": copy.deepcopy(state["release_freeze"])})
            if str(payload.get("confirmation", "")) != self.FREEZE_CONFIRMATION:
                return RehearsalResult("CONFIRMATION_REQUIRED")
            operator = str(payload.get("operator", "")).strip()[:160]
            commit = str(payload.get("commit", "")).strip()
            if not operator:
                return RehearsalResult("OPERATOR_REQUIRED")
            if not self.COMMIT_PATTERN.fullmatch(commit):
                return RehearsalResult("INVALID_RELEASE_COMMIT")
            readiness = self._readiness(state)
            if not readiness["ready"]:
                return RehearsalResult("RELEASE_NOT_READY", {"readiness": readiness})

            snapshot_id = ""
            if self._create_snapshot is not None:
                snapshot = self._create_snapshot(
                    kind="release-freeze",
                    note="Phase 6.6 game-day release freeze snapshot.",
                )
                if not getattr(snapshot, "ok", False):
                    return RehearsalResult("SNAPSHOT_FAILED", {"result": getattr(snapshot, "data", {})})
                snapshot_id = str(getattr(snapshot, "data", {}).get("snapshot", {}).get("snapshot_id", ""))

            if self._register_known_good is not None:
                known_good = self._register_known_good(
                    commit=commit,
                    note="Phase 6.6 frozen game-day release candidate.",
                )
                if not getattr(known_good, "ok", False):
                    return RehearsalResult("KNOWN_GOOD_FAILED", {"result": getattr(known_good, "data", {})})

            completed = [item for item in state["rehearsals"] if item.get("status") == "completed"]
            now = int(self._clock())
            version = self._version()
            manifest = {
                "schema": self.SCHEMA,
                "frozen_at": now,
                "operator": operator,
                "release_version": version,
                "commit": commit.lower(),
                "snapshot_id": snapshot_id,
                "rehearsal_ids": [item["id"] for item in completed],
                "system_gates": readiness["system_gates"],
                "series_drills": readiness["series_drills"],
                "notes": str(payload.get("notes", "")).strip()[:4000],
            }
            self._write_json(self.release_manifest_file, manifest)
            state["release_freeze"] = {
                "frozen": True,
                "frozen_at": now,
                "operator": operator,
                "release_version": version,
                "commit": commit.lower(),
                "manifest_path": str(self.release_manifest_file),
                "snapshot_id": snapshot_id,
                "rehearsal_ids": manifest["rehearsal_ids"],
                "notes": manifest["notes"],
            }
            self._history(state, "release_frozen", {"commit": commit.lower(), "operator": operator})
            self._write(state)
            return RehearsalResult("RELEASE_FROZEN", {"release_freeze": copy.deepcopy(state["release_freeze"]), "manifest": manifest})

    def unfreeze_release(self, payload: Any) -> RehearsalResult:
        if not isinstance(payload, dict) or str(payload.get("confirmation", "")) != self.UNFREEZE_CONFIRMATION:
            return RehearsalResult("CONFIRMATION_REQUIRED")
        with self._lock:
            state = self._load()
            if not state["release_freeze"].get("frozen"):
                return RehearsalResult("RELEASE_NOT_FROZEN")
            reason = str(payload.get("reason", "")).strip()[:1000]
            operator = str(payload.get("operator", "")).strip()[:160]
            if not reason or not operator:
                return RehearsalResult("UNFREEZE_REASON_REQUIRED")
            previous = copy.deepcopy(state["release_freeze"])
            state["release_freeze"]["frozen"] = False
            state["release_freeze"]["notes"] = reason
            self._history(state, "release_unfrozen", {"operator": operator, "reason": reason})
            self._write(state)
            return RehearsalResult("RELEASE_UNFROZEN", {"previous": previous, "release_freeze": copy.deepcopy(state["release_freeze"])})

    def manifest(self) -> RehearsalResult:
        with self._lock:
            manifest = self._read_json(self.release_manifest_file, None)
            if not isinstance(manifest, dict):
                return RehearsalResult("MANIFEST_NOT_FOUND")
            return RehearsalResult("OK", {"manifest": manifest})

    def _readiness(self, state: dict[str, Any]) -> dict[str, Any]:
        completed = [item for item in state["rehearsals"] if item.get("status") == "completed"]
        open_blockers = [
            {
                "rehearsal_id": rehearsal["id"],
                **copy.deepcopy(blocker),
            }
            for rehearsal in state["rehearsals"]
            for blocker in rehearsal.get("blockers", [])
            if blocker.get("severity") == "blocking" and blocker.get("status") == "open"
        ]
        series_drills = []
        for catalog in self.DRILLS:
            if not catalog.get("required_series"):
                continue
            evidence = []
            for rehearsal in completed:
                drill = next((item for item in rehearsal["drills"] if item.get("key") == catalog["key"]), None)
                if drill and drill.get("result") == "passed":
                    evidence.append(
                        {
                            "rehearsal_id": rehearsal["id"],
                            "note": drill.get("note", ""),
                            "evidence": drill.get("evidence", ""),
                        }
                    )
            series_drills.append(
                {
                    "key": catalog["key"],
                    "label": catalog["label"],
                    "passed": bool(evidence),
                    "evidence": evidence,
                }
            )

        try:
            raw_gates = self._load_system_gates()
        except Exception as exc:
            raw_gates = {
                "system_gate_loader": {
                    "ready": False,
                    "label": "System gate loader",
                    "note": str(exc),
                }
            }
        if not isinstance(raw_gates, dict):
            raw_gates = {}
        system_gates = []
        for key, value in raw_gates.items():
            item = value if isinstance(value, dict) else {"ready": bool(value)}
            system_gates.append(
                {
                    "key": str(key),
                    "label": str(item.get("label", key)),
                    "ready": bool(item.get("ready", False)),
                    "note": str(item.get("note", "")),
                }
            )
        system_gates.sort(key=lambda item: item["key"])

        conditions = {
            "required_rehearsals": len(completed) >= self.REQUIRED_REHEARSALS,
            "series_drills": all(item["passed"] for item in series_drills),
            "no_open_blockers": not open_blockers,
            "system_gates": bool(system_gates) and all(item["ready"] for item in system_gates),
        }
        return {
            "ready": all(conditions.values()),
            "conditions": conditions,
            "required_rehearsals": self.REQUIRED_REHEARSALS,
            "completed_rehearsals": len(completed),
            "completed_rehearsal_ids": [item["id"] for item in completed],
            "series_drills": series_drills,
            "open_blockers": open_blockers,
            "system_gates": system_gates,
            "release_freeze": copy.deepcopy(state["release_freeze"]),
        }

    def _load(self) -> dict[str, Any]:
        raw = self._read_json(self.state_file, self.DEFAULT_STATE)
        state = self._normalize(raw)
        if not self.state_file.exists() or raw != state:
            self._write_json(self.state_file, state)
        return state

    def _normalize(self, raw: Any) -> dict[str, Any]:
        state = copy.deepcopy(self.DEFAULT_STATE)
        incoming = raw if isinstance(raw, dict) else {}
        state["rehearsals"] = copy.deepcopy(incoming.get("rehearsals", [])) if isinstance(incoming.get("rehearsals"), list) else []
        release = incoming.get("release_freeze", {})
        if isinstance(release, dict):
            state["release_freeze"].update(copy.deepcopy(release))
        state["history"] = copy.deepcopy(incoming.get("history", [])) if isinstance(incoming.get("history"), list) else []
        state["history"] = state["history"][-500:]
        try:
            state["updated_at"] = int(incoming.get("updated_at", 0) or 0)
        except (TypeError, ValueError):
            state["updated_at"] = 0
        return state

    def _write(self, state: dict[str, Any]) -> None:
        state["schema"] = self.SCHEMA
        state["updated_at"] = int(self._clock())
        self._write_json(self.state_file, state)

    def _history(self, state: dict[str, Any], event: str, detail: dict[str, Any]) -> None:
        state["history"].append(
            {
                "event": str(event),
                "detail": copy.deepcopy(detail),
                "at": int(self._clock()),
            }
        )
        state["history"] = state["history"][-500:]

    def _new_id(self, state: dict[str, Any], now: int) -> str:
        existing = {str(item.get("id", "")) for item in state["rehearsals"]}
        while True:
            candidate = f"rehearsal-{now}-{self._token_factory()}"
            if candidate not in existing:
                return candidate

    @staticmethod
    def _find_rehearsal(state: dict[str, Any], rehearsal_id: str) -> dict[str, Any] | None:
        target = str(rehearsal_id or "")
        return next((item for item in state["rehearsals"] if str(item.get("id", "")) == target), None)

    def _version(self) -> str:
        try:
            return self.version_file.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return ""

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return copy.deepcopy(default)

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
