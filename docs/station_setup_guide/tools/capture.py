"""Capture the Station Setup Guide's screenshots from a brand-new install.

Resets this worktree to a fresh install (no state, config, identity profile or
PIN), starts the statistician guide's isolated demo instance on its own port,
and walks the first-run wizard and setup pages as a new station would:
"Westside Sports Network" (WSN), a fictional station.

Refuses to run in the production folder.

Usage:  .venv/Scripts/python.exe docs/station_setup_guide/tools/capture.py <runtime_dir>
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import Page, sync_playwright

TOOLS = Path(__file__).resolve().parent
GUIDE = TOOLS.parent
REPO = GUIDE.parents[1]
SHOTS = GUIDE / "screenshots"
PORT = 5075
BASE = f"http://127.0.0.1:{PORT}"
PIN = "135790"
SEED_FILES = ("state.json", "identity_profile.json", "security.json")


def fresh_install(runtime: Path) -> dict[str, bytes]:
    if "My Drive" in str(REPO) or "Google Drive" in str(REPO):
        raise SystemExit("Refusing to reset data inside the production folder.")
    kept = {name: (REPO / name).read_bytes() for name in SEED_FILES if (REPO / name).exists()}
    subprocess.run(["git", "-C", str(REPO), "clean", "-fdxq", "--", "Data"], check=True)
    subprocess.run(["git", "-C", str(REPO), "checkout", "--", "Data"], check=True)
    for name in SEED_FILES:
        (REPO / name).unlink(missing_ok=True)
    (REPO / "Data" / "Settings" / "config.json").unlink(missing_ok=True)
    shutil.rmtree(runtime, ignore_errors=True)
    runtime.mkdir(parents=True)
    return kept


def restore(kept: dict[str, bytes]) -> None:
    subprocess.run(["git", "-C", str(REPO), "clean", "-fdxq", "--", "Data"], check=True)
    subprocess.run(["git", "-C", str(REPO), "checkout", "--", "Data"], check=True)
    for name, data in kept.items():
        (REPO / name).write_bytes(data)
    for leftover in (REPO / "static" / "organization").glob("organization-logo*"):
        if not subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", str(leftover)],
                              capture_output=True).returncode == 0:
            leftover.unlink()


def demo_logo(path: Path) -> None:
    image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 504, 504), fill=(18, 52, 120, 255), outline=(255, 196, 0, 255), width=22)
    try:
        font = ImageFont.truetype("arialbd.ttf", 150)
    except OSError:
        font = ImageFont.load_default()
    draw.text((256, 256), "WSN", fill=(255, 255, 255, 255), font=font, anchor="mm")
    image.save(path)


def wait_for_server() -> None:
    for _ in range(120):
        try:
            urllib.request.urlopen(f"{BASE}/api/onboarding/context", timeout=2)
            return
        except Exception:
            time.sleep(0.5)
    raise SystemExit("Demo instance did not start.")


class Shots:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.count = 0
        self.log: list[dict[str, str]] = []

    def take(self, slug: str, note: str = "", element: str | None = None, full: bool = False) -> None:
        self.count += 1
        path = SHOTS / f"{self.count:02d}_{slug}.png"
        self.page.wait_for_timeout(700)
        if element:
            locator = self.page.locator(element).first
            locator.scroll_into_view_if_needed()
            self.page.wait_for_timeout(300)
            locator.screenshot(path=str(path))
        else:
            self.page.screenshot(path=str(path), full_page=full)
        self.log.append({"file": path.name, "note": note})
        print("captured", path.name, flush=True)


def scroll_to_heading(page: Page, text: str, offset: int = 90) -> None:
    page.evaluate(
        """([text, offset]) => {
          const h = [...document.querySelectorAll('h1,h2,h3')].find(x => x.offsetParent && x.textContent.trim() === text);
          if (h) window.scrollTo(0, h.getBoundingClientRect().top + window.scrollY - offset);
        }""",
        [text, offset],
    )
    page.wait_for_timeout(400)


def module(page: Page, name: str) -> None:
    page.evaluate(f"showModule('{name}')")
    page.wait_for_timeout(1500)
    page.evaluate("window.scrollTo(0,0)")


def walk(page: Page, shots: Shots, logo: Path) -> None:
    page.goto(BASE + "/")
    page.wait_for_timeout(1500)
    shots.take("wizard-blank", "First launch: the setup wizard")
    page.fill("#orgName", "Westside Sports Network")
    page.fill("#shortName", "WSN")
    page.select_option("#sport", "football")
    page.fill("#schoolName", "Westside High School")
    page.set_input_files("#logoFile", str(logo))
    page.wait_for_timeout(1500)
    shots.take("wizard-filled", "Wizard filled in")
    page.click("#finishBtn")
    page.wait_for_selector("#guidesStep:not([hidden])", timeout=15000)
    shots.take("wizard-guides", "Finish: the guides step")
    page.click("#openConsoleBtn")
    page.wait_for_timeout(2500)
    shots.take("create-pin", "Create the operator PIN")
    page.fill("#newPin", PIN)
    page.fill("#confirmPin", PIN)
    page.evaluate("setupPin()")
    page.wait_for_timeout(3000)
    if page.locator("#loginPin").is_visible():
        shots.take("login", "Operator login with sport tiles")
        page.fill("#loginPin", PIN)
        page.evaluate("login()")
        page.wait_for_timeout(3000)
    shots.take("command-center", "Command Center on a new install")

    module(page, "settings")
    shots.take("settings-guides", "Settings: Guides and Organization")
    scroll_to_heading(page, "Organization")
    shots.take("settings-organization", "Settings: Organization")
    scroll_to_heading(page, "Appearance")
    shots.take("settings-appearance", "Settings: Appearance")
    scroll_to_heading(page, "Sports")
    shots.take("settings-sports", "Settings: Sports and Retired Tools")
    scroll_to_heading(page, "OBS")
    shots.take("settings-obs", "Settings: OBS")
    scroll_to_heading(page, "Quick Launch")
    shots.take("settings-quick-launch", "Settings: Quick Launch and Station Social Media")

    module(page, "schools")
    shots.take("schools", "School Database")
    module(page, "rosters")
    shots.take("rosters", "Rosters")
    module(page, "sponsors")
    shots.take("sponsors", "Sponsors")
    module(page, "assets")
    shots.take("media-library", "Media Library tab")
    module(page, "graphics")
    shots.take("graphics", "Graphics: player graphic")
    module(page, "obs")
    shots.take("obs-manager", "OBS Manager")
    scroll_to_heading(page, "Browser Source Setup")
    shots.take("obs-browser-source", "OBS Manager: Browser Source Setup")
    module(page, "games")
    shots.take("game-manager", "Game Manager")
    module(page, "pregame")
    shots.take("pregame", "Pre-Game Setup")
    module(page, "statistician")
    scroll_to_heading(page, "Mobile / USB Connection", offset=150)
    # Show a sample address rather than this computer's real one.
    page.evaluate(
        """() => document.querySelectorAll('.connection-panel *').forEach(el => {
          if (el.children.length === 0 && /^https?:\\/\\/[0-9.]+:\\d+/.test(el.textContent.trim()))
            el.textContent = 'http://192.168.1.50:5050';
        })"""
    )
    shots.take("connection", "Statistician: Mobile / USB Connection")
    module(page, "diagnostics")
    page.wait_for_timeout(2500)
    shots.take("system-check", "System Check")


def main() -> None:
    runtime = Path(sys.argv[1]).resolve()
    kept = fresh_install(runtime)
    shutil.rmtree(SHOTS, ignore_errors=True)
    SHOTS.mkdir(parents=True)
    logo = runtime / "wsn-logo.png"
    demo_logo(logo)
    log = open(runtime / "server.log", "w", encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, str(REPO / "docs" / "statistician_guide" / "tools" / "run_demo_instance.py"),
         str(runtime), str(PORT)],
        cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        wait_for_server()
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 860})
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            shots = Shots(page)
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
        restore(kept)


if __name__ == "__main__":
    main()
