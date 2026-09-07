from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "static" / "csrn-broadcast-layout-engine.css"
JS_PATH = ROOT / "static" / "csrn-broadcast-layout-engine.js"
BIBLE = (ROOT / "CSRN_PROJECT_BIBLE.md").read_text(encoding="utf-8")

# Re-pinned Round 9 (2026-08-31): the Neon renderer files were intentionally
# evolved after the Gate 11.6 freeze (Neon disabled as a selectable option in
# Round 6; shared broadcast-layout engine rebuilt for the "Collegiate Tech"
# series). No renderer change in Round 9 -- these constants now match the
# shipped bytes and the BIBLE record.
CSS_SHA256 = "087BC0B9768A2E4A94D74A44904EF1E153E37D6E5FB7CD42CBD377C53208EB97"
JS_SHA256 = "1798F224878CB25CA4D2F304B4F33D8CF4838AC926AC84C67A4006C4D6A46914"


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


