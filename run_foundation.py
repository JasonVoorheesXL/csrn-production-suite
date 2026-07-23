from __future__ import annotations

import logging
import os

import app as csrn_app
from foundation_runtime import install_foundation_runtime


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Preserve existing domain-specific loaders and savers. They retain their current
# list/dict compatibility behavior while resolving the hardened global load_json
# and save_json functions at runtime. Roster and package persistence are replaced
# explicitly because roster deletion needs domain-aware handling and packages
# previously bypassed save_json with a direct write_text call.
_preserved_names = (
    "load_schools", "save_schools",
    "load_broadcasters", "save_broadcasters",
    "load_sponsors", "save_sponsors",
    "load_assets", "save_assets",
    "load_venues", "save_venues",
    "load_logos", "save_logos",
    "load_broadcasts", "save_broadcasts",
    "load_build_journal", "save_build_journal",
)
_preserved = {
    name: getattr(csrn_app, name)
    for name in _preserved_names
    if hasattr(csrn_app, name)
}

runtime = install_foundation_runtime(csrn_app)

for _name, _function in _preserved.items():
    setattr(csrn_app, _name, _function)

application = csrn_app.app


if __name__ == "__main__":
    host = os.environ.get("CSRN_HOST", "0.0.0.0")
    port = int(os.environ.get("CSRN_PORT", "5050"))
    debug = os.environ.get("CSRN_DEBUG", "0") == "1"
    application.run(host=host, port=port, debug=debug, threaded=True)
