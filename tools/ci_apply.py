from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"


def main() -> None:
    text = APP_PATH.read_text(encoding="utf-8")
    if "from graphics_service import GraphicsService" in text:
        print("Phase 4.11 GraphicsService integration is already present.")
        return
    runpy.run_path(
        str(ROOT / "tools" / "apply_phase_4_11.py"),
        run_name="__main__",
    )


if __name__ == "__main__":
    main()
