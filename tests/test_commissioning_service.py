from __future__ import annotations

import json
from pathlib import Path

from commissioning_service import HardwareOBSCommissioningService


READY_OBS = {
    "reachable": True,
    "authenticated": True,
    "profile_matches": True,
    "scene_collection_matches": True,
    "required_scene_exists": True,
    "browser_source_exists": True,
    "browser_source_in_required_scene": True,
    "program_visual_scene_exists": True,
    "graphic_source_exists": True,
    "camera_source_exists": False,
    "error": "",
}


def config() -> dict:
    return {
        "obs": {
            "profile": "CSRN Production",
            "scene_collection": "CSRN Master",
            "required_scene": "10.01 - FOOTBALL SCOREBUG",
            "browser_source": "BRWSR - Football Scorebug",
            "program_visual_scene": "10.02 - PROGRAM VISUAL",
            "graphic_source": "IMG - Broadcast Background",
        }
    }


def service(tmp_path: Path, obs: dict | None = None) -> HardwareOBSCommissioningService:
    return HardwareOBSCommissioningService(
        profile_file=tmp_path / "commissioning.json",
        load_config=config,
        validate_obs=lambda: dict(READY_OBS if obs is None else obs),
        clock=lambda: 1_700_000_000,
    )


def complete_required_checks(instance: HardwareOBSCommissioningService) -> None:
    for key in instance.DEVICE_CHECKS:
        assert instance.set_check(section="device", key=key, passed=True).ok
    for key in instance.AUDIO_CHECKS:
        assert instance.set_check(section="audio_checks", key=key, passed=True).ok
    for key in instance.NETWORK_CHECKS:
        if key != "backup_internet_verified":
            assert instance.set_check(section="network_checks", key=key, passed=True).ok
    assert instance.run_obs_check().ok


def test_load_creates_normalized_default_profile(tmp_path: Path) -> None:
    instance = service(tmp_path)
    result = instance.load()
    assert result.code == "OK"
    assert result.data["profile"]["device"]["model"] == "P4next"
    assert result.data["profile"]["channels"][0]["speaker"] == "Announcer 1"
    assert (tmp_path / "commissioning.json").exists()


def test_load_repairs_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "commissioning.json"
    path.write_text("not-json", encoding="utf-8")
    result = service(tmp_path).load()
    assert result.data["profile"]["schema"] == 1
    assert json.loads(path.read_text(encoding="utf-8"))["schema"] == 1


def test_update_profile_normalizes_device_and_channels(tmp_path: Path) -> None:
    instance = service(tmp_path)
    result = instance.update_profile(
        {
            "device": {"model": "P4next", "sample_rate_hz": "48000"},
            "channels": [
                {"channel": 1, "enabled": True, "speaker": " Avery "},
                {"channel": 7, "enabled": True, "speaker": "Ignored"},
            ],
            "notes": " Ready ",
        }
    )
    profile = result.data["profile"]
    assert result.code == "PROFILE_UPDATED"
    assert profile["device"]["sample_rate_hz"] == 48000
    assert profile["channels"][0]["speaker"] == "Avery"
    assert len(profile["channels"]) == 4
    assert profile["notes"] == "Ready"


def test_update_profile_rejects_non_object(tmp_path: Path) -> None:
    assert service(tmp_path).update_profile([]).code == "PROFILE_MUST_BE_OBJECT"


def test_set_device_check(tmp_path: Path) -> None:
    result = service(tmp_path).set_check(
        section="device", key="sd_card_installed", passed=True
    )
    assert result.code == "CHECK_UPDATED"
    assert result.data["profile"]["device"]["sd_card_installed"] is True


def test_set_audio_check_preserves_note(tmp_path: Path) -> None:
    result = service(tmp_path).set_check(
        section="audio_checks",
        key="no_clipping",
        passed=True,
        note="Peaks below zero dBFS",
    )
    assert result.data["profile"]["audio_checks"]["no_clipping"] == {
        "passed": True,
        "note": "Peaks below zero dBFS",
    }


def test_set_check_rejects_invalid_section(tmp_path: Path) -> None:
    result = service(tmp_path).set_check(
        section="unknown", key="no_clipping", passed=True
    )
    assert result.code == "INVALID_CHECK_SECTION"


def test_set_check_rejects_invalid_key(tmp_path: Path) -> None:
    result = service(tmp_path).set_check(
        section="audio_checks", key="unknown", passed=True
    )
    assert result.code == "INVALID_CHECK_KEY"


def test_set_check_requires_boolean(tmp_path: Path) -> None:
    result = service(tmp_path).set_check(
        section="audio_checks", key="no_clipping", passed="yes"
    )
    assert result.code == "PASSED_MUST_BE_BOOLEAN"


def test_run_obs_check_records_expected_and_observed_contract(tmp_path: Path) -> None:
    result = service(tmp_path).run_obs_check()
    check = result.data["obs_check"]
    assert result.code == "OBS_CHECK_COMPLETE"
    assert check["ready"] is True
    assert check["expected"]["profile"] == "CSRN Production"
    assert check["observed"]["camera_source_exists"] is False


def test_run_obs_check_handles_validator_failure(tmp_path: Path) -> None:
    instance = HardwareOBSCommissioningService(
        profile_file=tmp_path / "commissioning.json",
        load_config=config,
        validate_obs=lambda: (_ for _ in ()).throw(RuntimeError("OBS offline")),
        clock=lambda: 1_700_000_000,
    )
    result = instance.run_obs_check()
    assert result.data["obs_check"]["ready"] is False
    assert result.data["obs_check"]["observed"]["error"] == "OBS offline"


def test_report_is_incomplete_before_operator_checks(tmp_path: Path) -> None:
    result = service(tmp_path).report()
    assert result.code == "COMMISSIONING_INCOMPLETE"
    assert result.data["report"]["ready"] is False


def test_report_is_ready_after_required_checks(tmp_path: Path) -> None:
    instance = service(tmp_path)
    complete_required_checks(instance)
    result = instance.report()
    assert result.code == "COMMISSIONING_READY"
    assert result.data["report"]["ready"] is True
    assert result.data["report"]["recommended_ready"] is False


def test_backup_internet_is_recommended_not_required(tmp_path: Path) -> None:
    instance = service(tmp_path)
    complete_required_checks(instance)
    report = instance.report().data["report"]
    backup = next(
        item for item in report["checks"]
        if item["key"] == "network.backup_internet_verified"
    )
    assert backup["required"] is False
    assert report["ready"] is True


def test_duplicate_enabled_speakers_block_readiness(tmp_path: Path) -> None:
    instance = service(tmp_path)
    complete_required_checks(instance)
    profile = instance.load().data["profile"]
    profile["channels"][1]["speaker"] = profile["channels"][0]["speaker"]
    instance.update_profile(profile)
    result = instance.report()
    assignment = next(
        item for item in result.data["report"]["checks"]
        if item["key"] == "channels.assignments"
    )
    assert assignment["passed"] is False
    assert result.code == "COMMISSIONING_INCOMPLETE"


