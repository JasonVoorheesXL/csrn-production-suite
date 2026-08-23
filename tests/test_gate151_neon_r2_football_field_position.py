from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_football_has_overhead_field_position_module_only() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    assert 'if(s.sport==="football")return footballField(s)' in js
    assert 'n2-foot-field' in js
    assert 'statistician-mode' in js
    assert 'data-statistician-mode="${statisticianMode}"' in js
    assert 'class="n2-ball-line"' in js
    assert 'BALL ON ${esc(f.raw)}' in js
    assert 'if(s.sport==="baseball"||s.sport==="softball")' in js
    assert 'if(s.sport==="basketball")return footballField(s)' not in js


def test_football_field_supports_ball_spot_side_and_direction() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    for required in (
        "ballOnTeam",
        "fieldSide",
        "offenseDirection",
        "fieldDirection",
        "driveDirection",
        'possessionSide==="visitor"?"var(--n2-right)":"var(--n2-left)"',
    ):
        assert required in js


def test_football_field_stays_inside_1080_canvas() -> None:
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert ".n2-foot-field" in css
    assert ".n2-ball-line" in css
    assert "--n2-ball-neon" in css


def test_layout_lab_fixture_exercises_field_position() -> None:
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
    assert 'state.game.ballOn="N 38"' in lab
    assert 'state.game.ballOnTeam="NORTHWOOD"' in lab
    assert 'state.game.fieldDirection="right"' in lab

def test_football_field_preserves_statistician_mode_compatibility() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    assert "statisticianMode" in js
    assert 'data-statistician-mode="${statisticianMode}"' in js


