"""Capture the OBS Setup Guide's app screenshots from a brand-new install.

Reuses the Station Setup Guide's capture helpers (fresh install of the
fictional "Westside Sports Network", demo instance on its own port, restore
afterwards). OBS itself is not driven; its steps are described in the text.

Refuses to run in the production folder.

Usage:  .venv/Scripts/python.exe docs/obs_setup_guide/tools/capture.py <runtime_dir>
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

TOOLS = Path(__file__).resolve().parent
GUIDE = TOOLS.parent
REPO = GUIDE.parents[1]
sys.path.insert(0, str(REPO / "docs" / "station_setup_guide" / "tools"))
import capture as station  # noqa: E402

SHOTS = GUIDE / "screenshots"


def walk(page, shots, logo: Path) -> None:
    page.goto(station.BASE + "/")
    page.wait_for_timeout(1500)
    page.fill("#orgName", "Westside Sports Network")
    page.fill("#shortName", "WSN")
    page.select_option("#sport", "football")
    page.set_input_files("#logoFile", str(logo))
    page.wait_for_timeout(1500)
    page.click("#finishBtn")
    page.wait_for_selector("#guidesStep:not([hidden])", timeout=15000)
    page.click("#openConsoleBtn")
    page.wait_for_timeout(2500)
    page.fill("#newPin", station.PIN)
    page.fill("#confirmPin", station.PIN)
    page.evaluate("setupPin()")
    page.wait_for_timeout(3000)
    if page.locator("#loginPin").is_visible():
        page.fill("#loginPin", station.PIN)
        page.evaluate("login()")
        page.wait_for_timeout(3000)

    station.module(page, "obs")
    shots.take("obs-manager-top", "OBS Manager before OBS is connected")
    station.scroll_to_heading(page, "Browser Source Setup")
    shots.take("obs-manager-download", "OBS Manager: download the scene collection")
    station.module(page, "settings")
    station.scroll_to_heading(page, "OBS")
    shots.take("settings-obs", "Settings > OBS")


def main() -> None:
    runtime = Path(sys.argv[1]).resolve()
    kept = station.fresh_install(runtime)
    shutil.rmtree(SHOTS, ignore_errors=True)
    SHOTS.mkdir(parents=True)
    station.SHOTS = SHOTS
    logo = runtime / "wsn-logo.png"
    station.demo_logo(logo)
    log = open(runtime / "server.log", "w", encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, str(REPO / "docs" / "statistician_guide" / "tools" / "run_demo_instance.py"),
         str(runtime), str(station.PORT)],
        cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        station.wait_for_server()
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 860})
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            shots = station.Shots(page)
            walk(page, shots, logo)
            browser.close()
        (GUIDE / "capture_log.json").write_text(
            json.dumps({"shots": shots.log, "page_errors": errors}, indent=2), encoding="utf-8"
        )
        print("page errors:", errors)
    finally:
        server.terminate()
        server.wait(timeout=20)
        log.close()
        station.restore(kept)


if __name__ == "__main__":
    main()
