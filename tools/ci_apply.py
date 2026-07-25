from __future__ import annotations

from tools.apply_phase_4_14 import apply


if __name__ == "__main__":
    changed = apply()
    print(
        "Applied Phase 4.14 ConfigurationService integration for CI."
        if changed
        else "Phase 4.14 ConfigurationService integration already present."
    )
