from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CSRN venue weather monitoring.")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds; minimum 30.")
    parser.add_argument("--once", action="store_true", help="Run one refresh and exit.")
    args = parser.parse_args()

    from app import get_weather_service
    from weather_worker import WeatherPollingWorker

    worker = WeatherPollingWorker(
        weather_service=get_weather_service(),
        interval_seconds=args.interval,
    )
    if args.once:
        result = worker.run_once()
        print(result.code)
        if result.data:
            print(result.data)
        return 0 if result.ok or result.code == "POLL_THROTTLED" else 1

    print(f"CSRN weather monitor started; polling every {worker.interval_seconds} seconds.")
    print("Press Ctrl+C to stop.")
    try:
        worker.run_forever()
    except KeyboardInterrupt:
        worker.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
