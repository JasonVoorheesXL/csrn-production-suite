from __future__ import annotations

import time
from threading import Event
from typing import Any, Callable


class WeatherPollingWorker:
    """Bounded background polling loop for the venue weather service."""

    def __init__(
        self,
        *,
        weather_service: Any,
        interval_seconds: int = 60,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.weather_service = weather_service
        self.interval_seconds = max(30, int(interval_seconds))
        self._sleeper = sleeper
        self._stop = Event()

    def stop(self) -> None:
        self._stop.set()

    def run_once(self):
        return self.weather_service.refresh(force=False)

    def run_forever(self) -> None:
        while not self._stop.is_set():
            self.run_once()
            if self._stop.wait(self.interval_seconds):
                break

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()
