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


def _fake_webview(events: list[str], captured: dict | None = None):
    def _start(**k):
        events.append("loop")
        if captured is not None:
            captured.update(k)
    return types.SimpleNamespace(
        create_window=lambda *a, **k: events.append("window"),
        start=_start,
        settings={},
        screens=[],
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


# --------------------------------------------------------------------------
# CLI parsing -- the installer's shortcuts (csrn-production-suite.iss) and
# post-install [Run] entry all launch with `--installed`; app.py's
# resolve_product_paths() reads it straight off sys.argv. main()'s own
# argparse must accept it too, or a strict parse_args() rejects it as an
# unrecognized argument and exits before the window (or even the health
# check) ever runs -- with console=False that's a silent, invisible failure
# the very first time someone launches from the Desktop/Start Menu shortcut.
# --------------------------------------------------------------------------


def test_main_accepts_the_installed_flag_the_installer_shortcuts_pass(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        csrn_desktop, "run", lambda **k: captured.update(k) or 0
    )
    assert csrn_desktop.main(["--installed"]) == 0
    assert captured == {"health_timeout": csrn_desktop.HEALTH_TIMEOUT_SECONDS}


def test_main_accepts_installed_and_health_timeout_together(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        csrn_desktop, "run", lambda **k: captured.update(k) or 0
    )
    assert csrn_desktop.main(["--installed", "--health-timeout", "5"]) == 0
    assert captured == {"health_timeout": 5}


def test_installer_shortcuts_only_pass_flags_main_understands() -> None:
    # Guards the other direction: if the .iss ever grows a new
    # Parameters: value, main()'s argparse must be updated to accept it too.
    root = Path(csrn_desktop.__file__).resolve().parent
    iss = (root / "packaging/windows/csrn-production-suite.iss").read_text(encoding="utf-8")
    known_flags = {"--health-timeout", "--installed", "-h", "--help"}
    for line in iss.splitlines():
        if 'Parameters: "' not in line:
            continue
        params = line.split('Parameters: "', 1)[1].split('"', 1)[0]
        for token in params.split():
            if token.startswith("--") or token.startswith("-"):
                assert token in known_flags, (
                    f"{token!r} is passed by the installer but main()'s "
                    "argparse doesn't accept it -- the installed shortcuts "
                    "would fail to launch"
                )


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


# --------------------------------------------------------------------------
# Window / taskbar icon (the running app must show the CSRN badge)
# --------------------------------------------------------------------------


def test_window_icon_resolves_to_the_bundled_csrn_ico() -> None:
    icon = csrn_desktop._window_icon()
    assert icon is not None
    assert Path(icon).name == "csrn-logo.ico"
    assert Path(icon).is_file()


def test_run_passes_the_window_icon_to_pywebview_start(monkeypatch) -> None:
    events: list[str] = []
    captured: dict = {}
    server = _FakeServer()
    monkeypatch.setattr(csrn_desktop, "current_state", lambda: "DOWN")
    monkeypatch.setattr(csrn_desktop, "wait_until_healthy", lambda *a, **k: True)
    monkeypatch.setitem(sys.modules, "app", _fake_app(server, events))
    monkeypatch.setitem(sys.modules, "webview", _fake_webview(events, captured))

    assert csrn_desktop.run(health_timeout=1) == 0
    assert Path(captured["icon"]).name == "csrn-logo.ico"


def test_run_enables_downloads_before_starting_the_window(monkeypatch) -> None:
    # Regression guard for the 2026-09-03 fix: ALLOW_DOWNLOADS is off by
    # default upstream, and the in-app Broadcaster Print Sheet PDF viewer
    # (openPdfInApp() in index.html) relies on its built-in download button
    # actually working -- without this, that button is a silent no-op.
    events: list[str] = []
    server = _FakeServer()
    fake_webview = _fake_webview(events)
    monkeypatch.setattr(csrn_desktop, "current_state", lambda: "DOWN")
    monkeypatch.setattr(csrn_desktop, "wait_until_healthy", lambda *a, **k: True)
    monkeypatch.setitem(sys.modules, "app", _fake_app(server, events))
    monkeypatch.setitem(sys.modules, "webview", fake_webview)

    assert csrn_desktop.run(health_timeout=1) == 0
    assert fake_webview.settings.get("ALLOW_DOWNLOADS") is True


# --------------------------------------------------------------------------
# Window sizing / centering -- must fit whatever screen it opens on
# --------------------------------------------------------------------------


class _FakeScreen:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height


def test_window_geometry_shrinks_to_fit_a_smaller_screen() -> None:
    webview = types.SimpleNamespace(screens=[_FakeScreen(1366, 768)])
    geometry = csrn_desktop._window_geometry(webview)

    assert geometry["width"] <= 1366
    assert geometry["height"] <= 768
    # fully on screen: the window plus its centered offset never exceeds
    # the physical display in either dimension
    assert geometry["x"] + geometry["width"] <= 1366
    assert geometry["y"] + geometry["height"] <= 768
    assert geometry["x"] >= 0
    assert geometry["y"] >= 0


def test_window_geometry_centers_on_the_primary_screen() -> None:
    webview = types.SimpleNamespace(screens=[_FakeScreen(1920, 1080)])
    geometry = csrn_desktop._window_geometry(webview)

    assert geometry["x"] == (1920 - geometry["width"]) // 2
    assert geometry["y"] == (1080 - geometry["height"]) // 2


def test_window_geometry_keeps_preferred_size_on_a_large_screen() -> None:
    webview = types.SimpleNamespace(screens=[_FakeScreen(2560, 1440)])
    geometry = csrn_desktop._window_geometry(webview)

    assert geometry["width"] == csrn_desktop.WINDOW_WIDTH
    assert geometry["height"] == csrn_desktop.WINDOW_HEIGHT


def test_window_geometry_falls_back_to_static_size_without_screen_info() -> None:
    webview = types.SimpleNamespace(screens=[])
    geometry = csrn_desktop._window_geometry(webview)
    assert geometry == {
        "width": csrn_desktop.WINDOW_WIDTH,
        "height": csrn_desktop.WINDOW_HEIGHT,
        "x": None,
        "y": None,
    }


def test_window_geometry_survives_screens_raising(monkeypatch) -> None:
    class _Boom:
        @property
        def screens(self):
            raise RuntimeError("GUI toolkit not ready")

    geometry = csrn_desktop._window_geometry(_Boom())
    assert geometry["width"] == csrn_desktop.WINDOW_WIDTH
    assert geometry["x"] is None


def test_create_window_passes_explicit_centered_geometry(monkeypatch) -> None:
    captured: dict = {}

    def _create_window(*a, **k):
        captured.update(k)

    webview = types.SimpleNamespace(
        screens=[_FakeScreen(1366, 768)],
        create_window=_create_window,
    )
    csrn_desktop._create_window(webview)

    assert captured["width"] <= 1366
    assert captured["height"] <= 768
    assert captured["x"] is not None and captured["y"] is not None
    assert captured["min_size"][0] <= captured["width"]
    assert captured["min_size"][1] <= captured["height"]


def test_shipped_csrn_logo_ico_is_transparent_and_multi_resolution() -> None:
    # Regression guard for the 2026-09-02 fix: the .ico must not carry an
    # opaque white box, and must ship the standard icon sizes.
    from PIL import Image

    path = Path(csrn_desktop.__file__).resolve().parent / "static" / "csrn-logo.ico"
    im = Image.open(path)
    sizes = {s[0] for s in im.ico.sizes()}
    assert {16, 32, 48, 256} <= sizes
    im.size = (256, 256)
    im.load()
    rgba = im.convert("RGBA")
    assert rgba.getpixel((0, 0))[3] == 0          # transparent corner, not white
    assert rgba.getpixel((2, 128))[3] == 0        # transparent outside the circle
    assert rgba.getpixel((128, 128))[3] == 255    # opaque logo centre


def test_pyinstaller_spec_embeds_the_window_icon() -> None:
    root = Path(csrn_desktop.__file__).resolve().parent
    spec = (root / "packaging/windows/CSRNProductionSuite.spec").read_text(encoding="utf-8")
    assert 'icon=str(ROOT / "static" / "csrn-logo.ico")' in spec


def test_bundled_runtime_hook_wires_playwright_and_hf_offline() -> None:
    root = Path(csrn_desktop.__file__).resolve().parent
    hook = (root / "packaging/windows/rthook_bundled_runtime.py").read_text(encoding="utf-8")
    assert "PLAYWRIGHT_BROWSERS_PATH" in hook
    assert "ms-playwright" in hook
    assert "CSRN_WHISPER_MODEL_DIR" in hook
    assert "HF_HUB_OFFLINE" in hook


# --------------------------------------------------------------------------
# DesktopApi -- native file dialog for Settings -> Quick Launch "Choose..."
# (2026-09-03 fix: a plain <input type="file"> only ever hands the page a
# bare filename in this WebView2-based shell, never a real path.)
# --------------------------------------------------------------------------


def test_run_wires_the_desktop_api_into_create_window(monkeypatch) -> None:
    events: list[str] = []
    captured: dict = {}
    server = _FakeServer()
    monkeypatch.setattr(csrn_desktop, "current_state", lambda: "DOWN")
    monkeypatch.setattr(csrn_desktop, "wait_until_healthy", lambda *a, **k: True)
    monkeypatch.setitem(sys.modules, "app", _fake_app(server, events))

    def _create_window(*a, js_api=None, **k):
        captured["js_api"] = js_api
        events.append("window")

    fake_webview = types.SimpleNamespace(
        create_window=_create_window,
        start=lambda **k: events.append("loop"),
        settings={},
        screens=[],
    )
    monkeypatch.setitem(sys.modules, "webview", fake_webview)

    assert csrn_desktop.run(health_timeout=1) == 0
    assert isinstance(captured["js_api"], csrn_desktop.DesktopApi)


def test_create_window_passes_the_api_through_as_js_api() -> None:
    captured: dict = {}

    def _create_window(*a, **k):
        captured.update(k)

    webview = types.SimpleNamespace(
        screens=[_FakeScreen(1366, 768)],
        create_window=_create_window,
    )
    api = csrn_desktop.DesktopApi()
    csrn_desktop._create_window(webview, api=api)

    assert captured["js_api"] is api


def test_pick_broadcast_software_returns_the_chosen_path(monkeypatch) -> None:
    fake_window = types.SimpleNamespace(
        create_file_dialog=lambda *a, **k: ("C:\\obs-studio\\bin\\64bit\\obs64.exe",)
    )
    fake_webview = types.SimpleNamespace(
        windows=[fake_window], OPEN_DIALOG="open"
    )
    monkeypatch.setitem(sys.modules, "webview", fake_webview)

    api = csrn_desktop.DesktopApi()
    assert api.pick_broadcast_software() == "C:\\obs-studio\\bin\\64bit\\obs64.exe"


def test_pick_broadcast_software_returns_empty_string_when_cancelled(monkeypatch) -> None:
    fake_window = types.SimpleNamespace(create_file_dialog=lambda *a, **k: None)
    fake_webview = types.SimpleNamespace(windows=[fake_window], OPEN_DIALOG="open")
    monkeypatch.setitem(sys.modules, "webview", fake_webview)

    api = csrn_desktop.DesktopApi()
    assert api.pick_broadcast_software() == ""


def test_pick_broadcast_software_survives_a_dialog_failure(monkeypatch) -> None:
    def _boom(*a, **k):
        raise RuntimeError("GUI toolkit not ready")

    fake_window = types.SimpleNamespace(create_file_dialog=_boom)
    fake_webview = types.SimpleNamespace(windows=[fake_window], OPEN_DIALOG="open")
    monkeypatch.setitem(sys.modules, "webview", fake_webview)

    api = csrn_desktop.DesktopApi()
    assert api.pick_broadcast_software() == ""  # never raises into the JS bridge


def test_pick_broadcast_software_returns_empty_string_with_no_open_window(monkeypatch) -> None:
    fake_webview = types.SimpleNamespace(windows=[], OPEN_DIALOG="open")
    monkeypatch.setitem(sys.modules, "webview", fake_webview)

    api = csrn_desktop.DesktopApi()
    assert api.pick_broadcast_software() == ""


def test_settings_prefers_the_native_dialog_and_falls_back_to_the_file_input() -> None:
    html = (Path(csrn_desktop.__file__).resolve().parent / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "async function chooseBroadcastSoftware()" in html
    assert "window.pywebview&&window.pywebview.api" in html
    assert "api.pick_broadcast_software()" in html
    assert 'onclick="chooseBroadcastSoftware()"' in html
    # the plain file input stays wired as the fallback for a plain browser
    assert 'onchange="pickBroadcastSoftware(this)"' in html


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
