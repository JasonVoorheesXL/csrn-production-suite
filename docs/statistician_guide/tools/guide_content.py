"""Text of the CSRN Statistician Field Guide (football).

Every behaviour described here was observed while walkthrough.py drove the
real Statistician Console through demo broadcast FB-DEMO-GUIDE-001; see
capture_log.json for the game state behind each screenshot.

Block types are rendered by render_pdf.py:
  ("section", number, title, lede)   dark phase opener (starts a new page)
  ("h2"|"h3"|"p", html)
  ("steps"|"bullets", [html, ...])
  ("fields", [(name, html), ...])    field-by-field explanation
  ("table", [head...], [[cell...], ...])
  ("callout", tip|warn|stop|rule, title, html)
  ("fig", slug, caption[, full|narrow|small])
  ("side", slug, caption, [blocks])  tall form screenshot beside its explanation
  ("pair", (slug, caption), (slug, caption))
  ("keep", [blocks]) / ("break",)
"""

from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_VERSION = next(
    line.split(" —")[0].strip()
    for line in (_REPO / "VERSION.txt").read_text(encoding="utf-8").splitlines()
    if line.startswith("Version ")
)


def ui(label: str, tone: str = "") -> str:
    return f'<span class="ui {tone}">{label}</span>'


COVER_LEDE = (
    "You've been handed the stat chair. This guide walks you through a complete football game on "
    "CSRN's Statistician Console &mdash; from the moment your screen opens to the moment the game is "
    "closed out as Final &mdash; one phase at a time, explaining every button and field the first "
    "time you touch it."
)
COVER_META = (
    f"Every screenshot was captured from the real Statistician Console (CSRN Production Suite {_VERSION}) driving a "
    "fictional demo game: <b style='color:#fff'>Northgate Falcons vs. Riverside Otters</b>, "
    "broadcast FB-DEMO-GUIDE-001. All schools, players and numbers are invented.<br>"
    "Covers the Statistician screen only. Broadcast creation, rosters, OBS and the "
    "Broadcaster/Director consoles are handled by your producer."
)

SECTIONS_INDEX = [
    ("0", "Before You Start: How This Screen Thinks", ""),
    ("1", "Pregame: Opening Your Screen & the Coin Toss", ""),
    ("2", "The Opening Kickoff", ""),
    ("3", "Live Play Entry: The 1st Quarter", ""),
    ("4", "Jerseys That Don't Match (Unresolved Players)", ""),
    ("5", "Scoring Plays: TD, PAT, 2-Point, FG, Safety", ""),
    ("6", "Ending a Quarter", ""),
    ("7", "Halftime", ""),
    ("8", "The Second-Half Kickoff", ""),
    ("9", "4th Quarter & Overtime", ""),
    ("10", "End of Game: Confirm Final", ""),
    ("A", "Quick Reference Card", ""),
]

INTRO = [
    ("h2", "Your job in one sentence"),
    ("p", "You tell the system <b>who had the ball, who touched it, and where the ball ended up</b>. "
          "The system works out everything else &mdash; yards gained, down and distance, first downs, "
          "touchdowns, safeties, possession changes and the score &mdash; and pushes it to the broadcast "
          "graphics and the official stats."),
    ("callout", "rule", "THE THREE GOLDEN RULES",
     "<b>1. Keep up with the game.</b> Enter each play as soon as the ball is dead. Speed beats perfection; "
     "almost anything can be fixed later.<br>"
     "<b>2. Never stop to troubleshoot live.</b> If a jersey won't match or something looks odd, record the "
     "play anyway, jot down the play number, and tell your producer at the next break.<br>"
     "<b>3. Mistake? Use Undo.</b> If you notice a wrong entry right away, " + ui("Undo Last Event", "gold") +
     " removes it cleanly. Then enter it again correctly."),
    ("h2", "Field-spot language: LEFT and RIGHT, not team names"),
    ("p", "The screen describes the field as you see it from the press box: the <b>LEFT GOAL</b> line, the "
          "<b>50</b>, and the <b>RIGHT GOAL</b> line. A spot such as <code>LEFT 30</code> means &ldquo;the 30-yard "
          "line on the left half of the field.&rdquo; Arrows such as <b>R &larr;</b> or <b>N &rarr;</b> show which way "
          "a team is driving. Teams switch ends every quarter; the screen flips the arrows for you."),
    ("h2", "What you'll need"),
    ("bullets", [
        "The 6-digit <b>operator PIN</b> &mdash; your producer gives it to you.",
        "The phone, tablet or laptop you'll enter stats on, connected to the same network as the production laptop.",
        "Both teams' printed rosters (jersey numbers), and a pen &mdash; for noting plays that need a follow-up fix.",
    ]),
]

BODY = [
    # ------------------------------------------------------------------ 0
    ("section", "0", "Before You Start: How This Screen Thinks",
     "Two ideas make the whole console make sense: you are the official source of game data, "
     "and every play is entered as a <i>start spot &rarr; end spot</i> movement."),
    ("h2", "You are the authoritative source"),
    ("p", "When the producer hands control to the Statistician Console, the broadcaster's game-data buttons "
          "lock and your entries become the official record. That's why the header of your screen says "
          + ui("ACTIVE") + " and &ldquo;Statistician Console is the authoritative game-data source.&rdquo; If it "
          "ever says DISABLED instead, stop and tell your producer &mdash; your entries would be blocked."),
    ("h2", "Every play is a movement on the field"),
    ("p", "For runs, passes, punts and kicks you set where the ball <b>ended</b> on a slider. The start "
          "spot is already filled in from the previous play. The system subtracts the two to get yards, then "
          "applies the football rules: reach the line to gain and it's a first down; reach the end zone "
          "you're attacking and it's a touchdown; get pushed back into your own end zone and it's a safety. "
          "You never type yards and you never press a &ldquo;first down&rdquo; button for normal plays."),
    ("h2", "The screen guides you through special moments"),
    ("p", "After a touchdown the screen shows a <b>TRY REQUIRED</b> panel; after a score or at the start of a "
          "half it shows <b>KICKOFF REQUIRED</b>. While one of those is showing, the normal Run/Pass "
          "buttons are hidden or blocked, so you can't accidentally skip the try or the kickoff. "
          "Follow the panel at the top and you will always be on the right next step."),
    ("table", ["Color on screen", "What it means"], [
        ["<b style='color:#157347'>Green</b> jersey name under a number", "Jersey found on that team's roster &mdash; player resolved."],
        ["<b style='color:#b07d10'>Amber</b> &ldquo;Not found on active roster&rdquo;", "Jersey not on that team's roster. The play still records; see Phase 4."],
        ["Green-outlined team card", "That team is on <b>OFFENSE</b> (has the ball)."],
        ["Gold-outlined team card", "That team is on <b>DEFENSE</b>."],
        ["Red " + ui("Record Play", "red") + " / " + ui("Confirm Event", "red") + " buttons", "The button that actually saves. Nothing is saved until you press it."],
    ]),

    # ------------------------------------------------------------------ 1
    ("section", "1", "Pregame: Opening Your Screen & the Coin Toss",
     "The broadcast is already created and live. Here's how to get to your console, confirm you're on "
     "the right game, and record the coin toss."),
    ("h2", "Step 1 &mdash; Log in and choose the Statistician console"),
    ("pair", ("login", "Operator Login. Type the 6-digit PIN your producer gives you, then press Unlock."),
             ("choose_console", "Choose Console: pick Statistician.")),
    ("steps", [
        "Open the address your producer gives you (it ends in <code>:5050</code>). You'll see <b>Operator Login</b>.",
        "Type the PIN in the <b>PIN</b> box. The dots hide the digits. Press " + ui("Unlock", "red") + ".",
        "If you opened the connection link or QR code from your producer, a <b>Choose Console</b> pop-up appears: press "
        + ui("Statistician") + ". (Broadcaster is the play-by-play operator's console; Read-Only Monitor can't change "
        "anything.) No pop-up? Press " + ui("Switch Console") + " in the top-right of the header to bring it up.",
    ]),
    ("h2", "Step 2 &mdash; Tour the console and confirm the game"),
    ("fig", "pregame_overview", "The Statistician Console before kickoff. The header shows the matchup and the LIVE badge; "
     "the console itself starts with the ACTIVE badge, possession strip, coin-toss panel, scoreboard and team cards."),
    ("h3", "Confirm you have the right game"),
    ("bullets", [
        "<b>Header, top right:</b> the matchup &mdash; here <i>Northgate vs Riverside</i>. It must match tonight's game.",
        "<b>Badge next to it:</b> " + ui("LIVE", "green") + " means the broadcast has been started by the producer.",
        "<b>Scoreboard strip:</b> home team on the left (Northgate), visitor on the right (Riverside), both 0, <b>Q1</b>.",
        "<b>Statistician Console badge:</b> " + ui("ACTIVE") + ", with the line &ldquo;Statistician Console is the "
        "authoritative game-data source.&rdquo;",
    ]),
    ("callout", "stop", "WRONG GAME, OR NOT ACTIVE?",
     "If the team names are wrong, the badge says DISABLED, or the status line says &ldquo;Enable the Statistician "
     "Console from Command Center,&rdquo; don't enter anything. Tell your producer &mdash; only they can load the "
     "right game or hand control to you."),
    ("h3", "What each area of the console does"),
    ("fields", [
        ("Status line", "One-line confirmation of who controls game data, plus green/red notices after every action "
                        "(&ldquo;Play recorded.&rdquo;, or why something was blocked)."),
        ("&#127944; POSSESSION strip", "Who has the ball, the ball spot, and down &amp; distance. Your at-a-glance sanity check."),
        ("Special-moment panel", "Appears only when something must happen next: <b>OPENING COIN TOSS</b>, "
                                 "<b>KICKOFF REQUIRED</b>, <b>TRY REQUIRED</b>."),
        ("Scoreboard", "Home score, down &amp; distance and quarter, visitor score. Updated by the system &mdash; you never type scores."),
        ("Team cards", "One per team. Play buttons live here: " + ui("Run") + " " + ui("Pass") + " " + ui("Punt") + " "
                       + ui("TD") + " " + ui("FG") + " " + ui("1st Down") + " " + ui("Penalty") + " on the offense; "
                       + ui("Turnover") + " " + ui("Penalty") + " on the defense. Buttons change as possession changes."),
        ("Game Clock", "Start/Stop and adjust the clock (Phase 3)."),
        ("Action bar", ui("Undo Last Event", "gold") + " " + ui("Restore Last Undone") + " " + ui("Quick Edit Last Play", "red") + " "
                       + ui("Record Ejection") + " " + ui("Play Commercial", "green") + "."),
        ("Lower controls", "Manual corrections: Possession, Quarter, Down &amp; Distance, Field Position, Drive "
                           "Direction, plus <b>Period Administration</b> (quarters, halftime, overtime, Final) and the "
                           "<b>Play Register</b> &mdash; the list of every play you've entered."),
    ]),
    ("fig", "pregame_lower", "Lower half of the console: manual correction buttons, the Field Position slider, "
     "Drive Direction, Game Context and Period Administration. You'll mostly use Period Administration.", "narrow"),
    ("callout", "tip", "HANDS OFF THE CORRECTION BUTTONS",
     "Possession, Quarter, Down &amp; Distance and Field Position are <b>manual overrides</b>. In a normal game the "
     "system keeps them right for you. You'll use them only for overtime setup (Phase 9) or if your producer asks."),
    ("h2", "Step 3 &mdash; Record the opening coin toss"),
    ("side", "coin_toss_form", "Opening Coin Toss form: Riverside (visitor) won and deferred.", [
        ("p", "Before the first play the console shows <b>OPENING COIN TOSS &mdash; COIN TOSS REQUIRED</b>. "
              "Press " + ui("Enter Coin Toss", "red") + "."),
        ("fields", [
            ("Who won the coin toss?", "Home or Visitor."),
            ("What did they elect to do?", "<b>Receive</b>, <b>Defer</b>, <b>Kick</b>, or <b>Defend a direction</b>."),
            ("Opening receiving team", "Leave on <i>Auto from election</i>; it's worked out from the choice above."),
            ("Opening receiver drives", "Which end zone the receiving team attacks first, as seen from your seat: "
                                        "<b>RIGHT &rarr;</b> or <b>&larr; LEFT</b>."),
            ("Second-half receiving team", "Leave on <i>Auto</i>. It's used automatically at halftime."),
        ]),
        ("p", "The grey summary under the fields restates the result in plain English &mdash; read it before saving. "
              "Press " + ui("Save Coin Toss", "red") + "."),
    ]),
    ("fig", "coin_toss_saved", "After saving: the coin toss reads COMPLETE, the green notice confirms who kicks and who "
     "receives each half, and a KICKOFF REQUIRED panel appears. The Run/Pass buttons stay hidden until the kickoff is entered."),
    ("callout", "tip", "MADE A MISTAKE ON THE TOSS?",
     ui("Edit Coin Toss") + " stays available until the first play is recorded."),

    # ------------------------------------------------------------------ 2
    ("section", "2", "The Opening Kickoff",
     "Every kick &mdash; kickoff, free kick, punt &mdash; uses the same play form: a kicker, a returner, and "
     "three spots on the field."),
    ("p", "In the <b>KICKOFF REQUIRED &mdash; RIVERSIDE</b> panel, press " + ui("Open Detailed Kickoff", "red") +
          ". The kickoff play form opens with the kicking team already chosen."),
    ("side", "kickoff_form_empty", "The kickoff form as it opens. Riverside kicks from RIGHT 40, driving &larr;.", [
        ("fields", [
            ("Title &amp; context line", "<i>Kickoff &mdash; Riverside</i>, then the current down, ball spot and drive direction."),
            ("Drive badge <b>&larr; R</b>", "Riverside is driving toward the LEFT goal."),
            ("Start Spot", "Where the ball was kicked from. Filled in and locked. Use " + ui("Correct Start Spot") +
                           " only if it's genuinely wrong (e.g. after a kickoff penalty)."),
            ("Landed / Caught Spot", "Where the kick was caught or first touched. Drag the slider."),
            ("End Spot", "Where the return ended (ball dead). Drag the slider; " + ui("End &minus;1") + " / " +
                         ui("End +1") + " fine-tune one yard at a time."),
            ("Kicker / Punter Jersey", "Kicking team's jersey number."),
            ("Returner Jersey", "Receiving team's jersey number."),
            ("Checkboxes", "<b>Fumble</b>, <b>Fumble lost</b>, <b>Out of bounds</b>, <b>Touchback</b>. Tick only what happened."),
            ("Notes", "Optional free text."),
            ("Preview line", "Live calculation, e.g. <i>Kick distance: 55 yards &middot; Return: 25 yards.</i>"),
        ]),
    ]),
    ("side", "kickoff_form_filled", "Filled in: lands at LEFT 5, returned by #22 to LEFT 30.", [
        ("h3", "Entering the kick"),
        ("steps", [
            "Type the kicker's number (<b>15</b>) in <b>Kicker / Punter Jersey</b>.",
            "Type the returner's number (<b>22</b>) in <b>Returner Jersey</b>. Watch the line under the box: "
            "<b style='color:#157347'>#22 &mdash; Devin Okafor</b> in green means the player was found on Northgate's roster.",
            "Drag <b>Landed / Caught Spot</b> to where it was fielded &mdash; <code>LEFT 5</code>.",
            "Drag <b>End Spot</b> to where the returner went down &mdash; <code>LEFT 30</code>.",
            "Check the preview: <i>Kick distance: 55 yards &middot; Return: 25 yards.</i> Press " + ui("Record Play", "red") + ".",
        ]),
        ("callout", "tip", "TOUCHBACK?",
         "Drag Landed to the end zone and tick <b>Touchback</b>; the system places the ball at the 20 (Phase 5 shows one)."),
    ]),
    ("fig", "after_opening_kickoff", "After the kickoff: &ldquo;Play recorded.&rdquo;, the special panel is gone, "
     "Northgate is on offense (green card) with 1st &amp; 10 at LEFT 30, and the play buttons have appeared."),

    # ------------------------------------------------------------------ 3
    ("section", "3", "Live Play Entry: The 1st Quarter",
     "Runs, passes (complete, incomplete, sack, interception), penalties, the clock, fumbles and punts &mdash; "
     "each shown with the form, then the result."),
    ("h2", "Picking the right button"),
    ("p", "Always use the buttons on the card of the team that <b>had the ball when the play started</b> (green "
          "outline, OFFENSE). The one exception is " + ui("Penalty") + ": use it on the card of the team that "
          "<b>committed</b> the foul. The defense card only offers " + ui("Turnover") + " and " + ui("Penalty") + "."),
    ("h2", "Run"),
    ("side", "run_form", "Run &mdash; Northgate. #22 resolves to Devin Okafor; End Spot dragged to LEFT 36.", [
        ("steps", [
            "On the offense card press " + ui("Run") + ".",
            "Type the ball carrier in <b>Ball Carrier Jersey</b>. Look for the green name.",
            "Drag <b>End Spot</b> to where the runner was downed. The preview says <i>Calculated result: 6 yards.</i>",
            "Tick <b>Out of bounds</b> if he went out (it stops the clock), <b>Kneel</b> for a victory-formation kneel, "
            "or <b>Fumble</b>/<b>Fumble lost</b> if the ball came out (shown later in this phase).",
            "Press " + ui("Record Play", "red") + ".",
        ]),
        ("p", "The form closes and the screen shows <b>Play recorded.</b> The down, distance and ball spot update on their own."),
    ]),
    ("fig", "after_run", "After a 6-yard run: 2nd &amp; 4 at LEFT 36. You didn't type the down or the distance &mdash; the system did."),
    ("fig", "register_after_run", "The Play Register at the bottom of the console lists each play, newest first. "
     "Tap a play to see its full record on the right; Edit is for corrections later.", "narrow"),
    ("h2", "Fixing a mistake right away: Undo Last Event"),
    ("pair", ("mistake_recorded", "Oops &mdash; the end spot was dragged too far, giving a bogus first down."),
             ("after_undo", "After " + "Undo Last Event" + ": the play is removed and the down, distance and spot are restored.")),
    ("p", ui("Undo Last Event", "gold") + " reverses the most recent play or event completely, including any score or "
          "possession change it caused. Your browser first asks <i>&ldquo;Undo this: &hellip;?&rdquo;</i> naming the play "
          "&mdash; check it's the right one and press <b>OK</b>. Then simply enter the play again. " + ui("Restore Last Undone") + " brings back "
          "something you undid by accident. " + ui("Quick Edit Last Play", "red") + " opens the last play's correction form "
          "&mdash; handy for fixing a jersey or spot without undoing."),
    ("callout", "warn", "UNDO ONLY THE MOST RECENT PLAY",
     "Undo always removes the <i>latest</i> event. If the mistake was several plays ago, don't undo a string of good "
     "plays to reach it &mdash; note the play number and let it be fixed after the game."),
    ("h2", "Pass &mdash; complete"),
    ("side", "pass_complete_form", "Pass &mdash; complete from #7 to #4, ending at LEFT 48.", [
        ("fields", [
            ("Passer Jersey", "The quarterback (or whoever threw it)."),
            ("Pass Result", "<b>Complete</b>, <b>Incomplete</b>, <b>Interception</b>, <b>Sack</b> or <b>Spike</b>. "
                            "The form changes to match: different jersey boxes appear for each."),
            ("Receiver Jersey", "Who caught it (or, for an incomplete pass, who it was thrown to)."),
            ("End Spot", "Where the receiver was downed &mdash; not where he caught it."),
        ]),
        ("p", "Press " + ui("Record Play", "red") + ". This 12-yard gain passes the line to gain, so the system awards a "
              "first down automatically."),
    ]),
    ("fig", "after_pass_complete", "1st &amp; 10 at LEFT 48 after the 12-yard completion.", "narrow"),
    ("h2", "Pass &mdash; incomplete"),
    ("side", "pass_incomplete_form", "Incomplete: the End Spot slider locks to the line of scrimmage.", [
        ("p", "Set <b>Pass Result</b> to <b>Incomplete</b>. The End Spot locks, because the ball returns to where the play "
              "started. Enter the passer and the intended receiver, then " + ui("Record Play", "red") + "."),
        ("p", "Result: 2nd &amp; 10, same spot, clock stopped."),
    ]),
    ("fig", "after_pass_incomplete", "Down advances, distance and spot unchanged.", "narrow"),
    ("h2", "Pass &mdash; sack"),
    ("side", "pass_sack_form", "Sack: the Receiver box is replaced by Sack By &mdash; Defender Jersey.", [
        ("p", "Set <b>Pass Result</b> to <b>Sack</b>. Type the defender who made the sack in <b>Sack By &mdash; Defender "
              "Jersey</b> (it resolves against the <i>defense's</i> roster: #99 Hunter Graves). Drag End Spot back to where "
              "the QB went down (LEFT 42), then " + ui("Record Play", "red") + "."),
        ("p", "Result: 3rd &amp; 16 at LEFT 42 (a 6-yard loss). The sack is credited to #99 and counted as a sack, not a pass attempt."),
    ]),
    ("fig", "after_sack", "3rd &amp; 16 after the sack.", "narrow"),
    ("h2", "Penalty"),
    ("side", "penalty_form", "Penalty on Riverside (pressed on the Riverside card): Defensive Offside, 5 yards.", [
        ("fields", [
            ("Unit", "Offensive, Defensive, Special Teams, or General / Other. Pre-set from the button you pressed."),
            ("Penalty", "Pick the foul from the list. Choosing one fills in its standard yardage."),
            ("Yards", "Change only if the officials marked off a different distance."),
            ("Ruling", "<b>Accepted / Enforced</b>, <b>Declined</b>, <b>Offsetting Penalties</b>, or <b>Flag Picked Up</b>."),
            ("Enforcement Spot", "Leave blank to enforce from the current ball spot."),
            ("Checkboxes", "<b>Half the distance</b>, <b>Automatic first down</b>, <b>Loss of down</b>, <b>Retry down</b>, "
                           "<b>Untimed down</b>. Common ones tick themselves (e.g. automatic first down for defensive holding)."),
        ]),
        ("p", "Press " + ui("Record Penalty", "red") + ". The ball moves and the down/distance updates."),
    ]),
    ("fig", "after_penalty", "Riverside offside: 3rd &amp; 16 becomes 3rd &amp; 11 at LEFT 47.", "narrow"),
    ("h2", "The game clock &mdash; and timeouts"),
    ("pair", ("clock_running", "Start runs the clock (shows RUNNING)."),
             ("clock_stopped", "Stop freezes it (shows STOPPED).")),
    ("fields", [
        (ui("Start", "green") + " / " + ui("Stop", "red"), "Run and stop the game clock to match the stadium clock."),
        (ui("&minus;10") + " " + ui("&minus;1") + " " + ui("+1") + " " + ui("+10"), "Nudge the clock by seconds to match the stadium clock."),
        (ui("Set"), "Type an exact time."),
        (ui("Reset 12:00"), "Back to a full 12-minute quarter."),
        (ui("Show / Hide"), "Shows or hides the clock on the broadcast graphic."),
    ]),
    ("callout", "warn", "THERE IS NO TIMEOUT BUTTON",
     "This version of the Statistician Console does not record timeouts. When a team calls timeout, press "
     + ui("Stop", "red") + " so the clock matches the stadium, then carry on. If your producer wants timeouts noted, "
     "type <i>&ldquo;Timeout Riverside&rdquo;</i> in the <b>Notes</b> box of the next play."),
    ("h2", "Interception"),
    ("side", "pass_interception_form", "Interception: picked at RIGHT 40 by #24, returned to RIGHT 45.", [
        ("p", "Set <b>Pass Result</b> to <b>Interception</b>. Two new things appear: an "
              "<b>Interception / Recovery Spot</b> slider and the <b>Returner Jersey</b> box (the defender who picked it off)."),
        ("steps", [
            "Passer Jersey: <b>7</b>.",
            "Drag <b>Interception / Recovery Spot</b> to where the ball was caught (<code>RIGHT 40</code>).",
            "Returner Jersey: <b>24</b> (Riverside's Trent Vaughn).",
            "Drag <b>End Spot</b> to where the return ended (<code>RIGHT 45</code>).",
            "The preview reads <i>Turnover at RIGHT 40 &middot; Return: 5 yards &middot; New possession.</i> " + ui("Record Play", "red") + ".",
        ]),
    ]),
    ("fig", "after_interception", "After the interception: Riverside is now on offense (green card), 1st &amp; 10 at RIGHT 45, "
     "driving &larr;. The cards swapped their buttons automatically."),
    ("h2", "Fumble"),
    ("side", "fumble_lost_form", "Riverside run, fumble lost: Northgate #52 recovers at the 50 and returns to RIGHT 47.", [
        ("p", "Fumbles are entered on the play they happened on (here a " + ui("Run") + " by Riverside #5)."),
        ("fields", [
            ("Fumble", "The ball came out, but the <i>same</i> team kept it. A <b>Fumble Recovered By &mdash; Teammate</b> "
                       "box appears if someone else on offense recovered."),
            ("Fumble lost", "The <i>other</i> team recovered. Ticking it also ticks Fumble."),
            ("Interception / Recovery Spot", "Where the defense recovered (<code>50</code>)."),
            ("Returner Jersey", "The defender who recovered (<b>52</b>)."),
            ("End Spot", "Where the recovery return ended (<code>RIGHT 47</code>)."),
        ]),
        ("p", "Result: possession flips to Northgate, 1st &amp; 10 at RIGHT 47."),
    ]),
    ("fig", "after_fumble", "After the lost fumble: Northgate's ball again."),
    ("h2", "Punt"),
    ("side", "punt_form", "Punt by Northgate #3: lands at RIGHT 10, returned by Riverside #1 to RIGHT 15.", [
        ("p", "Press " + ui("Punt") + " on the kicking team's card. It's the same form as a kickoff, with three punt-only "
              "checkboxes:"),
        ("fields", [
            ("Fair catch", "Returner signalled for a fair catch &mdash; ball is dead where caught."),
            ("Blocked", "The punt was blocked."),
            ("Muffed punt &mdash; kicking team recovered", "Returner muffed it and the kicking team got it back."),
            ("Touchback", "Into the end zone; ball to the 20."),
        ]),
    ]),
    ("fig", "after_punt", "After the punt: Riverside ball, 1st &amp; 10 at RIGHT 15."),
    ("h2", "Reading the Play Register"),
    ("fig", "register_q1", "The 1st-quarter register. The left label (Play 4 &middot; Incomplete Pass, Play 5 &middot; Sack, "
     "Play 7 &middot; Interception) is always right; see the warning below about the description text."),
    ("callout", "warn", "KNOWN DISPLAY QUIRK IN THE PLAY REGISTER",
     "In this version the register's <i>description</i> for incomplete passes, sacks and interceptions can read like a "
     "completion (e.g. <i>&ldquo;#7 Marcus Hale complete to # for &minus;6 yards&rdquo;</i> on the sack), and a run's "
     "description can drop the fumble detail. <b>This is display-only:</b> the play label on the left is correct, the "
     "game state was right, and the saved play and box score are correct (the sack, interception and fumble are all "
     "credited properly). Don't re-enter or undo these plays."),
    ("h2", "The other buttons on the cards"),
    ("table", ["Button", "When to use it"], [
        [ui("TD"), "Rarely needed. Normal touchdowns score automatically when a Run/Pass End Spot reaches the end zone "
                   "(Phase 5). Use only if your producer asks you to log a touchdown without a play."],
        [ui("FG"), "Field goal attempts &mdash; made, missed or blocked (Phase 5)."],
        [ui("Turnover"), "A turnover that isn't part of a play you entered (e.g. a turnover on downs correction). Interceptions and "
                         "fumbles normally go in the Pass/Run form as shown above."],
        [ui("1st Down"), "Manual first-down marker. Normal first downs are automatic; use only to correct a measurement."],
        [ui("Record Ejection"), "Logs an ejected player or coach. Ejected players can't be credited on later plays."],
        [ui("Play Commercial", "green"), "Plays the next sponsor ad. Only if your producer asks you to run commercials."],
    ]),

    # ------------------------------------------------------------------ 4
    ("section", "4", "Jerseys That Don't Match (Unresolved Players)",
     "Sometimes the number you see isn't on that team's roster &mdash; a wrong number on the roster, a blank "
     "roster entry, a player wearing a different jersey, or just a misread. Here's exactly what happens, "
     "and what to do: <b>keep going</b>."),
    ("h2", "Case 1: the number belongs to the other team"),
    ("side", "mismatch_run_form", "Riverside run, ball carrier #22. Riverside has no #22 (it's a Northgate number).", [
        ("p", "As soon as you type the number, the line under the box turns <b style='color:#b07d10'>amber</b>: "
              "<i>&ldquo;#22 &mdash; Not found on active roster.&rdquo;</i> The form checks only the team that had the ball, "
              "so it never borrows the other team's #22."),
        ("p", "<b>Press " + ui("Record Play", "red") + " anyway.</b> The play records normally: yards, down and distance "
              "all update. The jersey is saved as just <i>#22</i> with no name, and the system flags the play internally as a "
              "<b>team mismatch</b> so it can be corrected after the game. It will <b>not</b> credit Northgate's #22 by mistake."),
        ("callout", "tip", "STALE MESSAGE",
         "The &ldquo;Play recorded.&rdquo; under the buttons in this screenshot is left over from the previous play &mdash; ignore it."),
    ]),
    ("fig", "mismatch_after", "After recording: 2nd &amp; 5 at RIGHT 20. The game moved on exactly as it should."),
    ("h2", "Case 2: the number isn't on anyone's roster"),
    ("side", "offroster_pass_form", "Riverside pass to #44, a number on neither roster.", [
        ("p", "Exactly the same treatment: amber &ldquo;Not found on active roster,&rdquo; record it anyway. The "
              "completion and yardage count for the team; only the receiver's name is missing."),
    ]),
    ("fig", "register_unresolved", "In the register the unresolved plays show a bare number with no name: "
     "<i>#22 run for 5 yards</i> and <i>complete to #44 for 8 yards</i>."),
    ("fig", "unresolved_play_detail", "Tap a play to see its canonical record on the right side of the register.", "narrow"),
    ("callout", "rule", "WHAT TO DO WHEN YOU SEE AMBER",
     "<b>1.</b> Double-check the number on the field if you can do it in a second or two. If you misread it, retype it.<br>"
     "<b>2.</b> Otherwise <b>record the play anyway.</b> Don't hunt through rosters, don't stop the game, don't undo.<br>"
     "<b>3.</b> Write down the <b>play number</b> from the register (e.g. &ldquo;Play 10 &mdash; Riverside #22&rdquo;) and tell your "
     "producer at the next break. Someone fixes the name after the game with the register's " + ui("Edit") + " button.<br>"
     "<b>4.</b> Keep entering the next plays normally."),

    # ------------------------------------------------------------------ 5
    ("section", "5", "Scoring Plays: TD, PAT, 2-Point, FG, Safety",
     "You never type a score. Touchdowns and safeties come from the End Spot; tries and field goals have "
     "their own guided pop-up. One example of every scoring outcome follows."),
    ("h2", "Touchdown (run)"),
    ("side", "td_run_form", "Riverside #5 run from RIGHT 28: End Spot dragged all the way to LEFT GOAL.", [
        ("p", "Enter it like any run, but drag <b>End Spot</b> all the way into the end zone the team is attacking "
              "(the slider label reads <code>LEFT GOAL</code> or <code>RIGHT GOAL</code>). The preview shows the full yardage."),
        ("p", "On " + ui("Record Play", "red") + " the system scores <b>6 points</b> and opens the <b>TRY REQUIRED</b> panel."),
    ]),
    ("fig", "td_try_pending", "Riverside 6, Northgate 0. TRY REQUIRED &mdash; RIVERSIDE with four buttons. Play buttons are "
     "hidden until the try is entered."),
    ("fields", [
        (ui("XP GOOD", "green"), "Kicked extra point good (+1)."),
        (ui("XP NO GOOD", "gold"), "Kick missed or blocked (+0)."),
        (ui("2PT GOOD", "green"), "Two-point conversion by run or pass succeeded (+2)."),
        (ui("2PT FAILED", "gold"), "Two-point attempt failed (+0)."),
    ]),
    ("h2", "PAT by run &mdash; 2-point conversion good"),
    ("side", "two_point_run_form", "2PT GOOD: scorer #5, Play Type Rush.", [
        ("p", "Press " + ui("2PT GOOD", "green") + ". The <b>Try</b> pop-up opens with <b>Try Outcome: Good</b> already set."),
        ("fields", [
            ("Scorer Jersey #", "Pick the runner (or receiver) from the list. Roster players show with names."),
            ("Play Type", "<b>Rush</b> for a run, <b>Reception</b> for a pass (then a <b>QB / Passer</b> box appears)."),
            ("Try Outcome", "Good / Failed / Blocked / Retry. Pre-set by the button you pressed."),
            ("Statistician Mode", "Optional: tick to add yardage detail. Not needed for tries."),
            ("Graphic Duration", "How long the score graphic shows on air. Leave at 8 seconds unless told otherwise."),
        ]),
        ("p", "Press " + ui("Confirm Event", "red") + "."),
    ]),
    ("fig", "after_two_point_run", "Riverside 8, Northgate 0. The panel now reads KICKOFF REQUIRED &mdash; RIVERSIDE."),
    ("h2", "Kickoff with a touchback"),
    ("side", "kickoff_touchback_form", "Kickoff into the end zone: Landed dragged to RIGHT GOAL, Touchback ticked.", [
        ("p", "After every score the kickoff is required next. Press " + ui("Open Detailed Kickoff", "red") +
              ", enter the kicker, drag <b>Landed</b> into the end zone and tick <b>Touchback</b>. No returner needed."),
    ]),
    ("fig", "after_touchback", "Touchback: Northgate ball, 1st &amp; 10 at its own 20."),
    ("h2", "Touchdown (pass) and a kicked PAT"),
    ("side", "td_pass_form", "Northgate #7 to #88: End Spot at the goal line Northgate is attacking (80 yards).", [
        ("p", "A touchdown pass is a complete " + ui("Pass") + " whose End Spot is in the end zone."),
    ]),
    ("fig", "td_pass_try_pending", "Northgate 6, Riverside 8 &mdash; TRY REQUIRED &mdash; NORTHGATE.", "narrow"),
    ("side", "xp_good_form", "XP GOOD: pick the kicker (#3 Eli Sanderson), Outcome: Good.", [
        ("p", "Press " + ui("XP GOOD", "green") + ". Choose the kicker from <b>Kicker Jersey #</b>; <b>Outcome</b> is already "
              "<i>Good</i>. " + ui("Confirm Event", "red") + "."),
    ]),
    ("fig", "after_xp_good", "Northgate 7, Riverside 8 &mdash; and the kickoff is required again."),
    ("h2", "PAT kick no good"),
    ("side", "xp_no_good_form", "XP NO GOOD in the 4th quarter: Outcome &ldquo;Missed / No Good&rdquo;.", [
        ("p", "Same pop-up; " + ui("XP NO GOOD", "gold") + " sets <b>Outcome</b> to <i>Missed / No Good</i>. You can "
              "change it to <i>Blocked</i> if it was blocked. Still pick the kicker."),
    ]),
    ("fig", "after_xp_no_good_tied", "No points added: Northgate 16, Riverside 16.", "narrow"),
    ("h2", "PAT by pass &mdash; 2-point conversion failed"),
    ("side", "two_point_pass_failed_form", "2PT FAILED: Play Type Reception, intended receiver #85, passer #12.", [
        ("p", ui("2PT FAILED", "gold") + " sets <b>Try Outcome</b> to <i>Failed</i>. Choose <b>Reception</b> as the Play Type, "
              "pick the intended receiver as Scorer and the QB as Passer, then " + ui("Confirm Event", "red") + "."),
    ]),
    ("fig", "after_two_point_failed", "Riverside 16 (no points added for the failed try), kickoff required.", "narrow"),
    ("h2", "Field goal"),
    ("side", "fg_good_form", "FG on the Northgate card: kicker #3, Outcome Made, Distance 32.", [
        ("p", "Press " + ui("FG") + " on the kicking team's card."),
        ("fields", [
            ("Kicker Jersey #", "The kicker."),
            ("Outcome", "<b>Made</b>, <b>Missed / No Good</b>, or <b>Blocked</b>."),
            ("Distance (yds)", "Optional, but fill it in: line of scrimmage + 17 (e.g. ball at the 15 = 32 yards)."),
            ("Miss/Block Result Spot", "Appears for a miss: where the defense takes over (optional)."),
        ]),
        ("p", ui("Confirm Event", "red") + ". A made field goal adds <b>3 points</b> and sets up the kickoff."),
    ]),
    ("fig", "after_fg_good", "Northgate 10, Riverside 16 after the field goal.", "narrow"),
    ("h2", "Safety"),
    ("p", "There is no Safety button &mdash; and you don't need one. Enter the play normally and drag the End Spot into the "
          "<b>offense's own</b> end zone. In this example Northgate fair-caught a punt at its own 2, then was tackled in its "
          "own end zone on the next run."),
    ("side", "safety_run_form", "Northgate run from RIGHT 2: End Spot dragged to RIGHT GOAL (Northgate's own goal line).", [
        ("p", "On " + ui("Record Play", "red") + " the system awards <b>2 points to the defense</b> and opens a "
              "<b>free kick</b> by the team that gave up the safety."),
    ]),
    ("fig", "after_safety_free_kick_pending", "Safety: Riverside 10, Northgate 7. The panel asks for Northgate's free kick."),
    ("side", "free_kick_form", "The free kick uses the same kickoff form: Open Detailed Kickoff.", [
        ("p", "Enter it exactly like a kickoff: kicker, landed spot, returner, end spot."),
    ]),
    ("callout", "tip", "SCORE LOOKS WRONG?",
     "Check the last play's End Spot first. A touchdown that didn't score usually means the End Spot stopped one yard "
     "short of the goal; a surprise safety means the slider went to the wrong goal line. " + ui("Undo Last Event", "gold") +
     " and re-enter."),

    # ------------------------------------------------------------------ 6
    ("section", "6", "Ending a Quarter",
     "Quarter changes are one button in Period Administration. Teams switch ends and the screen flips the field for you."),
    ("side", "period_card_q1", "Period Administration at the end of the 1st quarter.", [
        ("fields", [
            (ui("End Quarter", "gold"), "Ends the current quarter. Use it when the officials signal the end of the quarter."),
            ("Status line", "<i>QUARTER &middot; Q1</i> &mdash; where the game is. Watch it change."),
            ("Correct Quarter 1&ndash;4, OT", "Manual override only, if the quarter shown is wrong."),
            (ui("Start Halftime", "gold"), "Manual halftime switch. You won't normally need it: End Quarter at the end of Q2 starts halftime."),
            (ui("Start Second Half"), "Starts the 3rd quarter (Phase 8)."),
            (ui("Untimed Down Complete"), "After a penalty extends a period with an untimed down: press once that down is played."),
            (ui("Start Overtime"), "Phase 9."),
            (ui("Confirm Final", "red"), "Phase 10."),
        ]),
    ]),
    ("steps", [
        "When the quarter ends, make sure the last play of the quarter is entered.",
        "Press " + ui("End Quarter", "gold") + ".",
        "Check the scoreboard shows the new quarter (<b>Q2</b>) and the possession strip still has the right team and yard line.",
    ]),
    ("fig", "after_end_q1", "Q2 begins. Same down, distance and possession &mdash; but the ball spot flipped from LEFT 20 to "
     "RIGHT 20 because the teams changed ends. That's correct: it's still Northgate's own 20."),
    ("pair", ("period_card_end_q3", "End of Q3: status QUARTER &middot; Q3."),
             ("after_end_q3", "After End Quarter: Q4, ends switched again (LEFT 20 &rarr; RIGHT 20).")),

    # ------------------------------------------------------------------ 7
    ("section", "7", "Halftime",
     "Ending the 2nd quarter puts the game into halftime automatically. Nothing to enter during the break."),
    ("steps", [
        "Enter the last play of the half (here Riverside kneels to run out the clock: " + ui("Run") + " with <b>Kneel</b> ticked).",
        "Press " + ui("End Quarter", "gold") + " in Period Administration.",
        "Check the Period Administration status reads <b>HALFTIME &middot; Q2</b> and the top button now says " + ui("End Halftime", "gold") + ".",
    ]),
    ("side", "kneel_form", "Last play of the half: Riverside #12 kneels (Kneel ticked).", [
        ("p", "The <b>Kneel</b> box records a victory-formation kneel so it's shown as a kneel in the stats."),
    ]),
    ("pair", ("after_end_q2", "After End Quarter at the end of Q2."),
             ("period_card_end_q2", "HALFTIME &middot; Q2. Second-half receiver (Visitor) came from the coin toss.")),
    ("fields", [
        ("Second-half receiving team", "Filled in automatically from the coin toss (Riverside deferred, so Riverside receives). "
                                       "Change only if the officials tell you otherwise."),
        ("Second-half receiving team drives", "<i>Mirror first half (default)</i> is right in most games. If the receiving "
                                              "team chooses a different end, set it here before starting the second half. "
                                              "Missed it? See &ldquo;Direction looks wrong after halftime?&rdquo; in Phase 8."),
    ]),
    ("callout", "tip", "DURING THE BREAK",
     "Use halftime to tell your producer about any amber/unresolved plays you noted in the first half."),

    # ------------------------------------------------------------------ 8
    ("section", "8", "The Second-Half Kickoff",
     "One button starts the 3rd quarter and sets up the kickoff; then it's the same kickoff form as Phase 2."),
    ("steps", [
        "When the teams line up for the second-half kickoff, press " + ui("Start Second Half") + " (" + ui("End Halftime", "gold") +
        " at the top of the card does the same thing).",
        "The quarter becomes <b>Q3</b> and a <b>KICKOFF REQUIRED &mdash; NORTHGATE</b> panel appears (Northgate kicks, because Riverside receives).",
        "Press " + ui("Open Detailed Kickoff", "red") + " and enter the kick, the returner and the spots.",
    ]),
    ("fig", "second_half_kickoff_pending", "Q3, KICKOFF REQUIRED &mdash; NORTHGATE."),
    ("h2", "Direction looks wrong after halftime?"),
    ("p", "By default the screen assumes the teams simply swap ends from the first half. Sometimes they don't. For "
          "example, the receiving team chooses the other goal, or the halftime dropdown was left on <i>Mirror first half</i>. "
          "<b>Check the arrow before you enter the second-half kickoff.</b> In this example Northgate is actually kicking "
          "toward the LEFT goal, but the screen still has it driving &rarr;."),
    ("side", "direction_wrong_kickoff_form", "The tell: the kickoff form's badge reads N &rarr; and the kick starts at LEFT 40, "
     "but on the field Northgate is kicking toward the LEFT goal.", [
        ("h3", "Fixing it at the kickoff (the common case)"),
        ("steps", [
            "Press " + ui("Cancel") + " to close the kickoff form without recording.",
            "Scroll to <b>Field Position</b> and press the correct " + ui("&larr; Drive") + " or " + ui("Drive &rarr;") +
            " button. The big arrows in the <b>Drive Direction</b> card do the same thing. Either one sets the team shown in the "
            "POSSESSION strip, and the other team automatically switches to the opposite direction.",
            "Press " + ui("Open Detailed Kickoff", "red") + " again. The badge now reads <b>&larr; N</b> and the kick starts from "
            "Northgate's own 40 (RIGHT 40). Enter the kickoff as normal.",
        ]),
        ("p", "That's all a kickoff needs, because the kickoff form re-places the kicker at their own 40 based on direction."),
    ]),
    ("pair", ("direction_before_fix", "Before: Drive &rarr; is lit; Game Context says <i>LEFT 40 &middot; Northgate &middot; 60 to goal</i>."),
             ("direction_after_fix", "After pressing &larr; Drive: the ball has <b>not</b> moved, so the same LEFT 40 now reads "
                                     "<i>40 to goal</i>.")),
    ("callout", "stop", "IF YOU NOTICE IN THE MIDDLE OF A DRIVE",
     "Changing the direction does <b>not</b> move the ball. The spot stays on the same side of the field (here LEFT 40), "
     "so its meaning flips: what was the team's own 40 becomes the opponent's 40. Mid-drive, after pressing the correct "
     "Drive button you must also drag the <b>Field Position</b> ball to where the ball really is. Then check that "
     "<b>Game Context</b> shows the right &ldquo;yards to goal.&rdquo; Otherwise the next plays will count yards, first downs "
     "and touchdowns toward the wrong goal. Plays already entered while the direction was wrong may have wrong yardage. "
     "Don't undo the drive; note the play numbers for your producer."),
    ("callout", "warn", "THE &ldquo;BALL:&rdquo; LABEL USES FIXED SIDES",
     "The <b>Ball:</b> label above the green field always names the left half after the home team and the right half "
     "after the visitor, even after the teams switch ends. After the fix above it still reads <i>&ldquo;Northgate 40&rdquo;</i>, "
     "although LEFT 40 is now the end Riverside defends. Trust the ball's position, the Drive arrow and Game Context, "
     "not the team name in that label."),
    ("callout", "tip", "PREVENT IT AT HALFTIME",
     "If you know the receiving team picked a different end, set <b>Second-half receiving team drives</b> in Period "
     "Administration <i>before</i> pressing Start Second Half."),
    ("h2", "Entering the second-half kickoff"),
    ("side", "second_half_kickoff_form", "Second-half kickoff after the fix: &larr; N, from RIGHT 40. Northgate #3 to Riverside #1.", [
        ("p", "Same form as the opening kickoff: kicker, Landed / Caught Spot, returner, End Spot, " + ui("Record Play", "red") + "."),
    ]),
    ("fig", "after_second_half_kickoff", "Riverside ball, 1st &amp; 10 at LEFT 32, now driving &rarr;. You're back to normal play entry."),
    ("callout", "warn", "&ldquo;SECOND HALF CAN START ONLY FROM HALFTIME&rdquo;",
     "If you see this pop-up, the game was never put into halftime (or the second half already started). Check the "
     "Period Administration status line before pressing anything else, and ask your producer if it doesn't say HALFTIME."),

    # ------------------------------------------------------------------ 9
    ("section", "9", "4th Quarter & Overtime",
     "The 4th quarter plays exactly like the others. If it ends tied, the screen asks for a Final/Overtime "
     "decision and walks you into overtime."),
    ("h2", "End of regulation"),
    ("steps", [
        "Enter the final play of the 4th quarter (here Riverside kneels with the game tied 16&ndash;16).",
        "Press " + ui("End Quarter", "gold") + ".",
        "Period Administration shows <b>Q4 COMPLETE &middot; Q4 &middot; Final/OT decision required</b>.",
        "If one team is ahead, go to Phase 10 and " + ui("Confirm Final", "red") + ". If tied, continue below.",
    ]),
    ("pair", ("after_end_regulation", "Tied 16&ndash;16, Q4 complete."),
             ("period_card_end_regulation", "Period Administration just before End Quarter in Q4.")),
    ("h2", "Starting overtime"),
    ("side", "period_card_overtime_setup", "Overtime setup: Riverside (Visitor) first, starting spot LEFT 10.", [
        ("fields", [
            ("Overtime possession", "The team that goes on offense first (decided by the overtime coin toss)."),
            ("Overtime starting spot", "Where the ball is placed, in field-spot language: <code>LEFT 10</code> or "
                                       "<code>RIGHT 10</code> = the 10-yard line on that side. Use the spot the officials use "
                                       "(your state association's overtime rule)."),
        ]),
        ("steps", [
            "Set <b>Overtime possession</b>.",
            "Type the <b>Overtime starting spot</b>.",
            "Press " + ui("Start Overtime") + ". Both fields are required.",
        ]),
    ]),
    ("fig", "overtime_started", "QOT: Riverside, 1st &amp; 10 at LEFT 10. Overtime is untimed, so the clock is hidden "
     "from the broadcast."),
    ("h2", "First overtime possession"),
    ("side", "ot_fg_missed_form", "Riverside FG attempt from the 10: Outcome &ldquo;Missed / No Good&rdquo;, 27 yards.", [
        ("p", "Enter overtime plays exactly as in regulation. Here Riverside's possession ends with a missed field goal."),
    ]),
    ("fig", "after_ot_fg_missed", "After the miss, possession switched to Northgate &mdash; but the ball is still at LEFT 10, "
     "Riverside's attacking spot. Northgate's possession must start at the other 10."),
    ("h2", "Second overtime possession: place the ball yourself"),
    ("p", "The system hands the ball to the other team but does <b>not</b> move it to their overtime starting spot. "
          "This is the one time you'll use the manual controls:"),
    ("steps", [
        "<b>Possession:</b> confirm the correct team is highlighted (press it if not).",
        "<b>Field Position:</b> drag the ball on the green field to this team's overtime spot. Here Northgate is "
        "driving &rarr;, so its spot is the 10-yard line nearest the RIGHT goal.",
        "<b>Down &amp; Distance:</b> press " + ui("1st") + " if needed.",
    ]),
    ("fig", "ot_second_possession_setup", "Northgate's overtime possession set up: Possession Home, 1st &amp; 10, ball at the "
     "right-hand 10 (driving &rarr;). Remember the &ldquo;Ball:&rdquo; label uses fixed sides (Phase 8).", "narrow"),
    ("side", "ot_fg_good_form", "Northgate FG from the 10: Made, 27 yards.", [
        ("p", "Northgate kicks the winning field goal: " + ui("FG") + " on the Northgate card, Outcome <b>Made</b>."),
    ]),
    ("fig", "after_ot_fg_good", "Northgate 19, Riverside 16."),
    ("callout", "warn", "IGNORE &ldquo;KICKOFF REQUIRED&rdquo; IN OVERTIME",
     "After an overtime score the console still shows a <b>KICKOFF REQUIRED</b> panel. There are no kickoffs in overtime: "
     "do <b>not</b> open the kickoff form. Go to Period Administration instead."),
    ("h2", "Ending the overtime period"),
    ("steps", [
        "When both teams have had their possession, press " + ui("End Quarter", "gold") + ".",
        "Status reads <b>OVERTIME COMPLETE &middot; QOT &middot; Final/OT decision required</b>.",
        "Still tied? Set possession and spot again and press " + ui("Start Overtime") + ". Someone won? Go to Phase 10.",
    ]),
    ("fig", "period_card_overtime_complete", "OVERTIME COMPLETE: ready for Confirm Final.", "small"),

    # ------------------------------------------------------------------ 10
    ("section", "10", "End of Game: Confirm Final",
     "Final is the only end state you touch. It locks the result, archives every play into the game record "
     "and tells the rest of the system the game is over."),
    ("h2", "Before you confirm"),
    ("bullets", [
        "The scoreboard matches the stadium scoreboard.",
        "The Play Register looks complete &mdash; scroll through it once.",
        "You've told your producer about any amber/unresolved plays.",
    ]),
    ("fig", "register_before_final", "The register just before Final, newest play first.", "narrow"),
    ("h2", "Confirming"),
    ("steps", [
        "In Period Administration press " + ui("Confirm Final", "red") + ". It only works after <b>Q4 COMPLETE</b> or "
        "<b>OVERTIME COMPLETE</b>; if the quarter hasn't been ended, you'll get a message saying so.",
        "Your browser asks <i>&ldquo;Confirm the game is FINAL?&rdquo;</i> Press <b>OK</b>.",
    ]),
    ("h2", "How you know the game is correctly closed out"),
    ("fig", "final_page_header", "The header badge changes from LIVE to FINAL.", "full"),
    ("pair", ("period_card_final", "Period Administration status: FINAL."),
             ("final_console", "The scoreboard keeps the final score, 19&ndash;16.")),
    ("table", ["You see", "What it means"], [
        ["Header badge " + ui("FINAL"), "The broadcast is marked completed with the final score."],
        ["Period status <b>FINAL &middot; QOT</b>", "The game clock is stopped for good; no more periods."],
        ["Play Register says <i>No plays recorded.</i>", "<b>Expected.</b> On Final the system moves every play into the "
                                                        "game's permanent archive and clears the live list. Nothing is lost: "
                                                        "in this demo all 35 plays and the full box score were saved."],
        ["A leftover KICKOFF REQUIRED panel", "Harmless after an overtime score. Don't enter anything."],
    ]),
    ("fig", "register_final", "After Final the live Play Register is empty because the plays have been archived.", "narrow"),
    ("callout", "rule", "YOU'RE DONE",
     "Once you see <b>FINAL</b>, stop entering data. Hand your notes (any play numbers with amber jerseys) to the producer, "
     "then log out with " + ui("Log Out") + " in the header. If you pressed Confirm Final by mistake, tell the producer "
     "right away rather than trying to fix it yourself."),

    # ------------------------------------------------------------------ A
    ("section", "A", "Quick Reference Card",
     "Tear-off summary: what to press for every situation on the Statistician Console."),
    ("table", ["Situation", "Press", "Fill in", "Watch for"], [
        ["Opening coin toss", ui("Enter Coin Toss", "red"), "Winner, election, drive direction", "Summary line, then " + ui("Save Coin Toss", "red")],
        ["Kickoff / free kick", ui("Open Detailed Kickoff", "red"), "Kicker, returner, Landed, End", "Touchback box for end-zone kicks"],
        ["Run", ui("Run") + " (offense)", "Ball carrier, End", "Kneel, Out of bounds, Fumble / Fumble lost"],
        ["Complete pass", ui("Pass") + " &rarr; Complete", "Passer, receiver, End", "End = where he was downed"],
        ["Incomplete pass", ui("Pass") + " &rarr; Incomplete", "Passer, intended receiver", "End locks automatically"],
        ["Sack", ui("Pass") + " &rarr; Sack", "Passer, sacker, End", "Sacker = defense jersey"],
        ["Interception", ui("Pass") + " &rarr; Interception", "Passer, pick spot, returner, End", "Possession flips"],
        ["Fumble lost", ui("Run") + "/" + ui("Pass") + " + Fumble lost", "Recovery spot, recoverer, End", "Possession flips"],
        ["Punt", ui("Punt"), "Punter, returner, Landed, End", "Fair catch, Blocked, Muffed, Touchback"],
        ["Penalty", ui("Penalty") + " on the <b>fouling</b> team", "Unit, penalty, ruling", "Auto first down / loss of down boxes"],
        ["Timeout", ui("Stop", "red") + " the clock", "&mdash;", "No timeout button; optional note"],
        ["Touchdown", ui("Run") + "/" + ui("Pass") + ", End in end zone", "As normal", "TRY REQUIRED panel"],
        ["Extra point", ui("XP GOOD", "green") + " / " + ui("XP NO GOOD", "gold"), "Kicker", ui("Confirm Event", "red")],
        ["2-point try", ui("2PT GOOD", "green") + " / " + ui("2PT FAILED", "gold"), "Scorer, Rush/Reception, passer", ui("Confirm Event", "red")],
        ["Field goal", ui("FG"), "Kicker, outcome, distance", "Made = +3, then kickoff"],
        ["Safety", ui("Run") + "/" + ui("Pass") + ", End in <b>own</b> end zone", "As normal", "+2 defense, free kick"],
        ["Wrong jersey (amber)", ui("Record Play", "red") + " anyway", "&mdash;", "Note play number for producer"],
        ["Mistake just now", ui("Undo Last Event", "gold"), "Re-enter play", "Only undoes the latest event"],
        ["End of quarter", ui("End Quarter", "gold"), "&mdash;", "Ends switch; spot label flips"],
        ["Halftime", ui("End Quarter", "gold") + " after Q2", "&mdash;", "HALFTIME &middot; Q2"],
        ["Second half", ui("Start Second Half"), "Then the kickoff", "Q3 KICKOFF REQUIRED"],
        ["Direction wrong", ui("&larr; Drive") + " / " + ui("Drive &rarr;"), "Mid-drive: also move the ball", "Game Context yards-to-goal"],
        ["Overtime", ui("Start Overtime"), "Possession + spot", "Move ball yourself for 2nd possession"],
        ["Game over", ui("Confirm Final", "red"), "OK the browser prompt", "FINAL badge; register archived"],
    ]),
]
