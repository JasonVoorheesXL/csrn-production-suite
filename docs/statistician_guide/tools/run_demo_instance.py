"""Run a throwaway CSRN Command Center for the statistician guide.

Source-mode checkout only. Every path the app could write outside this
worktree (state authority file, production template state, GameDay / core
backups, anything under %LOCALAPPDATA%) is redirected into a scratch runtime
folder, and the server binds its own port so it can never collide with the
live install (5050/5051). The isolated media server is not started.

The demo broadcast id is pinned to ``FB-DEMO-GUIDE-001`` so the seeded game
can never be confused with, or collide with, a real broadcast file.

Usage:  .venv/Scripts/python.exe docs/statistician_guide/tools/run_demo_instance.py <runtime_dir> [port]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEMO_BROADCAST_ID = "FB-DEMO-GUIDE-001"


def main() -> None:
    runtime = Path(sys.argv[1]).resolve()
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5072
    if port in (5050, 5051):
        raise SystemExit("Refusing to bind a live-install port.")
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "localappdata").mkdir(exist_ok=True)
    os.environ.update(
        {
            "LOCALAPPDATA": str(runtime / "localappdata"),
            "CSRN_GAME_DAY_LOCAL_STATE": "1",
            "CSRN_STATE_AUTHORITY_FILE": str(runtime / "authority-state.json"),
            "CSRN_PRODUCTION_TEMPLATE_STATE_PATH": str(runtime / "template.json"),
            "CSRN_GAME_DAY_BACKUP_ROOT": str(runtime / "gameday-backups"),
            "CSRN_CORE_BACKUP_ROOT": str(runtime / "core-backups"),
        }
    )
    for key in ("CSRN_RUNTIME_ROOT", "CSRN_DATA_ROOT", "CSRN_INSTALLED"):
        os.environ.pop(key, None)

    repo = Path(__file__).resolve().parents[3]
    os.chdir(repo)
    sys.path.insert(0, str(repo))

    import broadcast_service

    broadcast_service.BroadcastService.next_id = (
        lambda self, *args, **kwargs: DEMO_BROADCAST_ID
    )

    import app

    app.ensure_data_architecture()
    app.load_config()
    print(f"Demo instance on http://127.0.0.1:{port}  runtime={runtime}", flush=True)
    app.app.run(host="127.0.0.1", port=port, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
