"""Timeouts left reach the on-air board: the count in the runtime view, the bars on Collegiate Tech."""
from pathlib import Path

from state_service import StateService

ROOT = Path(__file__).resolve().parents[1]


def counts(state):
    return StateService.__new__(StateService).runtime_view(state).data["state"].get("timeouts_left")


def timeout(team, quarter, **extra):
    return {"event": "TIMEOUT", "team": team, "quarter": quarter, "broadcast_id": "G1", **extra}


def game(quarter="1", events=(), sport="Football"):
    return {"sport": sport, "quarter": quarter, "broadcast_id": "G1", "events": list(events)}


def test_a_new_game_has_three_each():
    assert counts(game()) == {"home": 3, "visitor": 3, "allowance": 3}


def test_a_timeout_is_charged_to_the_right_team():
    assert counts(game(events=[timeout("home", "1"), timeout("home", "2")])) == {"home": 1, "visitor": 3, "allowance": 3}


def test_an_undone_timeout_comes_back():
    assert counts(game(events=[timeout("visitor", "1", undone=True)]))["visitor"] == 3


def test_the_second_half_resets():
    assert counts(game("3", [timeout("home", "1"), timeout("home", "2")]))["home"] == 3
    assert counts(game("4", [timeout("home", "3")]))["home"] == 2


def test_overtime_gets_one_bar():
    assert counts(game("OT")) == {"home": 1, "visitor": 1, "allowance": 1}


def test_another_games_timeout_is_not_counted():
    assert counts(game(events=[{**timeout("home", "1"), "broadcast_id": "OTHER"}]))["home"] == 3


def test_other_sports_get_no_football_count():
    assert counts(game(sport="Basketball")) is None
    assert counts(game(sport="Baseball")) is None


def test_the_collegiate_family_draws_the_bars_and_the_cached_files_changed_version():
    runtime = (ROOT / "static/csrn-production-theme-runtime.js").read_text(encoding="utf-8")
    assert "if (!isCollegiateFamily(alias)) return;" in runtime
    assert "patchCollegiateTimeouts(root, currentAlias, runtime);" in runtime
    assert runtime.count("/static/csrn-collegiate-timeouts.css?v=1") == 2
    assert "csrn-production-theme-runtime.js?v=19.7-timeouts" in (ROOT / "templates/overlay.html").read_text(encoding="utf-8")
