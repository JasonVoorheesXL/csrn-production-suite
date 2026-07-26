from __future__ import annotations

from types import SimpleNamespace

import pytest

from caption_worker import (
    CaptionWorkerDependencyError,
    ChannelCaptionWorker,
    resample_48k_to_16k,
    rms_level,
)


def test_rms_level_empty() -> None:
    assert rms_level([]) == 0.0


def test_rms_level_known_values() -> None:
    assert rms_level([1.0, -1.0]) == 1.0


def test_resample_48k_to_16k_uses_three_to_one_decimation() -> None:
    assert resample_48k_to_16k(list(range(12))) == [0, 3, 6, 9]


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
