from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHASE_PREPARATION = ROOT / "tools" / "ci_apply.py"


def main() -> None:
    if not PHASE_PREPARATION.exists():
        print("No optional CI phase preparation is present.")
        return
    print(f"Applying optional CI preparation: {PHASE_PREPARATION.name}")
    runpy.run_path(str(PHASE_PREPARATION), run_name="__main__")


if __name__ == "__main__":
    main()
