from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from caption_worker import CaptionWorkerDependencyError, CaptionWorkerSettings, ChannelCaptionWorker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run channel-separated CSRN live captions.")
    parser.add_argument("--device", default=None, help="sounddevice input device name or index")
    parser.add_argument("--model", default="small.en", help="faster-whisper model name")
    parser.add_argument("--chunk-seconds", type=float, default=3.0)
    parser.add_argument("--speech-threshold", type=float, default=0.008)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from app import get_caption_service, load_state

    device = args.device
    if isinstance(device, str) and device.isdigit():
        device = int(device)
    worker = ChannelCaptionWorker(
        caption_service=get_caption_service(),
        load_broadcast_id=lambda: str(load_state().get("broadcast_id", "")),
        settings=CaptionWorkerSettings(
            device=device,
            model_name=args.model,
            chunk_seconds=max(1.0, float(args.chunk_seconds)),
            speech_threshold=max(0.0, float(args.speech_threshold)),
        ),
    )
    print("Starting CSRN channel-based caption worker. Press Ctrl+C to stop.")
    try:
        worker.run_forever()
    except CaptionWorkerDependencyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        worker.stop()
        print("Caption worker stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
