from __future__ import annotations

from apply_phase_4_24 import apply


if __name__ == "__main__":
    changed = apply()
    if changed:
        print("Phase 4.24 consolidation cleanup applied for CI.")
    else:
        print("Phase 4.24 consolidation cleanup already present for CI.")
