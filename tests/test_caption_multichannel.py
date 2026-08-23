from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

try:
    import numpy as np
except ImportError:  # The installer may run outside the CSRN GPU environment.
    np = None

from caption_service import CaptionService
from caption_worker import (
    CaptionWorkerSettings,
    ChannelCaptionWorker,
    caption_channel_mappings,
    resolve_audio_input_device,
)


class FakeSoundDevice:
    def __init__(self) -> None:
        self._devices = [
            {
                "name": "CABLE Output (VB-Audio Virtual Cable)",
                "max_input_channels": 2,
                "default_samplerate": 48000,
                "hostapi": 1,
            },
            {
                "name": "CABLE Output (VB-Audio Virtual Cable)",
                "max_input_channels": 16,
                "default_samplerate": 48000,
                "hostapi": 0,
            },
            {
                "name": "Line (3- ZOOM P4next Audio)",
                "max_input_channels": 2,
                "default_samplerate": 48000,
                "hostapi": 0,
            },
            {
                "name": "Line (3- ZOOM P4next Audio)",
                "max_input_channels": 12,
                "default_samplerate": 48000,
                "hostapi": 1,
            },
            {
                "name": "Line (3- ZOOM P4next Audio)",
                "max_input_channels": 12,
                "default_samplerate": 48000,
                "hostapi": 2,
            },
        ]
        self._host_apis = [
            {"name": "Windows DirectSound"},
            {"name": "Windows WASAPI"},
            {"name": "Windows WDM-KS"},
        ]

    def query_devices(self):
        return self._devices

    def query_hostapis(self):
        return self._host_apis


class StreamingFakeSoundDevice(FakeSoundDevice):
    def __init__(self) -> None:
        super().__init__()
        self.opened_channels = 0
        self.opened_dtype = ""

    def InputStream(self, **kwargs):
        self.opened_channels = int(kwargs["channels"])
        self.opened_dtype = str(kwargs["dtype"])
        callback = kwargs["callback"]
        if self.opened_dtype == "int16":
            block = np.zeros((6, self.opened_channels), dtype=np.int16)
            block[:, 3] = 8192
        else:
            block = np.zeros((6, self.opened_channels), dtype=np.float32)
            block[:, 3] = 0.25

        class Stream:
            def __enter__(self):
                callback(block, len(block), None, None)
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

        return Stream()


class FakeCaptionService:
    def __init__(self) -> None:
        self.ingested = []

    def status(self):
        return SimpleNamespace(
            data={
                "profile": {
                    "channels": [
                        {
                            "channel": 1,
                            "device_channel": 4,
                            "speaker": "Jason",
                            "enabled": True,
                        }
                    ]
                }
            }
        )

    def ingest_segment(self, payload):
        self.ingested.append(payload)
        return SimpleNamespace(ok=True, code="OK")


class FakeWhisperModel:
    last_audio = None
    last_kwargs = None

    def __init__(self, model_name, *, device, compute_type):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type

    def transcribe(self, audio, **kwargs):
        FakeWhisperModel.last_audio = audio
        FakeWhisperModel.last_kwargs = kwargs
        return [SimpleNamespace(text="Testing captions.", avg_logprob=-0.1)], None


class CaptionMultichannelTests(unittest.TestCase):
    def test_legacy_channels_map_to_same_hardware_channel(self) -> None:
        profile = {
            "channels": [
                {"channel": 1, "speaker": "Jason", "enabled": True},
                {"channel": 2, "speaker": "Jordan", "enabled": False},
            ]
        }
        self.assertEqual(
            caption_channel_mappings(profile),
            [{"channel": 1, "device_channel": 1}],
        )

    def test_explicit_hardware_mapping_is_preserved(self) -> None:
        profile = {
            "channels": [
                {
                    "channel": 1,
                    "device_channel": 9,
                    "speaker": "Sound Pads",
                    "enabled": True,
                }
            ]
        }
        self.assertEqual(
            caption_channel_mappings(profile),
            [{"channel": 1, "device_channel": 9}],
        )

    def test_resolver_honors_an_explicit_full_channel_endpoint(self) -> None:
        device, info, host_api = resolve_audio_input_device(
            FakeSoundDevice(),
            requested_device="3",
            requested_name="Line (3- ZOOM P4next Audio)",
            minimum_channels=1,
        )
        self.assertEqual(device, 3)
        self.assertEqual(info["max_input_channels"], 12)
        self.assertEqual(host_api, "Windows WASAPI")

    def test_resolver_replaces_an_inadequate_two_channel_alias(self) -> None:
        device, info, host_api = resolve_audio_input_device(
            FakeSoundDevice(),
            requested_device="2",
            requested_name="Line (3- ZOOM P4next Audio)",
            minimum_channels=4,
        )
        self.assertEqual(device, 3)
        self.assertEqual(info["max_input_channels"], 12)
        self.assertEqual(host_api, "Windows WASAPI")

    def test_resolver_replaces_wdm_ks_with_wasapi_endpoint(self) -> None:
        device, info, host_api = resolve_audio_input_device(
            FakeSoundDevice(),
            requested_device="4",
            requested_name="Line (3- ZOOM P4next Audio)",
            minimum_channels=2,
        )
        self.assertEqual(device, 3)
        self.assertEqual(info["max_input_channels"], 12)
        self.assertEqual(host_api, "Windows WASAPI")

    def test_resolver_prefers_full_directsound_caption_bus_over_stale_wasapi_id(self) -> None:
        device, info, host_api = resolve_audio_input_device(
            FakeSoundDevice(),
            requested_device="0",
            requested_name="CABLE Output (VB-Audio Virtual Cable)",
            minimum_channels=1,
            requested_host_api="Windows WASAPI",
        )
        self.assertEqual(device, 1)
        self.assertEqual(info["max_input_channels"], 16)
        self.assertEqual(host_api, "Windows DirectSound")

    def test_profile_migration_adds_device_channel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            service = CaptionService(
                profile_file=root / "caption_profile.json",
                state_file=root / "caption_state.json",
                transcripts_dir=root / "transcripts",
            )
            result = service.update_profile(
                {
                    "source_type": "audio_device",
                    "audio_device": "1",
                    "audio_device_name": "Line (3- ZOOM P4next Audio)",
                }
            )
            self.assertTrue(result.ok)
            channels = result.data["profile"]["channels"]
            self.assertEqual([item["device_channel"] for item in channels], [1, 2, 3, 4])

    @unittest.skipIf(np is None, "NumPy is not installed in this Python environment")
    def test_worker_opens_full_device_and_reads_assigned_hardware_channel(self) -> None:
        FakeWhisperModel.last_audio = None
        FakeWhisperModel.last_kwargs = None
        sound_device = StreamingFakeSoundDevice()
        caption_service = FakeCaptionService()
        events = []
        worker = None

        def on_event(event):
            events.append(event)
            if event.get("type") == "caption":
                worker.stop()

        worker = ChannelCaptionWorker(
            caption_service=caption_service,
            load_broadcast_id=lambda: "test",
            settings=CaptionWorkerSettings(
                device="0",
                device_name="Line (3- ZOOM P4next Audio)",
                sample_rate=12,
                recognition_rate=4,
                chunk_seconds=0.5,
                overlap_seconds=0,
                speech_threshold=0.001,
            ),
            on_event=on_event,
        )
        worker._optional_dependencies = lambda: (np, sound_device, FakeWhisperModel)
        worker.run_forever()

        self.assertEqual(sound_device.opened_channels, 12)
        self.assertEqual(sound_device.opened_dtype, "float32")
        self.assertEqual(len(caption_service.ingested), 1)
        self.assertEqual(caption_service.ingested[0]["channel"], 1)
        event_types = [event.get("type") for event in events]
        self.assertLess(event_types.index("opening_stream"), event_types.index("ready"))
        self.assertIn("callback", event_types)
        ready = next(event for event in events if event.get("type") == "ready")
        self.assertEqual(ready["mappings"], [{"channel": 1, "device_channel": 4}])
        self.assertEqual(FakeWhisperModel.last_audio.dtype, np.float32)
        self.assertTrue(FakeWhisperModel.last_audio.flags["C_CONTIGUOUS"])
        self.assertEqual(FakeWhisperModel.last_kwargs["beam_size"], 5)
        self.assertFalse(FakeWhisperModel.last_kwargs["vad_filter"])
        self.assertTrue(FakeWhisperModel.last_kwargs["without_timestamps"])
        self.assertIn("football", FakeWhisperModel.last_kwargs["initial_prompt"].lower())

    @unittest.skipIf(np is None, "NumPy is not installed in this Python environment")
    def test_worker_can_capture_int16_and_normalizes_before_transcription(self) -> None:
        sound_device = StreamingFakeSoundDevice()
        caption_service = FakeCaptionService()
        events = []
        worker = None

        def on_event(event):
            events.append(event)
            if event.get("type") == "caption":
                worker.stop()

        worker = ChannelCaptionWorker(
            caption_service=caption_service,
            load_broadcast_id=lambda: "test",
            settings=CaptionWorkerSettings(
                device="0",
                device_name="Line (3- ZOOM P4next Audio)",
                sample_rate=12,
                recognition_rate=4,
                chunk_seconds=0.5,
                overlap_seconds=0,
                speech_threshold=0.001,
                capture_dtype="int16",
            ),
            on_event=on_event,
        )
        worker._optional_dependencies = lambda: (np, sound_device, FakeWhisperModel)
        worker.run_forever()

        self.assertEqual(sound_device.opened_dtype, "int16")
        self.assertEqual(len(caption_service.ingested), 1)
        chunk = next(event for event in events if event.get("type") == "chunk")
        self.assertGreater(chunk["level"], 0.2)


if __name__ == "__main__":
    unittest.main()
