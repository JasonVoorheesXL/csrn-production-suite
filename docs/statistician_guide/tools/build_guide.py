"""Rebuild the statistician guide end to end.

1. Reset this worktree's demo data (refuses to run in the production folder).
2. Start the isolated demo instance and seed FB-DEMO-GUIDE-001.
3. Drive the real Statistician Console with Playwright (walkthrough.py),
   saving screenshots to docs/statistician_guide/screenshots/.
4. Stop the instance and render the PDF (render_pdf.py).

Usage:  .venv/Scripts/python.exe docs/statistician_guide/tools/build_guide.py <runtime_dir> [--skip-capture]
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
GUIDE = TOOLS.parent
REPO = GUIDE.parents[1]
PORT = 5072


def reset_demo_data(runtime: Path) -> None:
    if "My Drive" in str(REPO) or "Google Drive" in str(REPO):
        raise SystemExit("Refusing to reset data inside the production folder.")
    # Data/ starts as a pristine checkout in this worktree; everything the app
    # wrote there is demo data. Remove it and restore tracked files.
    subprocess.run(["git", "-C", str(REPO), "clean", "-fdxq", "--", "Data"], check=True)
    subprocess.run(["git", "-C", str(REPO), "checkout", "--", "Data"], check=True)
    for name in ("security.json",):
        (REPO / name).unlink(missing_ok=True)
    (REPO / "state.json").write_text("{}\n", encoding="utf-8")
    settings = REPO / "Data" / "Settings"
    settings.mkdir(parents=True, exist_ok=True)
    (settings / "config.json").write_text(
        json.dumps(
            {
                "organization": {
                    "name": "Caledonia Sports Radio Network",
                    "short_name": "CSRN",
                    "logo_path": "static/csrn-logo.png",
                    "primary_color": "#c9203b",
                    "secondary_color": "#000000",
                    "accent_color": "#ffffff",
                    "logo": "",
                },
                "broadcast_defaults": {
                    "venue": "Northgate Memorial Stadium (DEMO)",
                    "sport": "Football",
                    "timezone": "America/Chicago",
                    "theme": "CSRN Dark",
                    "home_school_id": "",
                    "visual_mode": "graphic",
                },
                "obs": {"websocket_enabled": False, "controlled_commands": False,
                        "host": "127.0.0.1", "port": 4455, "password": ""},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    shutil.rmtree(runtime, ignore_errors=True)
    runtime.mkdir(parents=True)


def wait_for_server() -> None:
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/security-status", timeout=2)
            return
        except Exception:
            time.sleep(0.5)
    raise SystemExit("Demo instance did not start.")


def main() -> None:
    runtime = Path(sys.argv[1]).resolve()
    python = sys.executable
    if "--skip-capture" not in sys.argv:
        reset_demo_data(runtime)
        log = open(runtime / "server.log", "w", encoding="utf-8")
        server = subprocess.Popen(
            [python, str(TOOLS / "run_demo_instance.py"), str(runtime), str(PORT)],
            cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            wait_for_server()
            subprocess.run([python, str(TOOLS / "seed_demo_broadcast.py"), str(runtime), str(PORT)],
                           cwd=REPO, check=True)
            subprocess.run([python, str(TOOLS / "walkthrough.py"), str(runtime), str(PORT)]
                           + [a for a in sys.argv[2:] if a.startswith("--until=")],
                           cwd=REPO, check=True)
        finally:
            server.terminate()
            server.wait(timeout=20)
    if (TOOLS / "render_pdf.py").exists():
        subprocess.run([python, str(TOOLS / "render_pdf.py")], cwd=REPO, check=True)


if __name__ == "__main__":
    main()
