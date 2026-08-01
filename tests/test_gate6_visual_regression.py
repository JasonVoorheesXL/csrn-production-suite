from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _scorebug_fragment(overlay: str) -> str:
    start = overlay.index('<div id="scorebug"')
    end = overlay.index('<div id="eventTicker"', start)
    return overlay[start:end]


def test_scorebug_identity_order_places_record_below_mascot() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    scorebug = _scorebug_fragment(overlay)

    home_name = scorebug.index('id="homeName"')
    home_mascot = scorebug.index('id="homeMascot"')
    home_record = scorebug.index('id="homeRecord"')
    visitor_name = scorebug.index('id="visitorName"')
    visitor_mascot = scorebug.index('id="visitorMascot"')
    visitor_record = scorebug.index('id="visitorRecord"')

    assert home_name < home_mascot < home_record
    assert visitor_name < visitor_mascot < visitor_record
    assert scorebug.count('class="name-wrap"') == 2


def test_empty_identity_rows_collapse_without_geometry_changes() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")

    assert ".mascot:empty{display:none}" in overlay
    assert ".team-record:empty{display:none}" in overlay
    assert "grid-template-columns:484px 174px 484px;height:112px" in overlay
    assert "grid-template-columns:738px 248px 738px;height:224px" in overlay


def test_score_elements_remain_outside_identity_stacks() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    scorebug = _scorebug_fragment(overlay)

    home_stack_end = scorebug.index('</div><div id="homeScore"')
    visitor_score = scorebug.index('id="visitorScore"')
    visitor_stack = scorebug.index('<div class="name-wrap">', visitor_score)

    assert scorebug.index('id="homeRecord"') < home_stack_end
    assert visitor_score < visitor_stack
    assert scorebug.index('id="visitorRecord"') > visitor_stack


def test_gate6_overlay_revision_is_published_consistently() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "const OVERLAY_SCHEMA_REVISION='gate6-logo-fallback-v1';" in overlay
    assert 'OVERLAY_SCHEMA_REVISION = "gate6-logo-fallback-v1"' in app


def test_gate5_record_rendering_rules_remain_unchanged() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")

    assert "function structuredRecord(value)" in overlay
    assert "return ties?`${wins}-${losses}-${ties}`:`${wins}-${losses}`" in overlay
    assert "official&&Boolean(state.region_game)" in overlay
    assert "return region?`${overall} • REG ${region}`:overall" in overlay
    assert "scorebugRecord(s,'home')" in overlay
    assert "scorebugRecord(s,'visitor')" in overlay

def test_runtime_state_polling_is_bounded_and_non_overlapping() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    command = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    assert "refreshInFlight" in overlay
    assert "AbortController" in overlay
    assert "setTimeout(refresh,delay)" in overlay
    assert "setInterval(refresh,300)" not in overlay
    assert "statePollInFlight" in command
    assert "AbortController" in command
    assert "if (!authenticated || statePollInFlight) return" in command


def test_halftime_keeps_scorebug_and_replaces_center_game_status() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    service = (ROOT / "game_operations_service.py").read_text(encoding="utf-8")

    assert "state[\"scorebug_visible\"] = True" in service
    assert "halftime?'HALFTIME'" in overlay
    assert "center.classList.toggle('halftime',halftime)" in overlay
    assert "center.classList.toggle('no-clock',halftime||!s.clock_visible)" in overlay
    assert "const downOff=halftime||" in overlay
    assert ".center.halftime .quarter" in overlay


def test_fast_ticker_speed_is_one_and_a_half_times_the_prior_preset() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")

    assert "{very_slow:24,slow:36,normal:84,fast:189}" in overlay
    assert "{very_slow:24,slow:36,normal:84,fast:126}" not in overlay

def test_scorebug_logo_fallback_handles_valid_missing_and_broken_media() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")

    assert "function setScorebugLogo(id,url,teamName)" in overlay
    assert "const fallback=identityMonogramData(normalizedName)" in overlay
    assert "if(!requested)" in overlay
    assert "logo.dataset.mediaState='fallback'" in overlay
    assert "logo.onerror=()=>{if(logo.dataset.requestedLogo===requested)useFallback()}" in overlay
    assert "setScorebugLogo('homeLogo',hi.logo,s.home_team||'HOME')" in overlay
    assert "setScorebugLogo('visitorLogo',vi.logo,s.visitor_team||'VISITOR')" in overlay


def test_broken_scorebug_logo_is_not_retried_on_every_state_poll() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")

    assert "logo.dataset.requestedLogo===requested" in overlay
    assert "logo.dataset.mediaState==='fallback'&&logo.dataset.fallbackName===normalizedName" in overlay
    assert "for(const [id,url] of [['homeLogo',hi.logo],['visitorLogo',vi.logo]])" not in overlay
    assert "logo.style.display='none'" not in overlay
