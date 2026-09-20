from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_gate143_does_not_hash_freeze_the_complete_shared_catalog() -> None:
    source = (ROOT / "tests" / "test_gate142_heritage_press_visual_freeze.py").read_text(encoding="utf-8")
    assert "'static/csrn-layout-lab.html':" not in source
    assert "shared_layout_lab_preserves_heritage_registration_semantically" in source


def test_gate143_shared_catalog_preserves_heritage_and_has_no_standalone_neon_renderer() -> None:
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")

    assert lab.count("csrn-heritage-press-engine.css?v=14.1") == 1
    assert lab.count("csrn-heritage-press-engine.js?v=14.1") == 1
    assert "const heritageEngine=window.CSRNHeritagePressEngine;" in lab
    assert "packageId===heritageEngine.packageId?heritageEngine:" in lab
    assert "...heritageEngine.validateManifests()" in lab
    assert "heritageEngine.manifests[heritageEngine.packageId]" in lab

    # Neon (2026-09 redesign) renders through the shared layout engine like Collegiate
    # Tech, so the lab no longer loads or routes to a standalone Neon engine (the
    # retired ones are archived under tests/retired/neon_v1/). Heritage is unchanged.
    assert not re.findall(r"csrn-neon-[\w-]*\.(?:css|js)", lab)
    assert "neonR" not in lab and "CSRNNeonR" not in lab


