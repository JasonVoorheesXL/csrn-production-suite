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


def _create_window(webview):
    return webview.create_window(
        WINDOW_TITLE,
        WINDOW_URL,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT),
        confirm_close=True,
    )


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

    _create_window(webview)
    webview.start(func=None, gui=None, debug=False)
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
    args = parser.parse_args(argv)
    return run(health_timeout=args.health_timeout)


if __name__ == "__main__":
    raise SystemExit(main())
