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


def _free_port() -> int:
    """An unused loopback port chosen by the OS (bind to 0, read it back)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


# pywebview 6.2.1's own defaults (webview.settings), used only when pywebview is
# not importable. When it is, the double copies the *installed* version's
# defaults and signatures instead, so it tracks upgrades on its own.
_PYWEBVIEW_SETTINGS_FALLBACK = {
    "ALLOW_DOWNLOADS": False,
    "ALLOW_FILE_URLS": True,
    "DRAG_REGION_SELECTOR": ".pywebview-drag-region",
    "DRAG_REGION_DIRECT_TARGET_ONLY": False,
    "DEFAULT_HTTP_PORT": 42001,
    "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,
    "OPEN_DEVTOOLS_IN_DEBUG": True,
    "REMOTE_DEBUGGING_PORT": None,
    "IGNORE_SSL_ERRORS": False,
    "SHOW_DEFAULT_MENUS": True,
    "WEBVIEW2_RUNTIME_PATH": None,
}
_PYWEBVIEW_CREATE_WINDOW_FALLBACK = (
    "title", "url", "html", "js_api", "width", "height", "x", "y", "screen", "resizable",
    "fullscreen", "min_size", "hidden", "frameless", "easy_drag", "shadow", "focus", "minimized",
    "maximized", "on_top", "confirm_close", "background_color", "transparent", "text_select",
    "zoomable", "draggable", "vibrancy", "menu", "localization", "server", "http_port", "server_args",
)
_PYWEBVIEW_START_FALLBACK = (
    "func", "args", "localization", "gui", "debug", "http_server", "http_port", "user_agent",
    "private_mode", "storage_path", "menu", "server", "server_args", "ssl", "icon",
)


class _ImmutableSettings(dict):
    """Same contract as pywebview's ``webview.settings`` (an ImmutableDict):
    existing keys may be modified, unknown keys are rejected, none deleted."""

    def __setitem__(self, key, value):
        if key not in self:
            raise KeyError(f"Cannot add new key '{key}'. Only existing keys can be modified.")
        super().__setitem__(key, value)

    def __delitem__(self, key):
        raise KeyError("Deleting keys is not allowed.")


class _Screen:
    """The shape of a pywebview Screen: the shell reads ``.width`` / ``.height``."""

    def __init__(self, width: int, height: int) -> None:
        self.width, self.height = width, height


def _real_pywebview_facts():
    """(settings defaults, create_window params, start params) from the installed
    pywebview when there is one, else the pinned 6.2.1 fallbacks above."""
    import inspect

    try:
        import webview as real  # imported BEFORE the test swaps sys.modules["webview"]

        return (
            dict(real.settings),
            tuple(inspect.signature(real.create_window).parameters),
            tuple(inspect.signature(real.start).parameters),
        )
    except Exception:  # noqa: BLE001 -- not installed / cannot import: use the pinned facts
        return (
            dict(_PYWEBVIEW_SETTINGS_FALLBACK),
            _PYWEBVIEW_CREATE_WINDOW_FALLBACK,
            _PYWEBVIEW_START_FALLBACK,
        )


def test_shell_run_real_server_clean_shutdown_on_window_close(monkeypatch, tmp_path) -> None:
    """Round 21D headless: real csrn_desktop.run() + real in-process server
    on a daemon thread + real command_center_clean_shutdown() + real
    server.close(); only the pywebview window is faked (start() returns ==
    the user closed it).

    Runs on OS-chosen ports, so it never depends on -- or disturbs -- a real CSRN
    instance holding :5050/:5051, and it passes (never skips) either way. The
    port is not part of what this test asserts: the shell's constants are
    pinned by test_csrn_desktop.py, and run()'s call shape is pinned textually
    elsewhere, so the ports are redirected from here rather than by changing
    production code.
    """
    import functools
    import urllib.request

    import waitress

    import csrn_desktop

    settings_defaults, create_window_params, start_params = _real_pywebview_facts()

    port = _free_port()
    health_url = f"http://127.0.0.1:{port}/api/health"
    window_url = f"http://127.0.0.1:{port}/?module=pregame"

    # -- the shell: every place that freezes 5050 (module constants, and default
    # arguments bound at import time) is pointed at our port. -----------------
    monkeypatch.setattr(csrn_desktop, "PORT", port)
    monkeypatch.setattr(csrn_desktop, "HEALTH_URL", health_url)
    monkeypatch.setattr(csrn_desktop, "WINDOW_URL", window_url)
    probe = functools.partial(csrn_desktop.probe_health, url=health_url)
    monkeypatch.setattr(csrn_desktop, "probe_health", probe)
    monkeypatch.setattr(
        csrn_desktop, "port_is_listening", functools.partial(csrn_desktop.port_is_listening, port=port)
    )
    monkeypatch.setattr(
        csrn_desktop, "wait_until_healthy", functools.partial(csrn_desktop.wait_until_healthy, health_check=probe)
    )

    # -- the server: the real Waitress server, bound to loopback on our port. ----
    real_create_server = waitress.create_server

    def create_server_on_our_port(application, **kwargs):
        kwargs.update(host="127.0.0.1", port=port)
        return real_create_server(application, **kwargs)

    monkeypatch.setattr(waitress, "create_server", create_server_on_our_port)

    # The isolated media server is a process-wide singleton hard-bound to :5051 and
    # is not what this test is about; fake it exactly as the first test in this
    # file does. Likewise skip touching the real install's Data/config.
    monkeypatch.setattr(app_module, "start_isolated_media_server", lambda *a, **k: 5051)
    monkeypatch.setattr(app_module, "ensure_data_architecture", lambda: None)
    monkeypatch.setattr(app_module, "load_config", lambda: {})

    rec = tmp_path / "Data" / "Backups" / "Recovery"
    rec.mkdir(parents=True)
    marker = rec / "active_session.json"
    marker.write_text('{"pid": 1}', encoding="utf-8")
    monkeypatch.setenv("CSRN_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("CSRN_DATA_ROOT", str(tmp_path / "Data"))
    # point the recovery service's session marker at our planted file
    monkeypatch.setattr(app_module, "GAME_DAY_RECOVERY_DIR", rec, raising=False)
    monkeypatch.setattr(app_module, "RECOVERY_SERVICE", None, raising=False)

    # command_center_clean_shutdown() flushes the state mirror, which is a real file
    # in the project folder (the owner's state.json on a live install). Stub the
    # repository so this test can never write it -- and assert the flush happens.
    class _Repo:
        flushes = 0

        def flush(self):
            _Repo.flushes += 1

    monkeypatch.setattr(app_module, "STATE_REPOSITORY", _Repo())

    seen: dict = {"calls": []}

    class _FakeWebview:
        """A pywebview double with the real object's shape and rules."""

        settings = _ImmutableSettings(settings_defaults)
        screens = [_Screen(1920, 1080)]
        windows: list = []

        @staticmethod
        def _check(name, kwargs, allowed):
            unknown = sorted(set(kwargs) - set(allowed))
            assert not unknown, f"webview.{name}() got kwargs pywebview does not accept: {unknown}"

        @classmethod
        def create_window(cls, *args, **kwargs):
            cls._check("create_window", kwargs, create_window_params)
            # ALLOW_DOWNLOADS must already be on when the window is created.
            seen["calls"].append(("create_window", args, kwargs, cls.settings["ALLOW_DOWNLOADS"]))
            return object()

        @classmethod
        def start(cls, *args, **kwargs):
            cls._check("start", kwargs, start_params)
            seen["calls"].append(("start", args, kwargs, cls.settings["ALLOW_DOWNLOADS"]))
            try:
                with urllib.request.urlopen(health_url, timeout=3) as r:
                    seen["health"] = r.status
            except Exception as e:  # noqa: BLE001
                seen["health"] = repr(e)

    monkeypatch.setitem(__import__("sys").modules, "webview", _FakeWebview)

    try:
        rc = csrn_desktop.run(health_timeout=60)
    finally:
        app_module.RECOVERY_SERVICE = None  # next real use rebuilds cleanly

    assert rc == 0
    assert seen.get("health") == 200          # server really served, in-process, on our port
    assert not marker.exists()                # command_center_clean_shutdown() ran
    assert _Repo.flushes == 1                 # ...and flushed the state mirror
    assert not _listening(port)               # server.close() released the port

    # The shell's webview contract: ALLOW_DOWNLOADS is turned on -- and only that --
    # before the window is created and before start() blocks.
    names = [c[0] for c in seen["calls"]]
    assert names == ["create_window", "start"]
    assert [c[3] for c in seen["calls"]] == [True, True]
    expected = dict(settings_defaults, ALLOW_DOWNLOADS=True)
    assert dict(_FakeWebview.settings) == expected

    create_kwargs = seen["calls"][0][2]
    assert seen["calls"][0][1][1] == window_url            # opens the URL it just served
    assert isinstance(create_kwargs["js_api"], csrn_desktop.DesktopApi)
    assert create_kwargs["confirm_close"] is True
    # the shell fitted the window to the (fake) 1920x1080 primary screen
    assert create_kwargs["width"] <= 1920 and create_kwargs["height"] <= 1080
    assert create_kwargs["x"] == (1920 - create_kwargs["width"]) // 2
