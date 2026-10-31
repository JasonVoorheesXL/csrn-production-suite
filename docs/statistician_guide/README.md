# Statistician Screen walkthrough (football)

`static/guides/statistician-guide-football.pdf` (shipped with the app and opened from Settings > Guides) is a CSRN-branded how-to for a first-time volunteer
statistician. It covers the Statistician Console only, phase by phase, from pregame through Final.

Every screenshot in `screenshots/` was captured by Playwright driving the real console against a
fictional demo broadcast, `FB-DEMO-GUIDE-001` (Northgate Falcons vs. Riverside Otters, with invented
rosters). `capture_log.json` records the game state behind each screenshot.
`capture_statistics.json` is the box score the demo game produced.

## Rebuild

From a worktree (the build refuses to run in the production folder):

```
.venv/Scripts/python.exe docs/statistician_guide/tools/build_guide.py <scratch_runtime_dir>
```

This resets the worktree's `Data/` to a pristine checkout and writes a credential-free demo
`Data/Settings/config.json`, `state.json` and a fresh throwaway PIN. It then starts an isolated
instance on port 5072, with `%LOCALAPPDATA%`, the state authority file, the template state and the
backup roots all redirected into the scratch dir. It seeds the demo game, drives the walkthrough and
renders the PDF.

To re-render only the PDF from the existing screenshots, run `tools/render_pdf.py`.

| File | Role |
|---|---|
| `tools/run_demo_instance.py` | Isolated server; pins the broadcast id to `FB-DEMO-GUIDE-001` |
| `tools/seed_demo_broadcast.py` | Invented schools/rosters, creates, loads and starts the broadcast, hands control to the statistician |
| `tools/walkthrough.py` | Playwright script that plays the game and captures screenshots |
| `tools/guide_content.py` | All guide text |
| `tools/guide.css`, `tools/render_pdf.py` | CSRN print theme; HTML to PDF via Playwright Chromium, merged with pypdf |
