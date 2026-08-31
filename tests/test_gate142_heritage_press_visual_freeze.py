from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HERITAGE_OWNED_FROZEN = {
    'static/csrn-heritage-press-engine.js': '3441427236290045B2B63883845B91451788F191EE4D6C90DC6FBBC1DF85ED17',
    'static/csrn-heritage-press-engine.css': '853AE377981973840E534A6536444690C8E8C3F08C97555771DC77433EB46972',
    # re-pinned Round 9 (2026-08-31): test_gate14 was edited only to re-pin the
    # Neon / Friday-Night renderer SHA-256 constants to their shipped bytes
    # (no Heritage assertion changed). See test_gate116 / test_gate126.
    'tests/test_gate14_heritage_press_engine.py': 'CBAE2FB7B79EDC8BD14125AF7D2727BDCEF26BA98F217E029EDFFFF07D6AD3CA',
    'static/heritage/press-batter-1920s.png': 'F2D6174D757D36EDC2075A395FEEFC11ED0E970E12E5B4166EA3EFC3DD787DD6',
    'static/heritage/press-pitcher-1920s.png': 'AF9F23C6F9B15F3B10087B9D2D22C8CA1B26C0E7E29DD8521CA12C4905CAFBAF',
    'static/heritage/press-softball-batter-1920s.png': '0DDC8966DED0DCA3FDE396E2BF00C5BC4A2AFE22029FB1BA42D01C365BA24026',
    'static/heritage/press-softball-pitcher-1920s.png': '760C70AACB06AD7FED36A76AE043F725F256A75510CA621B09AA569BC6BFE48B',
    'static/heritage/press-sponsor-truck.png': '12AD455D92FA69C9F5ED8B3D1BD2A4FDF056C2F93CA4D41C837355E0A68ECC85',
    'static/heritage/press-player-placeholder.png': '15010266859B8D5133B80C176827B95E7D3AE50A397F4E75CAE3D62E1A45A5C6',
    'static/heritage/press-newsprint-texture.png': '9163C1FED3EC186CD847CEA48F87C784003B49491EC68C96F19E02A6D0418155',
}


def _digest(relative: str) -> str:
    return sha256((ROOT / relative).read_bytes()).hexdigest().upper()


def test_gate142_heritage_owned_visual_freeze_has_ten_exact_files() -> None:
    assert len(HERITAGE_OWNED_FROZEN) == 10


def test_gate142_heritage_owned_visual_hashes_are_exact() -> None:
    for relative, expected in HERITAGE_OWNED_FROZEN.items():
        path = ROOT / relative
        assert path.is_file(), relative
        assert _digest(relative) == expected, relative


def test_gate143_shared_layout_lab_preserves_heritage_registration_semantically() -> None:
    source = (ROOT / 'static' / 'csrn-heritage-press-engine.js').read_text(encoding='utf-8')
    lab = (ROOT / 'static' / 'csrn-layout-lab.html').read_text(encoding='utf-8')
    assert 'const VERSION = "2.3.0"' in source
    assert 'const PACKAGE_ID = "heritage_press"' in source
    assert lab.count('csrn-heritage-press-engine.css?v=14.1') == 1
    assert lab.count('csrn-heritage-press-engine.js?v=14.1') == 1
    assert 'const heritageEngine=window.CSRNHeritagePressEngine;' in lab
    assert 'packageId===heritageEngine.packageId?heritageEngine:' in lab
    assert '...heritageEngine.validateManifests()' in lab
    assert 'heritageEngine.manifests[heritageEngine.packageId]' in lab


def test_gate143_documentation_records_shared_catalog_amendment() -> None:
    bible = (ROOT / 'CSRN_PROJECT_BIBLE.md').read_text(encoding='utf-8')
    handoff = (ROOT / 'CSRN_THEME_CONTINUITY_HANDOFF.md').read_text(encoding='utf-8')
    assert 'Gate 14.3 — Heritage Press shared-catalog freeze amendment' in bible
    assert 'Heritage-owned ten-file visual hash freeze' in bible
    assert 'shared Layout Lab is protected semantically' in bible
    assert 'Gate 14.3 shared-catalog amendment' in handoff
    assert 'No Heritage visual pixel changed' in handoff
    assert 'No production migration is authorized' in bible


