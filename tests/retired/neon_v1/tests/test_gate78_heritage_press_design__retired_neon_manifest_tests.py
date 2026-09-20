"""RETIRED (Neon redesign, 2026-09): the ten tests below were extracted verbatim from
tests/test_gate78_heritage_press_design.py. They pin the OLD standalone Neon manifest
(top-full 1840x250 lane, "Neon Sports Network"), which no longer exists. Not collected;
see tests/retired/neon_v1/README.md.
"""

from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def test_gate716_neon_sports_network_manifest_and_version() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert 'const VERSION = "1.7.0"' in source
    assert 'id:"digital_neon", name:"Neon Sports Network"' in source
    assert 'data-neon-package="sports-network"' in source


def test_gate716_r3_neon_avoids_obsolete_176px_manifest_override() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    assert "width:1140,height:176" not in neon
    assert 'id:"digital_neon", name:"Neon Sports Network"' in neon


def test_gate719_neon_owns_top_full_lane_and_future_placements() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert '"top-full": {x: 40, y: 30, w: 1840, h: 280}' in source
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    assert neon.count('scorebug:{zone:"top-full",width:1840,height:250') == 4
    assert neon.count('captions:{zone:"bottom-center",height:56') == 4
    assert 'scorebug:{zone:"bottom-center"' not in neon


def test_gate719_r2_supersedes_old_neon_placement_contract_cleanly() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    assert neon.count('scorebug:{zone:"top-full",width:1840,height:250') == 4
    assert 'scorebug:{zone:"bottom-center",layer:100}' not in neon
    assert 'scorebug:{zone:"top-right",layer:100}' not in neon


def test_gate721_captions_are_placed_immediately_above_ticker() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    assert neon.count('captions:{zone:"bottom-center",height:56,stackAboveHeight:64,layer:120}') == 4
    assert 'offsetY:-66' not in neon


def test_gate721_r4_scorebug_footprint_matches_five_zone_height() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    assert neon.count('scorebug:{zone:"top-full",width:1840,height:250,layer:100}') == 4
    assert 'scorebug:{zone:"top-full",width:1840,height:210,layer:100}' not in neon


def test_gate721_r8_manifest_uses_approved_270px_and_rejects_210px() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    assert neon.count('scorebug:{zone:"top-full",width:1840,height:250,layer:100}') == 4
    assert 'scorebug:{zone:"top-full",width:1840,height:210,layer:100}' not in neon


def test_gate721_r9_caption_spacing_uses_builtin_bottom_lane_gap() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    assert neon.count('captions:{zone:"bottom-center",height:56,stackAboveHeight:64,layer:120}') == 4
    assert 'offsetY:-66' not in neon


def test_gate1000_rebuilds_the_neon_package_at_the_approved_scorebug_proportion() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    section = css[css.index("/* Gate 10.0 — Approved Concept System Rebuild."):]
    assert 'data-neon-convergence="approved-v2"' in source
    assert source.count('scorebug:{zone:"top-full",width:1840,height:250,layer:100}') == 4
    assert '"top-full": {x: 40, y: 30, w: 1840, h: 280}' in source
    assert "grid-template-columns:210px 350px 190px 340px 190px 350px 210px" in section
    assert "height:270px;" in section
    assert "width:340px!important" in section


def test_gate1000_bottom_lane_uses_declared_ticker_geometry() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    neon = source[source.index("digital_neon:"):source.index("collegiate_traditional:")]
    section = css[css.index("/* Gate 10.0 — Approved Concept System Rebuild."):]
    assert "const configuredStackHeight = Number(rule.stackAboveHeight);" in source
    assert "Number.isFinite(configuredStackHeight) && configuredStackHeight > 0" in source
    assert neon.count('ticker:{zone:"bottom-center",height:64,layer:110}') == 4
    assert neon.count('captions:{zone:"bottom-center",height:56,stackAboveHeight:64,layer:120}') == 4
    assert '.bl-component.bl-captions[data-zone="bottom-center"]' in section
    assert "transform:none!important" in section
    assert "height:56px!important" in section
    assert "max-height:56px" in section
    assert ".bl-neon-native-captions" in section
    assert ".bl-component.bl-ticker" in section
    assert "max-height:64px" in section
