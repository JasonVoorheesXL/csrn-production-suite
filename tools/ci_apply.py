from __future__ import annotations

from tools.apply_phase_4_13 import apply


if __name__ == "__main__":
    changed = apply()
    print(
        "Applied Phase 4.13 OBSService integration for CI."
        if changed
        else "Phase 4.13 OBSService integration already present for CI."
    )
