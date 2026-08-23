from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
BIBLE = (ROOT / "CSRN_PROJECT_BIBLE.md").read_text(encoding="utf-8")


def test_gate115_removes_every_command_core_boundary_effect() -> None:
    marker = "/* Gate 11.5 — Final phantom-glow removal before Neon freeze. */"
    assert marker in CSS
    closeout = CSS.split(marker, 1)[1]
    for selector in (
        ".bl-neon-command-core,",
        ".bl-neon-command-core::before,",
        ".bl-neon-command-core::after,",
        ".bl-neon-command-core>.bl-neon-core-shell,",
        ".bl-neon-command-core>.bl-neon-state,",
        ".bl-neon-command-core>.bl-game-state,",
        ".bl-neon-command-core>.bl-baseball-state",
    ):
        assert selector in closeout
    assert "border:0!important" in closeout
    assert "border-color:transparent!important" in closeout
    assert "outline:none!important" in closeout
    assert "box-shadow:none!important" in closeout
    assert "filter:none!important" in closeout


def test_gate115_preserves_internal_information_illumination() -> None:
    assert ".package-neon-approved .bl-sport-football .bl-clock" in CSS
    assert ".bl-inning{" in CSS
    assert ".bl-count{" in CSS
    assert ".bl-possession{" in CSS


def test_gate115_is_recorded_as_final_pre_freeze_baseline() -> None:
    assert "Gate 11.5 — Final phantom-glow removal" in BIBLE
    assert "final pre-freeze Neon visual baseline" in BIBLE
    assert "22-pixel cyan box shadow" in BIBLE
    assert "At Bat" in BIBLE
    assert "Pitcher" in BIBLE


