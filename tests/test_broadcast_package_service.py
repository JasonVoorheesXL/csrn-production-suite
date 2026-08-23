from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from broadcast_package_service import BroadcastPackageService


BROADCAST = {
    "broadcast_id": "FB-2026-5A-W01-001",
    "sport": "Football",
    "season": "2026",
    "week": "1",
    "classification": "5A",
    "level": "Varsity",
    "division": "Boys",
    "home_school_id": "caledonia",
    "visitor_school_id": "new-hope",
    "home_team": "Caledonia",
    "visitor_team": "New Hope",
    "home_identity": {"primary_color": "#C9203B"},
    "visitor_identity": {"primary_color": "#000000"},
    "venue": "Caledonia HS Football Field",
    "venue_id": "caledonia-football",
    "date": "2026-08-21",
    "scheduled_start": "19:00",
    "visual_mode": "graphic",
    "crew": {"play_by_play": "Jason"},
    "status": "planned",
}


class MemoryStore:
    def __init__(self) -> None:
        self.packages: list[dict[str, Any]] = []
        self.state: dict[str, Any] = {"existing": "preserved"}
        self.package_saves = 0
        self.state_saves = 0

    def load_packages(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.packages)

    def save_packages(self, items: list[dict[str, Any]]) -> None:
        self.packages = copy.deepcopy(items)
        self.package_saves += 1

    def load_state(self) -> dict[str, Any]:
        return copy.deepcopy(self.state)

    def save_state(self, state: dict[str, Any]) -> None:
        self.state = copy.deepcopy(state)
        self.state_saves += 1


def make_service(
    *,
    store: MemoryStore | None = None,
    broadcasts: list[dict[str, Any]] | None = None,
    now: float = 1000.25,
) -> tuple[BroadcastPackageService, MemoryStore]:
    memory = store or MemoryStore()
    service = BroadcastPackageService(
        load_packages=memory.load_packages,
        save_packages=memory.save_packages,
        load_broadcasts=lambda: copy.deepcopy(
            BROADCAST if broadcasts is None else broadcasts
        )
        if isinstance(BROADCAST if broadcasts is None else broadcasts, list)
        else [copy.deepcopy(BROADCAST)],
        load_rosters=lambda: [{"id": "roster-home"}],
        load_personnel=lambda: [{"id": "person-jason"}],
        load_sponsors=lambda: [{"id": "sponsor-1", "active": True}],
        load_config=lambda: {"obs": {"required_scene": "Scorebug"}},
        sponsor_contract_state=lambda _sponsor: "Active",
        load_state=memory.load_state,
        save_state=memory.save_state,
        clock=lambda: now,
    )
    return service, memory


def linked_package(**overrides: Any) -> dict[str, Any]:
    package = {
        "id": "pkg-existing",
        "name": "Friday Night Football",
        "broadcast_id": BROADCAST["broadcast_id"],
        "status": "Planning",
        "roster_ids": ["roster-home"],
        "personnel_ids": ["person-jason"],
        "sponsor_ids": ["sponsor-1"],
        "lineups": {"home": ["10"]},
        "graphics_profile": "CSRN Default",
        "notes": "",
        "locked": False,
        "updated_at": 900,
        "created_at": 800,
    }
    package.update(overrides)
    return package


def test_health_reports_ready_for_complete_package() -> None:
    service, _store = make_service()

    health = service.health(linked_package())

    assert health["ready"] is True
    assert health["score"] == 100
    assert all(check["ok"] for check in health["checks"])


def test_create_applies_defaults_and_list_recalculates_health() -> None:
    service, store = make_service()

    created = service.create(
        {
            "broadcast_id": BROADCAST["broadcast_id"],
            "roster_ids": ["roster-home"],
            "personnel_ids": ["person-jason"],
        }
    )

    assert created.ok
    package = created.data["package"]
    assert package["id"] == "pkg-1000250"
    assert package["name"] == "Untitled Broadcast Package"
    assert package["status"] == "Planning"
    assert package["graphics_profile"] == "CSRN Default"
    assert store.package_saves == 1

    listed = service.list_packages()
    assert listed[0]["id"] == package["id"]
    assert "health" in listed[0]


def test_locked_package_requires_unlock_for_update_and_cannot_delete() -> None:
    store = MemoryStore()
    store.packages = [linked_package(locked=True)]
    service, _store = make_service(store=store)

    blocked_update = service.update("pkg-existing", {"name": "Changed"})
    blocked_delete = service.delete("pkg-existing")
    updated = service.update(
        "pkg-existing",
        {"name": "Changed", "unlock": True, "locked": False},
    )

    assert blocked_update.code == "PACKAGE_LOCKED"
    assert blocked_delete.code == "PACKAGE_LOCKED"
    assert updated.ok
    assert updated.data["package"]["name"] == "Changed"
    assert updated.data["package"]["locked"] is False


def test_duplicate_resets_identity_status_and_lock() -> None:
    store = MemoryStore()
    store.packages = [linked_package(locked=True, status="Loaded")]
    service, _store = make_service(store=store)

    result = service.duplicate("pkg-existing")

    assert result.ok
    duplicate = result.data["package"]
    assert duplicate["id"] == "pkg-1000250"
    assert duplicate["name"] == "Friday Night Football Copy"
    assert duplicate["status"] == "Planning"
    assert duplicate["locked"] is False
    assert duplicate["created_at"] == 1000
    assert len(store.packages) == 2


def test_load_hydrates_state_and_marks_package_loaded() -> None:
    store = MemoryStore()
    store.packages = [linked_package()]
    service, _store = make_service(store=store)

    result = service.load("pkg-existing")

    assert result.ok
    assert result.data["state"]["existing"] == "preserved"
    assert result.data["state"]["broadcast_created"] is True
    assert result.data["state"]["broadcast_id"] == BROADCAST["broadcast_id"]
    assert result.data["state"]["broadcast_package_id"] == "pkg-existing"
    assert result.data["state"]["package_roster_ids"] == ["roster-home"]
    assert result.data["state"]["package_lineups"] == {"home": ["10"]}
    assert store.state_saves == 1
    assert store.packages[0]["status"] == "Loaded"
    assert store.packages[0]["last_loaded_at"] == 1000


def test_missing_package_and_broadcast_return_domain_errors() -> None:
    service, _store = make_service()
    assert service.update("missing", {}).code == "NOT_FOUND"
    assert service.delete("missing").code == "NOT_FOUND"
    assert service.duplicate("missing").code == "NOT_FOUND"
    assert service.load("missing").code == "NOT_FOUND"

    store = MemoryStore()
    store.packages = [linked_package()]
    no_broadcast_service, _store = make_service(
        store=store,
        broadcasts=[],
    )
    assert (
        no_broadcast_service.load("pkg-existing").code
        == "BROADCAST_NOT_FOUND"
    )

