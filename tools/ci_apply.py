from __future__ import annotations

from tools.apply_phase_4_21 import apply


if __name__ == "__main__":
    changed = apply()
    if changed:
        print("Phase 4.21 GameOperationsService integration applied for CI.")
    else:
        print("Phase 4.21 GameOperationsService integration already present for CI.")
