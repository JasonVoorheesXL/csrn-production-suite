"""Drive the real Statistician Console through a fictional football game.

Every action goes through the actual page (clicks, typed jersey numbers,
moved spot sliders); nothing is faked. A screenshot is saved for each
meaningful state, and a JSON log of the game state after every capture is
written to capture_log.json so the guide text can be checked against what
the screen really did.

Usage:  walkthrough.py <runtime_dir> <port> [--until=<phase>]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

GUIDE = Path(__file__).resolve().parents[1]
SHOTS = GUIDE / "screenshots"
VIEWPORT = {"width": 1280, "height": 1250}

STATE_SUMMARY = """() => {
  const s = currentState || {};
  const plays = (s.plays || []).filter(p => !p.undone);
  const last = plays[plays.length - 1] || {};
  return {
    score: `${s.home_team} ${s.home_score} - ${s.visitor_team} ${s.visitor_score}`,
    quarter: s.quarter, down: s.down, distance: s.distance, ball_spot: s.ball_spot,
    possession: s.possession, phase: s.special_game_phase || '', kicking: s.kicking_team || '',
    halftime: s.halftime_active ?? s.halftime ?? null, status: s.status,
    game_status: s.game_status || '', final: s.final ?? s.game_final ?? null,
    period_state: s.period_state || s.period_status || '', clock: s.game_clock ?? s.clock ?? null,
    authority: s.game_data_authority,
    home_direction: s.home_direction, visitor_direction: s.visitor_direction,
    notice: (document.getElementById('statisticianActionNotice') || {}).textContent || '',
    period_text: (document.getElementById('periodStatus') || {}).textContent || '',
    plays: plays.length,
    last_play: {type: last.play_type, result: last.result, description: last.description,
                unresolved: last.unresolved_players, mismatch: last.team_mismatch_players,
                touchdown: last.touchdown, safety: last.safety, yards: last.yards,
                down: last.resulting_down, distance: last.resulting_distance},
  };
}"""

PLAY_SHEET = "#playEntryModal .event-confirm-sheet"
AUTO_SHEET = "#automationEventModal .event-confirm-sheet"
PENALTY_SHEET = "#penaltyModal .event-confirm-sheet"
CONSOLE = "#statisticianModule .statistician-console"
SCOREBOARD = "#statisticianModule .statistician-scoreboard"
CLOCK = "#statisticianModule .statistician-clock-pinned"
REGISTER = "#statisticianModule .statistician-register"
PERIOD = "#periodAdministrationCard"
STATE_BUTTONS_FROM = "#statPossessionButtons"


class Walk:
    def __init__(self, page: Page, base: str) -> None:
        self.page = page
        self.base = base
        self.count = 0
        self.log: list[dict] = []
        self.dialogs: list[str] = []
        page.on("dialog", self._dialog)

    def _dialog(self, dialog) -> None:
        self.dialogs.append(f"{dialog.type}: {dialog.message}")
        dialog.accept()

    # ---- capture -------------------------------------------------------
    def state(self) -> dict:
        return self.page.evaluate(STATE_SUMMARY)

    def _path(self, name: str) -> Path:
        self.count += 1
        return SHOTS / f"{self.count:02d}_{name}.png"

    def _record(self, path: Path) -> None:
        entry = {"file": path.name, **self.state()}
        if self.dialogs:
            entry["dialogs"] = self.dialogs[:]
            self.dialogs.clear()
        self.log.append(entry)
        print(json.dumps(entry), flush=True)

    def shot(self, name: str, target: str | None = None) -> None:
        self.page.wait_for_timeout(500)
        path = self._path(name)
        if target:
            self.page.locator(target).first.screenshot(path=str(path))
        else:
            self.page.screenshot(path=str(path))
        self._record(path)

    def region(self, name: str, top: str, bottom: str) -> None:
        """Capture the console from the top of one element to the bottom of another."""
        self.page.wait_for_timeout(500)
        box = self.page.evaluate(
            """([a, b]) => { const r1 = document.querySelector(a).getBoundingClientRect();
                 const r2 = document.querySelector(b).getBoundingClientRect();
                 const c = document.querySelector('#statisticianModule .statistician-console').getBoundingClientRect();
                 return {x: c.left + scrollX, y: r1.top + scrollY - 8, width: c.width,
                         height: r2.bottom - r1.top + 16}; }""",
            [top, bottom],
        )
        path = self._path(name)
        self.page.screenshot(path=str(path), full_page=True, clip=box)
        self._record(path)

    def top_half(self, name: str) -> None:
        self.region(name, "#statisticianModule .statistician-console > .section-heading-row", CLOCK)

    # ---- UI helpers ----------------------------------------------------
    def click(self, selector: str, wait: int = 900) -> None:
        self.page.locator(selector).first.click()
        self.page.wait_for_timeout(wait)

    def team_button(self, team: str, label: str) -> None:
        self.click(f"#statisticianControls article[data-team={team}] button:text-is('{label}')", 1500)

    def slider(self, element_id: str, coord: int) -> None:
        # Same events a drag fires: input while moving, change on release.
        self.page.evaluate(
            """([id, v]) => { const el = document.getElementById(id);
                 el.value = v; el.dispatchEvent(new Event('input', {bubbles: true}));
                 el.dispatchEvent(new Event('change', {bubbles: true})); }""",
            [element_id, coord],
        )
        self.page.wait_for_timeout(150)

    def jersey(self, element_id: str, number: str) -> None:
        self.page.fill(f"#{element_id}", "")
        self.page.type(f"#{element_id}", number, delay=60)
        self.page.wait_for_timeout(250)

    def check(self, element_id: str) -> None:
        self.page.locator(f"#{element_id}").check()
        self.page.wait_for_timeout(200)

    def select(self, element_id: str, value: str) -> None:
        self.page.select_option(f"#{element_id}", value)
        self.page.wait_for_timeout(250)

    def record_play(self) -> None:
        self.click("#playEntryModal button.primary:text-is('Record Play')", 2200)
        if self.page.is_visible("#playEntryModal"):
            message = self.page.locator("#playEntryMessage").inner_text()
            raise RuntimeError(f"Play not recorded: {message}")

    def period(self, label: str, wait: int = 2200) -> None:
        self.click(f"#periodAdministrationCard button:text-is('{label}')", wait)
        if self.page.is_visible("#eventConfirmModal"):
            self.shot(f"confirm_{label.lower().replace(' ', '_')}", "#eventConfirmModal .event-confirm-sheet")
            self.click("#eventConfirmAccept", wait)


# ---- play helpers ---------------------------------------------------------

def run_play(w: Walk, team: str, carrier: str, end: int, *, shot: str | None = None,
             fumble_lost: bool = False, turnover_at: int | None = None,
             recovered_by: str = "", kneel: bool = False) -> None:
    w.team_button(team, "Run")
    w.jersey("playBallCarrier", carrier)
    if kneel:
        w.check("playKneel")
    w.slider("playEndCoord", end)
    if fumble_lost:
        w.check("playFumbleLost")
        w.slider("playTurnoverCoord", turnover_at)
        w.jersey("playReturner", recovered_by)
        w.slider("playEndCoord", end)
    if shot:
        w.shot(shot, PLAY_SHEET)
    w.record_play()


def pass_play(w: Walk, team: str, passer: str, outcome: str, end: int | None = None, *,
              receiver: str = "", sacker: str = "", picked_at: int | None = None,
              returner: str = "", shot: str | None = None) -> None:
    w.team_button(team, "Pass")
    w.jersey("playPasser", passer)
    w.select("playPassOutcome", outcome)
    if receiver:
        w.jersey("playReceiver", receiver)
    if sacker:
        w.jersey("playSacker", sacker)
    if picked_at is not None:
        w.slider("playTurnoverCoord", picked_at)
        w.jersey("playReturner", returner)
    if end is not None:
        w.slider("playEndCoord", end)
    if shot:
        w.shot(shot, PLAY_SHEET)
    w.record_play()


def kick_play(w: Walk, team: str, kind: str, kicker: str, landing: int, end: int | None = None, *,
              returner: str = "", touchback: bool = False, fair_catch: bool = False,
              shot: str | None = None) -> None:
    if kind == "kickoff":
        w.click("#statisticianKickoffActions button", 1500)
    else:
        w.team_button(team, "Punt")
    w.jersey("playKicker", kicker)
    w.slider("playLandingCoord", landing)
    if returner:
        w.jersey("playReturner", returner)
    w.slider("playEndCoord", landing if end is None else end)
    if touchback:
        w.check("playTouchback")
    if fair_catch:
        w.check("playFairCatch")
    if shot:
        w.shot(shot, PLAY_SHEET)
    w.record_play()


def automation(w: Walk, *, selects: list[tuple[str, str]] = (), inputs: list[tuple[str, str]] = (),
               shot: str | None = None) -> None:
    w.page.wait_for_selector("#automationEventModal:not(.hidden)")
    for element_id, value in selects:
        w.select(element_id, value)
    for element_id, value in inputs:
        w.page.fill(f"#{element_id}", value)
    if shot:
        w.shot(shot, AUTO_SHEET)
    w.click("#automationEventModal button.primary", 2400)
    if w.page.is_visible("#automationEventModal"):
        message = w.page.locator("#automationEventMessage").inner_text()
        raise RuntimeError(f"Event not recorded: {message}")


def try_kick(w: Walk, outcome_button: str, kicker: str, shot: str) -> None:
    w.click(f"#statisticianTryActions button:text-is('{outcome_button}')", 1500)
    automation(w, selects=[("automationKickerNumber", kicker)], shot=shot)


def try_two_point(w: Walk, outcome_button: str, scorer: str, play_type: str, shot: str,
                  passer: str = "") -> None:
    w.click(f"#statisticianTryActions button:text-is('{outcome_button}')", 1500)
    selects = [("automationPlayType", play_type), ("automationScorerNumber", scorer)]
    if passer:
        selects.append(("automationPasserNumber", passer))
    automation(w, selects=selects, shot=shot)


def field_goal(w: Walk, team: str, kicker: str, outcome: str, distance: str, shot: str) -> None:
    w.team_button(team, "FG")
    automation(w, selects=[("automationKickerNumber", kicker), ("automationKickOutcome", outcome)],
               inputs=[("automationFgDistance", distance)], shot=shot)


# ---- phases ---------------------------------------------------------------

def phase_pregame(w: Walk, pin: str) -> None:
    p = w.page
    p.goto(w.base + "/?connect=1")
    p.wait_for_timeout(1500)
    p.fill("#loginPin", pin)
    w.shot("login", "#loginPanel")
    w.click("#loginPanel button.primary", 2500)
    w.shot("choose_console", "#connectionRoleModal .event-confirm-sheet")
    w.click("#connectionRoleModal button:text-is('Statistician')", 2500)
    w.shot("pregame_overview")
    w.region("pregame_lower", STATE_BUTTONS_FROM, PERIOD)
    w.click("#statisticianCoinTossButton", 1000)
    w.select("coinTossWinner", "visitor")
    w.select("coinTossElection", "defer")
    w.shot("coin_toss_form", "#coinTossModal .event-confirm-sheet")
    w.click("#coinTossModal button.primary", 2000)
    w.top_half("coin_toss_saved")


def phase_opening_kickoff(w: Walk) -> None:
    # Riverside kicks from RIGHT 40; ball lands at LEFT 5; Northgate #22 returns it to LEFT 30.
    w.click("#statisticianKickoffActions button", 1500)
    w.shot("kickoff_form_empty", PLAY_SHEET)
    w.jersey("playKicker", "15")
    w.jersey("playReturner", "22")
    w.slider("playLandingCoord", 5)
    w.slider("playEndCoord", 30)
    w.shot("kickoff_form_filled", PLAY_SHEET)
    w.record_play()
    w.top_half("after_opening_kickoff")


def phase_q1_plays(w: Walk) -> None:
    # Northgate ball at LEFT 30, driving right. 1st & 10.
    run_play(w, "home", "22", 36, shot="run_form")
    w.top_half("after_run")
    w.shot("register_after_run", REGISTER)
    # A mis-keyed play (wrong end spot), then Undo Last Event.
    run_play(w, "home", "22", 52)
    w.region("mistake_recorded", SCOREBOARD, ".statistician-action-bar")
    w.click("#statisticianModule .statistician-action-bar button:text-is('Undo Last Event')", 2200)
    w.region("after_undo", SCOREBOARD, ".statistician-action-bar")
    pass_play(w, "home", "7", "complete", 48, receiver="4", shot="pass_complete_form")
    w.shot("after_pass_complete", SCOREBOARD)
    pass_play(w, "home", "7", "incomplete", receiver="11", shot="pass_incomplete_form")
    w.shot("after_pass_incomplete", SCOREBOARD)
    pass_play(w, "home", "7", "sack", 42, sacker="99", shot="pass_sack_form")
    w.shot("after_sack", SCOREBOARD)
    # Riverside jumps offside: the penalty is entered on the team that committed it.
    w.team_button("visitor", "Penalty")
    w.page.evaluate("""() => { const sel = document.getElementById('penaltyName');
        const opt = [...sel.options].find(o => /offside|encroach/i.test(o.value));
        if (opt) { sel.value = opt.value; penaltySelectionChanged(); } }""")
    w.shot("penalty_form", PENALTY_SHEET)
    w.click("#penaltyModal button.primary", 2200)
    w.shot("after_penalty", SCOREBOARD)
    # Clock: there is no timeout button -- stop the clock.
    w.click(f"{CLOCK} button:text-is('Start')", 2600)
    w.shot("clock_running", CLOCK)
    w.click(f"{CLOCK} button:text-is('Stop')", 1000)
    w.shot("clock_stopped", CLOCK)
    # Interception: picked at RIGHT 40 by Riverside #24, returned to RIGHT 45.
    pass_play(w, "home", "7", "interception", 55, picked_at=60, returner="24",
              shot="pass_interception_form")
    w.top_half("after_interception")
    # Riverside run to the 50, fumble lost; Northgate #52 recovers and returns to RIGHT 47.
    run_play(w, "visitor", "5", 53, fumble_lost=True, turnover_at=50, recovered_by="52",
             shot="fumble_lost_form")
    w.top_half("after_fumble")
    # Northgate punts from RIGHT 47; lands RIGHT 10; Riverside #1 returns to RIGHT 15.
    kick_play(w, "home", "punt", "3", 90, 85, returner="1", shot="punt_form")
    w.top_half("after_punt")
    w.shot("register_q1", REGISTER)


def phase_unresolved(w: Walk) -> None:
    # Riverside ball at RIGHT 15 driving left. #22 is a NORTHGATE number.
    w.team_button("visitor", "Run")
    w.jersey("playBallCarrier", "22")
    w.slider("playEndCoord", 80)
    w.shot("mismatch_run_form", PLAY_SHEET)
    w.record_play()
    w.top_half("mismatch_after")
    # #44 is on nobody's roster.
    w.team_button("visitor", "Pass")
    w.jersey("playPasser", "12")
    w.jersey("playReceiver", "44")
    w.slider("playEndCoord", 72)
    w.shot("offroster_pass_form", PLAY_SHEET)
    w.record_play()
    w.shot("register_unresolved", REGISTER)
    w.page.locator("#statisticianEventRegister").get_by_text("#22 run for 5 yards").first.click()
    w.page.wait_for_timeout(700)
    w.shot("unresolved_play_detail", REGISTER)


def phase_scoring_first_half(w: Walk) -> None:
    # Riverside TD run from RIGHT 28 into the LEFT end zone.
    run_play(w, "visitor", "5", 0, shot="td_run_form")
    w.top_half("td_try_pending")
    try_two_point(w, "2PT GOOD", "5", "rush", "two_point_run_form")
    w.top_half("after_two_point_run")
    kick_play(w, "visitor", "kickoff", "15", 100, touchback=True, shot="kickoff_touchback_form")
    w.top_half("after_touchback")


def phase_quarter_two(w: Walk) -> None:
    w.shot("period_card_q1", PERIOD)
    w.period("End Quarter")
    w.top_half("after_end_q1")
    w.shot("period_card_q2", PERIOD)


def own(w: Walk, team: str, yards: int) -> int:
    """Slider coordinate `yards` from `team`'s own goal line (0-100, LEFT goal = 0)."""
    direction = w.page.evaluate(f"currentState.{team}_direction")
    return yards if direction == "right" else 100 - yards


def phase_scoring_q2(w: Walk) -> None:
    # Northgate ball at its own 20: 80-yard TD pass to #88.
    pass_play(w, "home", "7", "complete", own(w, "home", 100), receiver="88", shot="td_pass_form")
    w.top_half("td_pass_try_pending")
    try_kick(w, "XP GOOD", "3", "xp_good_form")
    w.top_half("after_xp_good")
    # Northgate kicks off; Riverside #1 returns from its 5 to its 25.
    kick_play(w, "home", "kickoff", "3", own(w, "visitor", 5), own(w, "visitor", 25),
              returner="1", shot="kickoff_return_form")
    # Riverside punts; Northgate fair-catches at its own 2.
    kick_play(w, "visitor", "punt", "15", own(w, "home", 2), returner="21", fair_catch=True,
              shot="punt_fair_catch_form")
    w.top_half("after_fair_catch")
    # Northgate is tackled in its own end zone: safety.
    run_play(w, "home", "22", own(w, "home", 0), shot="safety_run_form")
    w.top_half("after_safety_free_kick_pending")
    # Free kick from Northgate's 20; Riverside #1 returns it.
    kick_play(w, "home", "kickoff", "3", own(w, "visitor", 30), own(w, "visitor", 40),
              returner="1", shot="free_kick_form")
    w.top_half("after_free_kick")
    # Riverside kneels to run out the half.
    run_play(w, "visitor", "12", own(w, "visitor", 38), kneel=True, shot="kneel_form")
    w.shot("register_q2", REGISTER)


def phase_halftime(w: Walk) -> None:
    w.period("End Quarter")
    w.top_half("after_end_q2")
    w.shot("period_card_end_q2", PERIOD)


def phase_second_half_kickoff(w: Walk) -> None:
    w.period("Start Second Half")
    w.top_half("second_half_kickoff_pending")
    # Scenario: the teams did NOT simply mirror the first half -- on the field Northgate
    # is kicking the other way. Spot it in the kickoff form, close it, flip the direction.
    w.click("#statisticianKickoffActions button", 1500)
    w.shot("direction_wrong_kickoff_form", PLAY_SHEET)
    w.click("#playEntryModal button:text-is('Cancel')", 800)
    w.region("direction_before_fix", "#statisticianFieldPosition", "#statisticianModule .rules-card:has(#driveDirLeft)")
    current = w.page.evaluate("currentState[currentState.possession + '_direction']")
    flip = "Left" if current == "right" else "Right"
    w.click(f"#statisticianDrive{flip}", 2200)
    w.region("direction_after_fix", "#statisticianFieldPosition", "#statisticianModule .rules-card:has(#driveDirLeft)")
    w.top_half("direction_fixed_kickoff_pending")
    kick_play(w, "home", "kickoff", "3", own(w, "visitor", 8), own(w, "visitor", 32),
              returner="1", shot="second_half_kickoff_form")
    w.top_half("after_second_half_kickoff")


def phase_q3_q4(w: Walk) -> None:
    # Q3: Riverside 68-yard TD pass, 2PT pass fails.
    pass_play(w, "visitor", "12", "complete", own(w, "visitor", 100), receiver="80")
    w.top_half("q3_td_pass_try_pending")
    try_two_point(w, "2PT FAILED", "85", "reception", "two_point_pass_failed_form", passer="12")
    w.top_half("after_two_point_failed")
    kick_play(w, "visitor", "kickoff", "15", own(w, "home", 100), touchback=True)
    # Northgate drives to the Riverside 15 and kicks a 32-yard field goal.
    pass_play(w, "home", "7", "complete", own(w, "home", 85), receiver="17")
    field_goal(w, "home", "3", "made", "32", "fg_good_form")
    w.top_half("after_fg_good")
    kick_play(w, "home", "kickoff", "3", own(w, "visitor", 0), touchback=True)
    w.shot("period_card_end_q3", PERIOD)
    w.period("End Quarter")
    w.top_half("after_end_q3")
    # Q4: Riverside punts, Northgate returns to midfield and runs it in.
    kick_play(w, "visitor", "punt", "15", own(w, "home", 15), own(w, "home", 50), returner="21")
    run_play(w, "home", "22", own(w, "home", 100))
    w.top_half("q4_td_try_pending")
    try_kick(w, "XP NO GOOD", "3", "xp_no_good_form")
    w.top_half("after_xp_no_good_tied")
    kick_play(w, "home", "kickoff", "3", own(w, "visitor", 0), touchback=True)
    run_play(w, "visitor", "12", own(w, "visitor", 18), kneel=True)
    w.shot("register_q4", REGISTER)


def phase_overtime(w: Walk) -> None:
    w.shot("period_card_end_regulation", PERIOD)
    w.period("End Quarter")
    w.top_half("after_end_regulation")
    # Riverside gets the first overtime possession at Northgate's 10.
    spot = w.page.evaluate(f"spotFromCoord({own(w, 'visitor', 90)})")
    w.select("overtimePossession", "visitor")
    w.page.fill("#overtimeSpot", spot)
    w.shot("period_card_overtime_setup", PERIOD)
    w.period("Start Overtime")
    w.top_half("overtime_started")
    field_goal(w, "visitor", "15", "no_good", "27", "ot_fg_missed_form")
    w.top_half("after_ot_fg_missed")
    # Northgate's overtime possession: put the ball at Riverside's 10, 1st & 10.
    if w.state()["possession"] != "home":
        w.click("#statPossessionButtons button[data-value=home]", 1500)
    w.slider("statisticianFieldSlider", own(w, "home", 90))
    w.page.wait_for_timeout(1500)
    w.click("#statDownButtons button[data-value='1st']", 1200)
    w.region("ot_second_possession_setup", STATE_BUTTONS_FROM, "#statisticianFieldPosition")
    field_goal(w, "home", "3", "made", "27", "ot_fg_good_form")
    w.top_half("after_ot_fg_good")
    w.period("End Quarter")
    w.top_half("overtime_period_complete")
    w.shot("period_card_overtime_complete", PERIOD)


def phase_final(w: Walk) -> None:
    w.shot("register_before_final", REGISTER)
    w.period("Confirm Final", 3000)
    w.shot("final_page_header", "header, .suite-header, .app-header")
    w.top_half("final_console")
    w.shot("period_card_final", PERIOD)
    w.shot("register_final", REGISTER)
    stats = w.page.evaluate("fetch('/api/statistics').then(r => r.json())")
    (GUIDE / "capture_statistics.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")


PHASES = ["pregame", "opening_kickoff", "q1_plays", "unresolved", "scoring_first_half",
          "quarter_two", "scoring_q2", "halftime", "second_half_kickoff", "q3_q4", "overtime",
          "final"]


def main() -> None:
    runtime = Path(sys.argv[1]).resolve()
    port = int(sys.argv[2])
    until = next((a.split("=", 1)[1] for a in sys.argv[3:] if a.startswith("--until=")), PHASES[-1])
    pin = (runtime / "demo_pin.txt").read_text().strip()
    SHOTS.mkdir(parents=True, exist_ok=True)
    for old in SHOTS.glob("*.png"):
        old.unlink()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1.5)
        w = Walk(page, f"http://127.0.0.1:{port}")
        try:
            for name in PHASES:
                if name == "pregame":
                    phase_pregame(w, pin)
                else:
                    globals()[f"phase_{name}"](w)
                if name == until:
                    break
        except Exception:
            page.screenshot(path=str(GUIDE / "failure.png"))
            raise
        finally:
            (GUIDE / "capture_log.json").write_text(json.dumps(w.log, indent=2), encoding="utf-8")
            browser.close()


if __name__ == "__main__":
    main()
