from __future__ import annotations

import subprocess
import sys
import types

import pytest

import csrn_desktop


# --------------------------------------------------------------------------
# triage -- DOWN / HEALTHY / HUNG (mirrors the .ps1 launcher)
# --------------------------------------------------------------------------


def test_triage_down_when_nothing_is_listening() -> None:
    assert csrn_desktop.triage(port_listening=False, healthy=False) == "DOWN"


def test_triage_healthy_when_bound_and_health_ok() -> None:
    assert csrn_desktop.triage(port_listening=True, healthy=True) == "HEALTHY"


def test_triage_hung_when_bound_but_health_not_ok() -> None:
    assert csrn_desktop.triage(port_listening=True, healthy=False) == "HUNG"


# --------------------------------------------------------------------------
# server_command -- dev vs frozen
# --------------------------------------------------------------------------


def test_server_command_runs_app_py_in_a_source_checkout(monkeypatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    command = csrn_desktop.server_command(python_executable="py-exe")
    assert command[0] == "py-exe"
    assert command[1].endswith("app.py")


def test_server_command_re_execs_serve_only_when_frozen(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "CSRNProductionSuite.exe", raising=False)
    assert csrn_desktop.server_command() == ["CSRNProductionSuite.exe", "--serve-only"]


# --------------------------------------------------------------------------
# probe_health
# --------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc) -> None:
        return None


def test_probe_health_true_only_for_200_status_ok(monkeypatch) -> None:
    monkeypatch.setattr(
        csrn_desktop.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResponse(200, b'{"status": "ok"}'),
    )
    assert csrn_desktop.probe_health() is True


def test_probe_health_false_for_non_ok_body(monkeypatch) -> None:
    monkeypatch.setattr(
        csrn_desktop.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResponse(200, b'{"status": "starting"}'),
    )
    assert csrn_desktop.probe_health() is False


def test_probe_health_false_when_request_raises(monkeypatch) -> None:
    def _boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(csrn_desktop.urllib.request, "urlopen", _boom)
    assert csrn_desktop.probe_health() is False


# --------------------------------------------------------------------------
# wait_until_healthy
# --------------------------------------------------------------------------


def test_wait_until_healthy_returns_true_once_the_check_passes() -> None:
    calls = {"n": 0}

    def check() -> bool:
        calls["n"] += 1
        return calls["n"] >= 3

    clock = {"t": 0.0}
    ok = csrn_desktop.wait_until_healthy(
        deadline_seconds=60,
        health_check=check,
        sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
        now=lambda: clock["t"],
    )
    assert ok is True
    assert calls["n"] == 3


def test_wait_until_healthy_times_out_without_health() -> None:
    clock = {"t": 0.0}
    ok = csrn_desktop.wait_until_healthy(
        deadline_seconds=5,
        health_check=lambda: False,
        sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
        now=lambda: clock["t"],
    )
    assert ok is False


# --------------------------------------------------------------------------
# request_graceful_shutdown
# --------------------------------------------------------------------------


class _FakePopen:
    def __init__(self, *, exits_after_signal: bool = True, already_done: bool = False) -> None:
        self.signals: list = []
        self.terminated = False
        self.killed = False
        self._exits_after_signal = exits_after_signal
        self.returncode = 0 if already_done else None
        self._done = already_done

    def poll(self):
        return self.returncode

    def send_signal(self, sig) -> None:
        self.signals.append(sig)
        if self._exits_after_signal:
            self.returncode = 0
            self._done = True

    def wait(self, timeout=None):
        if self._done:
            return self.returncode
        raise subprocess.TimeoutExpired(cmd="csrn", timeout=timeout)

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0
        self._done = True

    def kill(self) -> None:  # pragma: no cover
        self.killed = True
        self.returncode = 0
        self._done = True


def test_graceful_shutdown_signals_a_running_child_and_waits() -> None:
    process = _FakePopen(exits_after_signal=True)
    rc = csrn_desktop.request_graceful_shutdown(process, timeout=1.0)
    assert rc == 0
    assert process.signals  # a signal was actually delivered
    assert process.terminated is False


def test_graceful_shutdown_is_a_noop_when_child_already_exited() -> None:
    process = _FakePopen(already_done=True)
    rc = csrn_desktop.request_graceful_shutdown(process, timeout=1.0)
    assert rc == 0
    assert process.signals == []


def test_graceful_shutdown_falls_back_to_terminate_on_timeout() -> None:
    process = _FakePopen(exits_after_signal=False)
    rc = csrn_desktop.request_graceful_shutdown(process, timeout=0.01)
    assert rc == 0
    assert process.signals  # asked nicely first
    assert process.terminated is True  # then hard-stopped


# --------------------------------------------------------------------------
# run() orchestration
# --------------------------------------------------------------------------


def test_run_aborts_on_hung_server_without_starting_anything(monkeypatch) -> None:
    monkeypatch.setattr(csrn_desktop, "current_state", lambda: "HUNG")
    started = []
    monkeypatch.setattr(csrn_desktop, "start_server", lambda *a, **k: started.append(1))
    assert csrn_desktop.run(health_timeout=1) == 1
    assert started == []


def test_run_starts_server_opens_window_then_shuts_down_cleanly(monkeypatch) -> None:
    events: list[str] = []

    fake_process = _FakePopen(exits_after_signal=True)
    monkeypatch.setattr(csrn_desktop, "current_state", lambda: "DOWN")
    monkeypatch.setattr(
        csrn_desktop, "start_server", lambda *a, **k: events.append("start") or fake_process
    )
    monkeypatch.setattr(csrn_desktop, "wait_until_healthy", lambda *a, **k: True)

    fake_webview = types.SimpleNamespace(
        create_window=lambda *a, **k: events.append("window"),
        start=lambda **k: events.append("loop"),
    )
    monkeypatch.setitem(sys.modules, "webview", fake_webview)

    shutdowns: list = []
    monkeypatch.setattr(
        csrn_desktop,
        "request_graceful_shutdown",
        lambda proc, **k: shutdowns.append(proc),
    )

    assert csrn_desktop.run(health_timeout=1) == 0
    assert events == ["start", "window", "loop"]
    assert shutdowns == [fake_process]  # window close -> clean server shutdown


def test_run_attaches_to_a_healthy_server_and_never_kills_it(monkeypatch) -> None:
    monkeypatch.setattr(csrn_desktop, "current_state", lambda: "HEALTHY")
    monkeypatch.setattr(
        csrn_desktop,
        "start_server",
        lambda *a, **k: pytest.fail("must not start a server when one is HEALTHY"),
    )
    monkeypatch.setattr(csrn_desktop, "wait_until_healthy", lambda *a, **k: True)

    fake_webview = types.SimpleNamespace(
        create_window=lambda *a, **k: None,
        start=lambda **k: None,
    )
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    monkeypatch.setattr(
        csrn_desktop,
        "request_graceful_shutdown",
        lambda *a, **k: pytest.fail("must not shut down a server the shell did not start"),
    )

    assert csrn_desktop.run(health_timeout=1) == 0


def test_run_reports_missing_pywebview_and_tears_down_a_shell_started_server(monkeypatch) -> None:
    fake_process = _FakePopen(exits_after_signal=True)
    monkeypatch.setattr(csrn_desktop, "current_state", lambda: "DOWN")
    monkeypatch.setattr(csrn_desktop, "start_server", lambda *a, **k: fake_process)
    monkeypatch.setattr(csrn_desktop, "wait_until_healthy", lambda *a, **k: True)
    monkeypatch.setitem(sys.modules, "webview", None)  # import webview -> ImportError

    shutdowns: list = []
    monkeypatch.setattr(
        csrn_desktop, "request_graceful_shutdown", lambda proc, **k: shutdowns.append(proc)
    )

    assert csrn_desktop.run(health_timeout=1) == 1
    assert shutdowns == [fake_process]


# --------------------------------------------------------------------------
# app.py wires SIGBREAK so a shell CTRL_BREAK_EVENT is a clean shutdown
# --------------------------------------------------------------------------


def test_app_routes_sigbreak_through_the_clean_shutdown_handler() -> None:
    from pathlib import Path

    source = Path(csrn_desktop.__file__).resolve().parent.joinpath("app.py").read_text(
        encoding="utf-8"
    )
    assert "signal.SIGBREAK" in source
    assert "_record_clean_shutdown_and_stop" in source
