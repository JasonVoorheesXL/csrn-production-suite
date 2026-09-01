"""Round 21A/21B: the shared Command Center server builder + the
signal-free clean-shutdown helper."""
from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import pytest

import app as app_module


def test_build_command_center_server_returns_a_bound_stoppable_server(monkeypatch) -> None:
    # Don't actually stand up the isolated media server on :5051 for a unit test.
    monkeypatch.setattr(app_module, "start_isolated_media_server", lambda *a, **k: 5051)
    monkeypatch.setattr(app_module, "ensure_data_architecture", lambda: None)
    monkeypatch.setattr(app_module, "load_config", lambda: {})

    server = app_module.build_command_center_server()
    try:
        # create_server(_start=True) binds the socket immediately.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            assert s.connect_ex(("127.0.0.1", 5050)) == 0  # something is listening

        t = threading.Thread(target=server.run, daemon=True)
        t.start()
        # serve for a beat, then stop it from this (non-server) thread
        time.sleep(0.3)
        server.close()
        t.join(timeout=5)
        assert not t.is_alive()  # server.run() returned after close()
    finally:
        try:
            server.close()
        except Exception:
            pass


def test_command_center_clean_shutdown_writes_marker_and_flushes(monkeypatch, tmp_path) -> None:
    removed = {"marker": False}
    flushed = {"n": 0}

    class _Recovery:
        def mark_clean_shutdown(self):
            removed["marker"] = True

    class _Repo:
        def flush(self):
            flushed["n"] += 1

    monkeypatch.setattr(app_module, "get_recovery_service", lambda: _Recovery())
    monkeypatch.setattr(app_module, "STATE_REPOSITORY", _Repo())

    # No SystemExit -- callable straight from the shell's thread.
    app_module.command_center_clean_shutdown()
    assert removed["marker"] is True
    assert flushed["n"] == 1

    # idempotent-safe: a second call must not raise either
    app_module.command_center_clean_shutdown()
    assert flushed["n"] == 2


def test_command_center_clean_shutdown_swallows_backend_errors(monkeypatch) -> None:
    def _boom():
        raise RuntimeError("recovery backend down")

    class _Repo:
        def flush(self):
            raise RuntimeError("mirror unavailable")

    monkeypatch.setattr(app_module, "get_recovery_service", _boom)
    monkeypatch.setattr(app_module, "STATE_REPOSITORY", _Repo())
    # must not propagate -- shutdown best-effort
    app_module.command_center_clean_shutdown()


def test_signal_handler_still_records_then_exits(monkeypatch) -> None:
    import signal as _signal

    calls = {"clean": 0}
    monkeypatch.setattr(
        app_module, "command_center_clean_shutdown", lambda: calls.__setitem__("clean", calls["clean"] + 1)
    )
    with pytest.raises(SystemExit) as exc:
        app_module._record_clean_shutdown_and_stop(_signal.SIGINT, None)
    assert exc.value.code == 0
    assert calls["clean"] == 1


def test_run_command_center_registers_handlers_before_serving() -> None:
    src = Path(app_module.__file__).read_text(encoding="utf-8")
    body = src.split("def run_command_center()", 1)[1].split("\nif __name__", 1)[0]
    # handlers registered, then the blocking run()
    assert body.index("signal.signal(signal.SIGINT") < body.index("server.run()")
    assert "signal.SIGBREAK" in body
    # the standalone entry is still just python app.py
    assert 'if __name__ == "__main__":\n    run_command_center()' in src
    # dev path builds the SAME server the shell will
    assert "build_command_center_server()" in body
