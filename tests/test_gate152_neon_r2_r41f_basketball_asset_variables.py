from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_r41f_basketball_asset_variables_are_emitted_without_breaking_r40_contract():
    js=(ROOT/'static/csrn-neon-r2-engine.js').read_text(encoding='utf-8')
    assert 'VERSION="2.0.0-r40"' in js
    assert 'artworkColorMode:"adaptive-blacklight-field-football"' in js
    required=[
        '--n2-basketball-r41-environment',
        '--n2-basketball-r41-home-court',
        '--n2-basketball-r41-visitor-court',
        '--n2-basketball-r41-home-rim',
        '--n2-basketball-r41-visitor-rim',
        '--n2-basketball-r41-underlay',
        '--n2-basketball-r41-home',
        '--n2-basketball-r41-visitor',
        '--n2-basketball-r41-ball-home',
        '--n2-basketball-r41-master',
        '--n2-basketball-r41-luminance',
        '--n2-basketball-r41-shadows',
        '--n2-basketball-r41-highlights',
    ]
    for token in required:
        assert token in js
