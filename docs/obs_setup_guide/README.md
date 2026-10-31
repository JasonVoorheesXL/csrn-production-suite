# OBS Setup Guide and scene collection

- `static/obs/production-suite-scene-collection.json`: the scene collection a new
  station imports into OBS (Scene Collection > Import). It holds the scenes and
  sources the app checks by default (Settings > OBS), using only sources that
  ship with OBS, and nothing from any one station's computer. The app offers it
  from the OBS Manager and Settings > OBS ("Download OBS Scene Collection").
- `static/guides/obs-setup-guide.pdf`: the guide, listed in `guides_catalog.py`
  for every station.

## Rebuild

From a round worktree, never the production folder:

    .venv/Scripts/python.exe docs/obs_setup_guide/tools/build_scene_collection.py
    .venv/Scripts/python.exe docs/obs_setup_guide/tools/capture.py C:/Users/Darth/CSRN-RoundWork/guiderun-obs
    .venv/Scripts/python.exe docs/obs_setup_guide/tools/render_pdf.py

`capture.py` reuses the Station Setup Guide's fresh-install capture helpers.
`tests/test_obs_scene_collection.py` fails if the shipped file drifts from the
builder or from the names in Settings > OBS.
