from __future__ import annotations

from apply_phase_5_8 import apply


if __name__ == "__main__":
    changed = apply()
    if changed:
        print("Phase 5.8 live-game route integration applied for CI.")
    else:
        print("Phase 5.8 live-game route integration already present for CI.")
