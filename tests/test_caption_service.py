from __future__ import annotations

import json
from pathlib import Path

from caption_service import CaptionService


def make_service(tmp_path: Path, now: list[float] | None = None) -> CaptionService:
    current = now or [100.0]
    return CaptionService(
        profile_file=tmp_path / "Settings" / "caption_profile.json",
        state_file=tmp_path / "Captions" / "caption_state.json",
        transcripts_dir=tmp_path / "Captions" / "Transcripts",
        clock=lambda: current[0],
    )


def enable(service: CaptionService, **overrides):
    payload = {
        "enabled": True,
        "overlay_visible": True,
        "display_delay_ms": 0,
        **overrides,
    }
    result = service.update_profile(payload)
    assert result.ok
    return result.data["profile"]


def segment(**overrides):
    return {
        "id": "seg-1",
        "broadcast_id": "game-1",
        "channel": 1,
        "text": "Touchdown Caledonia",
        "confidence": 0.95,
        "start_ms": 1000,
        "end_ms": 2500,
        **overrides,
    }


def test_status_creates_default_files(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    result = service.status()
    assert result.ok
    assert result.data["profile"]["channels"][0]["speaker"] == "Announcer 1"
    assert service.profile_file.exists()
    assert service.state_file.exists()


def test_profile_speaker_names_are_user_assignable(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    profile = service.status().data["profile"]
    profile["channels"][0]["speaker"] = "Alex"
    profile["channels"][1]["speaker"] = "Morgan"
    assert service.update_profile({"channels": profile["channels"]}).ok
    enable(service)
    result = service.ingest_segment(segment(channel=2))
    assert result.ok
    assert result.data["segment"]["speaker"] == "Morgan"


def test_legacy_profile_migrates_without_resetting_channels(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.profile_file.parent.mkdir(parents=True, exist_ok=True)
    service.profile_file.write_text(
        json.dumps(
            {
                "enabled": True,
                "overlay_visible": True,
                "minimum_confidence": 0.72,
                "display_delay_ms": 1200,
                "display_duration_ms": 6500,
                "max_lines": 2,
                "max_characters": 96,
                "profanity_policy": "mask",
                "profanity_words": [],
                "theme": "standard",
                "channels": [
                    {"channel": 1, "speaker": "Legacy Announcer", "enabled": True},
                    {"channel": 2, "speaker": "Spotter", "enabled": False},
                ],
            }
        ),
        encoding="utf-8",
    )

    profile = service.status().data["profile"]

    assert profile["channels"][0]["speaker"] == "Legacy Announcer"
    assert profile["channels"][0]["device_channel"] == 1
    assert profile["source_type"] == "manual"
    assert profile["audio_capture_dtype"] == "float32"
    assert profile["speech_threshold"] == 0.00075


def test_profile_update_enables_overlay(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    result = service.update_profile({"enabled": True, "overlay_visible": True})
    assert result.ok
    assert result.data["state"]["visible"] is True


def test_profile_persists_user_selectable_caption_source(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    result = service.update_profile(
        {
            "source_type": "audio_device",
            "audio_device": "3",
            "audio_device_name": "Line (ZOOM P4next)",
            "audio_capture_dtype": "int16",
            "caption_model": "medium.en",
            "channel_mode": "speaker_labeled",
            "speech_threshold": 0.00025,
        }
    )
    assert result.ok
    profile = result.data["profile"]
    assert profile["source_type"] == "audio_device"
    assert profile["audio_device"] == "3"
    assert profile["audio_device_name"] == "Line (ZOOM P4next)"
    assert profile["audio_capture_dtype"] == "int16"
    assert profile["caption_model"] == "medium.en"
    assert profile["channel_mode"] == "speaker_labeled"
    assert profile["speech_threshold"] == 0.00025


def test_profile_rejects_invalid_audio_capture_dtype(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    result = service.update_profile({"audio_capture_dtype": "pcm24"})
    assert result.code == "INVALID_PROFILE"


def test_profile_rejects_invalid_caption_model(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    result = service.update_profile({"caption_model": "made-up-whisper"})
    assert result.code == "INVALID_PROFILE"


def test_profile_rejects_unknown_caption_source_type(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    result = service.update_profile({"source_type": "p4next_only"})
    assert result.code == "INVALID_PROFILE"


def test_profile_rejects_invalid_speech_threshold(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    result = service.update_profile({"speech_threshold": 1})
    assert result.code == "INVALID_PROFILE"


def test_profile_rejects_invalid_confidence(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    result = service.update_profile({"minimum_confidence": 2})
    assert result.code == "INVALID_PROFILE"


def test_profile_rejects_duplicate_channels(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    result = service.update_profile(
        {
            "channels": [
                {"channel": 1, "speaker": "Alpha", "enabled": True},
                {"channel": 1, "speaker": "Beta", "enabled": True},
            ]
        }
    )
    assert result.code == "INVALID_PROFILE"


def test_ingest_assigns_speaker_from_physical_channel(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    enable(service)
    result = service.ingest_segment(segment(channel=2))
    assert result.ok
    assert result.data["segment"]["speaker"] == "Announcer 2"


def test_ingest_rejects_low_confidence(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    enable(service, minimum_confidence=0.8)
    result = service.ingest_segment(segment(confidence=0.79))
    assert result.code == "LOW_CONFIDENCE"
    assert service.transcript("game-1").data["segments"] == []


def test_ingest_rejects_disabled_channel(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    enable(service)
    result = service.ingest_segment(segment(channel=3))
    assert result.code == "CHANNEL_DISABLED"


def test_ingest_rejects_unconfigured_channel(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    enable(service)
    result = service.ingest_segment(segment(channel=9))
    assert result.code == "CHANNEL_NOT_CONFIGURED"


def test_ingest_persists_transcript(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    enable(service)
    assert service.ingest_segment(segment()).ok
    saved = json.loads((service.transcripts_dir / "game-1.json").read_text(encoding="utf-8"))
    assert saved[0]["text"] == "Touchdown Caledonia"


def test_ingest_keeps_overlay_when_transcript_is_locked(tmp_path: Path, monkeypatch) -> None:
    service = make_service(tmp_path)
    enable(service)
    original_write = CaptionService._write_json
    locked = {"enabled": True}

    def locked_transcript(path: Path, data) -> None:
        if locked["enabled"] and path.name == "game-1.json":
            raise PermissionError("simulated Google Drive lock")
        original_write(path, data)

    monkeypatch.setattr(CaptionService, "_write_json", staticmethod(locked_transcript))
    result = service.ingest_segment(segment())
    assert result.ok
    assert "transcript_warning" in result.data
    assert service.public_state().data["segments"][0]["text"] == "Touchdown Caledonia"

    locked["enabled"] = False
    assert service.ingest_segment(segment(id="seg-2", text="Second caption")).ok
    saved = json.loads((service.transcripts_dir / "game-1.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in saved] == ["seg-1", "seg-2"]


def test_public_state_honors_delay(tmp_path: Path) -> None:
    now = [100.0]
    service = make_service(tmp_path, now)
    enable(service, display_delay_ms=1000)
    assert service.ingest_segment(segment()).ok
    assert service.public_state().data["segments"] == []
    now[0] = 101.1
    assert service.public_state().data["segments"][0]["id"] == "seg-1"


def test_public_state_expires_old_caption(tmp_path: Path) -> None:
    now = [100.0]
    service = make_service(tmp_path, now)
    enable(service, display_duration_ms=1000)
    assert service.ingest_segment(segment()).ok
    now[0] = 102.0
    assert service.public_state().data["segments"] == []


def test_clear_removes_current_overlay_without_deleting_transcript(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    enable(service)
    service.ingest_segment(segment())
    result = service.clear()
    assert result.data["state"]["current"] == []
    assert len(service.transcript("game-1").data["segments"]) == 1


def test_visibility_can_be_hidden(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    enable(service)
    result = service.set_visibility(False)
    assert result.ok
    assert service.public_state().data["visible"] is False


def test_visibility_requires_boolean(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    assert service.set_visibility("yes").code == "VISIBLE_MUST_BE_BOOLEAN"


def test_correct_segment_updates_state_and_transcript(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    enable(service)
    service.ingest_segment(segment())
    result = service.correct_segment("seg-1", "Touchdown by number twelve")
    assert result.ok
    assert result.data["segment"]["corrected"] is True
    assert service.transcript("game-1").data["segments"][0]["text"] == "Touchdown by number twelve"


def test_correct_missing_segment_returns_not_found(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    assert service.correct_segment("missing", "Correction").code == "SEGMENT_NOT_FOUND"


def test_mask_policy_masks_configured_words(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    enable(service, profanity_policy="mask", profanity_words=["badword"])
    result = service.ingest_segment(segment(text="A badword call"))
    assert result.data["segment"]["text"] == "A ******* call"


def test_drop_policy_withholds_configured_words(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    enable(service, profanity_policy="drop", profanity_words=["badword"])
    result = service.ingest_segment(segment(text="A badword call"))
    assert result.data["segment"]["text"] == "[caption withheld]"


def test_long_caption_is_bounded(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    enable(service, max_characters=24)
    result = service.ingest_segment(segment(text="This caption is intentionally much too long"))
    assert len(result.data["segment"]["text"]) == 24
    assert result.data["segment"]["text"].endswith("…")


def test_srt_export_includes_speaker_and_timing(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    enable(service)
    service.ingest_segment(segment())
    content = service.export_srt("game-1").data["content"]
    assert "00:00:01,000 --> 00:00:02,500" in content
    assert "Announcer 1: Touchdown Caledonia" in content


def test_vtt_export_includes_voice_tag(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    enable(service)
    service.ingest_segment(segment())
    content = service.export_vtt("game-1").data["content"]
    assert content.startswith("WEBVTT")
    assert "<v Announcer 1>Touchdown Caledonia" in content


def test_broadcast_identifier_is_sanitized(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    enable(service)
    service.ingest_segment(segment(broadcast_id="../../game one"))
    assert (service.transcripts_dir / "game-one.json").exists()


