from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_gate150_neon_r1_fallback_files_remain_available() -> None:
    required = [
        "static/csrn-neon-r1-engine.css",
        "static/csrn-neon-r1-engine.js",
        "static/neon-r1/neon-r1-frame.svg",
        "static/neon-r1/neon-r1-football-clash.png",
        "static/neon-r1/neon-r1-basketball-clash.png",
        "static/neon-r1/neon-r1-baseball-clash.png",
        "static/neon-r1/neon-r1-softball-clash.png",
    ]
    for relative in required:
        assert (ROOT / relative).is_file(), relative


def test_gate150_shared_layout_has_exactly_one_active_neon_revision() -> None:
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")

    css_routes = re.findall(r"csrn-neon-r\d+-engine\.css\?v=[^\"']+", lab)
    js_routes = re.findall(r"csrn-neon-r\d+-engine\.js\?v=[^\"']+", lab)
    assert len(css_routes) == 1, css_routes
    assert len(js_routes) == 1, js_routes

    engine_defs = re.findall(r"const (neonR\d+Engine)=window\.CSRNNeonR\d+Engine;", lab)
    assert len(engine_defs) == 1, engine_defs
    neon_engine = engine_defs[0]

    assert f"if(!{neon_engine})throw new Error(" in lab
    assert f"packageId==={neon_engine}.packageId?{neon_engine}:" in lab
    assert f"...{neon_engine}.validateManifests()" in lab
    assert f"item.id==={neon_engine}.packageId?{neon_engine}.manifests[{neon_engine}.packageId]:" in lab


def test_gate150_neon_r2_can_replace_r1_without_deleting_fallback() -> None:
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
    if "csrn-neon-r2-engine.css?v=15.1-r2" in lab:
        assert "csrn-neon-r2-engine.js?v=15.1-r2" in lab
        assert "const neonR2Engine=window.CSRNNeonR2Engine;" in lab
        assert "csrn-neon-r1-engine.css?v=15.0-r1" not in lab
        assert "csrn-neon-r1-engine.js?v=15.0-r1" not in lab


