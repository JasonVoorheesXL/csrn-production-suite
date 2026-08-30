"""Round 7 Task C: the internal-only surfaces manifest is valid and its
referenced files / routes actually exist. Documentation only -- this test
just keeps the manifest from rotting silently.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "internal_only_surfaces.json"


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_is_valid_json_with_expected_shape() -> None:
    m = _manifest()
    assert m["schema"] == "csrn-internal-only-surfaces-v1"
    assert isinstance(m["entry_points"], list) and m["entry_points"]
    assert isinstance(m["route_blueprints"], list) and m["route_blueprints"]


def test_every_referenced_file_exists() -> None:
    m = _manifest()
    for ep in m["entry_points"]:
        assert (ROOT / ep["path"]).is_file(), ep["path"]
    for bp in m["route_blueprints"]:
        assert (ROOT / bp["module"]).is_file(), bp["module"]


def test_listed_internal_routes_are_actually_declared_in_their_module() -> None:
    m = _manifest()
    for bp in m["route_blueprints"]:
        src = (ROOT / bp["module"]).read_text(encoding="utf-8")
        for route in bp.get("internal_routes", []):
            assert route["path"] in src, f'{bp["module"]}: {route["path"]}'


def test_run_core_foundation_is_the_debug_entry_point() -> None:
    src = (ROOT / "run_core_foundation.py").read_text(encoding="utf-8")
    assert "CSRN_DEBUG" in src
    assert ".run(" in src  # application.run(...), i.e. the Flask dev server
