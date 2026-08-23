from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
OVERLAY = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
THEME_RUNTIME = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")
CAPTIONS_PAGE = (ROOT / "templates" / "captions.html").read_text(encoding="utf-8")


def test_control_center_exposes_caption_operator_controls() -> None:
    assert 'id="captionToggle"' in INDEX
    assert 'id="commandCaptionToggle"' in INDEX
    assert 'id="commandCaptionLiveToggle"' in INDEX
    assert 'id="commandCaptionRuntimeStatus"' in INDEX
    assert 'id="commandCaptionDiagnostics"' in INDEX
    assert 'id="commandCaptionChannelMeter"' in INDEX
    assert 'onclick="toggleCaptions()"' in INDEX
    assert 'onclick="toggleLiveCaptions()"' in INDEX
    assert 'onclick="clearCaptions()"' in INDEX
    assert 'onclick="sendTestCaption()"' in INDEX
    assert "window.open('/captions','_blank')" in INDEX
    assert INDEX.index('id="commandCaptionLiveToggle"') < INDEX.index('Game Data Control')


def test_control_center_assigns_caption_inputs_to_people() -> None:
    for marker in (
        'id="captionSourceType"',
        'id="captionAudioDevice"',
        'id="captionChannelMode"',
        'id="captionModel"',
        'id="captionSpeechThreshold"',
        'id="captionSpeechThresholdValue"',
        'id="captionInput1Enabled"',
        'id="captionInput1Person"',
        'id="captionInput1Speaker"',
        'id="captionInput2Enabled"',
        'id="captionInput2Person"',
        'id="captionInput2Speaker"',
        "function loadCaptionAudioDevices(",
        "function captionSourceTypeChanged()",
        "function captionProfilePayload(",
        "function captionSpeechThreshold(",
        "function captionSpeechThresholdChanged()",
        "function saveCaptionAssignments()",
        "function captionInputPersonChanged(channel)",
    ):
        assert marker in INDEX
    assert "/api/captions/profile" in INDEX
    assert "/api/captions/audio-devices" in INDEX
    assert "/api/captions/live/start" in INDEX
    assert "/api/captions/live/stop" in INDEX
    assert "source_type: sourceType" in INDEX
    assert "audio_device:" in INDEX
    assert "caption_model:" in INDEX
    assert "medium.en" in INDEX
    assert "turbo" in INDEX
    assert "large-v3" in INDEX
    assert "channel_mode:" in INDEX
    assert "speech_threshold:" in INDEX
    assert "channels: captionChannelsFromControls()" in INDEX
    assert "syncCaptionRuntimePolling()" in INDEX
    assert "refreshCaptionRuntimeStatus" in INDEX
    assert "renderCaptionChannelMeter()" in INDEX
    assert "last_audio_level" in INDEX
    assert "channel_levels" in INDEX
    assert "callback_count" in INDEX
    assert "callback_stale" in INDEX
    assert "stale " in INDEX


def test_caption_device_picker_prefers_caption_bus_not_p4next() -> None:
    assert "bestCaptionBus" in INDEX
    assert "CABLE Output" in INDEX or "cable output" in INDEX
    assert "bestP4next" not in INDEX
    assert "Number(device.channels || 0) >= 12" not in INDEX


def test_control_center_caption_test_uses_existing_caption_ingest_route() -> None:
    assert "function sendTestCaption()" in INDEX
    assert "/api/captions/segments" in INDEX
    assert "broadcast_id: currentState?.broadcast_id || 'manual-test'" in INDEX


def test_caption_overlays_hold_last_line_through_brief_empty_polls() -> None:
    assert "CAPTION_STICKY_MS = 2800" in THEME_RUNTIME
    assert "lastCaptionSnapshot" in THEME_RUNTIME
    assert "lastCaptionSnapshot.stateUpdatedAt === stateUpdatedAt" in THEME_RUNTIME
    assert "captionSegment" in THEME_RUNTIME
    assert "19.6-r18-r5-caption-sticky" in OVERLAY
    assert "CAPTION_STICKY_MS = 2800" in CAPTIONS_PAGE
    assert "lastCaptionSnapshot.updatedAt === updatedAt" in CAPTIONS_PAGE


def test_pre_game_setup_owns_preflight_controls() -> None:
    assert 'id="pregameModule"' in INDEX
    assert "Pre-Game Setup" in INDEX
    assert 'id="plannedBroadcastSelect"' in INDEX
    assert 'id="commandBroadcastSelect"' in INDEX
    assert 'id="broadcastConnectionQr"' in INDEX
    assert 'id="visualModeButtons"' in INDEX
    assert INDEX.index('id="plannedBroadcastSelect"') > INDEX.index('id="pregameModule"')
    assert INDEX.index('id="captionToggle"') > INDEX.index('id="pregameModule"')
    assert INDEX.index('Game Data Control') < INDEX.index('id="broadcasterGameDataControls"')
