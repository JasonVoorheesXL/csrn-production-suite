"""Text of the OBS Setup Guide (all sports).

App screenshots come from capture.py (a fresh install of the fictional
"Westside Sports Network"); the OBS steps are described in text, for OBS
Studio 30 or later. The scene collection it imports is built by
build_scene_collection.py. Block types: see the station guide's
guide_content.py.
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


def obs(*path: str) -> str:
    """An OBS menu path, set in bold rather than as an app button."""
    return " &rsaquo; ".join(f"<b>{step}</b>" for step in path)


COVER_LEDE = (
    "OBS puts your camera, sound and the app's scoreboard together and sends them to YouTube or Facebook. "
    "This guide gets a new station from a plain OBS install to a working broadcast scene in about fifteen "
    "minutes, using the ready-made scene collection that comes with the app."
)
COVER_META = (
    f"Written for OBS Studio 30 or later with Production Suite {_VERSION}. App screenshots come from a "
    "fictional station, <b style='color:#fff'>Westside Sports Network (WSN)</b>.<br>"
    "The same scenes are used for every sport: the scoreboard follows the sport of the game you load."
)

SECTIONS_INDEX = [
    ("1", "Import the Ready-Made Scene Collection", ""),
    ("2", "What's in the Collection", ""),
    ("3", "Your Background, Camera and Sound", ""),
    ("4", "Connect OBS to the App", ""),
    ("5", "Stream Settings and Going Live", ""),
    ("6", "When Something Looks Wrong", ""),
]

INTRO = [
    ("h2", "Before you start"),
    ("bullets", [
        "OBS Studio 30 or later, installed from <b>obsproject.com</b>, on the laptop that runs the app.",
        "The app running and signed in, so OBS can load its scoreboard pages.",
        "Your background image (1920 &times; 1080 PNG or JPG) and your camera plugged in, if you use one.",
    ]),
    ("h2", "Set OBS to 1920 &times; 1080"),
    ("p", f"In OBS open {obs('Settings', 'Video')} and set both <b>Base (Canvas) Resolution</b> and "
          "<b>Output (Scaled) Resolution</b> to <b>1920x1080</b>. Everything in the scene collection is "
          "built for that size."),
    ("callout", "tip", "YOUR EXISTING SCENES ARE SAFE",
     "Importing adds a new scene collection called <b>Production Suite</b>. Any collections you already "
     f"have stay exactly as they are, and you can switch between them from the {obs('Scene Collection')} menu."),
]

BODY = [
    # 1 ---------------------------------------------------------------------
    ("section", "1", "Import the Ready-Made Scene Collection",
     "One file holds every scene and source the app expects, already named and pointed at the app."),
    ("h2", "Download it from the app"),
    ("fig", "obs-manager-download", f"{ui('Game Day')} &rsaquo; {ui('OBS Manager')}: Browser Source Setup"),
    ("p", f"In the app open {ui('Game Day')} &rsaquo; {ui('OBS Manager')} (or {ui('System')} &rsaquo; "
          f"{ui('Settings')} &rsaquo; OBS) and click {ui('Download OBS Scene Collection', 'primary')}. "
          "Save <b>Production Suite.json</b> somewhere you'll find it, such as Documents."),
    ("h2", "Import it into OBS"),
    ("steps", [
        f"In OBS choose {obs('Scene Collection', 'Import')}.",
        "In the importer, click the <b>&hellip;</b> button in the empty row and choose <b>Production Suite.json</b>. "
        "Make sure its box is ticked, then click <b>Import</b>.",
        f"Open the {obs('Scene Collection')} menu again and choose <b>Production Suite</b>. OBS switches to the new scenes.",
    ]),
    ("callout", "rule", "LEAVE THE NAMES ALONE",
     "The app finds scenes and sources by name. Rename or move the sources below only if you also change "
     "the matching names in the app's Settings &rsaquo; OBS."),

    # 2 ---------------------------------------------------------------------
    ("section", "2", "What's in the Collection",
     "Eight scenes: three that do the work, and five empty dividers that keep the list tidy."),
    ("table", ["Scene", "Sources", "What it does"], [
        ["<b>30.01 - LIVE FOOTBALL</b>", "10.02 and 10.01, layered",
         "The scene you go live from. It stacks the program visual under the scoreboard."],
        ["<b>10.01 - FOOTBALL SCOREBUG</b>", "<b>BRWSR - Football Scorebug</b> (/overlay)<br><b>BRWSR - Pregame Delay</b> (/pregame-overlay)",
         "The app's scoreboard, and its pregame, halftime and delay screens on top. Both are web pages from "
         "the app at http://127.0.0.1:5050, 1920 &times; 1080, with see-through backgrounds."],
        ["<b>10.02 - PROGRAM VISUAL</b>", "<b>IMG - Broadcast Background</b><br><b>CAM - Primary Camera</b> (hidden)",
         "What sits behind the scoreboard: your background image or your camera. The app's "
         "<b>Use Graphic</b> / <b>Use Camera</b> buttons switch between them."],
        ["00 SYSTEM &middot; 10 CORE &middot; 20 GRAPHICS &middot; 30 BROADCAST &middot; 40 UTILITIES", "none",
         "Dividers. Leave them empty or use them for your own scenes."],
    ]),
    ("callout", "tip", "OTHER SPORTS",
     "The scenes say FOOTBALL, but nothing about them is football-only: the scoreboard page draws whatever "
     "sport the loaded game is. Basketball and baseball games use the same collection."),

    # 3 ---------------------------------------------------------------------
    ("section", "3", "Your Background, Camera and Sound",
     "The collection carries no pictures, devices or microphones from anyone else's computer, so you pick yours."),
    ("h2", "Background image"),
    ("steps", [
        "In the Scenes list click <b>10.02 - PROGRAM VISUAL</b>.",
        "Double-click <b>IMG - Broadcast Background</b> in Sources, click <b>Browse</b>, choose your 1920 &times; 1080 image and click OK.",
    ]),
    ("h2", "Camera"),
    ("steps", [
        "Still in 10.02, double-click <b>CAM - Primary Camera</b>, choose your camera under <b>Device</b> and click OK.",
        "It starts hidden: the app shows it when you click <b>Use Camera</b>. If your camera comes through a "
        "phone app or capture card with its own OBS source, add that source here instead and type its name "
        "into Settings &rsaquo; OBS &rsaquo; Camera Source Name.",
    ]),
    ("h2", "Sound"),
    ("p", f"Open {obs('Settings', 'Audio')} and choose your announcers' microphone or mixer under "
          "<b>Mic/Auxiliary Audio</b>. Those inputs play in every scene. For more microphones, add an "
          f"<b>Audio Input Capture</b> source for each to <b>30.01 - LIVE FOOTBALL</b>. Watch the "
          "levels in the Audio Mixer while someone talks."),

    # 4 ---------------------------------------------------------------------
    ("section", "4", "Connect OBS to the App",
     "With the connection on, the app checks OBS before each game and can switch the program visual for you."),
    ("h2", "In OBS"),
    ("steps", [
        f"Open {obs('Tools', 'WebSocket Server Settings')}.",
        "Tick <b>Enable WebSocket server</b>. Leave the port at <b>4455</b>.",
        "Tick <b>Enable Authentication</b> and click <b>Show Connect Info</b> to see the password (or set your own). Click OK.",
    ]),
    ("h2", "In the app"),
    ("fig", "settings-obs", f"{ui('System')} &rsaquo; {ui('Settings')} &rsaquo; OBS on a new install"),
    ("steps", [
        f"Open {ui('System')} &rsaquo; {ui('Settings')} and scroll to <b>OBS</b>.",
        "Set <b>WebSocket Enabled</b> to <b>Yes</b> and type the password from OBS. Host and port stay as they are.",
        "Leave <b>Scene Collection</b> and <b>Profile</b> blank; the app then accepts whatever OBS has open. "
        "The scene and source names already match the imported collection.",
        f"Click {ui('Save Configuration', 'primary')}.",
    ]),
    ("h2", "Test it"),
    ("fig", "obs-manager-top", f"{ui('OBS Manager')}: every line should read YES after the test"),
    ("p", f"Open {ui('Game Day')} &rsaquo; {ui('OBS Manager')} and click {ui('Test OBS Connection', 'primary')}. "
          "Each line should read YES, and Scenes Detected lists the imported scenes. Try "
          f"{ui('Use Camera')} and {ui('Use Graphic')} and watch 10.02 change in OBS."),
    ("callout", "rule", "CONTROLLED COMMANDS",
     "Settings &rsaquo; OBS &rsaquo; <b>Controlled Commands</b> lets the app show and hide the scoreboard in "
     "OBS for you. Leave it Disabled until the test is all green."),

    # 5 ---------------------------------------------------------------------
    ("section", "5", "Stream Settings and Going Live",
     "OBS sends the broadcast; YouTube or Facebook gives you the address to send it to."),
    ("steps", [
        f"In OBS open {obs('Settings', 'Stream')}, choose your service (YouTube or Facebook Live) and either "
        "connect your account or paste the stream key from your live dashboard.",
        f"In {obs('Settings', 'Output')}, a video bitrate of about 4500&ndash;6000 Kbps suits 1080p over a good "
        "connection; use less on a weaker one.",
        "Click <b>30.01 - LIVE FOOTBALL</b> in the Scenes list. That is the scene viewers see.",
        "When the app's pregame screen is up and your announcers are ready, click <b>Start Streaming</b>.",
    ]),
    ("callout", "tip", "QUICK LAUNCH",
     "In the app's Settings &rsaquo; Quick Launch, point <b>Broadcast Software</b> at OBS and add your "
     "YouTube and Facebook live pages. Pre-Game Setup then opens all three with one click each."),

    # 6 ---------------------------------------------------------------------
    ("section", "6", "When Something Looks Wrong",
     "Most problems come from the app not running, a name that doesn't match, or a page OBS cached."),
    ("table", ["What you see", "What to do"], [
        ["The scoreboard area is empty in OBS",
         "Make sure the app is running and a game is loaded, then right-click <b>BRWSR - Football Scorebug</b> "
         "&rsaquo; <b>Properties</b> &rsaquo; <b>Refresh cache of current page</b>."],
        ["The OBS Manager says a scene or source is missing",
         "Compare the name in OBS with Settings &rsaquo; OBS, letter for letter, including spaces and the dash."],
        ["Test OBS Connection fails",
         "Check that the WebSocket server is on in OBS, the port is 4455 in both places, and the password matches."],
        ["The scoreboard is cut off or too small",
         "Double-click the browser source and check Width 1920, Height 1080; check OBS's Video settings are 1920x1080."],
        ["The camera shows black",
         "Close any other program using the camera, then pick the device again in CAM - Primary Camera."],
    ]),
]
