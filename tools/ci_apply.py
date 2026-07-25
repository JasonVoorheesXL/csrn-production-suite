from __future__ import annotations

from apply_phase_5_3 import apply


if __name__ == "__main__":
    changed = apply()
    if changed:
        print("Phase 5.3 school and association Blueprint integration applied for CI.")
    else:
        print("Phase 5.3 school and association Blueprint integration already present for CI.")
