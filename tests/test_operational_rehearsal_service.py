from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from operational_rehearsal_service import OperationalRehearsalService


@dataclass
class StubResult:
    code: str = "OK"
    data: dict = field(default_factory=dict)
    ok: bool = True


def ready_gates() -> dict:
    return {
        "preflight": {"ready": True, "label": "Preflight", "note": "Ready"},
        "commissioning": {"ready": True, "label": "Commissioning", "note": "Ready"},
        "recovery": {"ready": True, "label": "Recovery", "note": "Clean"},
        "captions": {"ready": True, "label": "Captions", "note": "Assigned"},
        "weather": {"ready": True, "label": "Weather", "note": "Fresh"},
    }


def make_service(tmp_path: Path, *, gates=None):
    now = [1_700_000_000]
    tokens = iter([f"{index:06x}" for index in range(1, 100)])
    snapshot_calls = []
    known_good_calls = []

    def snapshot(**kwargs):
        snapshot_calls.append(kwargs)
        return StubResult(
            code="SNAPSHOT_CREATED",
            data={"snapshot": {"snapshot_id": "release-snapshot"}},
        )

    def known_good(**kwargs):
        known_good_calls.append(kwargs)
        return StubResult(code="KNOWN_GOOD_REGISTERED", data={"release": kwargs})

    version_file = tmp_path / "VERSION.txt"
    version_file.write_text("1.13.0-alpha.6f", encoding="utf-8")
    service = OperationalRehearsalService(
        state_file=tmp_path / "Data" / "Rehearsals" / "rehearsals.json",
        release_manifest_file=tmp_path / "Data" / "Releases" / "game_day_release_manifest.json",
        version_file=version_file,
        load_system_gates=(gates or ready_gates),
        create_snapshot=snapshot,
        register_known_good=known_good,
        clock=lambda: now[0],
        token_factory=lambda: next(tokens),
    )
    return service, now, snapshot_calls, known_good_calls


def create_rehearsal(service: OperationalRehearsalService, name="Rehearsal One") -> dict:
    result = service.create_rehearsal({"name": name, "operator": "Producer"})
    assert result.ok
    return result.data["rehearsal"]


def pass_drills(service: OperationalRehearsalService, rehearsal_id: str, *, each=True, series=False):
    for drill in service.catalog().data["drills"]:
        if (each and drill["required_each"]) or (series and drill["required_series"]):
            result = service.update_drill(
                rehearsal_id,
                drill["key"],
                {
                    "result": "passed",
                    "note": f"Passed {drill['key']}",
                    "evidence": f"evidence/{rehearsal_id}/{drill['key']}",
                },
            )
            assert result.ok


def complete(service: OperationalRehearsalService, rehearsal_id: str):
    return service.complete_rehearsal(
        rehearsal_id,
        {
            "confirmation": service.COMPLETE_CONFIRMATION,
            "signoff": "Lead Producer",
        },
    )


def prepare_ready_release(service: OperationalRehearsalService):
    first = create_rehearsal(service, "Full Game One")
    pass_drills(service, first["id"], each=True, series=True)
    assert complete(service, first["id"]).ok
    second = create_rehearsal(service, "Full Game Two")
    pass_drills(service, second["id"], each=True)
    assert complete(service, second["id"]).ok
    return first, second


def test_catalog_contains_two_rehearsal_policy_and_checklists(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    catalog = service.catalog().data
    assert catalog["required_rehearsals"] == 2
    assert any(item["key"] == "failure.obs_disconnect" for item in catalog["drills"])
    assert set(catalog["checklists"]) == {"pregame", "halftime", "postgame", "emergency"}


def test_status_creates_persistent_default_state(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    result = service.status()
    assert result.ok
    assert result.data["rehearsal"]["rehearsals"] == []
    assert service.state_file.exists()


def test_create_rehearsal_requires_object_name_and_operator(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    assert service.create_rehearsal([]).code == "REHEARSAL_REQUIRED"
    assert service.create_rehearsal({"operator": "Producer"}).code == "NAME_REQUIRED"
    assert service.create_rehearsal({"name": "Test"}).code == "OPERATOR_REQUIRED"


def test_create_rehearsal_has_complete_drill_catalog(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    rehearsal = create_rehearsal(service)
    assert rehearsal["status"] == "planned"
    assert len(rehearsal["drills"]) == len(service.DRILLS)
    saved = json.loads(service.state_file.read_text(encoding="utf-8"))
    assert saved["rehearsals"][0]["id"] == rehearsal["id"]


def test_update_drill_requires_result_and_note(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    rehearsal = create_rehearsal(service)
    assert service.update_drill(rehearsal["id"], "missing", {}).code == "DRILL_NOT_FOUND"
    assert service.update_drill(
        rehearsal["id"], "pregame.preflight", {"result": "maybe"}
    ).code == "DRILL_RESULT_INVALID"
    assert service.update_drill(
        rehearsal["id"], "pregame.preflight", {"result": "passed"}
    ).code == "DRILL_NOTE_REQUIRED"


def test_update_drill_starts_rehearsal_and_records_evidence(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    rehearsal = create_rehearsal(service)
    result = service.update_drill(
        rehearsal["id"],
        "pregame.preflight",
        {"result": "passed", "note": "Passed", "evidence": "video-01"},
    )
    assert result.data["rehearsal"]["status"] == "in_progress"
    assert result.data["drill"]["evidence"] == "video-01"


def test_blocking_defect_requires_resolution(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    rehearsal = create_rehearsal(service)
    added = service.add_blocker(
        rehearsal["id"],
        {"description": "OBS source missing", "severity": "blocking"},
    )
    blocker = added.data["blocker"]
    assert service.update_blocker(
        rehearsal["id"], blocker["id"], {"status": "resolved"}
    ).code == "BLOCKER_RESOLUTION_REQUIRED"
    resolved = service.update_blocker(
        rehearsal["id"],
        blocker["id"],
        {"status": "resolved", "resolution": "Source restored and retested"},
    )
    assert resolved.data["blocker"]["status"] == "resolved"


def test_open_blocker_prevents_rehearsal_completion(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    rehearsal = create_rehearsal(service)
    pass_drills(service, rehearsal["id"], each=True)
    service.add_blocker(rehearsal["id"], {"description": "Audio clipping"})
    result = complete(service, rehearsal["id"])
    assert result.code == "REHEARSAL_INCOMPLETE"
    assert result.data["open_blockers"]


def test_missing_required_each_drills_prevent_completion(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    rehearsal = create_rehearsal(service)
    result = complete(service, rehearsal["id"])
    assert result.code == "REHEARSAL_INCOMPLETE"
    assert "pregame.preflight" in result.data["missing_drills"]


def test_rehearsal_completion_requires_exact_confirmation_and_signoff(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    rehearsal = create_rehearsal(service)
    pass_drills(service, rehearsal["id"], each=True)
    assert service.complete_rehearsal(rehearsal["id"], {"confirmation": "yes"}).code == "CONFIRMATION_REQUIRED"
    assert service.complete_rehearsal(
        rehearsal["id"], {"confirmation": service.COMPLETE_CONFIRMATION}
    ).code == "SIGNOFF_REQUIRED"
    assert complete(service, rehearsal["id"]).data["rehearsal"]["status"] == "completed"


def test_completed_rehearsal_is_locked_until_reopened(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    rehearsal = create_rehearsal(service)
    pass_drills(service, rehearsal["id"], each=True)
    assert complete(service, rehearsal["id"]).ok
    assert service.update_drill(
        rehearsal["id"], "pregame.preflight", {"result": "failed", "note": "Changed"}
    ).code == "REHEARSAL_COMPLETED_LOCKED"
    assert service.reopen_rehearsal(rehearsal["id"], {"confirmation": "wrong"}).code == "CONFIRMATION_REQUIRED"
    reopened = service.reopen_rehearsal(
        rehearsal["id"], {"confirmation": service.REOPEN_CONFIRMATION}
    )
    assert reopened.data["rehearsal"]["status"] == "in_progress"


def test_readiness_requires_two_completed_rehearsals(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    rehearsal = create_rehearsal(service)
    pass_drills(service, rehearsal["id"], each=True, series=True)
    assert complete(service, rehearsal["id"]).ok
    readiness = service.readiness().data["readiness"]
    assert readiness["completed_rehearsals"] == 1
    assert readiness["conditions"]["required_rehearsals"] is False


def test_series_failure_drills_may_be_split_across_rehearsals(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    first = create_rehearsal(service, "One")
    second = create_rehearsal(service, "Two")
    series = [item for item in service.catalog().data["drills"] if item["required_series"]]
    for index, drill in enumerate(series):
        target = first if index % 2 == 0 else second
        assert service.update_drill(
            target["id"], drill["key"], {"result": "passed", "note": "Injected and recovered"}
        ).ok
    for rehearsal in (first, second):
        pass_drills(service, rehearsal["id"], each=True)
        assert complete(service, rehearsal["id"]).ok
    assert service.readiness().data["readiness"]["conditions"]["series_drills"] is True


def test_system_gate_failure_blocks_release_readiness(tmp_path: Path) -> None:
    def gates():
        value = ready_gates()
        value["weather"] = {"ready": False, "label": "Weather", "note": "Stale"}
        return value

    service, *_ = make_service(tmp_path, gates=gates)
    prepare_ready_release(service)
    readiness = service.readiness().data["readiness"]
    assert readiness["ready"] is False
    assert next(item for item in readiness["system_gates"] if item["key"] == "weather")["ready"] is False


def test_freeze_requires_confirmation_operator_and_commit(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    prepare_ready_release(service)
    assert service.freeze_release({}).code == "CONFIRMATION_REQUIRED"
    assert service.freeze_release({"confirmation": service.FREEZE_CONFIRMATION}).code == "OPERATOR_REQUIRED"
    assert service.freeze_release(
        {"confirmation": service.FREEZE_CONFIRMATION, "operator": "Producer", "commit": "invalid"}
    ).code == "INVALID_RELEASE_COMMIT"


def test_freeze_creates_snapshot_known_good_and_manifest(tmp_path: Path) -> None:
    service, _, snapshot_calls, known_good_calls = make_service(tmp_path)
    first, second = prepare_ready_release(service)
    result = service.freeze_release(
        {
            "confirmation": service.FREEZE_CONFIRMATION,
            "operator": "Lead Producer",
            "commit": "abcdef1234567890",
            "notes": "Frozen after two rehearsals",
        }
    )
    assert result.code == "RELEASE_FROZEN"
    assert result.data["manifest"]["rehearsal_ids"] == [first["id"], second["id"]]
    assert result.data["manifest"]["snapshot_id"] == "release-snapshot"
    assert snapshot_calls[0]["kind"] == "release-freeze"
    assert known_good_calls[0]["commit"] == "abcdef1234567890"
    saved = json.loads(service.release_manifest_file.read_text(encoding="utf-8"))
    assert saved["release_version"] == "1.13.0-alpha.6f"


def test_frozen_release_blocks_rehearsal_mutation(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    first, _ = prepare_ready_release(service)
    assert service.freeze_release(
        {
            "confirmation": service.FREEZE_CONFIRMATION,
            "operator": "Producer",
            "commit": "abcdef1",
        }
    ).ok
    assert service.create_rehearsal({"name": "Three", "operator": "Producer"}).code == "RELEASE_FROZEN"
    assert service.update_drill(
        first["id"], "pregame.preflight", {"result": "passed", "note": "Again"}
    ).code == "RELEASE_FROZEN"


def test_release_unfreeze_requires_reason_and_operator(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    prepare_ready_release(service)
    service.freeze_release(
        {
            "confirmation": service.FREEZE_CONFIRMATION,
            "operator": "Producer",
            "commit": "abcdef1",
        }
    )
    assert service.unfreeze_release({"confirmation": "wrong"}).code == "CONFIRMATION_REQUIRED"
    assert service.unfreeze_release(
        {"confirmation": service.UNFREEZE_CONFIRMATION, "operator": "Producer"}
    ).code == "UNFREEZE_REASON_REQUIRED"
    result = service.unfreeze_release(
        {
            "confirmation": service.UNFREEZE_CONFIRMATION,
            "operator": "Producer",
            "reason": "Correct caption timing defect",
        }
    )
    assert result.code == "RELEASE_UNFROZEN"
    assert result.data["release_freeze"]["frozen"] is False


def test_manifest_returns_not_found_before_freeze(tmp_path: Path) -> None:
    service, *_ = make_service(tmp_path)
    assert service.manifest().code == "MANIFEST_NOT_FOUND"


def test_gate_loader_exception_is_reported_as_blocking_gate(tmp_path: Path) -> None:
    def broken():
        raise RuntimeError("gate failure")

    service, *_ = make_service(tmp_path, gates=broken)
    readiness = service.readiness().data["readiness"]
    assert readiness["conditions"]["system_gates"] is False
    assert readiness["system_gates"][0]["key"] == "system_gate_loader"


