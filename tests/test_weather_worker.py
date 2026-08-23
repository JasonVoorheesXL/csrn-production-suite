from __future__ import annotations

from weather_worker import WeatherPollingWorker


class Service:
    def __init__(self):
        self.calls = 0

    def refresh(self, *, force=False):
        self.calls += 1
        return {"force": force}


def test_worker_enforces_thirty_second_minimum() -> None:
    worker = WeatherPollingWorker(weather_service=Service(), interval_seconds=1)
    assert worker.interval_seconds == 30


def test_run_once_uses_non_forced_refresh() -> None:
    service = Service()
    worker = WeatherPollingWorker(weather_service=service)
    assert worker.run_once() == {"force": False}
    assert service.calls == 1


def test_stop_marks_worker_stopped() -> None:
    worker = WeatherPollingWorker(weather_service=Service())
    assert worker.stopped is False
    worker.stop()
    assert worker.stopped is True


