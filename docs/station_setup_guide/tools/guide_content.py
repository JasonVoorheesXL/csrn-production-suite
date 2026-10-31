"""Text of the Station Setup Guide (all sports).

Every screen described here was captured by capture.py from a brand-new
install of the fictional station "Westside Sports Network" (WSN); see
capture_log.json. Block types are the statistician guide's, rendered by
render_pdf.py:
  ("section", number, title, lede)   opener (starts a new page)
  ("h2"|"h3"|"p", html)
  ("steps"|"bullets", [html, ...])
  ("fields", [(name, html), ...])
  ("table", [head...], [[cell...], ...])
  ("callout", tip|warn|stop|rule, title, html)
  ("fig", slug, caption[, full|narrow|small])
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


def menu(*path: str) -> str:
    return " &rsaquo; ".join(ui(step) for step in path)


COVER_LEDE = (
    "You've installed the Production Suite. This guide takes your station from the first launch to its "
    "first live broadcast: your station's name and logo, the sports you cover, schools and rosters, your "
    "crew and sponsors, OBS, and the routine for every game night."
)
COVER_META = (
    f"Every screenshot was captured from a brand-new install (Production Suite {_VERSION}) set up as a "
    "fictional station, <b style='color:#fff'>Westside Sports Network (WSN)</b>. Your screens show your "
    "station's name and logo instead.<br>"
    "This guide is the same for every sport. Keeping stats during a game is covered by the statistician "
    "guide for your sport, under Settings &rsaquo; Guides."
)

SECTIONS_INDEX = [
    ("1", "First Launch: the Setup Wizard and Your PIN", ""),
    ("2", "Your Station in Settings", ""),
    ("3", "Schools, Rosters and Crew", ""),
    ("4", "Sponsors, Media and Graphics", ""),
    ("5", "Connecting OBS", ""),
    ("6", "Your First Game", ""),
    ("7", "Phones and Tablets", ""),
    ("8", "Every Game Night", ""),
]

INTRO = [
    ("h2", "What you'll need"),
    ("bullets", [
        "A Windows laptop that stays in the press box for the game, with the Production Suite installed.",
        "<b>OBS Studio</b> (or the streaming software you use) on the same laptop.",
        "Your station's logo as a PNG or JPG. A square image works best; a plain background can be removed for you.",
        "Your license file, if the app asks for one on first launch.",
        "About 30 minutes for the first setup. After that, a new game takes a couple of minutes.",
    ]),
    ("h2", "How the app is laid out"),
    ("p", "Everything lives in one window, the console. The menu across the top has five groups, and they "
          "never move, so the same button is always in the same place on game night:"),
    ("table", ["Menu group", "What's in it"], [
        [ui("Game Day"), "Pre-Game Setup, Command Center, Statistician, OBS Manager"],
        [ui("Setup"), "Game Manager, School Database, Rosters, Personnel"],
        [ui("Production"), "Graphics, Sponsors (with the Media Library tab)"],
        [ui("Publishing"), "Social Publishing"],
        [ui("System"), "Settings, System Check"],
    ]),
    ("callout", "tip", "THE GUIDES ARE ALWAYS IN THE APP",
     f"Open {menu('System', 'Settings')}; the first section, <b>Guides</b>, lists this guide and the "
     "statistician guide for each sport you've switched on."),
]

BODY = [
    # 1 ---------------------------------------------------------------------
    ("section", "1", "First Launch: the Setup Wizard and Your PIN",
     "The first time the app opens it asks a few questions about your station, points you to these guides, "
     "and has you create the PIN every operator uses to sign in."),
    ("h2", "The setup wizard"),
    ("p", "Only the organization name is required; everything else can be filled in later from Settings."),
    ("pair", ("wizard-blank", "The wizard on a brand-new install"),
             ("wizard-filled", "Filled in for Westside Sports Network")),
    ("fields", [
        ("Organization / team name", "Your station's full name, as it appears on the pregame and halftime screens."),
        ("Short name", "The short form, such as <b>WSN</b>. It names the app on every screen "
                       "(&ldquo;WSN Production Suite&rdquo;) and appears on the broadcast as &ldquo;THIS IS WSN&rdquo;."),
        ("Primary sport", "The sport you broadcast most. It is switched on for you; switch on others in Settings."),
        ("Primary school", "Your home school. It becomes the first school in the School Database and your default venue."),
        ("Organization logo", "Your logo. If it sits on a plain white or colored square, upload it again later "
                              "from Settings, where the app offers a copy with the background removed."),
    ]),
    ("p", f"Click {ui('Finish', 'primary')}, or {ui('Skip for now')} to fill everything in later."),
    ("fig", "wizard-guides", "After the wizard: the guides for your station", "narrow"),
    ("p", "The last step lists the guides for your station: this one, plus the statistician guide for your "
          "primary sport. A sport without its own guide yet is marked <b>Coming soon</b>. "
          f"Click {ui('Open the console', 'primary')} when you're ready."),
    ("h2", "Create the operator PIN"),
    ("fig", "create-pin", "Every operator signs in with one 6-digit PIN", "narrow"),
    ("p", "Pick a 6-digit PIN and enter it twice. Everyone who runs the console, from the producer to the "
          "statistician, signs in with it, so share it only with your crew, and keep a copy somewhere safe: "
          "a lost PIN has to be reset by support."),
    ("callout", "tip", "SPORT TILES AT SIGN-IN",
     "The sign-in screen shows a tile for each sport you've switched on. Pick the sport for tonight's game; "
     "you can change it later from the sport list at the top right without signing in again."),
    ("fig", "command-center", "The Command Center on a new install, before any game exists"),

    # 2 ---------------------------------------------------------------------
    ("section", "2", "Your Station in Settings",
     f"{menu('System', 'Settings')} holds everything about your station. Work down it once now; "
     "you'll rarely need it again."),
    ("fig", "settings-guides", "The top of Settings: Guides, then your organization"),
    ("h2", "Organization"),
    ("fig", "settings-organization", "Organization: name, short name, colors and logo"),
    ("p", "The wizard filled most of this in. If you uploaded a logo there and it sits on a plain square, "
          f"upload it again here with {ui('Upload Logo')}: the app offers a cleaned copy with the background "
          "removed. The three colors are your station's colors for the broadcast "
          f"screens. {ui('Use Placeholder Logo')} clears the logo, and "
          f"a neutral microphone mark is shown until a logo is set. Click {ui('Save Configuration', 'primary')} "
          "at the bottom of the page after any change here."),
    ("h2", "Appearance"),
    ("fig", "settings-appearance", "Appearance: how the console itself looks"),
    ("p", "These choices only change the console on this computer, not the broadcast. Pick a brand color for "
          "the main buttons, a frame shape for your logo, and whether the glass effect is on. If the app "
          "removed your logo's background, choose <b>Use Cleaned Logo</b> here. "
          f"Click {ui('Save Appearance', 'primary')}."),
    ("h2", "Sports"),
    ("fig", "settings-sports", "Sports: tick the sports your station broadcasts"),
    ("p", "Tick every sport you broadcast. A sport that isn't ticked disappears from the sign-in tiles and the "
          "sport list, but its schools, rosters, games and stats are kept, and ticking it again brings it "
          "straight back. At least one sport stays on. The statistician guides under <b>Guides</b> follow "
          "these ticks."),
    ("callout", "rule", "RETIRED TOOLS",
     "Below Sports, <b>Show retired tools</b> brings back older features most stations don't use (live "
     "captions, the Layout Builder, game recaps, broadcast packages and the theme manager). Leave it off "
     "unless you've been told you need one of them."),
    ("h2", "Quick Launch and Station Social Media"),
    ("fig", "settings-quick-launch", "Quick Launch buttons and your station's social links"),
    ("fields", [
        ("Broadcast Software", f"Your streaming program. {ui('Detect Installed')} finds OBS and similar programs. "
                               "Pre-Game Setup then gets a button that opens it."),
        ("YouTube / Facebook URL", "The pages where you start your live stream, so Pre-Game Setup can open them."),
        ("Station Social Media", "Your Facebook, YouTube, X and website links. Facebook and YouTube appear on the "
                                 "pregame and halftime screens; a link left blank simply isn't shown."),
    ]),
    ("p", f"The <b>OBS</b> section of Settings is covered in step 5. Click {ui('Save Configuration', 'primary')} when you're done."),

    # 3 ---------------------------------------------------------------------
    ("section", "3", "Schools, Rosters and Crew",
     "The app names teams, shows logos and identifies players from what you enter here, so set up your "
     "own school first and add opponents as the schedule comes."),
    ("h2", "School Database"),
    ("fig", "schools", f"{menu('Setup', 'School Database')}"),
    ("p", "Every team in a game is a school record: its name as the broadcast says it, its nickname, colors and "
          "logo. The wizard created your home school; add each opponent before you build its game. Upload a "
          "logo for each school so it appears on the scoreboard and the pregame screen."),
    ("h2", "Rosters"),
    ("fig", "rosters", f"{menu('Setup', 'Rosters')}: one roster per team, per season, per level"),
    ("p", f"Click {ui('Create Roster', 'primary')}, choose the school, sport, season and level, then add players "
          "with their jersey numbers and positions. Jersey numbers are what the statistician types during "
          "the game, so they must match the uniforms."),
    ("callout", "tip", "HEADSHOTS",
     "Add a headshot to a player and it appears on the player graphics, such as the touchdown graphic. "
     "Photos straight from a camera are fine: the app shrinks them on upload, so they stay small."),
    ("h2", "Personnel"),
    ("fig", "personnel", f"{menu('Setup', 'Personnel')}: your broadcast crew, coaches and officials"),
    ("p", "Add your announcers, producer and statistician, plus coaches you interview. Each person can have a "
          "role and a headshot."),

    # 4 ---------------------------------------------------------------------
    ("section", "4", "Sponsors, Media and Graphics",
     "Sponsors pay for your broadcasts; the app shows their logos and plays their commercials."),
    ("h2", "Sponsors"),
    ("fig", "sponsors", f"{menu('Production', 'Sponsors')}"),
    ("p", f"Click {ui('Add Sponsor', 'primary')} for each sponsor: name, status, contract dates, the lead-in "
          "the announcers use (&ldquo;Presented by&rdquo;) and the logo. Only sponsors marked "
          "<b>Available for graphics</b> are offered on the broadcast."),
    ("h2", "Media Library"),
    ("fig", "media-library", f"The {ui('Media Library')} tab, next to Sponsors"),
    ("p", "The library holds the files the broadcast uses: sponsor logos and commercials, player highlights "
          "and backgrounds. Upload a file once here and pick it wherever it's needed."),
    ("h2", "Graphics"),
    ("fig", "graphics", f"{menu('Production', 'Graphics')}: the player graphic"),
    ("p", "The player graphic runs by itself when a player scores. Open it here to choose its look and the "
          "sponsor shown with it."),

    # 5 ---------------------------------------------------------------------
    ("section", "5", "Connecting OBS",
     "OBS shows the app's scoreboard and screens as web pages layered over your video. Set it up once; "
     "the app can then check it before every game."),
    ("h2", "Quickest: import the ready-made scene collection"),
    ("fig", "obs-browser-source", f"{menu('Game Day', 'OBS Manager')}: download the scene collection or open the OBS Setup Guide"),
    ("p", f"Click {ui('Download OBS Scene Collection', 'primary')}, then in OBS choose <b>Scene Collection &rsaquo; "
          "Import</b> and pick the file. It adds every scene and source the app expects, already named and pointed "
          "at the app, without touching your other OBS scenes. The <b>OBS Setup Guide</b> (Settings &rsaquo; Guides) "
          "walks through the import, your background, camera and sound, and the connection, step by step."),
    ("h2", "Or add the browser sources yourself"),
    ("steps", [
        "In OBS, create the scene named in the OBS Manager (for football, <b>10.01 - FOOTBALL SCOREBUG</b>).",
        "Add a <b>Browser Source</b> to it with the name shown, URL <b>http://127.0.0.1:5050/overlay</b>, "
        "width 1920 and height 1080. This is the scoreboard.",
        "In the scene you use before the game, at halftime and during delays, add another Browser Source with "
        "URL <b>http://127.0.0.1:5050/pregame-overlay</b>, also 1920 &times; 1080.",
    ]),
    ("callout", "warn", "THE NAMES MUST MATCH",
     "The OBS Manager can only check a scene or source whose name matches Settings exactly, capital letters "
     "and spaces included. If your station uses its own names, change them in Settings &rsaquo; OBS instead."),
    ("h2", "Let the app talk to OBS"),
    ("fig", "settings-obs", f"{menu('System', 'Settings')} &rsaquo; OBS"),
    ("steps", [
        f"In OBS, open <b>Tools &rsaquo; WebSocket Server Settings</b>, turn the server on and note its port and password.",
        f"In Settings &rsaquo; OBS, set {ui('WebSocket Enabled')} to <b>Yes</b> and enter the port and password.",
        "Leave <b>Scene Collection</b> and <b>Profile</b> blank to accept whatever OBS has open, "
        f"then click {ui('Save Configuration', 'primary')}.",
        f"Open {menu('Game Day', 'OBS Manager')} and click {ui('Test OBS Connection')}. Each line should turn green.",
    ]),
    ("fig", "obs-manager", "The OBS Manager before the first test"),
    ("p", f"Turn on {ui('Controlled Commands')} in Settings only if you want the app to show and hide the "
          "scoreboard in OBS for you; until then OBS stays fully in your hands."),

    # 6 ---------------------------------------------------------------------
    ("section", "6", "Your First Game",
     "Each broadcast is one game. Build it ahead of time; on game night you load it and go."),
    ("h2", "Create the broadcast"),
    ("fig", "game-manager", f"{menu('Setup', 'Game Manager')}"),
    ("p", f"Click {ui('New Broadcast', 'primary')} and fill in the sport and its rules, the season, level and "
          "week, the home and visiting schools, the venue, date and start time. Each game gets an ID such as "
          "<b>FB-2026-5A-W01-001</b> (sport, season, classification, week, number)."),
    ("h2", "Pre-Game Setup"),
    ("fig", "pregame", f"{menu('Game Day', 'Pre-Game Setup')}"),
    ("p", "On game night, start here: load the broadcast, open your streaming software and stream pages with "
          "the Quick Launch buttons, work through the checklist, and choose the overlay theme and the program "
          f"visual. Then {ui('Open Command Center', 'primary')}."),
    ("h2", "Command Center and the Statistician"),
    ("p", "The Command Center runs the broadcast: going live, the score and clock, timeouts, the pregame and "
          "halftime screens. When a statistician keeps the game, click <b>Enable Statistician Console</b> "
          "there and the Statistician screen takes over the game data."),
    ("callout", "tip", "HAND THE STAT CHAIR ITS GUIDE",
     "Everything on the Statistician screen is explained, play by play, in the statistician guide for your "
     "sport (Settings &rsaquo; Guides)."),

    # 7 ---------------------------------------------------------------------
    ("section", "7", "Phones and Tablets",
     "A second person can run the statistician screen or controls from a phone or tablet on the same "
     "network as the laptop."),
    ("fig", "connection", f"{menu('Game Day', 'Statistician')} &rsaquo; Mobile / USB Connection"),
    ("steps", [
        "Connect the phone or tablet to the same Wi-Fi as the laptop, or to the laptop's hotspot.",
        f"Open the Statistician screen on the laptop and scroll to <b>Mobile / USB Connection</b>; click "
        f"{ui('Refresh Addresses')} if you just changed networks.",
        "Type the address shown into the phone's browser, or tap Copy and send it to the phone, then sign in "
        "with the operator PIN.",
    ]),
    ("callout", "warn", "USB TETHERING",
     "If the laptop gets its internet from a phone over USB, that phone often can't open the app itself. "
     "Use a second phone or tablet for the statistician."),

    # 8 ---------------------------------------------------------------------
    ("section", "8", "Every Game Night",
     "Setup is done. This is the short routine for each broadcast."),
    ("fig", "system-check", f"{menu('System', 'System Check')}: green means ready"),
    ("steps", [
        "Start the laptop, then the app, then OBS.",
        f"Open {menu('System', 'System Check')} and click {ui('Check System', 'primary')}. Fix anything red; "
        "decide about anything marked as a warning.",
        f"Open {menu('Game Day', 'Pre-Game Setup')}, load tonight's broadcast and work through the checklist.",
        "Show the pregame screen, start your stream, and go live from the Command Center.",
        "After the final, check the box score under Statistician &rsaquo; <b>Box Score</b> and post the "
        "final-score card from Social Publishing.",
    ]),
    ("callout", "tip", "IF SOMETHING GOES WRONG",
     f"{menu('System', 'System Check')} has {ui('Export Incident Bundle')}. It saves what the app knows about "
     "the problem in one file you can send for help."),
]
