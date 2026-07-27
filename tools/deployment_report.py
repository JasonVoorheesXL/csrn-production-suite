from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect CSRN deployment and licensing status.")
    parser.add_argument("--support-bundle", action="store_true")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    import app

    if args.support_bundle:
        result = app.get_deployment_service().create_support_bundle(note=args.note)
    else:
        result = app.get_deployment_service().status()
    print(json.dumps({"status": result.code, **result.data}, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
