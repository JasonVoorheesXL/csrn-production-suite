from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_broadcast_identity_field_names_do_not_fall_back_to_fixture_names():
    js = read("static/csrn-production-theme-runtime.js")
    block = js[js.index("function normalizeTeam"):js.index("function activeEvents")]
    assert "team.broadcast_name" in block
    assert "team.official_name" in block
    assert "authoritativeName" in block

def test_team_change_can_invalidate_render_without_score_change():
    js = read("static/csrn-production-theme-runtime.js")
    start = js.index("const signature = JSON.stringify([")
    end = js.index("]);", start)
    signature = js[start:end]
    assert "runtime.home_school_id" in signature
    assert "runtime.visitor_school_id" in signature
    assert "runtime.home_identity" in signature
    assert "runtime.visitor_identity" in signature


