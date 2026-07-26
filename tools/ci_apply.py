from __future__ import annotations

from apply_phase_6_2 import apply


if __name__ == "__main__":
    changed = apply()
    print(
        "Phase 6.2 social event publishing integration applied for CI."
        if changed
        else "Phase 6.2 integration already present for CI."
    )
