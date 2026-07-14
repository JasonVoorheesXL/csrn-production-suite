CSRN PRODUCTION SUITE
Version 1.2 Alpha — Event Engine v1 Hotfix 4 — Event Engine v1 Hotfix 1
==========================================

PURPOSE
CSRN Production Suite is a local broadcast operations platform for managing
schools, venues, branding, game schedules, live scorebug data, and OBS output.

STABLE BASELINE
- Version: 1.0 Alpha
- Milestone: Phase 3.1 — Event Engine v1
- Internal build ID: V1.0A-P2-STABLE
- Promoted from: Build 0019 Corrected R4 Hotfix 6

START THE APPLICATION
1. Extract this folder to a permanent location.
2. Run RUN_CSRN_COMMAND_CENTER.bat.
3. The launcher creates a local Python environment and installs dependencies.
4. Open http://127.0.0.1:5050 if the browser does not open automatically.

MIGRATION
When prompted during first launch, select the previous working CSRN folder.
The upgrade manager preserves persistent schools, venues, logos, broadcasts,
settings, security data, and operator state.

OBS OVERLAY
Browser Source URL: http://127.0.0.1:5050/overlay
Recommended Browser Source size: 1920 x 1080

PRIMARY MODULES
- Game Manager: create, edit, delete, and manage broadcasts
- Command Center: load and operate an existing broadcast
- School Database: school identity, mascot, colors, and branding
- OBS Manager: validate WebSocket, scene, and Browser Source readiness
- Broadcast Team: operator and announcer assignments
- Settings: system configuration and maintenance

PHASE 2 FEATURES
- MHSAA Class 5A school database pilot
- Certified logo and generated monogram fallback
- Planned, Prepared, Live, and Completed broadcast lifecycle
- Persistent live game state for recovery and review
- Adaptive football scorebug for Graphic and Camera modes
- Possession glow and football indicator
- Optional clock display and configurable down/distance
- Simplified mobile game controls

FILES
- VERSION.txt: release identity and supported capabilities
- CHANGELOG.txt: consolidated development history
- Data/Logs/build_journal.json: detailed internal build journal
- requirements.txt: Python dependencies
- RUN_CSRN_COMMAND_CENTER.bat: normal launcher
- RESET_OPERATOR_PIN.bat: operator PIN reset utility

ROLLBACK
Keep your previous accepted installation unchanged until this package passes
local verification. This package should then become the rollback and source
baseline for Phase 3 development.

MIGRATION FIX
This hotfix detects both legacy Build_#### folders and semantic Version 1.0 Alpha / Hotfix folders located beside the new installation.


GRAPHICS ENGINE V1
Use the Graphics tab to configure and show the Lower Third Master. The lower third is rendered through the existing OBS browser source; no additional OBS source is required.


VERSION 1.3 ALPHA — ROSTER ENGINE V1
---------------------------------------
Open the new Rosters module to create a season roster. Varsity Football is the default workflow. Player records are fully editable, use Active/Inactive status, and may be removed between seasons. Jersey numbers may be changed at any time; duplicate numbers generate a warning rather than blocking the save.

CSV columns:
number,first_name,last_name,preferred_name,position,grade,height,weight,captain,starter,status


PLAYER GRAPHICS ENGINE V1
- Roster/player selection
- Preferred name on-air; full name retained for roster/search
- Player ID, Touchdown, Player of the Game, and Starting Lineup ID categories
- Optional sponsor lead-in/name/logo
- Headshot fallback to certified team logo/monogram


Personnel Engine: use the Personnel module to create reusable people records and the Graphics module to send Personnel Identification graphics to air.
