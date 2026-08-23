from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = (ROOT / "static/csrn-layout-lab.html").read_text(encoding="utf-8")
BIBLE = (ROOT / "CSRN_PROJECT_BIBLE.md").read_text(encoding="utf-8")
HANDOFF = (ROOT / "CSRN_THEME_CONTINUITY_HANDOFF.md").read_text(encoding="utf-8")


FROZEN = {
    "static/csrn-eight-bit-gameday-engine.js": "3830863DEE0B7424666096BD14D12B813D88BE6491394A85EE06162AAAC81206",
    "static/csrn-eight-bit-gameday-engine.css": "6CFA49C22E2F9DE74E97E4BBA8FB9FE09E1F10F4AE64242066FBC9A728643BC4",
    "static/8bit-gameday/athletes/football-athletes.png": "97213E78E4E19349A57969C3B0BA0C213AFA443D155CEE768918CCEEAE1CA53A",
    "static/8bit-gameday/athletes/basketball-athletes.png": "44C4CA5601AD3FB1A0BB9185861DC6FA3EE9B02048979AE8F4AE7F3D5644F57B",
    "static/8bit-gameday/athletes/baseball-athletes.png": "932AEEFF1E4D17D11318DF7FE1BE2901A2927E0D260A2764091F4D56B571026C",
    "static/8bit-gameday/athletes/softball-athletes.png": "868700C27899492234A8BE0CF09C9FC1BF8744C29A7EE4341AEB0C0D2124D658",
    "static/8bit-gameday/environments/football-stadium.png": "73E2D3C8FA4C6116673D8D1D86E4A74E37B1769F761B1A301F195390D2524FBE",
    "static/8bit-gameday/environments/basketball-gym.png": "16ECCA9574D8A7987959756DA43447AC3EF70889A91071BD5377FA192A76EE40",
    "static/8bit-gameday/environments/baseball-ballpark.png": "35C5CAEDF418B083E4C50C4E17CE27608EA883B4F245B7C5773DE49790CC7674",
    "static/8bit-gameday/environments/softball-park.png": "8339250948C155B1ADFF764F40F0F0C10AB59BA169868ABDA3C1606832602C9F",
    "static/8bit-gameday/frame/cabinet-frame.png": "965273611CD458566F5F42D25583E289BB621995FBFA365052023A5038174981",
}


def _digest(relative: str) -> str:
    return sha256((ROOT / relative).read_bytes()).hexdigest().upper()


def test_gate138_freezes_every_approved_eight_bit_visual_file() -> None:
    assert len(FROZEN) == 11
    for relative, expected in FROZEN.items():
        assert (ROOT / relative).is_file(), relative
        assert _digest(relative) == expected, relative


def test_gate138_locks_the_layout_lab_route_and_isolated_renderer() -> None:
    assert LAB.count('csrn-eight-bit-gameday-engine.css?v=13.7') == 1
    assert LAB.count('csrn-eight-bit-gameday-engine.js?v=13.7') == 1
    assert "packageId===pixelEngine.packageId?pixelEngine:" in LAB
    assert 'packageSelect.value="pixel_gameday"' in LAB


def test_gate138_records_the_freeze_and_next_theme_sequence() -> None:
    assert "Gate 13.8 — 8-Bit Gameday visual freeze" in BIBLE
    assert "8-Bit Gameday — COMPLETE AND FROZEN" in HANDOFF
    assert "Friday Night Stadium — COMPLETE AND FROZEN" in HANDOFF
    for theme in ("Heritage Press", "Neon Sports Network", "Collegiate", "Classic", "Modern", "Minimal"):
        assert theme in HANDOFF
    assert "production overlay and OBS remain on Gate 6" in HANDOFF



