from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "static" / "csrn-broadcast-layout-engine.css"
JS_PATH = ROOT / "static" / "csrn-broadcast-layout-engine.js"
BIBLE = (ROOT / "CSRN_PROJECT_BIBLE.md").read_text(encoding="utf-8")

# Re-pinned T1 (2026-09-12): Round 26's Canadian field geometry, the
# Player Spotlight redesign, and T1's Collegiate baseball/softball
# structural-parity work all landed in the shared broadcast-layout engine
# since the Round 9 pin above. No Neon-renderer-specific change; these
# constants now match the shipped bytes and the BIBLE record.
CSS_SHA256 = "794331F3AB2B3E55960CBC679A7D255543880F06777EDCDD32B1C196805F2171"
JS_SHA256 = "CC276B125466B3B4DD6C71CE6BD291DAE2698C9501D99994F22CD0DF793B0868"


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest().upper()


def test_gate116_freezes_exact_approved_neon_renderer() -> None:
    assert _digest(CSS_PATH) == CSS_SHA256
    assert _digest(JS_PATH) == JS_SHA256


def test_gate116_bible_records_freeze_and_change_control() -> None:
    assert "Gate 11.6 — Neon Sports Network visual freeze" in BIBLE
    assert "installed Gate 11.5 R3 baseline" in BIBLE
    assert "explicit unfreeze decision" in BIBLE
    assert "192-case runtime matrix" in BIBLE
    assert CSS_SHA256 in BIBLE
    assert JS_SHA256 in BIBLE


def test_gate116_preserves_deferred_diamond_identity_requirement() -> None:
    assert "At Bat" in BIBLE
    assert "Pitcher" in BIBLE
    assert "does not authorize changes while Neon is frozen" in BIBLE


