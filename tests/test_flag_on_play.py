"""Flag on the play: a penalty attached to a run or pass (2026-10-25 simulation).

The officials' rulings below come from the 2025 MHSAA finals the console was
tested against. Before this, a foul during a play could only be entered as a
separate penalty after the play, so the down had already advanced ("3rd & 11"
where the officials replayed 2nd down).
"""
from __future__ import annotations

from pathlib import Path

from canonical_state_service import CanonicalStateFoundation as C
from tests.test_rules_service import base_state, build_service

HTML = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")


def _state(ball_spot: str, down: str, distance: str, **extra) -> dict:
    state = base_state()  # home drives right, visitor left
    state.update({"ball_spot": ball_spot, "down": down, "distance": distance, **extra})
    return state


def _flag(team: str, unit: str, name: str, yards: int, enforcement: str = "end_of_play", **extra) -> dict:
    return {"team": team, "unit": unit, "name": name, "yards": yards, "outcome": "accepted",
            "enforcement": enforcement, **extra}


def _run(start: str, end: str, flag: dict | None = None) -> dict:
    payload = {"team": "home", "play_type": "run", "player_number": "22", "start_spot": start, "end_spot": end}
    if flag is not None:
        payload["flag"] = flag
    return payload


def test_offensive_holding_on_a_run_replays_the_down_from_the_end_of_the_run() -> None:
    # D3 final, 2nd qtr: 2-4 at the MT 8, run for 3 to the MT 5, holding on
    # DeWitt 10 yards to the MT 15 -> 2nd & 11.
    service, current, *_ = build_service(_state("RIGHT 8", "2nd", "4"))
    result = service.play(_run("RIGHT 8", "RIGHT 5", _flag("home", "Offensive", "Holding", 10)))
    assert result.code == "OK", result.data
    assert (current["ball_spot"], current["down"], current["distance"]) == ("RIGHT 15", "2nd", "11")
    play = result.data["play"]
    assert play["yards"] == 3  # the run still counts for the ball carrier
    assert play["penalty"]["applied"] is True and play["penalty"]["enforced_yards"] == 10
    assert "penalty on Caledonia: Holding, 10 yards from the end of the play" in play["result"]


def test_holding_after_a_completion_keeps_the_original_line_to_gain() -> None:
    # D2 final, 1st qtr: 1-10 at the Dexter 45, completion for 3, Dexter
    # holding 10 yards to the Dexter 38 -> 1st & 17.
    service, current, *_ = build_service(_state("LEFT 45", "1st", "10"))
    payload = {"team": "home", "play_type": "pass", "passer_number": "12", "receiver_number": "3",
               "pass_outcome": "complete", "start_spot": "LEFT 45", "end_spot": "LEFT 48",
               "flag": _flag("home", "Offensive", "Holding", 10)}
    result = service.play(payload)
    assert result.code == "OK", result.data
    assert (current["ball_spot"], current["down"], current["distance"]) == ("LEFT 38", "1st", "17")


def test_goal_to_go_holding_stays_goal_to_go() -> None:
    # D4 final, 3rd qtr: 2nd & Goal at the 6, run for 2, holding 10 yards
    # from the end of the run -> 2nd & Goal from the 14.
    service, current, *_ = build_service(_state("RIGHT 6", "2nd", "6"))
    result = service.play(_run("RIGHT 6", "RIGHT 4", _flag("home", "Offensive", "Holding", 10)))
    assert result.code == "OK", result.data
    assert (current["ball_spot"], current["down"], current["distance"]) == ("RIGHT 14", "2nd", "14")
    assert C.goal_to_go(current) is True


def test_spot_of_the_foul_enforcement() -> None:
    # 1st & 10 at own 20; run to the 35; holding at the 28 -> 10 yards from
    # the 28 = the 18; replay 1st down from the original line (the 30): 1st & 12.
    service, current, *_ = build_service(_state("LEFT 20", "1st", "10"))
    flag = _flag("home", "Offensive", "Holding", 10, "spot_of_foul", spot="LEFT 28")
    result = service.play(_run("LEFT 20", "LEFT 35", flag))
    assert result.code == "OK", result.data
    assert (current["ball_spot"], current["down"], current["distance"]) == ("LEFT 18", "1st", "12")
    assert "from the spot of the foul (Caledonia 28)" in result.data["play"]["result"]


def test_defensive_foul_on_a_failed_fourth_down_keeps_the_ball_with_the_offense() -> None:
    # 4th & 15 at the 40, incomplete, defensive holding 10 (no automatic
    # first down under NFHS) -> offense keeps it, 4th & 5 from the 50.
    service, current, *_ = build_service(_state("LEFT 40", "4th", "15"))
    payload = {"team": "home", "play_type": "pass", "passer_number": "12", "pass_outcome": "incomplete",
               "start_spot": "LEFT 40", "end_spot": "LEFT 40",
               "flag": _flag("visitor", "Defensive", "Holding", 10)}
    result = service.play(payload)
    assert result.code == "OK", result.data
    assert current["possession"] == "home"
    assert (current["ball_spot"], current["down"], current["distance"]) == ("50", "4th", "5")
    assert result.data["play"]["turnover"] is False
    assert "turnover on downs" not in result.data["play"]["result"]


def test_defensive_foul_whose_yardage_reaches_the_line_gives_a_first_down() -> None:
    service, current, *_ = build_service(_state("LEFT 40", "3rd", "8"))
    payload = {"team": "home", "play_type": "pass", "passer_number": "12", "pass_outcome": "incomplete",
               "start_spot": "LEFT 40", "end_spot": "LEFT 40",
               "flag": _flag("visitor", "Defensive", "Pass Interference", 15)}
    result = service.play(payload)
    assert result.code == "OK", result.data
    assert (current["ball_spot"], current["down"], current["distance"]) == ("RIGHT 45", "1st", "10")


def test_dead_ball_foul_after_the_play_counts_the_down() -> None:
    # 1st & 10, run for 5, then a 15-yard personal foul on the defense after
    # the play: 2nd & 5 becomes 1st & 10 twenty yards on.
    service, current, *_ = build_service(_state("LEFT 20", "1st", "10"))
    result = service.play(_run("LEFT 20", "LEFT 25", _flag("visitor", "Defensive", "Personal Foul", 15, "after_play")))
    assert result.code == "OK", result.data
    assert (current["ball_spot"], current["down"], current["distance"]) == ("LEFT 40", "1st", "10")


def test_declined_flag_is_logged_and_the_play_stands() -> None:
    service, current, *_ = build_service(_state("LEFT 20", "1st", "10"))
    flag = {**_flag("visitor", "Defensive", "Offside", 5), "outcome": "declined"}
    result = service.play(_run("LEFT 20", "LEFT 32", flag))
    assert result.code == "OK", result.data
    assert (current["ball_spot"], current["down"], current["distance"]) == ("LEFT 32", "1st", "10")
    assert "penalty on New Hope: Offside, declined" in result.data["play"]["result"]
    assert result.data["play"]["penalty"]["applied"] is False


def test_a_touchdown_wiped_out_by_a_flag_must_be_a_no_play() -> None:
    service, current, saved, *_ = build_service(_state("RIGHT 10", "1st", "10"))
    result = service.play(_run("RIGHT 10", "RIGHT GOAL", _flag("home", "Offensive", "Holding", 10)))
    assert result.code == "FLAG_NEEDS_NO_PLAY"
    assert saved == [] and current["home_score"] == 0


def test_a_punt_flag_is_enforced_from_the_end_of_the_kick() -> None:
    # Kick flags arrived with the 2026-10-30 simulation fixes: holding on the
    # receiving team at the end of a fair-caught punt costs it 10 yards.
    service, current, *_ = build_service(_state("LEFT 20", "4th", "10"))
    result = service.play({"team": "home", "play_type": "punt", "start_spot": "LEFT 20", "landing_spot": "RIGHT 40",
                           "end_spot": "RIGHT 40", "kicker_number": "9", "fair_catch": True,
                           "flag": _flag("visitor", "Special Teams", "Holding", 10)})
    assert result.code == "OK"
    assert (current["possession"], current["ball_spot"], current["down"], current["distance"]) == \
        ("visitor", "RIGHT 30", "1st", "10")


def test_spot_of_foul_needs_a_spot() -> None:
    service, *_ = build_service(_state("LEFT 20", "1st", "10"))
    result = service.play(_run("LEFT 20", "LEFT 25", _flag("home", "Offensive", "Holding", 10, "spot_of_foul")))
    assert result.code == "FLAG_SPOT_REQUIRED"


def test_the_flag_is_stored_with_the_play_entry_for_edits() -> None:
    service, current, *_ = build_service(_state("RIGHT 8", "2nd", "4"))
    result = service.play(_run("RIGHT 8", "RIGHT 5", _flag("home", "Offensive", "Holding", 10)))
    entry = result.data["play"]["entry"]
    assert entry["flag"]["name"] == "Holding" and entry["flag"]["enforcement"] == "end_of_play"
    rebuilt = service.entry_from_play({**result.data["play"], "entry": None})
    assert rebuilt["flag"]["name"] == "Holding"


def test_console_play_form_has_a_flag_section() -> None:
    assert 'id="playFlagEnabled"' in HTML
    for enforcement in ("end_of_play", "spot_of_foul", "after_play", "no_play"):
        assert f'value="{enforcement}"' in HTML
    assert "payload.flag=" in HTML


def test_edit_play_restores_the_flag_into_the_form() -> None:
    assert "restorePlayFlag(entry.flag);" in HTML
    assert "function restorePlayFlag(flag)" in HTML


def test_reentering_a_flagged_play_re_applies_the_foul() -> None:
    service, current, *_ = build_service(_state("RIGHT 8", "2nd", "4"))
    first = service.play(_run("RIGHT 8", "RIGHT 5", _flag("home", "Offensive", "Holding", 10)))
    assert first.code == "OK", first.data
    edited = service.reenter(first.data["play"]["event_id"], {**first.data["play"]["entry"], "source": "statistician"})
    assert edited.code == "OK", edited.data
    assert (current["ball_spot"], current["down"], current["distance"]) == ("RIGHT 15", "2nd", "11")
