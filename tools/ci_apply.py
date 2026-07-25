from __future__ import annotations

from tools.apply_phase_4_17 import apply


if __name__ == "__main__":
    changed = apply()
    if changed:
        print("Phase 4.17 UpgradeService integration applied for CI.")
    else:
        print("Phase 4.17 UpgradeService integration already present for CI.")
