"""CSRN Production Suite -- pywebview desktop shell.

Opens ONE native window at ``http://127.0.0.1:5050/?module=pregame``.

**In-process model (Round 21).** When this shell needs to start the
server it does so *in the same process*: it imports ``app``, builds the
Waitress server with ``app.build_command_center_server()``, and runs it on
a daemon thread while the pywebview window owns the main thread. On window
close it calls ``app.command_center_clean_shutdown()`` (recovery marker +
Drive state-mirror flush) and then ``server.close()`` -- **directly in
Python, with no OS signals, no subprocess, and no re-exec**. This replaces
the old child-process + ``CTRL_BREAK_EVENT`` scheme, which could not
deliver a signal to a windowed (``console=False``) frozen build.

What this shell deliberately does NOT change:
  * OBS browser sources keep hitting ``http://127.0.0.1:5050/overlay`` (and
    the scorebug / ticker / scene URLs) directly -- OBS never goes through
    this window.
  * Phone / tablet / iPad statistician access over the LAN keeps working
    because the server still binds ``0.0.0.0:5050`` (``app.py`` unchanged);
    this shell only points a *local* window at ``127.0.0.1``.
  * ``python app.py`` / RUN_CSRN_COMMAND_CENTER.bat + Ctrl+C is untouched.

If a healthy server is already running, this shell just opens a window at
it and never starts or stops anything.
"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import threading
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

HOST = "127.0.0.1"
PORT = 5050
HEALTH_URL = f"http://{HOST}:{PORT}/api/health"
WINDOW_URL = f"http://{HOST}:{PORT}/?module=pregame"
WINDOW_TITLE = "CSRN Command Center"
WINDOW_ICON = BASE_DIR / "static" / "csrn-logo.ico"

# Window sizing -- the control surface is dense (readiness grid, coin-toss
# modal, setup grids), so start large with a real minimum.
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 1000
WINDOW_MIN_WIDTH = 1280
WINDOW_MIN_HEIGHT = 800

HEALTH_TIMEOUT_SECONDS = 60
SERVER_JOIN_SECONDS = 10.0

_LOGGER = logging.getLogger("csrn.desktop")


# --------------------------------------------------------------------------
# Health / triage -- mirrors CSRN_GAME_DAY_LAUNCHER.ps1's Get-CsrnHealth.
# --------------------------------------------------------------------------


def port_is_listening(host: str = HOST, port: int = PORT, timeout: float = 0.75) -> bool:
    """True when something holds a listening socket on ``host:port``."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def probe_health(url: str = HEALTH_URL, timeout: float = 3.0) -> bool:
    """True only when ``/api/health`` answers 200 with ``{"status": "ok"}``.

    Intentionally lock-free on the server side -- it distinguishes a healthy
    instance from one that is bound but hung.
    """

    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (localhost)
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 -- any failure means "not healthy"
        return False
    return isinstance(payload, dict) and payload.get("status") == "ok"


def triage(port_listening: bool, healthy: bool) -> str:
    """DOWN (start it) / HEALTHY (attach) / HUNG (bound but not answering)."""

    if not port_listening:
        return "DOWN"
    return "HEALTHY" if healthy else "HUNG"


def current_state() -> str:
    listening = port_is_listening()
    healthy = probe_health() if listening else False
    return triage(listening, healthy)


def wait_until_healthy(
    deadline_seconds: int = HEALTH_TIMEOUT_SECONDS,
    *,
    health_check=probe_health,
    sleep=time.sleep,
    now=time.monotonic,
) -> bool:
    """Poll ``/api/health`` until healthy or the deadline passes."""

    started = now()
    while now() - started < deadline_seconds:
        if health_check():
            return True
        sleep(1.0)
    return health_check()


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def _window_geometry(webview) -> dict[str, int | None]:
    """Width/height/x/y for ``create_window``, fitted to whatever screen the
    shell is actually opening on.

    WINDOW_WIDTH/HEIGHT (1600x1000) are sized for the dense control surface,
    but that's larger than plenty of real screens (a 1366x768 laptop panel,
    a scaled-down external monitor). pywebview centers by splitting the
    width/height difference across both edges -- when the window is bigger
    than the screen that difference is negative, which pushes the title bar
    (and its close button) above/left of the visible screen. ``webview.screens``
    can be read before ``create_window``/``start`` are called, so we use the
    real primary-display size to clamp the window down and center it
    explicitly, instead of trusting pywebview's own "default: centered"
    x/y behaviour to save us on an oversized window."""
    try:
        screens = webview.screens
        primary = screens[0] if screens else None
    except Exception:  # noqa: BLE001 -- never let a screen query block startup
        primary = None

    if primary is None:
        return {"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT, "x": None, "y": None}

    screen_width = int(primary.width)
    screen_height = int(primary.height)

    # Leave headroom for the taskbar / window chrome so the whole window --
    # title bar and close button included -- lands on screen, not just its
    # center point.
    margin = 60
    width = min(WINDOW_WIDTH, max(screen_width - margin, WINDOW_MIN_WIDTH))
    height = min(WINDOW_HEIGHT, max(screen_height - margin, WINDOW_MIN_HEIGHT))
    # Never claim more than the physical screen exists, even on a display
    # too small to honor the "preferred" minimum.
    width = min(width, screen_width)
    height = min(height, screen_height)

    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    return {"width": width, "height": height, "x": x, "y": y}


class DesktopApi:
    """Exposed to the page as ``window.pywebview.api`` (see ``_create_window``).

    A plain ``<input type="file">`` never exposes a real filesystem path in
    a Chromium-based webview -- WebView2 deliberately withholds it, the same
    as every other modern browser, handing the page only the bare filename.
    That is why the Settings -> Quick Launch "Choose..." picker for the
    broadcast-software path was saving unusable values like ``obs64.exe``
    instead of a real path. pywebview's own native file dialog does not have
    that restriction, so the page calls this method instead when it is
    running inside this shell.
    """

    def pick_broadcast_software(self) -> str:
        try:
            import webview  # noqa: PLC0415 -- optional GUI dependency, imported late

            window = webview.windows[0] if webview.windows else None
            if window is None:
                return ""
            result = window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=("Programs (*.exe)", "All files (*.*)"),
            )
        except Exception:  # noqa: BLE001 -- a dialog failure must never crash the shell
            _LOGGER.exception("Broadcast-software file dialog failed.")
            return ""
        if not result:
            return ""  # operator cancelled
        return str(result[0])


def _create_window(webview, api=None):
    geometry = _window_geometry(webview)
    min_size = (
        min(WINDOW_MIN_WIDTH, geometry["width"]),
        min(WINDOW_MIN_HEIGHT, geometry["height"]),
    )
    return webview.create_window(
        WINDOW_TITLE,
        WINDOW_URL,
        width=geometry["width"],
        height=geometry["height"],
        x=geometry["x"],
        y=geometry["y"],
        min_size=min_size,
        confirm_close=True,
        js_api=api,
    )


def _window_icon() -> str | None:
    """The CSRN badge for the running window / taskbar entry.

    ``webview.start(icon=...)`` is a GTK/Qt-only feature upstream (see
    pywebview's own ``examples/icon.py``: "This is supported only on GTK
    and QT. For other platforms, icon is set during freezing.") -- on
    Windows this value is accepted but never wired to the native window's
    HICON. We still pass it (harmless, and it's what other platforms need),
    but on Windows it does not, and cannot, put the CSRN badge on the
    window itself.

    On Windows, a window that never sets its own icon falls back to the
    icon embedded in the *hosting process's exe* for both the title bar and
    the taskbar button. In dev mode that host is the venv's ``python.exe``,
    so a generic Python icon is expected there and is not fixable from this
    module. In the packaged build the host is ``CSRNProductionSuite.exe``,
    which the .spec embeds ``csrn-logo.ico`` into -- that's what actually
    puts the CSRN badge on the window, not this function. If the frozen exe
    still shows a stale icon, suspect Windows' taskbar icon cache
    (iconcache.db) holding on to an earlier unbadged build rather than the
    code here.

    Returns None if the asset is missing so the shell never fails to open.
    """
    return str(WINDOW_ICON) if WINDOW_ICON.is_file() else None


def run(*, health_timeout: int = HEALTH_TIMEOUT_SECONDS) -> int:
    """Start (or attach to) the server in-process, then run the pywebview
    loop; on window close, shut a shell-started server down cleanly."""

    state = current_state()
    _LOGGER.info("CSRN server state: %s", state)

    if state == "HUNG":
        _LOGGER.error(
            "Port %s is bound but /api/health is not answering. Close the "
            "stuck CSRN process (or reboot) and relaunch.",
            PORT,
        )
        return 1

    server = None            # the in-process Waitress server, if we own one
    server_thread = None
    if state == "DOWN":
        import app  # noqa: PLC0415 -- heavy import; only when we own the server

        server = app.build_command_center_server()
        server_thread = threading.Thread(
            target=server.run, name="csrn-command-center", daemon=True
        )
        server_thread.start()

    if not wait_until_healthy(health_timeout):
        _LOGGER.error(
            "CSRN did not become healthy on port %s within %ss.",
            PORT,
            health_timeout,
        )
        if server is not None:
            server.close()
        return 1

    try:
        import webview  # noqa: PLC0415 -- optional GUI dependency, imported late
    except ImportError:
        _LOGGER.error(
            "pywebview is not installed (it is pinned in requirements.txt "
            "for a packaged build)."
        )
        if server is not None:
            server.close()
        return 1

    # Off by default upstream. Needed for the in-app Broadcaster Print
    # Sheet viewer (openPdfInApp() in index.html): without this, the PDF
    # viewer's own built-in download button silently does nothing -- no
    # error, no file, on every platform pywebview supports it on. Must be
    # set before create_window()/start() per pywebview's own docs.
    webview.settings["ALLOW_DOWNLOADS"] = True

    _create_window(webview, api=DesktopApi())
    webview.start(func=None, gui=None, debug=False, icon=_window_icon())
    # webview.start() blocks until every window is closed.

    if server is not None:
        # Only tear down a server THIS shell started; an attached-to server
        # (another operator may be using it, OBS may be pulling overlays)
        # is left running.
        _LOGGER.info("Window closed -- clean shutdown of the in-process server.")
        import app  # noqa: PLC0415 -- already imported above; cheap

        try:
            app.command_center_clean_shutdown()
        finally:
            server.close()
            if server_thread is not None:
                server_thread.join(timeout=SERVER_JOIN_SECONDS)
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="CSRN Production Suite desktop shell (pywebview)."
    )
    parser.add_argument(
        "--health-timeout",
        type=int,
        default=HEALTH_TIMEOUT_SECONDS,
        help="Seconds to wait for /api/health before giving up.",
    )
    parser.add_argument(
        "--installed",
        action="store_true",
        help=(
            "Force installed-mode data paths (the %%LOCALAPPDATA%%/PossumFrog "
            "runtime root) even when not frozen. The installer's shortcuts "
            "(csrn-production-suite.iss) always pass this; sys.frozen alone "
            "already implies it for a packaged .exe, so this flag mainly "
            "exists so `--installed` never fails argument parsing, and so a "
            "dev-mode `python.exe csrn_desktop.py --installed` run can be "
            "used to sanity-check installed-mode paths (e.g. the data "
            "migration) without a full PyInstaller build. See "
            "product_paths.resolve_product_paths()."
        ),
    )
    args = parser.parse_args(argv)
    return run(health_timeout=args.health_timeout)


if __name__ == "__main__":
    raise SystemExit(main())
