"""OBS setup (2026-10-31): the ready-made scene collection a new station imports
holds exactly the scenes and sources Settings > OBS names by default, uses only
stock OBS sources, and carries nothing from any one station's computer.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "static" / "obs" / "production-suite-scene-collection.json"
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")


def _collection() -> dict:
    return json.loads(COLLECTION.read_text(encoding="utf-8"))


def _by_name() -> dict:
    return {source["name"]: source for source in _collection()["sources"]}


def test_names_match_what_the_app_checks_by_default() -> None:
    import app as app_module

    obs = app_module.DEFAULT_CONFIG["obs"]
    sources = _by_name()
    scorebug = [item["name"] for item in sources[obs["required_scene"]]["settings"]["items"]]
    assert obs["browser_source"] in scorebug
    visual = [item["name"] for item in sources[obs["program_visual_scene"]]["settings"]["items"]]
    assert obs["graphic_source"] in visual and obs["camera_source"] in visual
    assert sources[obs["browser_source"]]["id"] == "browser_source"


def test_browser_sources_point_at_the_app_at_1080p() -> None:
    sources = _by_name()
    assert sources["BRWSR - Football Scorebug"]["settings"]["url"] == "http://127.0.0.1:5050/overlay"
    assert sources["BRWSR - Pregame Delay"]["settings"]["url"] == "http://127.0.0.1:5050/pregame-overlay"
    for name in ("BRWSR - Football Scorebug", "BRWSR - Pregame Delay"):
        assert (sources[name]["settings"]["width"], sources[name]["settings"]["height"]) == (1920, 1080)


def test_only_stock_sources_and_nothing_station_specific() -> None:
    kinds = {source["id"] for source in _collection()["sources"]}
    assert kinds <= {"scene", "browser_source", "image_source", "dshow_input"}
    text = COLLECTION.read_text(encoding="utf-8")
    for word in ("CSRN", "Caledonia", "Users", "C:\\\\", "droidcam", "atkaudio", "vlc"):
        assert word.lower() not in text.lower(), word
    collection = _collection()
    assert collection["name"] == "Production Suite"
    assert collection["current_program_scene"] == "30.01 - LIVE FOOTBALL"
    uuids = {source["uuid"] for source in collection["sources"]}
    assert all(item["source_uuid"] in uuids for s in collection["sources"] for item in s["settings"].get("items", []))


def test_the_shipped_file_is_what_the_builder_makes() -> None:
    spec = importlib.util.spec_from_file_location(
        "build_scene_collection", ROOT / "docs" / "obs_setup_guide" / "tools" / "build_scene_collection.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    assert _collection() == builder.collection()


def test_obs_manager_and_settings_offer_the_download_and_guide() -> None:
    link = 'href="/static/obs/production-suite-scene-collection.json" download="Production Suite.json"'
    assert HTML.count(link) == 2
    assert HTML.count("openPdfInApp('/static/guides/obs-setup-guide.pdf','OBS Setup Guide')") == 2
    assert (ROOT / "static" / "guides" / "obs-setup-guide.pdf").is_file()
