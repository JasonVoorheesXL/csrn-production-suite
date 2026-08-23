from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_neon_r2_isolated_files_and_approved_contract():
    js=(ROOT/"static/csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    css=(ROOT/"static/csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    lab=(ROOT/"static/csrn-layout-lab.html").read_text(encoding="utf-8")
    assert 'VERSION="2.0.0-r40"' in js
    assert 'Neon Sports Network R2' in js
    assert 'AT BAT' in js
    assert 'Top Performers' not in js and 'TOP PERFORMERS' not in js
    assert 'slice(0,3)' in js
    assert 'statisticianMode' in js and 'BALL ON' in js
    assert 'csrn-neon-r2-engine.css?v=15.1-r40' in lab
    assert 'csrn-neon-r2-engine.js?v=15.1-r40' in lab
    assert 'CSRNNeonR2Engine' in lab
    assert 'csrn-neon-r1-engine.js?v=15.0-r1' not in lab
    assert '--n2-left' in css and '--n2-right' in css
def test_neon_r2_has_four_neutral_and_eight_uniform_masks():
    asset=ROOT/"static/neon-r2"
    for sport in ("football","basketball","baseball","softball"):
        assert (asset/f"{sport}-neutral.png").is_file()
        assert (asset/f"{sport}-left-mask.png").is_file()
        assert (asset/f"{sport}-right-mask.png").is_file()
