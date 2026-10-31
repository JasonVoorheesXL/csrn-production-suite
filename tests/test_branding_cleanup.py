"""Branding cleanup (2026-10-31): a new station sees no CSRN station text or
art. CSRN stays only as the vendor (license messages, (c) footer) and inside
retired tools.
"""
from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
# sha1 of the headset art that had the CSRN badge on its earcup.
BADGED_HEADSET_SHA1 = "84fd6e2e75416d61e73e4659398ac3a22181f477"


def test_new_installs_accept_any_obs_profile_and_scene_collection() -> None:
    import app as app_module

    obs = app_module.DEFAULT_CONFIG["obs"]
    assert obs["profile"] == "" and obs["scene_collection"] == ""
    # The functional scene and source names stay.
    assert obs["required_scene"] == "10.01 - FOOTBALL SCOREBUG"
    source = (ROOT / "broadcast_service.py").read_text(encoding="utf-8")
    assert "CSRN Production" not in source


def test_pregame_headset_art_no_longer_carries_the_badge() -> None:
    html = (TEMPLATES / "pregame_universal_overlay.html").read_text(encoding="utf-8")
    payload = re.search(r'id="broadcastHeadsetImage"[^>]*src="data:image/png;base64,([^"]+)"', html).group(1)
    assert hashlib.sha1(base64.b64decode(payload)).hexdigest() != BADGED_HEADSET_SHA1


def test_station_facing_text_does_not_say_csrn() -> None:
    index = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    for gone in ("CSRN School ID", "Matches CSRN", "Current CSRN", "DragonFly differs from CSRN",
                 "CSRN never ingests video", "CSRN automatically links", "CSRN discovers"):
        assert gone not in index, gone
    social = (TEMPLATES / "social_manager.html").read_text(encoding="utf-8")
    assert "CSRN" not in re.sub(r"csrn-[\w.-]+|CSRN[A-Z_]\w*", "", social)
    pregame = (TEMPLATES / "pregame_universal_overlay.html").read_text(encoding="utf-8")
    assert "CSRN resolved the venue area" not in pregame
