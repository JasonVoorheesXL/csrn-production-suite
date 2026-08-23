from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_gate143_does_not_hash_freeze_the_complete_shared_catalog() -> None:
    source = (ROOT / "tests" / "test_gate142_heritage_press_visual_freeze.py").read_text(encoding="utf-8")
    assert "'static/csrn-layout-lab.html':" not in source
    assert "shared_layout_lab_preserves_heritage_registration_semantically" in source


def test_gate143_shared_catalog_preserves_heritage_and_one_active_neon_renderer() -> None:
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")

    assert lab.count("csrn-heritage-press-engine.css?v=14.1") == 1
    assert lab.count("csrn-heritage-press-engine.js?v=14.1") == 1
    assert "const heritageEngine=window.CSRNHeritagePressEngine;" in lab
    assert "packageId===heritageEngine.packageId?heritageEngine:" in lab
    assert "...heritageEngine.validateManifests()" in lab
    assert "heritageEngine.manifests[heritageEngine.packageId]" in lab

    neon_css = re.findall(r"csrn-neon-r\d+-engine\.css\?v=[^\"']+", lab)
    neon_js = re.findall(r"csrn-neon-r\d+-engine\.js\?v=[^\"']+", lab)
    assert len(neon_css) == 1, neon_css
    assert len(neon_js) == 1, neon_js

    engine_defs = re.findall(r"const (neonR\d+Engine)=window\.CSRNNeonR\d+Engine;", lab)
    assert len(engine_defs) == 1, engine_defs
    neon_engine = engine_defs[0]

    assert f"if(!{neon_engine})throw new Error(" in lab
    assert f"packageId==={neon_engine}.packageId?{neon_engine}:" in lab
    assert f"...{neon_engine}.validateManifests()" in lab
    assert f"item.id==={neon_engine}.packageId?{neon_engine}.manifests[{neon_engine}.packageId]:" in lab


