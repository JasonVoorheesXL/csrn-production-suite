from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_r3_consumes_actual_broadcast_identity_schema():
    js = read("static/csrn-production-theme-runtime.js")
    assert "team.broadcast_name" in js
    assert "team.official_name" in js
    assert "team.preferred_scorebug_name" in js
    assert 'const homeSource = productionTeamSource(source, "home")' in js
    assert 'const visitorSource = productionTeamSource(source, "visitor")' in js

def test_r3_selected_game_identity_is_in_render_signature():
    js = read("static/csrn-production-theme-runtime.js")
    for marker in (
        "runtime.broadcast_id",
        "runtime.home_school_id",
        "runtime.visitor_school_id",
        "runtime.home_team",
        "runtime.visitor_team",
        "runtime.home_identity",
        "runtime.visitor_identity",
        "runtime.venue_id",
        "runtime.venue",
    ):
        assert marker in js

def test_r3_preserves_venue_in_normalized_state():
    js = read("static/csrn-production-theme-runtime.js")
    assert "base.venue = textValue(" in js
    assert "source.venue" in js
    assert "base.venue_id = base.venueId" in js

def test_r3_audited_stadium_media_hosts_are_fail_closed():
    js = read("static/csrn-production-theme-runtime.js")
    assert 'eight_bit_gameday: ".bl-8bit-video-board"' in js
    assert 'friday_night_stadium: ".bl-fns-video-board"' in js
    assert "Object.prototype.hasOwnProperty.call(auditedNativeBoards, alias)" in js
    assert "if (!host || host.parentElement !== board) return null" in js

def test_r3_legacy_fullscreen_media_is_suppressed_every_poll():
    js = read("static/csrn-production-theme-runtime.js")
    assert "function enforceLegacyMediaOwnership(mode)" in js
    assert '["playerHighlight", mode === "highlight"]' in js
    assert '["sponsorSpotlight", mode === "sponsor"]' in js
    assert "enforceLegacyMediaOwnership(polledVideoMode)" in js
    assert 'node.style.setProperty("display", "none", "important")' in js

def test_r3_css_backstop_hides_legacy_fullscreen_media():
    css = read("static/csrn-production-theme-runtime.css")
    assert "html.csrn-production-theme-highlight-active body #playerHighlight" in css
    assert "html.csrn-production-theme-sponsor-active body #sponsorSpotlight" in css
