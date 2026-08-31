"""CSRN-INTERNAL debug entry point -- do NOT include in a commercial build.

This is a second Flask entry point that runs `application.run(..., debug=...)`
(the Werkzeug dev server). The real game-day launcher is `app.py` ->
`waitress.serve`. A packaged build must ship only the waitress path; this file
is catalogued in docs/internal_only_surfaces.json and, unlike the internal
HTTP routes, cannot be gated at runtime -- it must simply be excluded from the
bundle. See app.py:internal_tools_enabled().
"""

from __future__ import annotations

import logging
import os

import app as csrn_app
from core_repository_runtime import install_core_repository_runtime


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

runtime = install_core_repository_runtime(csrn_app)
application = csrn_app.app


if __name__ == "__main__":
    host = os.environ.get("CSRN_HOST", "0.0.0.0")
    port = int(os.environ.get("CSRN_PORT", "5050"))
    debug = os.environ.get("CSRN_DEBUG", "0") == "1"
    application.run(host=host, port=port, debug=debug, threaded=True)
