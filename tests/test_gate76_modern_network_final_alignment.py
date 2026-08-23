from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gate76_engine_and_asset_versions_advance_together() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
    assert 'const VERSION = "1.7.0"' in source
    assert lab.count("csrn-broadcast-layout-engine.js?v=11") == 1
    assert lab.count("csrn-broadcast-layout-engine.css?v=11") == 1


def test_modern_baseball_role_columns_are_left_aligned_and_fixed() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "grid-template-columns:104px 74px minmax(260px,1fr) 280px" in css
    assert ".bl-modern-baseball .bl-modern-baseball-role .bl-baseball-context" in css
    assert "text-align:left" in css
    assert "justify-content:flex-start" in css


def test_modern_baseball_run_labels_use_role_accent_and_separation() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert ".bl-modern-baseball .bl-run-label" in css
    assert "color:#ffd85a" in css
    assert "transform:translateY(-3px)" in css


def test_modern_baseball_state_module_retains_full_height_right_edge() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert ".bl-modern-baseball .bl-baseball-state" in css
    assert "border-top-right-radius:14px" in css
    assert "border-bottom-right-radius:14px" in css


def test_modern_football_logos_are_round_clipped_with_thin_white_border() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert ".bl-modern.bl-sport-football .bl-logo" in css
    assert "border:1px solid rgba(255,255,255,.95)" in css
    assert "border-radius:50%" in css
    assert "overflow:hidden" in css
    assert ".bl-modern.bl-sport-football .bl-logo img" in css
    assert "object-fit:contain" in css


