from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

import csrn_desktop


# --------------------------------------------------------------------------
# triage -- DOWN / HEALTHY / HUNG
# --------------------------------------------------------------------------


def test_triage_down_when_nothing_is_listening() -> None:
    assert csrn_desktop.triage(port_listening=False, healthy=False) == "DOWN"


def test_triage_healthy_when_bound_and_health_ok() -> None:
    assert csrn_desktop.triage(port_listening=True, healthy=True) == "HEALTHY"


def test_triage_hung_when_bound_but_health_not_ok() -> None:
    assert csrn_desktop.triage(port_listening=True, healthy=False) == "HUNG"


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
# run() -- in-process model (Round 21): server on a daemon thread, window
# on the main thread, window-close -> command_center_clean_shutdown() +
# server.close(), all in Python. No subprocess, no signals, no re-exec.
# --------------------------------------------------------------------------


class _FakeServer:
    def __init__(self) -> None:
        self.ran = False
        self.closed = False

    def run(self) -> None:  # runs on the daemon thread
        self.ran = True

    def close(self) -> None:
        self.closed = True


def _fake_app(server: _FakeServer, events: list[str]):
    return types.SimpleNamespace(
        build_command_center_server=lambda: events.append("build") or server,
        command_center_clean_shutdown=lambda: events.append("clean"),
    )


def _fake_webview(events: list[str]):
    return types.SimpleNamespace(
        create_window=lambda *a, **k: events.append("window"),
        start=lambda **k: events.append("loop"),
    )


def test_run_aborts_on_hung_server_without_touching_anything(monkeypatch) -> None:
    monkeypatch.setattr(csrn_desktop, "current_state", lambda: "HUNG")
    monkeypatch.setitem(
        sys.modules, "app",
        types.SimpleNamespace(
            build_command_center_server=lambda: pytest.fail("must not build a server when HUNG")
        ),
    )
    assert csrn_desktop.run(health_timeout=1) == 1


def test_run_starts_inprocess_server_opens_window_then_shuts_down_cleanly(monkeypatch) -> None:
    events: list[str] = []
    server = _FakeServer()
    monkeypatch.setattr(csrn_desktop, "current_state", lambda: "DOWN")
    monkeypatch.setattr(csrn_desktop, "wait_until_healthy", lambda *a, **k: True)
    monkeypatch.setitem(sys.modules, "app", _fake_app(server, events))
    monkeypatch.setitem(sys.modules, "webview", _fake_webview(events))

    assert csrn_desktop.run(health_timeout=1) == 0
    # built the server, opened the window, ran the loop, then cleaned up
    assert events == ["build", "window", "loop", "clean"]
    assert server.ran is True          # server.run() executed on the daemon thread
    assert server.closed is True       # server.close() called after the window closed


def test_run_attaches_to_a_healthy_server_and_never_starts_or_stops_one(monkeypatch) -> None:
    events: list[str] = []
    monkeypatch.setattr(csrn_desktop, "current_state", lambda: "HEALTHY")
    monkeypatch.setattr(csrn_desktop, "wait_until_healthy", lambda *a, **k: True)
    monkeypatch.setitem(
        sys.modules, "app",
        types.SimpleNamespace(
            build_command_center_server=lambda: pytest.fail("must not start a server when HEALTHY"),
            command_center_clean_shutdown=lambda: pytest.fail("must not shut down an attached server"),
        ),
    )
    monkeypatch.setitem(sys.modules, "webview", _fake_webview(events))

    assert csrn_desktop.run(health_timeout=1) == 0
    assert events == ["window", "loop"]


def test_run_missing_pywebview_stops_the_inprocess_server(monkeypatch) -> None:
    events: list[str] = []
    server = _FakeServer()
    monkeypatch.setattr(csrn_desktop, "current_state", lambda: "DOWN")
    monkeypatch.setattr(csrn_desktop, "wait_until_healthy", lambda *a, **k: True)
    monkeypatch.setitem(sys.modules, "app", _fake_app(server, events))
    monkeypatch.setitem(sys.modules, "webview", None)  # import webview -> ImportError

    assert csrn_desktop.run(health_timeout=1) == 1
    assert server.closed is True
    assert "clean" not in events  # never became healthy-with-a-window, so no marker write


def test_run_unhealthy_server_is_stopped_and_reported(monkeypatch) -> None:
    events: list[str] = []
    server = _FakeServer()
    monkeypatch.setattr(csrn_desktop, "current_state", lambda: "DOWN")
    monkeypatch.setattr(csrn_desktop, "wait_until_healthy", lambda *a, **k: False)
    monkeypatch.setitem(sys.modules, "app", _fake_app(server, events))

    assert csrn_desktop.run(health_timeout=1) == 1
    assert server.closed is True


def test_shell_has_no_subprocess_signal_or_serve_only_machinery() -> None:
    full = Path(csrn_desktop.__file__).read_text(encoding="utf-8")
    # skip the module docstring -- it *describes* what was removed
    src = full.split('"""', 2)[2]
    for gone in (
        "import subprocess",
        "import signal",
        "CTRL_BREAK_EVENT",
        '"--serve-only"',
        "def run_server_only",
        "def request_graceful_shutdown",
        "def server_command",
        "def start_server",
        "CREATE_NEW_PROCESS_GROUP",
        "Popen(",
    ):
        assert gone not in src, gone
    assert "app.build_command_center_server()" in src
    assert "app.command_center_clean_shutdown()" in src
    assert "server.close()" in src
    assert "threading.Thread(" in src  # server runs on a daemon thread


# --------------------------------------------------------------------------
# app.py still routes Ctrl+C (SIGINT/SIGTERM/SIGBREAK) through the clean path
# --------------------------------------------------------------------------


def test_app_routes_signals_through_the_clean_shutdown_handler() -> None:
    source = Path(csrn_desktop.__file__).resolve().parent.joinpath("app.py").read_text(
        encoding="utf-8"
    )
    assert "signal.SIGINT" in source and "signal.SIGBREAK" in source
    assert "_record_clean_shutdown_and_stop" in source
    assert "command_center_clean_shutdown" in source


def test_app_exposes_run_command_center_as_the_single_server_entry() -> None:
    import app as app_module

    assert callable(app_module.run_command_center)
    assert callable(app_module.build_command_center_server)
    source = Path(app_module.__file__).read_text(encoding="utf-8")
    assert "def run_command_center()" in source
    assert 'if __name__ == "__main__":\n    run_command_center()' in source
    # Round 21: exactly one place builds the server (create_server, so the
    # shell can hold the handle and .close() it in-process).
    assert source.count('create_server(app, host="0.0.0.0", port=5050') == 1
    assert 'serve(app, host="0.0.0.0"' not in source  # no blocking serve() wrapper


def test_run_core_foundation_is_not_a_packaging_entry_point() -> None:
    root = Path(csrn_desktop.__file__).resolve().parent
    spec = (root / "packaging/windows/CSRNProductionSuite.spec").read_text(encoding="utf-8")
    excludes_line = spec.split("excludes=", 1)[1].split("\n", 1)[0]
    assert '"pytest"' in excludes_line
    assert '"run_core_foundation"' in excludes_line


# --------------------------------------------------------------------------
# .spec + .iss shape
# --------------------------------------------------------------------------


def test_pyinstaller_spec_targets_the_shell_and_fixes_round14_gaps() -> None:
    root = Path(csrn_desktop.__file__).resolve().parent
    spec = (root / "packaging/windows/CSRNProductionSuite.spec").read_text(encoding="utf-8")

    assert 'ROOT / "csrn_desktop.py"' in spec        # entry = the shell
    assert "console=False" in spec                   # GUI shell, no console
    assert '_tree(ROOT / "rulesets", "rulesets")' in spec
    assert '"Graphics"' not in spec
    assert "collect_all" in spec and "ctranslate2" in spec and "onnxruntime" in spec
    assert "CSRN_WHISPER_MODEL_DIR" in spec
    assert "CSRN_BUNDLED_CHROMIUM_DIR" in spec
    assert "rthook_bundled_runtime.py" in spec


def test_bundled_runtime_hook_wires_playwright_and_hf_offline() -> None:
    root = Path(csrn_desktop.__file__).resolve().parent
    hook = (root / "packaging/windows/rthook_bundled_runtime.py").read_text(encoding="utf-8")
    assert "PLAYWRIGHT_BROWSERS_PATH" in hook
    assert "ms-playwright" in hook
    assert "CSRN_WHISPER_MODEL_DIR" in hook
    assert "HF_HUB_OFFLINE" in hook


def test_installer_launches_the_shell_exe_and_opens_the_lan_ports() -> None:
    root = Path(csrn_desktop.__file__).resolve().parent
    iss = (root / "packaging/windows/csrn-production-suite.iss").read_text(encoding="utf-8")

    assert 'MyAppExeName "CSRNProductionSuite.exe"' in iss
    launched = [
        line for line in iss.splitlines()
        if line.strip().startswith("Filename:") and "{#MyAppExeName}" in line
    ]
    assert launched
    assert not any(
        line.strip().startswith(("Filename:", "Source:")) and (".ps1" in line or ".bat" in line)
        for line in iss.splitlines()
    )
    assert "{autodesktop}\\{#MyAppName}" in iss
    assert "{group}\\{#MyAppName}" in iss or "{autoprograms}\\{#MyAppName}" in iss
    assert "localport=5050" in iss and "localport=5051" in iss
    assert "[UninstallRun]" in iss and "delete rule" in iss
    assert "MicrosoftEdgeWebview2Setup.exe" in iss
