from __future__ import annotations

import logging
import os

import app as csrn_app
from foundation_runtime import install_foundation_runtime


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

runtime = install_foundation_runtime(csrn_app)
application = csrn_app.app


if __name__ == "__main__":
    host = os.environ.get("CSRN_HOST", "0.0.0.0")
    port = int(os.environ.get("CSRN_PORT", "5050"))
    debug = os.environ.get("CSRN_DEBUG", "0") == "1"
    application.run(host=host, port=port, debug=debug, threaded=True)
