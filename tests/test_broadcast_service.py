from __future__ import annotations

import copy
from typing import Any

from broadcast_service import BroadcastService


class Harness:
    def __init__(self) -> None:
        self.broadcasts: list[dict[str, Any]] = []
        self.schools = {
            "caledonia": {
                "id": "caledonia",
                "broadcast_name": "Caledonia",
                "official_name": "Caledonia High School",
                "classification": "5A",
                "logo_ok": True,
            },
            "new-hope": {
                "id": "new-hope",
                "broadcast_name": "New Hope",
                "official_name": "New Hope High School",
                "classification": "5A",
                "logo_ok": False,
            },
        }
        self.state: dict[str, Any] = {"broadcast_id": "", "sentinel": True}
        self.saved_states: list[dict[str, Any]] = []
        self.detail_writes: list[tuple[dict[str, Any], bool]] = []
        self.detail_deletes: list[str] = []
        self.now = 1_700_000_000.0

    def load_broadcasts(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.broadcasts)

    def save_broadcasts(self, rows: list[dict[str, Any]]) -> None:
        self.broadcasts = copy.deepcopy(rows)

    def get_school(self, school_id: str) -> dict[str, Any] | None:
        school = self.schools.get(school_id)
        return copy.deepcopy(school) if school else None

    @staticmethod
    def resolve_venue(
        school: dict[str, Any] | None,
        sport: str,
    ) -> dict[str, Any] | None:
        if not school:
            return None
        return {
            "id": f"{school['id']}-{sport.lower()}",
            "name": f"{school['broadcast_name']} {sport} Field",
        }

    @staticmethod
    def build_identity(
        school: dict[str, Any] | None,
        sport: str,
    ) -> dict[str, Any]:
        return {
            "school_id": str((school or {}).get("id", "")),
            "sport": sport,
        }

    @staticmethod
    def logo_certification(school: dict[str, Any]):
        return bool(school.get("logo_ok")), ""

    @staticmethod
    def monogram(name: str) -> str:
        return "".join(part[0] for part in name.split() if part).upper()

    @staticmethod
    def load_config() -> dict[str, Any]:
        return {
            "broadcast_defaults": {
                "sport": "Football",
                "venue": "Default Venue",
                "visual_mode": "graphic",
            },
            "obs": {"profile": "CSRN Test"},
        }

    def load_state(self) -> dict[str, Any]:
        return copy.deepcopy(self.state)

    def save_state(self, state: dict[str, Any]) -> None:
        self.state = copy.deepcopy(state)
        self.saved_states.append(copy.deepcopy(state))

    @staticmethod
    def default_state() -> dict[str, Any]:
        return {"broadcast_id": "", "broadcast_created": False}

    def write_detail(self, record: dict[str, Any], existing_only: bool) -> None:
        self.detail_writes.append((copy.deepcopy(record), existing_only))

    def delete_detail(self, broadcast_id: str) -> None:
        self.detail_deletes.append(broadcast_id)

    def service(self) -> BroadcastService:
        return BroadcastService(
            load_broadcasts=self.load_broadcasts,
            save_broadcasts=self.save_broadcasts,
            get_school=self.get_school,
            resolve_venue=self.resolve_venue,
            build_identity=self.build_identity,
            logo_certification=self.logo_certification,
            school_monogram=self.monogram,
            load_config=self.load_config,
            load_state=self.load_state,
            save_state=self.save_state,
            default_state=self.default_state,
            write_detail=self.write_detail,
            delete_detail=self.delete_detail,
            clock=lambda: self.now,
            year_provider=lambda: "2026",
        )


def test_week_code_and_next_id_are_stable() -> None:
    harness = Harness()
    harness.broadcasts = [
        {"broadcast_id": "FB-2026-5A-W03-001"},
        {"broadcast_id": "FB-2026-5A-W03-004"},
        {"broadcast_id": "BB-2026-5A-W03-002"},
    ]
    service = harness.service()

    assert service.football_week_code("Week 3") == "W03"
    assert service.football_week_code("Playoff") == "WPLA"
    assert service.next_id("Football", "2026", "Class 5A", 3) == (
        "FB-2026-5A-W03-005"
    )


def test_list_records_filters_archived_and_sorts_schedule_descending() -> None:
    harness = Harness()
    harness.broadcasts = [
        {
            "broadcast_id": "older",
            "date": "2026-08-01",
            "scheduled_start": "07:00 PM",
        },
        {
            "broadcast_id": "newer",
            "date": "2026-08-08",
            "scheduled_start": "06:00 PM",
        },
        {
            "broadcast_id": "archived",
            "date": "2026-09-01",
            "archived": True,
        },
    ]

    result = harness.service().list_records()

    assert result.ok
    assert [row["broadcast_id"] for row in result.data["broadcasts"]] == [
        "newer",
        "older",
    ]
    all_rows = harness.service().list_records(include_archived=True)
    assert len(all_rows.data["broadcasts"]) == 3


def test_read_returns_copy_or_not_found() -> None:
    harness = Harness()
    harness.broadcasts = [{"broadcast_id": "game-1", "status": "planned"}]
    service = harness.service()

    found = service.read("game-1")
    assert found.ok
    found.data["broadcast"]["status"] = "changed"
    assert harness.broadcasts[0]["status"] == "planned"
    assert service.read("missing").code == "NOT_FOUND"


def test_create_builds_planned_record_and_branding_warning() -> None:
    harness = Harness()
    service = harness.service()

    result = service.create(
        {
            "home_school_id": "caledonia",
            "visitor_school_id": "new-hope",
            "season": "2026",
            "week": "2",
            "date": "2026-08-21",
            "scheduled_start": "07:30 PM",
            "crew": {"play_by_play": "Jason", "producer": "Jordan"},
        }
    )

    assert result.ok
    record = result.data["broadcast"]
    assert record["broadcast_id"] == "FB-2026-5A-W02-001"
    assert record["status"] == "planned"
    assert record["home_team"] == "Caledonia"
    assert record["visitor_team"] == "New Hope"
    assert record["venue_id"] == "caledonia-football"
    assert record["venue"] == "Caledonia Football Field"
    assert record["obs_profile"] == "CSRN Test"
    assert record["crew"]["play_by_play"] == "Jason"
    assert result.data["warnings"] == [
        "Visitor has no certified logo; NH monogram will be used."
    ]
    assert harness.broadcasts == [record]
    assert harness.detail_writes == [(record, False)]


def test_create_supports_manual_teams_and_defaults() -> None:
    harness = Harness()

    result = harness.service().create(
        {"home_team": "Alumni", "visitor_team": "Faculty"}
    )

    assert result.ok
    record = result.data["broadcast"]
    assert record["broadcast_id"] == "FB-2026-OPEN-W01-001"
    assert record["home_team"] == "Alumni"
    assert record["visitor_team"] == "Faculty"
    assert record["venue"] == "Default Venue"
    assert result.data["warnings"] == []


def test_update_preserves_contract_and_syncs_active_state() -> None:
    harness = Harness()
    harness.broadcasts = [
        {
            "broadcast_id": "game-1",
            "sport": "Football",
            "home_school_id": "caledonia",
            "visitor_school_id": "",
            "home_team": "Caledonia",
            "visitor_team": "Visitor",
            "home_identity": {"old": True},
            "visitor_identity": {"old": True},
            "created_at": 10,
        }
    ]
    harness.state = {"broadcast_id": "game-1", "date": "old"}

    result = harness.service().update(
        "game-1",
        {
            "visitor_school_id": "new-hope",
            "date": "2026-09-01",
            "venue": "Updated Stadium",
        },
    )

    assert result.ok
    record = result.data["broadcast"]
    assert record["visitor_team"] == "New Hope"
    assert record["date"] == "2026-09-01"
    assert record["created_at"] == 10
    assert record["updated_at"] == int(harness.now)
    assert harness.state["visitor_team"] == "New Hope"
    assert harness.state["venue"] == "Updated Stadium"
    assert result.data["warnings"] == [
        "Visitor has no certified logo; NH monogram will be used."
    ]
    assert harness.detail_writes[-1] == (record, False)


def test_update_missing_record_returns_not_found_without_writes() -> None:
    harness = Harness()

    result = harness.service().update("missing", {"date": "2026-01-01"})

    assert result.code == "NOT_FOUND"
    assert harness.detail_writes == []
    assert harness.saved_states == []


def test_set_status_normalizes_prepared_and_preserves_detail_contract() -> None:
    harness = Harness()
    harness.broadcasts = [{"broadcast_id": "game-1", "status": "planned"}]
    service = harness.service()

    invalid = service.set_status("game-1", "cancelled")
    assert invalid.code == "INVALID_STATUS"

    result = service.set_status("game-1", "prepared")
    assert result.ok
    assert result.data["broadcast"]["status"] == "planned"
    assert harness.detail_writes[-1][1] is True
    assert service.set_status("missing", "live").code == "NOT_FOUND"


def test_update_linked_status_sets_lifecycle_metadata_and_extra() -> None:
    harness = Harness()
    harness.broadcasts = [{"broadcast_id": "game-1", "status": "planned"}]
    service = harness.service()

    live = service.update_linked_status("game-1", "live", {"note": "started"})
    assert live.ok
    assert live.data["broadcast"]["started_at"] == int(harness.now)
    assert live.data["broadcast"]["note"] == "started"

    harness.now += 300
    completed = service.update_linked_status(
        "game-1",
        "completed",
        {"final_home_score": 28, "final_visitor_score": 14},
    )
    assert completed.data["broadcast"]["completed_at"] == int(harness.now)
    assert completed.data["broadcast"]["final_home_score"] == 28
    assert service.update_linked_status("", "live").code == "NO_BROADCAST_ID"
    assert service.update_linked_status("missing", "live").code == "NOT_FOUND"


def test_resume_record_clears_completion_fields() -> None:
    harness = Harness()
    harness.broadcasts = [
        {
            "broadcast_id": "game-1",
            "status": "completed",
            "completed_at": 10,
            "final_home_score": 21,
            "final_visitor_score": 7,
        }
    ]

    result = harness.service().resume_record("game-1")

    assert result.ok
    record = result.data["broadcast"]
    assert record["status"] == "live"
    assert "completed_at" not in record
    assert "final_home_score" not in record
    assert "final_visitor_score" not in record
    assert harness.detail_writes[-1] == (record, False)


def test_delete_removes_detail_and_resets_matching_active_state() -> None:
    harness = Harness()
    harness.broadcasts = [
        {"broadcast_id": "game-1"},
        {"broadcast_id": "game-2"},
    ]
    harness.state = {"broadcast_id": "game-1", "broadcast_created": True}
    service = harness.service()

    result = service.delete("game-1")

    assert result.ok
    assert result.data == {"deleted": "game-1"}
    assert harness.broadcasts == [{"broadcast_id": "game-2"}]
    assert harness.detail_deletes == ["game-1"]
    assert harness.state == {"broadcast_id": "", "broadcast_created": False}
    assert service.delete("missing").code == "NOT_FOUND"
