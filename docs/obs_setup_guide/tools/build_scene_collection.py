"""Build the OBS scene collection a new station imports (2026-10-31).

Writes static/obs/production-suite-scene-collection.json: the scenes and
sources the app expects (the names in Settings > OBS), using only sources that
ship with OBS itself, with nothing from any one station's computer in it (no
file paths, devices, audio plugins or stream settings).

Modelled on a working 1920x1080 collection; uuids are fixed (uuid5) so a
rebuild produces the same file.

  10.01 - FOOTBALL SCOREBUG   BRWSR - Football Scorebug  (/overlay)
                              BRWSR - Pregame Delay      (/pregame-overlay)
  10.02 - PROGRAM VISUAL      IMG - Broadcast Background (pick an image)
                              CAM - Primary Camera       (pick a camera; hidden)
  30.01 - LIVE FOOTBALL       10.02 then 10.01 nested: the scene you go live from
  00/10/20/30/40              empty dividers that keep the list in order

Usage:  .venv/Scripts/python.exe docs/obs_setup_guide/tools/build_scene_collection.py
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "static" / "obs" / "production-suite-scene-collection.json"
COLLECTION_NAME = "Production Suite"
APP = "http://127.0.0.1:5050"
WIDTH, HEIGHT = 1920, 1080
PREV_VER = 537001986  # OBS 32.0.x, as written by OBS itself
MAIN_CANVAS = "6c69626f-6273-4c00-9d88-c5136d61696e"  # libobs' fixed main-canvas id
_NAMESPACE = uuid.UUID("0b5b1f6e-5c1e-4a7e-9a8e-50726f645375")


def _uuid(name: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, name))


def source(name: str, kind: str, settings: dict, *, mixers: int, hotkeys: dict) -> dict:
    return {
        "prev_ver": PREV_VER,
        "name": name,
        "uuid": _uuid(name),
        "id": kind,
        "versioned_id": kind,
        "settings": settings,
        "mixers": mixers,
        "sync": 0,
        "flags": 0,
        "volume": 1.0,
        "balance": 0.5,
        "enabled": True,
        "muted": False,
        "push-to-mute": False,
        "push-to-mute-delay": 0,
        "push-to-talk": False,
        "push-to-talk-delay": 0,
        "hotkeys": hotkeys,
        "deinterlace_mode": 0,
        "deinterlace_field_order": 0,
        "monitoring_type": 0,
        "private_settings": {},
    }


AUDIO_HOTKEYS = {"libobs.mute": [], "libobs.unmute": [], "libobs.push-to-mute": [], "libobs.push-to-talk": []}


def browser(name: str, path: str) -> dict:
    return source(
        name,
        "browser_source",
        {"url": APP + path, "width": WIDTH, "height": HEIGHT, "reroute_audio": True},
        mixers=255,
        hotkeys={**AUDIO_HOTKEYS, "ObsBrowser.Refresh": []},
    )


def item(name: str, index: int, *, visible: bool = True, fill: bool = False) -> dict:
    """A scene item at the canvas origin; fill=True stretches it to the canvas."""
    return {
        "name": name,
        "source_uuid": _uuid(name),
        "visible": visible,
        "locked": False,
        "rot": 0.0,
        "scale_ref": {"x": float(WIDTH), "y": float(HEIGHT)},
        "align": 5,
        "bounds_type": 2 if fill else 0,
        "bounds_align": 0,
        "bounds_crop": False,
        "crop_left": 0,
        "crop_top": 0,
        "crop_right": 0,
        "crop_bottom": 0,
        "id": index,
        "group_item_backup": False,
        "pos": {"x": 0.0, "y": 0.0},
        "pos_rel": {"x": -1.7777777910232544, "y": -1.0},
        "scale": {"x": 1.0, "y": 1.0},
        "scale_rel": {"x": 1.0, "y": 1.0},
        "bounds": {"x": float(WIDTH), "y": float(HEIGHT)} if fill else {"x": 0.0, "y": 0.0},
        "bounds_rel": {"x": 3.555555582046509, "y": 2.0} if fill else {"x": 0.0, "y": 0.0},
        "scale_filter": "disable",
        "blend_method": "default",
        "blend_type": "normal",
        "show_transition": {"duration": 300},
        "hide_transition": {"duration": 300},
        "private_settings": {},
    }


def scene(name: str, items: list[dict]) -> dict:
    hotkeys = {"OBSBasic.SelectScene": []}
    for entry in items:
        hotkeys[f"libobs.show_scene_item.{entry['id']}"] = []
        hotkeys[f"libobs.hide_scene_item.{entry['id']}"] = []
    built = source(
        name,
        "scene",
        {"id_counter": len(items), "custom_size": False, "items": items},
        mixers=0,
        hotkeys=hotkeys,
    )
    built["canvas_uuid"] = MAIN_CANVAS
    return built


def collection() -> dict:
    sources = [
        browser("BRWSR - Football Scorebug", "/overlay"),
        browser("BRWSR - Pregame Delay", "/pregame-overlay"),
        source("IMG - Broadcast Background", "image_source", {}, mixers=0, hotkeys={}),
        source("CAM - Primary Camera", "dshow_input", {}, mixers=255, hotkeys=dict(AUDIO_HOTKEYS)),
        scene("00 - SYSTEM", []),
        scene("10 - CORE", []),
        # Bottom to top: the scoreboard, then the pregame/halftime/delay screens over it.
        scene("10.01 - FOOTBALL SCOREBUG", [
            item("BRWSR - Football Scorebug", 1),
            item("BRWSR - Pregame Delay", 2),
        ]),
        # The app switches between these two (Settings > OBS: graphic / camera source).
        scene("10.02 - PROGRAM VISUAL", [
            item("IMG - Broadcast Background", 1, fill=True),
            item("CAM - Primary Camera", 2, visible=False, fill=True),
        ]),
        scene("20 - GRAPHICS", []),
        scene("30 - BROADCAST", []),
        scene("30.01 - LIVE FOOTBALL", [
            item("10.02 - PROGRAM VISUAL", 1),
            item("10.01 - FOOTBALL SCOREBUG", 2),
        ]),
        scene("40 - UTILITIES", []),
    ]
    order = ["00 - SYSTEM", "10 - CORE", "10.01 - FOOTBALL SCOREBUG", "10.02 - PROGRAM VISUAL",
             "20 - GRAPHICS", "30 - BROADCAST", "30.01 - LIVE FOOTBALL", "40 - UTILITIES"]
    return {
        "name": COLLECTION_NAME,
        "sources": sources,
        "groups": [],
        "scene_order": [{"name": name} for name in order],
        "current_scene": "30.01 - LIVE FOOTBALL",
        "current_program_scene": "30.01 - LIVE FOOTBALL",
        "canvases": [],
        "current_transition": "Fade",
        "transition_duration": 300,
        "transitions": [],
        "quick_transitions": [
            {"name": "Cut", "duration": 300, "hotkeys": [], "id": 1, "fade_to_black": False},
            {"name": "Fade", "duration": 300, "hotkeys": [], "id": 2, "fade_to_black": False},
            {"name": "Fade", "duration": 300, "hotkeys": [], "id": 3, "fade_to_black": True},
        ],
        "saved_projectors": [],
        "preview_locked": False,
        "scaling_enabled": False,
        "scaling_level": 0,
        "scaling_off_x": 0.0,
        "scaling_off_y": 0.0,
        "modules": {},
        "resolution": {"x": WIDTH, "y": HEIGHT},
        "version": 2,
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(collection(), indent=4) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
