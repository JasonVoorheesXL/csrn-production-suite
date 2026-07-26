from __future__ import annotations

from typing import Any


def main(service: Any | None = None) -> int:
    if service is None:
        import app as app_module

        service = app_module.get_game_day_safety_service()

    result = service.ensure_startup_snapshot()
    preflight = result.data.get("preflight", {})
    for check in preflight.get("checks", []):
        status = "PASS" if check.get("ok") else (
            "WARN" if not check.get("required", True) else "FAIL"
        )
        print(f"[{status}] {check.get('label', check.get('key', 'Check'))}: {check.get('note', '')}")

    if result.code in {"PREFLIGHT_FAILED", "SNAPSHOT_FAILED"}:
        print(f"Game-day startup blocked: {result.code}")
        message = str(result.data.get("message", "")).strip()
        if message:
            print(message)
        return 1

    snapshot = result.data.get("snapshot", {})
    snapshot_id = str(snapshot.get("snapshot_id", ""))
    if result.code == "SNAPSHOT_CURRENT":
        print(f"Game-day safety snapshot is current: {snapshot_id}")
    else:
        print(f"Game-day safety snapshot created: {snapshot_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
