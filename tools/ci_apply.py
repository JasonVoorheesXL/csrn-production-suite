from __future__ import annotations

from apply_phase_5_10 import apply


if __name__ == "__main__":
    changed = apply()
    if changed:
        print("Phase 5.10 application factory integration applied for CI.")
    else:
        print("Phase 5.10 application factory integration already present for CI.")
