from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FROZEN = {
    # engine .js/.css re-pinned Round 9 (2026-08-31): rebuilt for the
    # "Collegiate Tech" series and commit 9064c67 ("Friday Night Stadium
    # test broadcast readiness"). The 9 artwork hashes below are unchanged.
    "static/csrn-friday-night-stadium-engine.js": "E2B3872D6D70A47FB733794CA02A46ADC4C3D9BAABBE192E6A17B96748926CBB",
    "static/csrn-friday-night-stadium-engine.css": "766686DAB90AABC40021919E65C01318FD426E86CB3E95A9B33CB72643E689AF",
    "static/friday-night-stadium/vs-lightning-silver.png": "2DF458CF70F4F891EA0FFEA84DD8DBA3DA74A9A2CBEEA7362BBA35FC382145D8",
    "static/friday-night-stadium/clash/football-athletes-keyed.png": "6355AA7C83095A9557134A0D413E65CE32354204C24EE1BA1D9E756D0092BBA9",
    "static/friday-night-stadium/clash/basketball-athletes-keyed.png": "0AA5470DF71548B1DB362B2899DBB4C8DDEA0F702E7AF7D03B9741A285D0FDA6",
    "static/friday-night-stadium/clash/baseball-athletes-keyed.png": "E287BAE9C37DED1C8D4B1F74C82619AAE4D55C6ADDC23C6057F536C67F8C9D67",
    "static/friday-night-stadium/clash/softball-athletes-keyed.png": "5A750FF5E5693491B1B41A0B5938D0068019810D99A04230E606A6954D996883",
    "static/friday-night-stadium/clash/football-field-background.png": "9AC56A8DE328C0C3CB210D7BC5BFA33D01F8DCB063726DE2C1AA3B4074D5B873",
    "static/friday-night-stadium/clash/basketball-court-background.png": "92490EE1AB3F6608802C6C89869E4135BC98701504EC9A3BDDBF58B2C12F5E8E",
    "static/friday-night-stadium/clash/baseball-ballpark-background.png": "447A85BC4AAD300A76621E99CD1F0E0E635BCD46325E1B2F18D644AADB27B2EB",
    "static/friday-night-stadium/clash/softball-ballpark-background.png": "7FEF1C3503A290F41AEB190916AD8B0FF6A293B774BA42CADF097470D36FD3C1",
}


def _digest(relative: str) -> str:
    return sha256((ROOT / relative).read_bytes()).hexdigest().upper()


def test_gate126_friday_night_stadium_renderer_and_art_are_frozen() -> None:
    assert len(FROZEN) == 11
    for relative, expected in FROZEN.items():
        assert (ROOT / relative).is_file(), relative
        assert _digest(relative) == expected, relative


def test_gate126_layout_lab_keeps_the_approved_frozen_route() -> None:
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
    assert lab.count('csrn-friday-night-stadium-engine.css?v=12.6') == 1
    assert lab.count('csrn-friday-night-stadium-engine.js?v=12.6') == 1
    assert 'packageId===stadiumEngine.packageId?stadiumEngine:engine' in lab


def test_gate126_bible_declares_the_visual_freeze_boundary() -> None:
    bible = (ROOT / "CSRN_PROJECT_BIBLE.md").read_text(encoding="utf-8")
    assert "Gate 12.6 — Friday Night Stadium visual freeze contract" in bible
    assert "eleven frozen renderer and artwork files" in bible
    assert "explicit user-authorized unfreeze gate" in bible


