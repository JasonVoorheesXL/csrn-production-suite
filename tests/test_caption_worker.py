from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from caption_worker import (
    CaptionWorkerDependencyError,
    CaptionRuntime,
    CaptionWorkerSettings,
    ChannelCaptionWorker,
    clean_football_caption_text,
    likely_broken_caption_fragment,
    coerce_audio_device_id,
    likely_silence_hallucination,
    normalize_caption_for_duplicate,
    normalize_caption_audio,
    resample_48k_to_16k,
    rms_level,
)


def test_rms_level_empty() -> None:
    assert rms_level([]) == 0.0


def test_rms_level_known_values() -> None:
    assert rms_level([1.0, -1.0]) == 1.0


def test_resample_48k_to_16k_uses_three_to_one_decimation() -> None:
    assert resample_48k_to_16k(list(range(12))) == [0, 3, 6, 9]


def test_numeric_audio_device_id_is_opened_as_integer() -> None:
    assert coerce_audio_device_id("1") == 1
    assert coerce_audio_device_id(2) == 2
    assert coerce_audio_device_id("Line (ZOOM P4next)") == "Line (ZOOM P4next)"
    assert coerce_audio_device_id("") is None


def test_quiet_caption_audio_is_normalized() -> None:
    samples = [0.001, -0.001, 0.001]
    boosted, gain = normalize_caption_audio(samples, 0.001, target_level=0.04, max_gain=80)
    assert gain == 40
    assert list(boosted) == pytest.approx([0.04, -0.04, 0.04])


def test_confidence_uses_average_log_probability() -> None:
    segments = [SimpleNamespace(avg_logprob=-0.1), SimpleNamespace(avg_logprob=-0.3)]
    confidence = ChannelCaptionWorker._confidence(segments)
    assert 0.81 < confidence < 0.83


def test_confidence_defaults_to_one_without_probabilities() -> None:
    assert ChannelCaptionWorker._confidence([SimpleNamespace()]) == 1.0


def test_optional_dependency_error_is_actionable(monkeypatch) -> None:
    worker = ChannelCaptionWorker(caption_service=object(), load_broadcast_id=lambda: "")

    def fail_import(name, *args, **kwargs):
        if name == "numpy":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    import builtins

    original_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", fail_import)
    with pytest.raises(CaptionWorkerDependencyError, match="numpy, sounddevice, and faster-whisper"):
        worker._optional_dependencies()


def test_live_caption_model_prefers_cuda_but_keeps_the_gpu_probe() -> None:
    # Round 15B: the GPU path is still preferred and still probes CUDA /
    # cuDNN float16 the same way -- it just no longer raises when the probe
    # fails (see the CPU-fallback tests below).
    source = Path(__file__).resolve().parents[1].joinpath("caption_worker.py").read_text(encoding="utf-8")
    assert '"cuda", "float16"' in source
    assert '"cpu",' in source and '"int8",' in source
    assert "_probe_cuda_float16" in source
    assert "get_cuda_device_count" in source
    assert 'get_supported_compute_types("cuda")' in source
    assert "cublas64_12.dll" in source
    assert "cudnn_ops64_9.dll" in source
    assert "_prepare_windows_cuda_dll_paths" in source
    assert "add_dll_directory" in source


class _FakeWhisperModel:
    # Mimic faster_whisper.WhisperModel enough for _load_model: the real
    # module prefix is what gates the hardware probe.
    __module__ = "faster_whisper.transcribe"

    def __init__(self, name, *, device, compute_type):
        self.name = name
        self.device = device
        self.compute_type = compute_type


def _fresh_worker() -> ChannelCaptionWorker:
    ChannelCaptionWorker._model_cache.clear()
    return ChannelCaptionWorker(
        caption_service=object(),
        load_broadcast_id=lambda: "",
        settings=CaptionWorkerSettings(model_name="small.en"),
    )


def test_caption_model_falls_back_to_cpu_int8_when_cuda_is_unavailable(
    monkeypatch, caplog
) -> None:
    monkeypatch.setattr(
        ChannelCaptionWorker,
        "_probe_cuda_float16",
        staticmethod(lambda: (False, "no CUDA device visible to CTranslate2")),
    )
    worker = _fresh_worker()
    with caplog.at_level(logging.INFO, logger="csrn.captions"):
        model = worker._load_model(_FakeWhisperModel)

    assert (model.device, model.compute_type) == ("cpu", "int8")
    device, compute_type, reason = worker._last_compute_target
    assert (device, compute_type) == ("cpu", "int8")
    assert "fallback" in reason.lower()
    assert "no CUDA device" in reason
    # The path taken must be visible from the logs alone.
    assert any(
        "cpu" in record.getMessage().lower() and "int8" in record.getMessage().lower()
        for record in caplog.records
    )


def test_caption_model_uses_cuda_float16_when_the_probe_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(
        ChannelCaptionWorker,
        "_probe_cuda_float16",
        staticmethod(lambda: (True, "")),
    )
    worker = _fresh_worker()
    model = worker._load_model(_FakeWhisperModel)

    assert (model.device, model.compute_type) == ("cuda", "float16")
    assert worker._last_compute_target[:2] == ("cuda", "float16")


def test_caption_model_status_event_reports_the_resolved_compute_path() -> None:
    service = RuntimeCaptionService({"source_type": "audio_device", "audio_device": "0"})
    runtime = CaptionRuntime(caption_service=service, load_broadcast_id=lambda: "g1")
    runtime._worker_event(
        {
            "type": "model",
            "device": "cpu",
            "compute_type": "int8",
            "reason": "CPU int8 fallback -- CUDA float16 unavailable: no CUDA device",
        }
    )
    status = runtime.status()
    assert status["model_device"] == "cpu"
    assert status["model_compute_type"] == "int8"
    assert "fallback" in status["model_compute_reason"].lower()


def test_caption_initial_prompt_includes_broadcast_football_vocabulary() -> None:
    from caption_worker import caption_initial_prompt

    prompt = caption_initial_prompt(("Darquez Williams",))
    for phrase in (
        "press box",
        "driving left to right",
        "left to right",
        "wide side of the field",
        "kick returner",
        "pick six",
        "pass incomplete",
        "six to nothing",
        "Darquez Williams",
    ):
        assert phrase in prompt


class RuntimeCaptionService:
    def __init__(self, profile):
        self.profile = profile
        self.updates = []

    def status(self):
        return SimpleNamespace(data={"profile": self.profile})

    def update_profile(self, payload):
        self.updates.append(payload)
        self.profile.update(payload)
        return SimpleNamespace(data={"profile": self.profile})


class FakeWorker:
    started = False
    stopped = False
    last_created = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakeWorker.last_created = self

    def run_forever(self):
        FakeWorker.started = True

    def stop(self):
        FakeWorker.stopped = True


def test_caption_runtime_requires_audio_device_source() -> None:
    service = RuntimeCaptionService({"source_type": "manual", "audio_device": ""})
    runtime = CaptionRuntime(caption_service=service, load_broadcast_id=lambda: "game-1")
    status = runtime.start()
    assert status["running"] is False
    assert status["error"] == "CAPTION_SOURCE_NOT_AUDIO_DEVICE"


def test_caption_runtime_requires_selected_device() -> None:
    service = RuntimeCaptionService({"source_type": "audio_device", "audio_device": ""})
    runtime = CaptionRuntime(caption_service=service, load_broadcast_id=lambda: "game-1")
    status = runtime.start()
    assert status["running"] is False
    assert status["error"] == "CAPTION_AUDIO_DEVICE_REQUIRED"


def test_caption_runtime_starts_and_stops_worker() -> None:
    FakeWorker.started = False
    FakeWorker.stopped = False
    FakeWorker.last_created = None
    service = RuntimeCaptionService(
        {
            "source_type": "audio_device",
            "audio_device": "0",
            "audio_device_name": "Line (ZOOM P4next)",
            "caption_model": "medium.en",
            "minimum_confidence": 0.72,
            "speech_threshold": 0.00005,
        }
    )
    runtime = CaptionRuntime(
        caption_service=service,
        load_broadcast_id=lambda: "game-1",
        worker_factory=FakeWorker,
    )
    started = runtime.start()
    stopped = runtime.stop()
    assert started["running"] is True
    assert service.updates[-1] == {
        "enabled": True,
        "overlay_visible": True,
        "display_delay_ms": 0,
        "minimum_confidence": 0.45,
    }
    assert FakeWorker.last_created.kwargs["settings"].speech_threshold == 0.00005
    assert FakeWorker.last_created.kwargs["settings"].model_name == "medium.en"
    assert stopped["running"] is False
    assert FakeWorker.started is True
    assert FakeWorker.stopped is True


def test_caption_runtime_uses_bundled_model_dir_env_when_no_profile_model(
    monkeypatch,
) -> None:
    # Round 15F: a frozen build's runtime hook sets CSRN_WHISPER_MODEL_DIR to
    # the bundled small.en directory so captions load offline.
    FakeWorker.last_created = None
    monkeypatch.setenv("CSRN_WHISPER_MODEL_DIR", r"C:\bundle\models\faster-whisper-small.en")
    service = RuntimeCaptionService(
        {"source_type": "audio_device", "audio_device": "0"}  # no caption_model
    )
    runtime = CaptionRuntime(
        caption_service=service,
        load_broadcast_id=lambda: "game-1",
        worker_factory=FakeWorker,
    )
    runtime.start()
    assert (
        FakeWorker.last_created.kwargs["settings"].model_name
        == r"C:\bundle\models\faster-whisper-small.en"
    )


def test_caption_runtime_profile_model_still_wins_over_the_bundle_env(
    monkeypatch,
) -> None:
    FakeWorker.last_created = None
    monkeypatch.setenv("CSRN_WHISPER_MODEL_DIR", r"C:\bundle\models\small.en")
    service = RuntimeCaptionService(
        {"source_type": "audio_device", "audio_device": "0", "caption_model": "medium.en"}
    )
    runtime = CaptionRuntime(
        caption_service=service,
        load_broadcast_id=lambda: "game-1",
        worker_factory=FakeWorker,
    )
    runtime.start()
    assert FakeWorker.last_created.kwargs["settings"].model_name == "medium.en"


def test_caption_runtime_tracks_per_channel_audio_levels() -> None:
    service = RuntimeCaptionService({"source_type": "audio_device", "audio_device": "0"})
    runtime = CaptionRuntime(caption_service=service, load_broadcast_id=lambda: "game-1")
    runtime._worker_event({"type": "audio", "channel": 1, "level": 0.1})
    runtime._worker_event({"type": "audio", "channel": 2, "level": 0.02})
    status = runtime.status()
    assert status["channel_levels"] == {"1": 0.1, "2": 0.02}


def test_caption_runtime_tracks_callback_count_and_age() -> None:
    now = [1000.0]
    service = RuntimeCaptionService({"source_type": "audio_device", "audio_device": "0"})
    runtime = CaptionRuntime(
        caption_service=service,
        load_broadcast_id=lambda: "game-1",
        clock=lambda: now[0],
    )
    runtime._status["running"] = True
    runtime._worker_event({"type": "callback"})
    now[0] = 1002.0
    status = runtime.status()
    assert status["callback_count"] == 1
    assert status["last_callback_age_seconds"] == 2
    assert status["callback_stale"] is False


def test_caption_runtime_marks_open_stream_without_callbacks_stale() -> None:
    now = [2000.0]
    service = RuntimeCaptionService({"source_type": "audio_device", "audio_device": "0"})
    runtime = CaptionRuntime(
        caption_service=service,
        load_broadcast_id=lambda: "game-1",
        clock=lambda: now[0],
    )
    runtime._status.update({"running": True})
    runtime._worker_event(
        {
            "type": "ready",
            "device_name": "CABLE Output",
            "host_api": "Windows WASAPI",
            "capture_channels": 2,
            "mappings": [{"channel": 1, "device_channel": 1}],
        }
    )
    now[0] = 2005.0
    status = runtime.status()
    assert status["callback_stale"] is True
    assert status["callback_count"] == 0
    assert "no callbacks" in status["audio_status"].lower()


def test_caption_runtime_stop_clears_cached_meter_levels() -> None:
    service = RuntimeCaptionService({"source_type": "audio_device", "audio_device": "0"})
    runtime = CaptionRuntime(
        caption_service=service,
        load_broadcast_id=lambda: "game-1",
        worker_factory=FakeWorker,
    )
    runtime.start()
    runtime._worker_event({"type": "callback"})
    runtime._worker_event({"type": "audio", "channel": 1, "level": 0.1})
    runtime._worker_event({"type": "hardware_audio", "levels": {1: 0.1}})
    status = runtime.stop()
    assert status["running"] is False
    assert status["channel_levels"] == {}
    assert status["hardware_levels"] == {}
    assert status["last_audio_level"] == 0.0
    assert status["last_chunk_level"] == 0.0


def test_worker_suppresses_recent_duplicate_caption_text() -> None:
    now = [100.0]
    worker = ChannelCaptionWorker(
        caption_service=object(),
        load_broadcast_id=lambda: "game-1",
        clock=lambda: now[0],
    )
    assert worker._is_recent_duplicate("Testing one two") is False
    assert worker._is_recent_duplicate("testing   one two") is True
    now[0] = 105.0
    assert worker._is_recent_duplicate("Testing one two") is False


def test_worker_suppresses_contained_overlap_fragments() -> None:
    now = [100.0]
    worker = ChannelCaptionWorker(
        caption_service=object(),
        load_broadcast_id=lambda: "game-1",
        clock=lambda: now[0],
    )
    assert worker._is_recent_duplicate("And welcome to Caledonia Sports Radio Network.") is False
    assert worker._is_recent_duplicate("Radio network.") is True
    assert worker._is_recent_duplicate("Touchdown!") is False


def test_worker_suppresses_punctuated_contained_overlap_fragments() -> None:
    now = [100.0]
    worker = ChannelCaptionWorker(
        caption_service=object(),
        load_broadcast_id=lambda: "game-1",
        clock=lambda: now[0],
    )
    assert worker._is_recent_duplicate("He's at the 30-20-10 touchdown.") is False
    assert worker._is_recent_duplicate("Touchdown!") is True


def test_clean_football_caption_text_fixes_common_play_call_homophones() -> None:
    assert (
        clean_football_caption_text(
            "All on the 45-yard line, it is now first and count.",
            ("Caledonia", "Cavaliers"),
        )
        == "Ball on the 45-yard line, it is now first and ten."
    )
    assert (
        clean_football_caption_text("Caledonia has a ball on the 45.", ("Caledonia",))
        == "Caledonia has the ball on the 45."
    )
    assert (
        clean_football_caption_text("1st and 10 cover layers players", ("Cavaliers",))
        == "First and ten Cavaliers"
    )
    assert clean_football_caption_text("It is first in 10 Cavaliers", ("Cavaliers",)) == "It is first and ten Cavaliers"
    assert clean_football_caption_text("After the kicker turn Caledonia now has the ball", ()) == "After the kick return Caledonia now has the ball"
    assert clean_football_caption_text("Of Yardline it is first and ten Cavaliers the kick", ("Cavaliers",)) == "It is first and ten Cavaliers"
    assert clean_football_caption_text("Backyard line it is first and ten Cavaliers", ("Cavaliers",)) == "It is first and ten Cavaliers"
    assert clean_football_caption_text("The kicker turner brought the ball back from the 15th", ()) == "The kick returner brought the ball back from the 15"
    assert clean_football_caption_text("Caledonia now has the ball on the 45-yard line. It is", ()) == "Caledonia now has the ball on the 45-yard line"
    assert clean_football_caption_text("Darkwes Williams off the edge", ("Darquez Williams",)) == "Darquez Williams off the edge"
    assert clean_football_caption_text("Quiz Williams off the edge", ("Jazz Williams",)) == "Jazz Williams off the edge"
    assert clean_football_caption_text("Here's it out he's got a receiver", ()) == "He airs it out he's got a receiver"
    assert clean_football_caption_text("Jeremiah Smith takes the", ()) == "Jeremiah Smith"
    assert clean_football_caption_text("He's at the 50 yard line 45", ()) == "He's at the 50-yard line"
    assert clean_football_caption_text("Line 45 40 35 30 25 20 10", ()) == ""
    assert clean_football_caption_text("5-20-10-5 Touchdown", ()) == "50-20-10-5 Touchdown"
    assert clean_football_caption_text("From Caledonia", ("Caledonia",)) == ""
    assert clean_football_caption_text("After a beautiful kicker turned", ()) == "After a beautiful kick return"
    assert clean_football_caption_text("After returning Caledonia.", ("Caledonia",)) == ""
    assert clean_football_caption_text("Return Caledonia has the ball on the 45-yard line it is now first and ten", ("Caledonia",)) == "After the return, Caledonia has the ball on the 45-yard line it is now first and ten"
    assert clean_football_caption_text("Open. He's at the 45, 40, 35, 30, 25, 20.", ()) == "He's at the 45, 40, 35, 30, 25, 20."
    assert clean_football_caption_text("Down Caledonia.", ("Caledonia",)) == ""
    assert clean_football_caption_text("Caledoni leads 6th and", ("Caledonia",)) == "Caledonia leads six to nothing"


def test_likely_broken_caption_fragment_blocks_short_non_play_shards() -> None:
    assert likely_broken_caption_fragment("Down Caledonia.", ("Caledonia",)) is True
    assert likely_broken_caption_fragment("After returning Caledonia.", ("Caledonia",)) is True
    assert likely_broken_caption_fragment("Touchdown Caledonia.", ("Caledonia",)) is False


def test_normalize_caption_for_duplicate_ignores_trailing_punctuation() -> None:
    assert normalize_caption_for_duplicate("Touchdown!") == "touchdown"
    assert normalize_caption_for_duplicate("He's at the 30-20-10 touchdown.") == "he s at the 30-20-10 touchdown"


def test_likely_silence_hallucination_blocks_common_noise_phrases() -> None:
    assert likely_silence_hallucination("I love you.", confidence=0.42, level=0.001) is True
    assert likely_silence_hallucination("Woof woof woof.", confidence=0.9, level=0.04) is True
    assert likely_silence_hallucination("Cheers!", confidence=0.75, level=0.02) is True
    assert likely_silence_hallucination("First and ten", confidence=0.55, level=0.004) is False


