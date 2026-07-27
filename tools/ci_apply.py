from __future__ import annotations

from apply_phase_6_10 import apply as apply_phase
from apply_phase_6_10_x_manual_policy import apply as apply_x_manual_policy
from fix_phase_6_10_idempotence import apply as apply_idempotence_fix


if __name__ == "__main__":
    apply_phase()
    apply_x_manual_policy()
    apply_idempotence_fix()
