"""Basketball panel parity (docs/BASKETBALL_PANEL_PARITY.md): Collegiate Tech's basketball board is now the same
cabinet / score row / team-snapshot rails / court-photo video board / bank structure as football and baseball, with no
shot clock, fed by a roster-resolved panel endpoint. This repo has no JS runner, so the JS/CSS is pinned by source
assertions here; its BEHAVIOUR was verified live in a real browser against a real seeded basketball game (see the doc).
"""

from __future__ import annotations

import re
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, request

from hoops_box_score_service import HoopsBoxScoreService  # noqa: F401  (the ledger reader this module builds on)
from hoops_lineup_service import HoopsLineupService
from hoops_overlay_panel import HoopsOverlayPanelService, build_panel, roster_lookup
from hoops_period_service import HoopsPeriodService
from hoops_rules_service import HoopsRulesService
from routes.hoops_game_routes import HoopsGameRoutesDependencies, create_hoops_game_blueprint

ROOT = Path(__file__).resolve().parents[1]
ENGINE = "static/csrn-broadcast-layout-engine.js"
ENGINE_CSS = "static/csrn-broadcast-layout-engine.css"
RUNTIME = "static/csrn-production-theme-runtime.js"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _game() -> dict[str, Any]:
    state = {
        "sport": "basketball", "country": "US", "region": None, "association": "NFHS",
        "home_team": "Home", "visitor_team": "Visitor", "home_score": 0, "visitor_score": 0,
        "home_school_id": "h-hs", "visitor_school_id": "v-hs",
    }
    HoopsPeriodService.start_game(state, HoopsRulesService.active_ruleset(state))
    return state


def _roster(school: str, rows: list[tuple[str, str, str, str]]) -> dict[str, Any]:
    return {"school_id": school, "sport": "Basketball", "players": [
        {"id": i, "number": n, "first_name": f, "last_name": last, "status": "active"} for i, n, f, last in rows]}


ROSTERS = [
    _roster("h-hs", [("h1", "3", "Marcus", "Reed"), ("h2", "23", "Jalen", "Brooks"), ("h3", "32", "Eli", "Watts")]),
    _roster("v-hs", [("v1", "2", "Cam", "Nguyen"), ("v2", "10", "Andre", "Fox")]),
]


# --- the panel feed ---------------------------------------------------------------------------------------------


def test_leaders_totals_and_last_basket_are_resolved_against_the_roster() -> None:
    state = _game()
    HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 2, "shooterId": "h2", "assistId": "h1"})
    HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 3, "shooterId": "h2"})
    HoopsRulesService.shot(state, {"team": "visitor", "made": False, "points": 2, "shooterId": "v1"})
    HoopsRulesService.rebound(state, {"team": "home", "playerId": "h3", "kind": "defensive"})
    HoopsRulesService.free_throw(state, {"team": "visitor", "made": True, "shooterId": "v2"})

    panel = build_panel(state, roster_lookup(ROSTERS, state))

    assert panel["leaders"]["home"] == {
        "name": "Jalen Brooks", "number": "23", "pts": 5, "reb": 0, "ast": 0, "line": "5 PTS · 0 REB · 0 AST"}
    assert panel["leaders"]["visitor"]["name"] == "Andre Fox" and panel["leaders"]["visitor"]["pts"] == 1
    assert panel["team_stats"]["home"] == {"fg": "2/2", "fg3": "1", "reb": "1"}
    assert panel["team_stats"]["visitor"] == {"fg": "0/1", "fg3": "0", "reb": ""}
    # the most recent made basket is the free throw
    assert panel["last_basket"] == {"team": "visitor", "points": 1, "name": "Andre Fox", "number": "10"}


def test_undo_is_honoured_because_the_feed_reads_the_rebuilt_ledger() -> None:
    from hoops_event_service import HoopsEventService

    state = _game()
    HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 2, "shooterId": "h1"})
    HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 3, "shooterId": "h2"})
    HoopsEventService.undo(state)
    panel = build_panel(state, roster_lookup(ROSTERS, state))
    assert panel["last_basket"]["name"] == "Marcus Reed" and panel["last_basket"]["points"] == 2
    assert panel["team_stats"]["home"]["fg3"] == "0"


def test_who_is_on_the_floor_comes_from_the_lineup_by_number_and_name() -> None:
    state = _game()
    HoopsLineupService.set_starting_five(state, "home", ["h1", "h2", "h3", "hx", "hy"])
    panel = build_panel(state, roster_lookup(ROSTERS, state))
    assert [p["number"] for p in panel["on_floor"]["home"][:3]] == ["3", "23", "32"]
    assert panel["on_floor"]["home"][1]["name"] == "Jalen Brooks"
    # ids missing from the roster degrade to blank, never to a crash or a wrong name
    assert panel["on_floor"]["home"][3] == {"name": "", "number": ""}
    assert panel["on_floor"]["visitor"] == []


def test_a_game_with_no_attributed_plays_gives_blanks_not_wrong_numbers() -> None:
    state = _game()
    panel = build_panel(state, roster_lookup(ROSTERS, state))
    assert panel["leaders"] == {"home": None, "visitor": None}
    assert panel["last_basket"] is None
    assert panel["team_stats"]["home"] == {"fg": "", "fg3": "", "reb": ""}


def test_unattributed_baskets_still_count_and_fall_back_to_the_team() -> None:
    state = _game()
    HoopsRulesService.shot(state, {"team": "visitor", "made": True, "points": 3})  # no shooterId
    panel = build_panel(state, roster_lookup(ROSTERS, state))
    assert panel["last_basket"] == {"team": "visitor", "points": 3, "name": "", "number": ""}
    assert panel["leaders"]["visitor"] is None and panel["team_stats"]["visitor"]["fg3"] == "1"


def test_roster_lookup_only_reads_each_teams_own_basketball_roster() -> None:
    state = _game()
    other_sport = {**_roster("h-hs", [("h1", "99", "Wrong", "Sport")]), "sport": "Football"}
    same_id_other_school = _roster("v-hs", [("h1", "77", "Visitor", "Homonym")])
    names = roster_lookup([other_sport, same_id_other_school, *ROSTERS], state)
    assert names["home"]["h1"]["name"] == "Marcus Reed"      # not the football roster's "Wrong Sport"
    assert "h1" in names["visitor"] and names["visitor"]["h1"]["name"] == "Visitor Homonym"  # ids are per team


def test_the_service_caches_the_roster_and_survives_a_roster_failure() -> None:
    state = _game()
    HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 2, "shooterId": "h1"})
    calls: list[int] = []
    clock = [0.0]

    def list_rosters():
        calls.append(1)
        return ROSTERS

    service = HoopsOverlayPanelService(list_rosters, now=lambda: clock[0])
    service.panel(state); service.panel(state); service.panel(state)
    assert len(calls) == 1                     # not re-read on every overlay poll
    clock[0] = 31.0
    service.panel(state)
    assert len(calls) == 2                     # refreshed after the TTL

    def broken():
        raise OSError("roster file locked")

    survivor = HoopsOverlayPanelService(broken).panel(state)
    assert survivor["leaders"]["home"]["name"] == "" and survivor["leaders"]["home"]["pts"] == 2  # names blank, data intact
    assert survivor["team_stats"]["home"]["fg"] == "1/1"


def _client(state: dict[str, Any], service: Any) -> Any:
    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def wrapped(*a: Any, **k: Any):
            return jsonify({"error": "AUTH_REQUIRED"}), 401
        return wrapped

    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(create_hoops_game_blueprint(HoopsGameRoutesDependencies(
        require_auth=require_auth, get_hoops_operations_service=lambda: None,
        load_state=lambda: state, get_panel_service=(lambda: service) if service else None)))
    return app.test_client()


def test_the_panel_route_is_public_read_only_and_basketball_only() -> None:
    state = _game()
    HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 2, "shooterId": "h1"})
    service = HoopsOverlayPanelService(lambda: ROSTERS)
    response = _client(state, service).get("/api/hoops/panel-state")      # no auth header: the OBS overlay has none
    assert response.status_code == 200 and response.get_json()["leaders"]["home"]["name"] == "Marcus Reed"
    assert _client({"sport": "football"}, service).get("/api/hoops/panel-state").status_code == 409
    assert _client(state, None).get("/api/hoops/panel-state").status_code == 503


def test_a_failure_in_the_derived_feed_is_never_a_500_for_the_overlay() -> None:
    class Exploding:
        def panel(self, state):
            raise RuntimeError("boom")

    response = _client(_game(), Exploding()).get("/api/hoops/panel-state")
    assert response.status_code == 200 and response.get_json()["leaders"] == {"home": None, "visitor": None}


def test_the_route_is_registered_public_in_the_architecture_guard() -> None:
    assert '"hoops_game_routes.hoops_panel_state"' in read("phase5_architecture.py")
    app_py = read("app.py")
    assert "get_panel_service=lambda: get_hoops_overlay_panel_service()" in app_py
    assert 'get_roster_service().list_rosters("")' in app_py


# --- the engine: one board, no shot clock ------------------------------------------------------------------------


def test_collegiate_basketball_is_the_full_tech_board_not_the_compact_strip() -> None:
    js = read(ENGINE)
    dispatch = js.split("    collegiate(state, sport, videoMode) {")[1].split("    classic(state, sport) {")[0]
    assert 'if (sport === "basketball") return collegiateBasketballScorebug(state, sport, videoMode);' in dispatch
    board = js.split("function collegiateBasketballScorebug(state, sport, videoMode) {")[1].split("\n  }\n")[0]
    # the same skeleton football and baseball use
    for piece in ("bl-college-cabinet", "bl-college-live-strip", "collegiateScoreClockRow(state)",
                  'collegiateMainDisplay(state, "basketball", videoMode)', "collegiateBasketballBank(state)",
                  "bl-collegiate-tech"):
        assert piece in board, piece
    # the main display is the shared one, so the rails, the video board and the video-mode hooks come for free
    stage = js.split("function collegiateStage(state, videoMode, sport")[1].split("</section>`;")[0]
    assert "data-module=\"video.board\"" in stage and 'data-sport="${esc(sport)}"' in stage


def test_basketball_claims_the_full_safe_canvas_like_the_other_three_sports() -> None:
    js = read(ENGINE)
    table = js.split("const COLLEGIATE_SPORT_COMPONENTS = Object.freeze(")[1].split("const PACKAGE_MANIFESTS")[0]
    basketball = table.split("basketball:{components:{")[1].split("}},")[0]
    assert 'scorebug:{zone:"full-safe",width:1840,height:1000,layer:100}' in basketball
    assert 'zone:"bottom-center"' not in basketball.split("scorebug:")[1].split("},")[0]


def test_collegiate_shows_no_shot_clock_anywhere() -> None:
    """Product decision 2026-09-14: no shot clock for basketball, ever. The cell existed on Collegiate's compact strip
    (it read SHOT14 / SHOT24 in the neon screenshots) and is gone from every Collegiate basketball path."""
    js = read(ENGINE)
    board = js.split("// ---- Collegiate Tech basketball")[1].split("function baseballInningPlan")[0]
    code = " ".join(line for line in board.splitlines() if not line.strip().startswith("//"))
    assert "shot" not in code.lower()
    # the fallthrough strip (any sport without its own board) passes includeAuxClock = false
    assert 'sportState(state,sport,"bl-college-state",false)' in js
    # the runtime no longer patches game.shotClock on Collegiate; the stored wire value is untouched for other themes
    patcher = read(RUNTIME).split("function applyBasketballBoardOverrides(root, alias, runtime) {")[1].split("\nfunction applyDiamondBoardOverrides")[0]
    assert "shotClock" not in patcher and "shot_clock" not in patcher


def test_the_board_carries_the_foul_timeout_bank_and_a_last_basket_callout() -> None:
    js = read(ENGINE)
    bank = js.split("function collegiateBasketballBank(state) {")[1].split("function collegiateBasketballScorebug")[0]
    for label in ("Possession", "Last Basket", "Fouls", "Timeouts"):
        assert f"<small>{label}</small>" in bank
    # the four cells reuse football's readout-bar class, so Neon's pill and cell rules attach with no new selector
    assert "bl-college-field-meta bl-college-court-meta" in bank
    assert 'data-bind="game.lastBasket"' in bank and 'data-module="game.field"' in bank
    row = js.split("function collegiateBasketballTeamRow(state, side) {")[1].split("function collegiateBasketballBank")[0]
    assert 'data-court-row="${side}"' in row and 'data-role="bonus"' in row
    assert 'IN BONUS' in js and 'IN 1+1' in js
    assert 'basketball: Object.freeze([["FG", "fg"], ["3PT", "fg3"], ["REB", "reb"]])' in js  # the snapshot rail's stats


def test_the_clash_screen_has_a_court_photo_for_plain_collegiate() -> None:
    css = read(ENGINE_CSS)
    rule = next(line for line in css.splitlines() if line.startswith('.bl-college-stage-field[data-sport="basketball"]'))
    assert "basketball-court-background.png" in rule and "var(--visitor-primary" in rule and "var(--home-primary" in rule
    assert (ROOT / "static/friday-night-stadium/clash/basketball-court-background.png").is_file()
    assert ".bl-college-court{" in css and ".bl-court-row{" in css


# --- the runtime: live patching + the wire-field fix --------------------------------------------------------------


def test_fouls_bonus_and_timeouts_fall_back_to_the_engines_own_hoops_block() -> None:
    """Found in this round's audit: the overlay read flat home_fouls / home_bonus / home_timeouts (HOOPS_OVERLAY_CONTRACT
    Sec.1) but /api/runtime-state only ever carried state["hoops"] (raw names), so they read blank live. The flat field
    still wins when present; the engine block is the fallback."""
    fn = read(RUNTIME).split("function productionBasketballState(source, gameSource) {")[1].split("\n}\n")[0]
    for flat, nested in (("home_fouls", "home_team_fouls"), ("visitor_fouls", "visitor_team_fouls"),
                         ("home_bonus", "home_bonus"), ("visitor_bonus", "visitor_bonus"),
                         ("home_timeouts", "home_timeouts"), ("visitor_timeouts", "visitor_timeouts")):
        assert f'"{flat}"' in fn and f'"{nested}"' in fn, (flat, nested)
    assert "const hoops = objectValue(source.hoops, gameSource.hoops);" in fn
    assert re.search(r'pick\("home_fouls", "homeFouls"\) \|\| nested\("home_team_fouls"\)', fn)  # flat first


def test_the_runtime_patches_the_basketball_board_live_and_polls_the_panel_feed() -> None:
    js = read(RUNTIME)
    assert 'const HOOPS_PANEL_URL = "/api/hoops/panel-state";' in js
    fetch_fn = js.split("async function fetchCollegiateHoopsPanel(runtime, alias) {")[1].split("\n}\n")[0]
    assert 'productionSportFamily(runtime && runtime.sport) !== "basketball"' in fetch_fn  # only basketball pays for it
    assert "< 2500" in fetch_fn and "cache.promise" in fetch_fn                            # cached + de-duplicated
    assert "await fetchCollegiateHoopsPanel(runtime, alias);" in js                        # in the poll, beside the statistics
    rails = js.split("function patchCollegiateRails(root, runtime, statistics) {")[1].split("\n}\n")[0]
    assert 'sport === "basketball"' in rails and "patchCollegiateBasketballRails(root, runtime, collegiateHoopsPanelCache.data)" in rails
    board = js.split("function patchCollegiateBasketballBoard(root, runtime, panel) {")[1].split("\nfunction basketballLeaderCandidates")[0]
    for hook in ("data-court-row", 'data-bind="game.lastBasket"', 'data-bind="game.foulsText"', 'data-bind="game.timeoutsText"',
                 'data-bind="game.possessionText"', "court.dataset.lastTeam"):
        assert hook in board, hook
    # names come from the rendered board so the patch cannot disagree with the markup it patches
    assert '.mascot"]`)?.textContent' in board


def test_the_leader_card_rotates_scoring_leader_and_who_is_on_the_floor() -> None:
    js = read(RUNTIME)
    fn = js.split("function basketballLeaderCandidates(panel, side) {")[1].split("\nfunction patchCollegiateBasketballRails")[0]
    assert '"Scoring Leader"' in fn and '"On the Floor"' in fn
    rails = js.split("function patchCollegiateBasketballRails(root, runtime, panel) {")[1].split("\nfunction patchCollegiateRails")[0]
    assert "COLLEGIATE_LEADER_ROTATION_MS" in rails and 'data-stat="${key}"' in rails
    assert '"Awaiting Stats"' in rails  # the same empty state football shows until stats exist


def test_layout_builder_hooks_are_not_basketball_special_cased() -> None:
    """The board is stamped through the shared applyRect() like every other sport, so the Layout Builder's mode masking
    and score_box placement need no basketball-specific code (both matrices pass live on basketball, Collegiate and Neon)."""
    js = read(ENGINE)
    assert js.count("node.dataset.component = placement.component;") == 1
    assert "basketball" not in js.split("function applyRect(node, placement) {")[1].split("\n  }")[0]
