from __future__ import annotations

import copy
import inspect
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

from flask import jsonify

from persistence_engine import (
    DataCorruptionError,
    DestructiveWriteBlocked,
    JsonPersistenceEngine,
    PersistencePolicy,
)
from roster_store import RosterStore


LOG = logging.getLogger("csrn.foundation")


class FoundationRuntime:
    """Install the v1.13 persistence protections around the existing application.

    This compatibility layer deliberately leaves the route and feature code in app.py
    intact. Python route functions resolve module globals when they execute, so replacing
    the module's load/save functions here upgrades the running application without a
    broad rewrite of the existing feature code.
    """

    LIST_GUARDS = PersistencePolicy(
        backup_count=10,
        block_empty_replacement=True,
        block_large_count_drop=True,
        max_count_drop_ratio=0.80,
    )
    NORMAL_POLICY = PersistencePolicy(backup_count=10)

    def __init__(self, module: Any) -> None:
        self.module = module
        data_dir = Path(module.DATA_DIR)
        self.engine = JsonPersistenceEngine(
            backup_root=data_dir / "Backups" / "Persistence",
            quarantine_root=data_dir / "Backups" / "Quarantine",
        )
        self.rosters = RosterStore(self.engine, Path(module.ROSTERS_FILE))
        self._local = threading.local()
        self._original_delete_roster = None

    @staticmethod
    def _valid_json(value: Any) -> bool:
        try:
            json.dumps(value)
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _valid_list(value: Any) -> bool:
        return isinstance(value, list) and all(isinstance(item, dict) for item in value)

    @staticmethod
    def _valid_dict(value: Any) -> bool:
        return isinstance(value, dict)

    def _audit(self, action: str, path: Path, detail: str = "") -> None:
        audit_file = Path(self.module.DATA_DIR) / "Logs" / "persistence_audit.log"
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        line = f"{int(time.time())}\t{action}\t{path}\t{detail}\n"
        try:
            with audit_file.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            LOG.exception("Unable to write persistence audit entry")

    def load_json(self, path: Path, default: Any) -> Any:
        path = Path(path)
        validator: Callable[[Any], bool] = self._valid_json
        if isinstance(default, list):
            validator = lambda value: isinstance(value, list)
        elif isinstance(default, dict):
            validator = self._valid_dict
        try:
            return self.engine.load(path, default, validator=validator)
        except DataCorruptionError as exc:
            self._audit("LOAD_FAILED", path, str(exc))
            raise

    def save_json(self, path: Path, data: Any) -> None:
        path = Path(path)
        policy = self.LIST_GUARDS if isinstance(data, list) else self.NORMAL_POLICY
        force = bool(getattr(self._local, "force_destructive", False))
        try:
            self.engine.save(
                path,
                data,
                validator=self._valid_json,
                policy=policy,
                force=force,
            )
            self._audit("SAVE", path, f"records={self.engine._record_count(data)} force={force}")
        except DestructiveWriteBlocked as exc:
            self._audit("SAVE_BLOCKED", path, str(exc))
            raise

    def load_rosters(self) -> list[dict[str, Any]]:
        items = self.rosters.load()
        changed = False
        for roster in items:
            before = copy.deepcopy(roster)
            roster.setdefault(
                "id",
                self.module.normalize_roster_id(
                    f"{roster.get('school_id','school')}-{roster.get('sport','football')}-"
                    f"{roster.get('season','season')}-{roster.get('level','varsity')}-"
                    f"{roster.get('division','boys')}"
                ),
            )
            roster.setdefault("school_id", "")
            roster.setdefault("sport", "Football")
            roster.setdefault("season", "")
            roster.setdefault("level", "Varsity")
            roster.setdefault("division", "Boys")
            roster.setdefault("players", [])
            if not isinstance(roster["players"], list):
                roster["players"] = []
            for player in roster["players"]:
                if not isinstance(player, dict):
                    continue
                player.setdefault(
                    "id",
                    self.module.normalize_player_id(
                        f"{player.get('number','')}-{player.get('first_name','')}-{player.get('last_name','')}"
                    ),
                )
                player.setdefault("preferred_name", "")
                player.setdefault("position", "")
                player.setdefault("secondary_position", "")
                player.setdefault("grade", "")
                player.setdefault("height", "")
                player.setdefault("weight", "")
                player.setdefault("captain", False)
                player.setdefault("starter", False)
                player.setdefault("status", "active")
                player.setdefault("headshot", "")
                player.setdefault("pronunciation", "")
                player.setdefault("pronunciation_verified", False)
            if roster != before:
                changed = True
        if changed:
            self.rosters.save(items, force=False)
            self._audit("ROSTER_NORMALIZED", Path(self.module.ROSTERS_FILE), f"records={len(items)}")
        return items

    def save_rosters(self, items: list[dict[str, Any]]) -> None:
        force = bool(getattr(self._local, "force_destructive", False))
        self.rosters.save(items, force=force)
        self._audit("ROSTER_SAVE", Path(self.module.ROSTERS_FILE), f"records={len(items)} force={force}")

    def _wrap_dict_list_store(
        self,
        path: Path,
        key: str,
        *,
        guard: bool = True,
    ) -> tuple[Callable[[], list[dict[str, Any]]], Callable[[list[dict[str, Any]]], None]]:
        path = Path(path)

        def load() -> list[dict[str, Any]]:
            raw = self.engine.load(path, {key: []}, validator=self._valid_dict)
            items = raw if isinstance(raw, list) else raw.get(key, [])
            return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []

        def save(items: list[dict[str, Any]]) -> None:
            force = bool(getattr(self._local, "force_destructive", False))
            policy = self.LIST_GUARDS if guard else self.NORMAL_POLICY
            self.engine.save(path, {key: items}, validator=self._valid_dict, policy=policy, force=force)
            self._audit("STORE_SAVE", path, f"records={len(items)} force={force}")

        return load, save

    def _wrap_plain_list_store(
        self,
        path: Path,
        *,
        guard: bool = True,
    ) -> tuple[Callable[[], list[dict[str, Any]]], Callable[[list[dict[str, Any]]], None]]:
        path = Path(path)

        def load() -> list[dict[str, Any]]:
            raw = self.engine.load(path, [], validator=lambda value: isinstance(value, list))
            return [item for item in raw if isinstance(item, dict)]

        def save(items: list[dict[str, Any]]) -> None:
            force = bool(getattr(self._local, "force_destructive", False))
            policy = self.LIST_GUARDS if guard else self.NORMAL_POLICY
            self.engine.save(path, items, validator=lambda value: isinstance(value, list), policy=policy, force=force)
            self._audit("STORE_SAVE", path, f"records={len(items)} force={force}")

        return load, save

    def _install_known_stores(self) -> None:
        m = self.module
        stores = [
            ("load_packages", "save_packages", getattr(m, "PACKAGES_FILE", None), "packages", True),
            ("load_schools", "save_schools", getattr(m, "SCHOOLS_FILE", None), None, True),
            ("load_broadcasters", "save_broadcasters", getattr(m, "BROADCASTERS_FILE", None), None, True),
            ("load_sponsors", "save_sponsors", getattr(m, "SPONSORS_FILE", None), None, True),
            ("load_assets", "save_assets", getattr(m, "ASSETS_FILE", None), None, True),
            ("load_venues", "save_venues", getattr(m, "VENUES_FILE", None), None, True),
            ("load_logos", "save_logos", getattr(m, "LOGOS_FILE", None), None, True),
            ("load_broadcasts", "save_broadcasts", getattr(m, "BROADCAST_INDEX_FILE", None), None, True),
            ("load_build_journal", "save_build_journal", getattr(m, "BUILD_JOURNAL_FILE", None), None, False),
        ]
        for load_name, save_name, path, key, guard in stores:
            if path is None or not hasattr(m, load_name) or not hasattr(m, save_name):
                continue
            if key:
                load, save = self._wrap_dict_list_store(path, key, guard=guard)
            else:
                load, save = self._wrap_plain_list_store(path, guard=guard)
            setattr(m, load_name, load)
            setattr(m, save_name, save)

    def _install_delete_roster_endpoint(self) -> None:
        m = self.module
        endpoint = "delete_roster"
        original = m.app.view_functions.get(endpoint)
        if original is None:
            return
        self._original_delete_roster = original

        @m.require_auth
        def foundation_delete_roster(roster_id: str):
            items = self.load_rosters()
            if not any(row.get("id") == roster_id for row in items):
                return jsonify({"error": "ROSTER_NOT_FOUND"}), 404
            remaining = [row for row in items if row.get("id") != roster_id]
            previous = bool(getattr(self._local, "force_destructive", False))
            self._local.force_destructive = len(remaining) == 0
            try:
                self.save_rosters(remaining)
            finally:
                self._local.force_destructive = previous
            return jsonify({"ok": True, "backup_created": True})

        foundation_delete_roster.__name__ = endpoint
        m.app.view_functions[endpoint] = foundation_delete_roster

    def _install_error_handlers(self) -> None:
        m = self.module

        @m.app.errorhandler(DataCorruptionError)
        def handle_corruption(exc: DataCorruptionError):
            LOG.exception("Persistence corruption detected")
            return jsonify({
                "error": "DATA_CORRUPTION",
                "message": str(exc),
                "recovery_required": True,
            }), 503

        @m.app.errorhandler(DestructiveWriteBlocked)
        def handle_destructive_write(exc: DestructiveWriteBlocked):
            return jsonify({
                "error": "DESTRUCTIVE_WRITE_BLOCKED",
                "message": str(exc),
            }), 409

    def install(self) -> "FoundationRuntime":
        m = self.module
        m.ensure_data_architecture()
        setattr(m, "load_json", self.load_json)
        setattr(m, "save_json", self.save_json)
        setattr(m, "load_rosters", self.load_rosters)
        setattr(m, "save_rosters", self.save_rosters)
        self._install_known_stores()
        self._install_delete_roster_endpoint()
        self._install_error_handlers()
        self._audit("FOUNDATION_RUNTIME_INSTALLED", Path(m.BASE_DIR), "v1.13")
        return self


def install_foundation_runtime(module: Any) -> FoundationRuntime:
    return FoundationRuntime(module).install()
