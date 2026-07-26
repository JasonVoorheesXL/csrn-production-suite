from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def render_report(report: dict[str, Any]) -> None:
    for item in report.get("checks", []):
        status = "PASS" if item.get("passed") else (
            "WARN" if not item.get("required", True) else "FAIL"
        )
        requirement = "required" if item.get("required", True) else "recommended"
        print(f"[{status}] {item.get('label', item.get('key', 'Check'))} ({requirement})")
        note = str(item.get("note", "")).strip()
        if note:
            print(f"       {note}")
    print()
    print(
        "Required checks: "
        f"{report.get('passed_required', 0)}/{report.get('required_total', 0)}"
    )
    print("Commissioning ready." if report.get("ready") else "Commissioning incomplete.")


def main(argv: list[str] | None = None, service: Any | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the CSRN P4next and OBS commissioning report."
    )
    parser.add_argument(
        "--obs-test",
        action="store_true",
        help="Refresh the read-only OBS contract check before reporting.",
    )
    args = parser.parse_args(argv)

    if service is None:
        from app import get_commissioning_service

        service = get_commissioning_service()

    if args.obs_test:
        obs_result = service.run_obs_check()
        check = obs_result.data.get("obs_check", {})
        print(
            "OBS contract check: "
            + ("ready" if check.get("ready") else "incomplete")
        )
        error = str(check.get("observed", {}).get("error", "")).strip()
        if error:
            print(f"OBS detail: {error}")
        print()

    result = service.report()
    render_report(result.data.get("report", {}))
    return 0 if result.code == "COMMISSIONING_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
