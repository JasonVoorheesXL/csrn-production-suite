"""CSRN Production Suite -- pywebview desktop shell (Round 15C).

Opens ONE native window at ``http://127.0.0.1:5050/?module=pregame``.
Waitress still serves everything underneath: this shell launches the
existing ``app.py`` as a child process (or, in a frozen build, re-execs
itself in ``--serve-only`` mode -- see Round 15D) and just owns the window.

What this shell deliberately does NOT change:
  * OBS browser sources keep hitting ``http://127.0.0.1:5050/overlay`` (and
    the scorebug / ticker / scene URLs) directly -- OBS never goes through
    this window.
  * Phone / tablet / iPad statistician access over the LAN keeps working
    because the server still binds ``0.0.0.0:5050`` (``app.py`` unchanged);
    this shell only points a *local* window at ``127.0.0.1``.

What this shell owns:
  * Health-gated window open -- the DOWN / HEALTHY / HUNG triage the
    PowerShell launcher already does, then wait for ``/api/health`` to
    answer ``{"status": "ok"}`` before showing the window.
  * Clean-shutdown-on-window-close -- a window close delivers no signal, so
    on close we send the child ``CTRL_BREAK_EVENT`` (Windows) / ``SIGTERM``
    (POSIX), which ``app.py`` routes through the same recovery-marker +
    Drive-mirror-flush path as Ctrl+C. If we merely *attached* to a server
    that was already running, closing the window leaves it running.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import socket
import subprocess
import sys
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
GRACEFUL_SHUTDOWN_SECONDS = 20.0

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


# --------------------------------------------------------------------------
# Child server process
# --------------------------------------------------------------------------


def server_command(python_executable: str | None = None) -> list[str]:
    """Argv for the underlying Waitress server.

    Frozen build: re-exec this same executable in ``--serve-only`` mode so
    the packaged app needs no ``.ps1`` / ``.bat`` chain (Round 15D wires the
    ``--serve-only`` branch into ``app.py``'s ``__main__``). Source checkout:
    run ``app.py`` with the active interpreter.
    """

    if getattr(sys, "frozen", False):
        return [sys.executable, "--serve-only"]
    return [python_executable or sys.executable, str(BASE_DIR / "app.py")]


def start_server(command: list[str] | None = None) -> subprocess.Popen:
    """Launch the child server in its own process group.

    A new process group is required so we can later deliver
    ``CTRL_BREAK_EVENT`` to the child alone without also signalling this
    shell.
    """

    command = command or server_command()
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    _LOGGER.info("Starting CSRN server: %s", " ".join(command))
    return subprocess.Popen(  # noqa: S603 -- fixed argv, no shell
        command,
        cwd=str(BASE_DIR),
        creationflags=creationflags,
    )


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


def request_graceful_shutdown(
    process: subprocess.Popen,
    *,
    timeout: float = GRACEFUL_SHUTDOWN_SECONDS,
) -> int | None:
    """Ask the child to shut down cleanly, then hard-stop if it will not.

    ``CTRL_BREAK_EVENT`` (Windows) / ``SIGTERM`` (POSIX) both land on
    ``app.py``'s ``_record_clean_shutdown_and_stop`` handler, which writes
    the clean-shutdown recovery marker and flushes the Drive state mirror
    before exiting -- so a shell close is never read as an unclean exit.
    """

    if process.poll() is not None:
        return process.returncode

    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
        else:
            process.send_signal(signal.SIGTERM)
    except (ProcessLookupError, OSError) as exc:  # pragma: no cover
        _LOGGER.warning("Could not signal the CSRN server: %s", exc)

    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _LOGGER.warning(
            "CSRN server did not exit within %.0fs of the shutdown request; "
            "terminating.",
            timeout,
        )
        process.terminate()
        try:
            return process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:  # pragma: no cover
            process.kill()
            return process.wait(timeout=5.0)


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
    """Start (or attach to) the server, then run the pywebview loop."""

    state = current_state()
    _LOGGER.info("CSRN server state: %s", state)

    server: subprocess.Popen | None = None
    started_by_shell = False

    if state == "HUNG":
        _LOGGER.error(
            "Port %s is bound but /api/health is not answering. Close the "
            "stuck CSRN process (or reboot) and relaunch.",
            PORT,
        )
        return 1

    if state == "DOWN":
        server = start_server()
        started_by_shell = True

    if not wait_until_healthy(health_timeout):
        _LOGGER.error(
            "CSRN did not become healthy on port %s within %ss.",
            PORT,
            health_timeout,
        )
        if server is not None and started_by_shell:
            request_graceful_shutdown(server)
        return 1

    try:
        import webview  # noqa: PLC0415 -- optional GUI dependency, imported late
    except ImportError:
        _LOGGER.error(
            "pywebview is not installed. `pip install pywebview` (it is in "
            "requirements.txt for a packaged build)."
        )
        if server is not None and started_by_shell:
            request_graceful_shutdown(server)
        return 1

    _create_window(webview)

    def _on_closed() -> None:
        # Only tear down a server THIS shell started; never kill one we just
        # attached to (another operator may be using it, OBS may be pulling
        # overlays from it).
        if server is not None and started_by_shell:
            _LOGGER.info("Window closed -- shutting the CSRN server down cleanly.")
            request_graceful_shutdown(server)

    webview.start(
        func=None,
        gui=None,
        debug=False,
    )
    # webview.start() blocks until every window is closed.
    _on_closed()
    return 0


def main(argv: list[str] | None = None) -> int:
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

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return run(health_timeout=args.health_timeout)


if __name__ == "__main__":
    raise SystemExit(main())
