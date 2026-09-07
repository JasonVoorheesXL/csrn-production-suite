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
CSS_SHA256 = "C170F0B6039C75A10FE6DB0EA847990064608D4A591F8021B4A61ED0A74F734A"
JS_SHA256 = "81D127814510042D4360BC30189D8F0D8A513D699287AA5F93490326EE6FEEF5"


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


