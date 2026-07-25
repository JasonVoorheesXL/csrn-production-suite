from __future__ import annotations

from apply_phase_5_4 import apply


if __name__ == "__main__":
    changed = apply()
    if changed:
        print("Phase 5.4 roster, personnel, and venue route integration applied for CI.")
    else:
        print("Phase 5.4 route integration already present for CI.")
