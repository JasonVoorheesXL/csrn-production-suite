from __future__ import annotations

from pathlib import Path
from typing import Any

from upgrade_service import UpgradeService


class RecordingLock:
    def __init__(self) -> None:
        self.events: list[str] = []

    def __enter__(self):
        self.events.append("enter")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.events.append("exit")
        return False


def build_service(
    tmp_path: Path,
    *,
    candidate: Any = None,
    report: Any = None,
    security: dict[str, Any] | None = None,
):
    calls: list[tuple[str, Any]] = []
    activated: list[str] = []
    store = {
        "status": "NOT_RUN",
        "source_build": "",
        "errors": [],
    }
    lock = RecordingLock()
    candidate_value = candidate if candidate is not None else {
        "available": True,
        "source_build": "Build_0018",
    }
    report_value = report if report is not None else {
        "status": "MIGRATED",
        "source_build": "Build_0018",
        "security_migrated": False,
        "errors": [],
    }
    security_value = security or {"secret_key": "migrated-secret"}

    def inspect(current_dir: Path):
        calls.append(("inspect", current_dir))
        if isinstance(candidate_value, Exception):
            raise candidate_value
        return candidate_value

    def migrate(current_dir: Path, defaults: dict[str, Any], include_security: bool):
        calls.append(
            (
                "migrate",
                {
                    "current_dir": current_dir,
                    "defaults": defaults,
                    "include_security": include_security,
                },
            )
        )
        if isinstance(report_value, Exception):
            raise report_value
        return report_value

    service = UpgradeService(
        current_dir=tmp_path,
        defaults={"application": {"version": "Version X"}},
        inspect_candidate=inspect,
        migrate=migrate,
        load_security=lambda: security_value,
        activate_secret_key=activated.append,
        report_store=store,
        migration_lock=lock,
    )
    return service, calls, activated, store, lock


def test_candidate_delegates_to_inspector_and_returns_copy(tmp_path: Path) -> None:
    candidate = {"available": True, "summary": {"schools": 2}}
    service, calls, _, _, _ = build_service(tmp_path, candidate=candidate)

    result = service.candidate()
    result.data["candidate"]["summary"]["schools"] = 99

    assert result.ok
    assert candidate["summary"]["schools"] == 2
    assert calls == [("inspect", tmp_path)]


def test_candidate_reports_inspection_failure(tmp_path: Path) -> None:
    service, _, _, _, _ = build_service(
        tmp_path,
        candidate=RuntimeError("inspection broke"),
    )

    result = service.candidate()

    assert result.code == "INSPECTION_FAILED"
    assert result.data["message"] == "inspection broke"


def test_candidate_rejects_non_mapping_payload(tmp_path: Path) -> None:
    service, _, _, _, _ = build_service(tmp_path, candidate=["invalid"])

    result = service.candidate()

    assert result.code == "INSPECTION_FAILED"


def test_status_returns_detached_report_copy(tmp_path: Path) -> None:
    service, _, _, store, _ = build_service(tmp_path)

    result = service.status()
    result.data["report"]["status"] = "CHANGED"

    assert result.ok
    assert store["status"] == "NOT_RUN"


def test_run_defaults_to_security_migration_enabled(tmp_path: Path) -> None:
    service, calls, _, _, _ = build_service(tmp_path)

    service.run()

    migrate_call = next(value for name, value in calls if name == "migrate")
    assert migrate_call["include_security"] is True


def test_run_accepts_security_migration_disabled(tmp_path: Path) -> None:
    service, calls, _, _, _ = build_service(tmp_path)

    service.run(False)

    migrate_call = next(value for name, value in calls if name == "migrate")
    assert migrate_call["include_security"] is False


def test_run_updates_shared_report_store(tmp_path: Path) -> None:
    report = {
        "status": "MIGRATED",
        "source_build": "Build_0020",
        "security_migrated": False,
        "errors": [],
    }
    service, _, _, store, _ = build_service(tmp_path, report=report)

    service.run()

    assert store == report
    assert "active_pin" not in store


def test_run_uses_migration_lock(tmp_path: Path) -> None:
    service, _, _, _, lock = build_service(tmp_path)

    service.run()

    assert lock.events == ["enter", "exit"]


def test_security_migration_refreshes_active_secret_key(tmp_path: Path) -> None:
    report = {
        "status": "MIGRATED",
        "security_migrated": True,
        "errors": [],
    }
    service, _, activated, _, _ = build_service(tmp_path, report=report)

    result = service.run()

    assert activated == ["migrated-secret"]
    assert result.data["report"]["active_pin"] == "PREVIOUS_PIN"
    assert "previous build" in result.data["report"]["pin_message"]


def test_no_security_migration_requests_new_pin(tmp_path: Path) -> None:
    service, _, activated, _, _ = build_service(tmp_path)

    result = service.run(False)

    assert activated == []
    assert result.data["report"]["active_pin"] == "CREATE_NEW_PIN"
    assert "Create a new 6-digit" in result.data["report"]["pin_message"]


def test_migration_exception_becomes_failed_report(tmp_path: Path) -> None:
    service, _, _, store, _ = build_service(
        tmp_path,
        report=RuntimeError("migration broke"),
    )

    result = service.run()

    assert result.ok
    assert result.data["report"]["status"] == "FAILED"
    assert result.data["report"]["errors"] == ["migration broke"]
    assert store["status"] == "FAILED"


def test_invalid_migration_report_is_normalized(tmp_path: Path) -> None:
    service, _, _, _, _ = build_service(tmp_path, report=["invalid"])

    result = service.run()

    assert result.data["report"]["status"] == "FAILED"
    assert "invalid report" in result.data["report"]["errors"][0]


def test_security_refresh_failure_is_reported_without_exposing_secret(tmp_path: Path) -> None:
    report = {
        "status": "MIGRATED",
        "security_migrated": True,
        "errors": [],
    }
    service, _, activated, store, _ = build_service(
        tmp_path,
        report=report,
        security={"secret_key": ""},
    )

    result = service.run()
    response = result.data["report"]

    assert activated == []
    assert response["security_refresh_failed"] is True
    assert "Security session refresh failed" in response["errors"][0]
    assert store["errors"] == []
    assert "secret_key" not in response
