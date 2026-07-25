from __future__ import annotations

from tools.apply_phase_4_18 import apply


if __name__ == "__main__":
    changed = apply()
    if changed:
        print("Phase 4.18 EventService integration applied for CI.")
    else:
        print("Phase 4.18 EventService integration already present for CI.")
