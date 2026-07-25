from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    runpy.run_path(
        str(ROOT / "tools" / "apply_phase_4_12.py"),
        run_name="__main__",
    )
