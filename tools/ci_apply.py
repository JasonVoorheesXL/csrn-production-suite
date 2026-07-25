from __future__ import annotations

from tools.apply_phase_4_23 import apply


if __name__ == "__main__":
    changed = apply()
    if changed:
        print("Phase 4.23 BroadcastLifecycleService integration applied for CI.")
    else:
        print("Phase 4.23 BroadcastLifecycleService integration already present for CI.")
