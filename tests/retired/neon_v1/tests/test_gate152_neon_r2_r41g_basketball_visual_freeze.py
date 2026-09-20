from pathlib import Path
import hashlib

ROOT=Path(__file__).resolve().parents[1]
EXPECTED={
    'static/csrn-neon-r2-engine.js': '6AFEE5D838FB183F975E10E2F29AA75526C675167D7AABE21B2D99075F3DCA5C',
    'static/csrn-neon-r2-engine.css': 'C9F1F9316EA1F16E86099F90DDD417075FF7111DA341867A8BFE2D7378EF043F',    'tests/test_gate152_neon_r2_r41f_basketball_asset_variables.py': '1C66D87F3DEB0B1DCA7199A31581A4E79D068AC87419CC6C5D0BE71793374DF7',
    'static/neon-r2/basketball-r41-ball-channel-home-glow-mask.png': '53C4863677C2766D93C9D246FC956800B1513D1B3DD8B03E620BC6562B520602',
    'static/neon-r2/basketball-r41-cutout-master.png': '0EF3E255CC075E539E59B01966D92258BF945CB5829FAE8F39BDEF87664A5649',
    'static/neon-r2/basketball-r41-environment-neutral.png': '04F4994D78D608E67D33A079C4A7DB26DBBD5A82519D12993786D7D173CB0013',
    'static/neon-r2/basketball-r41-highlights.png': 'F9B03B9D3919D937FB6741F6AC05800CEBA25F2EF1938238E15E96F0D9D64038',
    'static/neon-r2/basketball-r41-home-court-glow-mask.png': '1703293575C218BDD95D0FC2C6F5C8D811791C0FD81AFC808B07F0AAB8E808F2',
    'static/neon-r2/basketball-r41-home-primary-cutout.png': 'F6B639C9D0CC3852C6F58EE8CE0AAE371EC1C77F19F357705A71EBF4DB85EA5E',
    'static/neon-r2/basketball-r41-home-rim-net-glow-mask.png': '3AA262BF1596C94A8503DCD9F9BFDEAE625424EB1AE65D5A4515CBFE36128EF6',
    'static/neon-r2/basketball-r41-home-secondary-cutout.png': 'C2808B9FF1CF7271F972EBA4B32961C030750E3DDC9E3C9800C612D1491A4C6A',
    'static/neon-r2/basketball-r41-luminance.png': '326BCEC3A1F3292773217421631E7581FCAEDFCD24D51614A8ADB7B22B16DF91',
    'static/neon-r2/basketball-r41-player-occlusion-underlay.png': '5D841C6229C5683300B445AAF074E3CA1EB3C53B86D1E10759F2A84EB071797B',
    'static/neon-r2/basketball-r41-shadows.png': '661384833F6EA4FF9549C194443C2A9273957EAFD7868330763AE30494E95145',
    'static/neon-r2/basketball-r41-visitor-court-glow-mask.png': 'E13424AED31A5B4F3FD05C11F3B43831D51DBFD35834EBDDE9EAAEC4DFD0B6D8',
    'static/neon-r2/basketball-r41-visitor-primary-cutout.png': '1F12634AA18EF2238392E60FB2493AEFB75C5EE8E5220197B2E23C53DB12A29C',
    'static/neon-r2/basketball-r41-visitor-rim-net-glow-mask.png': 'E93CB5D49B3A54992B45C913E0244E74ABBBC6E43C0AE59455F1B47123FEC48B',
    'static/neon-r2/basketball-r41-visitor-secondary-cutout.png': 'C2808B9FF1CF7271F972EBA4B32961C030750E3DDC9E3C9800C612D1491A4C6A',
}

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()

def test_r41g_basketball_visual_hash_freeze() -> None:
    for relative, expected in EXPECTED.items():
        path=ROOT/relative
        assert path.is_file(), relative
        assert digest(path)==expected, relative

def test_r41g_preserves_frozen_r40_contract_strings() -> None:
    js=(ROOT/'static/csrn-neon-r2-engine.js').read_text(encoding='utf-8')
    assert 'VERSION="2.0.0-r40"' in js
    assert 'artworkColorMode:"adaptive-blacklight-field-football"' in js
    assert '--n2-basketball-r41-environment' in js


def test_r41g_visual_freeze_excludes_living_documentation() -> None:
    assert 'CSRN_PROJECT_BIBLE.md' not in EXPECTED
    assert 'CSRN_THEME_CONTINUITY_HANDOFF.md' not in EXPECTED


