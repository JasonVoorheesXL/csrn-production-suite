from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from app import get_rehearsal_service

    result = get_rehearsal_service().readiness()
    readiness = result.data.get("readiness", {})
    print("CSRN GAME-DAY RELEASE READINESS")
    print(f"Ready: {'YES' if readiness.get('ready') else 'NO'}")
    print(
        "Completed rehearsals: "
        f"{readiness.get('completed_rehearsals', 0)}/"
        f"{readiness.get('required_rehearsals', 2)}"
    )

    print("\nSeries failure drills:")
    for drill in readiness.get("series_drills", []):
        status = "PASS" if drill.get("passed") else "MISSING"
        print(f"  [{status}] {drill.get('label', drill.get('key', ''))}")

    print("\nSystem gates:")
    for gate in readiness.get("system_gates", []):
        status = "PASS" if gate.get("ready") else "BLOCK"
        note = str(gate.get("note", "")).strip()
        print(f"  [{status}] {gate.get('label', gate.get('key', ''))}")
        if note:
            print(f"         {note}")

    blockers = readiness.get("open_blockers", [])
    print(f"\nOpen blocking defects: {len(blockers)}")
    for blocker in blockers:
        print(
            "  - "
            f"{blocker.get('rehearsal_id', '')}: "
            f"{blocker.get('description', '')}"
        )

    freeze = readiness.get("release_freeze", {})
    print(f"Release frozen: {'YES' if freeze.get('frozen') else 'NO'}")
    if freeze.get("frozen"):
        print(f"Commit: {freeze.get('commit', '')}")
        print(f"Snapshot: {freeze.get('snapshot_id', '')}")

    return 0 if readiness.get("ready") or freeze.get("frozen") else 1


if __name__ == "__main__":
    raise SystemExit(main())
