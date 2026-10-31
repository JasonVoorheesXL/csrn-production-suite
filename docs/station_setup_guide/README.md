# Station Setup Guide

`static/guides/station-setup-guide.pdf` is the guide a new station reads first: the
first-run wizard, the operator PIN, Settings, schools and rosters, crew,
sponsors, OBS, the first game, phones and tablets, and the game-night routine.
It is the same for every sport; keeping stats is covered by the per-sport
statistician guides. The app lists both under Settings > Guides and at the end
of the first-run wizard (see `guides_catalog.py`).

Every screenshot comes from a brand-new install set up as a fictional station,
Westside Sports Network (WSN).

## Rebuild

Run from a round worktree, never the production folder (the capture resets
`Data/` and the root state files to a fresh install, then restores them):

    .venv/Scripts/python.exe docs/station_setup_guide/tools/capture.py C:/Users/Darth/CSRN-RoundWork/guiderun-station
    .venv/Scripts/python.exe docs/station_setup_guide/tools/render_pdf.py

The capture uses the statistician guide's `run_demo_instance.py` on port 5075.
Text lives in `tools/guide_content.py`; the renderer and stylesheet are adapted
from `docs/statistician_guide/tools/`.
