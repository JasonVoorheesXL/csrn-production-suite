# pywebview App-Shell Scoping (Round 14 — investigate only)

**Status:** scoping report. No integration code, no packaging changes, no
dependency additions were made in this round. Confirm the decisions flagged
below before Round 15 implementation starts.

**Goal:** wrap the existing Flask/Waitress backend in a pywebview desktop
shell so a customer double-clicks one icon and is in the app, instead of
running `CSRN_GAME_DAY_LAUNCHER.ps1` by hand.

---

## Task A — Current launch & runtime survey

### A.1 What happens today, double-click to running app

1. **Shortcut → `CSRN_GAME_DAY_LAUNCHER.ps1`** (PowerShell,
   `$ErrorActionPreference = "SilentlyContinue"`).
   - `$Repo` is a **hard-coded absolute path**
     (`C:\Users\Darth\My Drive\CSRN\…`) — dev-machine specific.
   - `$CommandCenter = "http://127.0.0.1:5050/?module=pregame"`.
2. **OBS:** `Get-Process obs64`; if absent, probe three install locations
   (`%ProgramFiles%`, `%ProgramFiles(x86)%`, `%LOCALAPPDATA%\Programs`) and
   `Start-Process` the first `obs64.exe` found. OBS is *launched* here but is
   not otherwise CSRN's concern (control is over OBS WebSocket, `obs_client.py`).
3. **CSRN health triage — `Get-CsrnHealth`, three states:**
   - `DOWN` — nothing listening on TCP 5050 → start CSRN.
   - `HEALTHY` — port bound **and** `GET /api/health` → 200 `{"status":"ok"}`
     within 3 s → do nothing.
   - `HUNG` — port bound but health check errored/timed out → WPF `MessageBox`
     names the owning PID (`Get-NetTCPConnection -LocalPort 5050 -State Listen`
     → `Get-Process`) and offers kill + restart. Decline → exit without opening
     tabs at a known-bad instance.
4. **Start when DOWN:** `Start-Process cmd.exe /k "RUN_CSRN_COMMAND_CENTER.bat"`
   in `$Repo` (a visible, persistent `cmd` window).
5. **`RUN_CSRN_COMMAND_CENTER.bat`:**
   - `cd /d "%~dp0"`; require `.venv\Scripts\python.exe` (else point at
     `SETUP_CSRN_ENVIRONMENT.bat`).
   - `python tools\environment_check.py --profile runtime` — Python must be
     **exactly 3.13.14** and every `requirements.txt` pin must match the
     installed version exactly; hard-fail otherwise.
   - `python tools\game_day_preflight.py` — `get_game_day_safety_service()
     .ensure_startup_snapshot()`: storage/JSON-state health + automatic safety
     snapshot; blocks on `PREFLIGHT_FAILED` / `SNAPSHOT_FAILED`.
   - `python tools\game_day_recovery.py startup` — `get_recovery_service()
     .mark_startup(pid=…)` writes the startup / unclean-shutdown marker.
   - `python app.py` — the server.
   - Exit 0 → `game_day_recovery.py shutdown` writes the clean-shutdown
     marker. Non-zero → marker retained → next start reports
     `UNCLEAN_SHUTDOWN_DETECTED`.
   - `pause`.
6. **`app.py` `__main__`:**
   - `PRODUCT_PATHS = resolve_product_paths(BASE_DIR, frozen = sys.frozen or
     "--installed" in sys.argv)`; `PRODUCT_PATHS.ensure()` creates dirs.
   - `ensure_data_architecture()`, `load_config()`.
   - Installs SIGINT/SIGTERM → `_record_clean_shutdown_and_stop` (clean-shutdown
     marker + `STATE_REPOSITORY.flush()` of the Drive mirror, then
     `raise SystemExit(0)`). **A force-kill or crash deliberately leaves the
     unclean marker.**
   - `start_isolated_media_server(...)` — a **second HTTP server**
     (`ThreadingHTTPServer` on `0.0.0.0:5051`, daemon thread,
     `routes/asset_routes.py`) serving sponsor/asset video/audio out-of-band
     from Waitress. **If 5051 cannot bind, the app refuses to start**
     (`SystemExit(1)`).
   - Prints the banner (`Laptop: http://127.0.0.1:5050`,
     `Phone/iPad: http://<lan-ip>:5050`, `OBS overlay: …/overlay`,
     `Media server: …:5051`).
   - `waitress.serve(app, host="0.0.0.0", port=5050, threads=16)` — blocks
     until a signal.
7. **Launcher waits** up to 60 × 1 s for `HEALTHY`, then opens **Chrome**
   (three candidate paths; falls back to the default browser):
   - `--new-window http://127.0.0.1:5050/?module=pregame` (the control surface);
   - a tab at the **Facebook Live** producer URL;
   - a tab at the **YouTube Live** dashboard URL.
   - Stream URLs: the literals in the script are fallbacks only — it first
     does `GET http://localhost:5050/api/identity/streaming-links` (5 s
     timeout) and overrides from the Identity Profile (Round 12).

### A.2 Runtime dependency inventory (what the app needs to function)

| Dependency | Notes |
|---|---|
| **Python 3.13.14 exactly** | `environment_check.SUPPORTED_PYTHON=(3,13,14)`. 3.14 breaks collection (missing `pronouncing`). |
| **`requirements.txt` (all pinned)** | Flask 3.0.3 / Werkzeug / Jinja2 / itsdangerous / click / blinker / MarkupSafe; **waitress 3.0.0**; **websocket-client 1.8.0** (OBS WebSocket, `obs_client.py`); **Pillow 12.3.0**; **numpy 2.5.2**; PyYAML; httpx/httpcore/h11/anyio/idna/certifi (weather NWS, Facebook, HF downloads). |
| **Live-caption ASR stack** | **sounddevice 0.5.5** (+ bundled PortAudio, `_sounddevice_data`) for capture; **faster-whisper 1.2.1 + ctranslate2 4.8.1 + onnxruntime 1.28.0 + tokenizers + huggingface-hub + hf-xet + av 18.0.0 (PyAV — bundles ffmpeg libs) + flatbuffers + protobuf + tqdm**. |
| **`playwright 1.62.0`** | Python package only. Used by `broadcaster_print_service.py` (roster print sheet → PDF via headless `page.pdf()`) and `dragonfly_service.py` (headless render/capture). |
| **Playwright Chromium browser** | **Separate ~150 MB download** (`playwright install chromium` → `%LOCALAPPDATA%\ms-playwright`), *not* a pip package. Feature-scoped: only the print-sheet and dragonfly features touch it. |
| **`pronouncing` 0.3.0 + `cmudict` 1.1.3** | Imported by `roster_service.py` (name pronunciation). **NOT in `requirements.txt`** — installed in the venv but unpinned/unlisted. `cmudict` ships a ~3.5 MB `cmudict.dict` data file. |
| **NVIDIA CUDA GPU + CUDA 12 cuBLAS + cuDNN 9** | `caption_worker._load_model()` loads faster-whisper with `device="cuda", compute_type="float16"` and **hard-errors** if CUDA / the DLLs (`cublas64_12.dll`, `cudnn_ops64_9.dll`) are absent. **Live captions are GPU-only — there is no CPU fallback in the current code.** |
| **faster-whisper model weights** | `CaptionWorkerSettings.model_name = "small.en"` (override: config `caption_model`). A bare name is downloaded from HuggingFace (`Systran/faster-whisper-small.en`, ~480 MB) into the HF cache on first caption start unless given a local directory. |
| **`static/`** | Theme engines (neon, friday-night, heritage-press, 8bit), layout engine JS/CSS, `csrn-logo.png` / `.ico`, navigation, `branding/`. Served by Flask relative to the `app` module root. |
| **`templates/`** | `index.html` (control surface), `overlay.html`, `pregame_universal_overlay.html`, `captions.html`, recap/social/theme/weather managers. |
| **`rulesets/`** | `rulesets/football/us-nfhs.json` + `us-ms-mhsaa.json`, resolved as `Path(__file__).resolve().parent / "rulesets"` in `ruleset_service.py`. Round 7 engine; consumers fall back to literals if missing. |
| **Identity Profile** | `identity_profile.json` (repo root in dev; runtime root when installed). Self-seeds (legacy Caledonia values if `state.json`/`config.json` exist, blank otherwise). Gitignored. |
| **Runtime data tree** | `Data/**` (Schools, Rosters, Personnel, Settings/config.json, Broadcasts, Venues, Logos, Assets, Sponsors, Captions, Backups, Logs…), `state.json`, `security.json`. Gitignored user data; relocates under `%LOCALAPPDATA%\PossumFrog\CSRN Production Suite` when installed. |
| **OBS Studio** | External app. Launched by the `.ps1`; controlled over OBS WebSocket. Not a Python dependency. |
| **No external `ffmpeg`/`ffprobe`/`node`** | ffmpeg libraries arrive inside the `av` (PyAV) wheel for faster-whisper audio decode; nothing shells out to a media binary. |

### A.3 Source-checkout assumptions vs. what `installed_mode` already handles

**Already handled** (frozen, or `--installed`, or `CSRN_INSTALLED` /
`CSRN_RUNTIME_ROOT` / `CSRN_DATA_ROOT`):

- All of `Data/`, `state.json`, `security.json`, `identity_profile.json`,
  Logs, Exports, Updates, Support, Licensing move to
  `%LOCALAPPDATA%\PossumFrog\CSRN Production Suite`; `PRODUCT_PATHS.ensure()`
  creates them.
- `internal_tools_enabled()` flips **OFF** (see C.6).
- `entitlement_service` switches from the dev entitlement to "unlicensed".
- `product_paths.migrate_legacy_runtime()` can copy a legacy colocated tree
  once, behind the phrase `MIGRATE LEGACY CSRN DATA`.

**Still assumes a source checkout / not frozen-safe:**

- **`CSRN_GAME_DAY_LAUNCHER.ps1`** — hard-coded `$Repo`; assumes `.venv`,
  `RUN_CSRN_COMMAND_CENTER.bat`, Chrome; opens external stream tabs. Entirely
  developer-oriented; the shell replaces it.
- **`RUN_CSRN_COMMAND_CENTER.bat`** — same `.venv` assumption; shells out to
  `python tools\*.py` three times (those scripts `import app`, so in a frozen
  build they would re-enter the bundle, not run as scripts).
- **`tools/environment_check.py`** — verifies pip metadata against
  `requirements.txt`; meaningless in a frozen build (no pip metadata, and no
  `requirements.txt` on disk unless bundled). The `.bat` preflight chain must
  be branched on `sys.frozen`.
- **`ruleset_service.rulesets_dir()`** = `Path(__file__).parent / "rulesets"`
  — the current `.spec` **does not bundle `rulesets/`**; a frozen build would
  silently degrade the Round 7 engine to literals everywhere. **Gap.**
- **`packaging/windows/CSRNProductionSuite.spec`** — `datas` lists a
  `Graphics/` dir that **does not exist** at repo root (stale), omits
  `rulesets/`, targets `app.py` with `console=True`.
- **`tools/game_day_recovery.py mark-known-good`** shells `git rev-parse HEAD`
  — no-op in a frozen build (harmless; that subcommand is not on the startup
  path).
- **`run_core_foundation.py`** — second Flask entry point with the Werkzeug
  debug server; `internal_only_surfaces.json` says exclude from the bundle
  entirely (it cannot be runtime-gated).
- **`Flask(__name__)`** (`import_name="app"`) — frozen onedir usually resolves
  `templates/` + `static/` via the bundled module path, but this is a known
  PyInstaller + Flask friction point; an explicit `template_folder` /
  `static_folder` or a `sys._MEIPASS` resource resolver removes the risk.

---

## Task B — pywebview integration shape (proposed, not built)

```
[ CSRNProductionSuite.exe ]
    ├─ Waitress: serve(app, host="0.0.0.0", port=5050, threads=16)   ← unchanged
    ├─ Isolated media server: 0.0.0.0:5051 (daemon thread)           ← unchanged
    ├─ Live-caption worker (in-process, started on demand)           ← unchanged
    └─ Main thread: webview.create_window(
                        "CSRN Command Center",
                        "http://127.0.0.1:5050/?module=pregame")
                    webview.start()                                  ← blocks until closed
```

pywebview opens **one** native window (WebView2 / Edge Chromium on Windows)
pointed at the already-running local Flask app. Waitress still serves every
byte; pywebview is only the chrome around the operator's control surface. The
double-click → PowerShell → `cmd` window → Chrome chain collapses into one
icon and one window, no visible console, no `pause`.

### B.1 What pywebview replaces

Only the operator's Chrome "Command Center" tab (`/?module=pregame` and the
modules it navigates to).

### B.2 What pywebview explicitly does NOT replace / touch

- **OBS browser sources.** OBS scrapes overlay URLs directly over HTTP —
  `http://127.0.0.1:5050/overlay`, the scorebug, tickers,
  pregame/halftime/postgame scenes, `pregame_universal_overlay.html`,
  `captions.html` — rendered by OBS's own embedded CEF browser hitting
  Waitress on 5050. The pywebview window is a *different* window and has no
  bearing on what OBS fetches. **OBS scene collection and source URLs are
  unchanged.**
- **Phone / tablet / iPad statistician access over the LAN.** Waitress
  already binds `0.0.0.0:5050`. As long as the shell keeps `host="0.0.0.0"`
  (never narrows it to `127.0.0.1`), every non-loopback client keeps working
  exactly as today. Session cookie is `SameSite=Strict`, `Secure=False` —
  fine for plain-HTTP LAN, no change.
- **The isolated media server on 5051.** Still a separate thread/server; the
  shell must preserve the "5051 fails → don't start" guard.
- **Windows Firewall.** First run still prompts to allow inbound 5050/5051
  (or the installer adds the rule). Unchanged.

### B.3 What the shell code must own

1. **Process lifecycle / ordering:**
   - Start Waitress + the media server.
   - **Poll `GET http://127.0.0.1:5050/api/health` until `{"status":"ok"}`**
     (the same lock-free probe the `.ps1` uses) before
     `webview.create_window`, with a timeout + error dialog.
   - Detect "5050 already bound" (another instance / a hung prior run) —
     replicate the `.ps1` DOWN/HEALTHY/HUNG triage, or single-instance-lock
     the exe and surface "CSRN is already running".
   - **Clean shutdown on window close.** Today only SIGINT/SIGTERM trigger
     `_record_clean_shutdown_and_stop` (clean-shutdown marker + Drive-mirror
     flush). A window close delivers no signal, so the shell's
     `on_closing` / `closed` handler must call the same path:
     `get_recovery_service().mark_clean_shutdown()` +
     `STATE_REPOSITORY.flush()` + stop Waitress + join the caption worker +
     stop the media server. Otherwise **every normal exit looks unclean** and
     the next start cries `UNCLEAN_SHUTDOWN_DETECTED`.
   - Replace the `.bat` preflight chain: call
     `get_game_day_safety_service().ensure_startup_snapshot()` and
     `get_recovery_service().mark_startup()` in-process at boot (already
     importable service calls); **skip `environment_check.py`** when frozen.

2. **Process model (owner decision):**
   - **(a) In-process** — shell runs `waitress.create_server(app, …)` on a
     thread, `webview.start()` on main. One PID, simplest lifecycle; but a
     hard crash takes window and server together, and pywebview + Waitress +
     the caption worker + onnxruntime/ctranslate2 share one interpreter.
   - **(b) Child process** *(recommended for the first cut)* — shell
     `Popen`s the existing `app.py` path (or an `--serve-only` mode) and owns
     only the window + health poll + teardown (send `CTRL_BREAK_EVENT` / a
     shutdown request so `app.py`'s existing signal handler still runs, then
     wait for the clean marker). Keeps `app.py.__main__` (signals, media
     server, banner) almost untouched; survives a UI crash; costs a second
     process + a shutdown IPC.

3. **Window chrome / sizing:**
   - Title `CSRN Command Center`; icon `static/csrn-logo.ico`.
   - Default ~1600 × 1000, `min_size` ~1280 × 800 (the control surface is
     dense). Resizable; remember last size/position in the runtime root.
   - Normal resizable window, **not** kiosk/fullscreen — operators run this
     beside OBS on one or two monitors.
   - `confirm_close=True` so a stray Alt-F4 mid-broadcast prompts ("CSRN is
     live — close anyway?"), ideally tied to broadcast-live state.
   - `webview.start(debug=False)` in production (gate dev tools / reload
     behind `CSRN_INTERNAL_TOOLS`).
   - **File downloads** (SRT/VTT caption exports, roster print-sheet PDF,
     recap/social exports, support bundle) currently rely on a browser's
     download handling. WebView2 download support via pywebview is limited —
     **verify each path works in the window, or re-route through a "save to
     `<runtime root>\Exports` + reveal in Explorer" server-side action.**

4. **LAN access unchanged** — the one hard rule is keep `host="0.0.0.0"`.
   Optional nicety: a menu item showing the LAN URL / a QR code for the
   statistician's iPad (`qrcode` is already vendored in `third_party/`).

5. **New dependency:** `pywebview` (pulls `pythonnet` + the Edge **WebView2
   runtime**; evergreen WebView2 is preinstalled on Win10 21H2+/Win11, a
   bootstrapper may be needed for older Win10). Round 15 adds the pin to
   `requirements.txt` + `environment_check`; this round adds nothing.

---

## Task C — Packaging & distribution mechanics

**Recommended path: PyInstaller *onedir* + Inno Setup** — exactly what
`packaging/windows/` already scaffolds and what `PHASE_6_7` commits to.

- **onedir, not onefile:** faster cold start (no self-extract to temp), and
  the CUDA / ctranslate2 / onnxruntime / WebView2 native libs behave far
  better unpacked. onefile is a non-starter with this much native baggage.
- **Alternatives considered:** Nuitka (better runtime perf, slower/finicky
  builds, weaker ecosystem for this native stack — not worth it now);
  briefcase/BeeWare (assumes its own app model — fights the existing
  factory/entry-point layout); ship-the-venv + launcher exe (no isolation,
  customer sees Python — rejected for a commercial build).

### C.1 Already reserved / in place

- `product_paths.ProductPaths`: `license_file =
  runtime_root/Licensing/license.json`, `installation_file =
  runtime_root/Licensing/installation.json`; `installed_mode` drives every
  path fork.
- `entitlement_service`: `_development_license()` for source checkouts;
  installed builds "begin unlicensed"; feature/sport scopes defined (core
  broadcast, captions, weather, graphics/stats, themes, social, recaps). No
  payment processor / activation server yet (explicitly out of `PHASE_6_7`
  scope).
- `tools/build_release_package.py`: deterministic ZIP + `release.json`
  (product id, semver, build, per-file size + SHA-256),
  `require_clean_tracked_tree`, reproducible timestamps — the *update
  payload* format, not the installer.
- `packaging/windows/csrn-production-suite.iss`: per-user install to
  `{localappdata}\Programs\PossumFrog\CSRN Production Suite`,
  `PrivilegesRequired=lowest`, x64, shortcuts pass **`--installed`**,
  uninstall removes `{app}` but **preserves**
  `%LOCALAPPDATA%\PossumFrog\CSRN Production Suite` runtime data. Fixed AppId
  GUID.
- `docs/internal_only_surfaces.json` + `internal_tools_enabled()` (Round 12).

### C.2 `.spec` is stale / incomplete

- Add `rulesets/` to `datas` (else the Round 7 engine silently degrades to
  literals).
- Drop the non-existent `Graphics/` entry; keep `templates/`, `static/`,
  `VERSION.txt`.
- Collect the native stack: `ctranslate2`, `onnxruntime`, `av`,
  `faster_whisper` (its `assets/`, incl. the Silero VAD `silero_vad.onnx`),
  `sounddevice` / `_sounddevice_data`, `tokenizers`, `numpy`; add `cmudict`
  **data files** (`cmudict/data/*`) and the `pronouncing` package.
  ctranslate2/onnxruntime typically need explicit `--collect-binaries`.
- Entry point becomes Round 15's shell (`csrn_desktop.py`); `console=False`;
  `app.py` stays importable; **exclude `run_core_foundation.py`** and
  `pytest`.

### C.3 Playwright Chromium — not pip-bundlable cleanly

Options (owner decision):
- **(a)** installer post-step runs `playwright install chromium` into the
  runtime root + set `PLAYWRIGHT_BROWSERS_PATH` (needs network at install
  time);
- **(b)** *(most reliable offline)* bundle a pinned Chromium as installer
  `[Files]` and point `PLAYWRIGHT_BROWSERS_PATH` at `{app}` (~150 MB added to
  the installer);
- **(c)** graceful-degrade the two dependent features (roster print-sheet
  PDF, dragonfly capture) with a "Chromium component not installed" message +
  an in-app "Install now" button.

### C.4 Live-caption model + CUDA

- `small.en` weights (~480 MB) download from HuggingFace on first caption
  start. For an offline install: bundle the CTranslate2-converted model under
  the runtime root and set `caption_model` to that path, **or**
  first-run-download with a progress UI.
- **CUDA 12 cuBLAS + cuDNN 9** are a hard runtime requirement for captions
  and should **not** be shipped in the installer (licensing + size). Document
  the prerequisite, detect it at caption-start (the code already raises a
  clear error), surface it in a readiness check. Consider adding a CPU `int8`
  fallback in Round 15 so captions are not strictly GPU-gated for smaller
  customers *(owner decision)*.

### C.5 First-run / onboarding flow — UNDEFINED

Round 12/13 built the Identity Profile **file** (blank-seeds on a fresh
install) and made it editable via `POST /api/config` /
`ConfigurationService`. There is **no first-run screen**. A fresh customer
double-clicking the icon today lands on `/?module=pregame` with a blank org
name, no schools, no logo. Round 15 needs a detect-blank-profile check →
route to a setup view (org name / short name / logo / colors, home venue,
timezone, primary school) that writes through the existing `/api/config`
surface, then continues to the normal control surface. **This is the single
biggest UX gap for a commercial build.**

### C.6 `CSRN_INTERNAL_TOOLS` OFF in a frozen build — confirmed correct

`internal_tools_enabled()` returns `not PRODUCT_PATHS.installed_mode`.
`installed_mode` is true when `getattr(sys, "frozen", False)` (PyInstaller
sets this) **or** `--installed` in argv (the `.iss` shortcuts pass it)
**or** the env vars. So a PyInstaller build resolves to `installed_mode =
True` → internal tools **OFF** by default.

**Caveat:** the packaging step must **not** set `CSRN_INTERNAL_TOOLS` in the
environment or any wrapper, and `run_core_foundation.py` must be physically
excluded (it is not gated). Add a build smoke test: launch the frozen exe,
assert `GET /api/diagnostics` → 404 and `GET /api/health` → 200.

### C.7 Code-signing / SmartScreen

The `.iss` states signing config is intentionally external. An unsigned exe +
installer will trip **SmartScreen "Windows protected your PC"** and can trip
AV heuristics (PyInstaller bootloader + bundled DLLs are a common
false-positive trigger). For a paid product this needs an **Authenticode
certificate**:

- standard **OV** cert ≈ $200–500/yr (SmartScreen reputation accrues over
  time / download volume);
- **EV** cert ≈ $300–700/yr (immediate SmartScreen trust; may require a
  hardware token / cloud HSM).

Sign both `CSRNProductionSuite.exe` and the Inno `Setup.exe`. *(Owner
decision: which cert, and who holds it — PossumFrog.)*

### C.8 Update mechanics — partially defined

Defined: `build_release_package.py` + `/api/deployment/update/validate|prepare`
give a validated ZIP payload with `release.json` hashes, a pre-update
snapshot, and a pending-update plan; `PHASE_6_7` states "the running Flask
process never replaces its own binaries — a stopped, external updater is
required".

Missing: the external updater executable itself; an update *check* (how does
the customer learn Round 15 shipped — a version endpoint the app polls, or a
manual "Check for updates"); the download host. Also the deployment routes
are currently `internal_only_surfaces.json`-gated, so an in-app customer
updater would need them (or a customer subset) un-gated.

**Simplest v1: manual reinstall** — customer downloads a new signed
installer that upgrades in place (Inno handles it; runtime data is
preserved). Auto-update is a Round 16+ project. *(Owner decision.)*

---

## Task D — Risks & open decisions for the owner

1. **Bundle size.** Rough: PyInstaller runtime + Flask/waitress (~30 MB) +
   numpy/Pillow (~40 MB) + the caption ASR stack (ctranslate2 + onnxruntime +
   tokenizers + av/ffmpeg libs, ~250–400 MB) + Playwright Chromium (~150 MB)
   + optional bundled whisper model (~480 MB) ≈ **~0.5 GB without the model,
   ~1 GB with it**. Decide: bundle the model or first-run-download? Bundle
   Chromium or post-install fetch? These swing the installer between ~250 MB
   and ~1 GB.
2. **Antivirus / SmartScreen false-positives without signing — a real risk,
   not hypothetical.** Unsigned PyInstaller onedir apps with bundled native
   DLLs are routinely SmartScreen-walled (no reputation) and occasionally
   Defender/third-party-AV-flagged. Impact on a non-technical customer: the
   "Windows protected your PC" wall, or a silently quarantined exe.
   Mitigation is code-signing (C.7) + submitting the binary for reputation.
   **Recommend budgeting for a cert before any customer ship.**
3. **Youth-tier / native-companion-app plans.** **No such plans are
   documented anywhere in the repo** — no "youth", "companion", or "rec
   league" references in `docs/`, and `ROADMAP.md` / `PHASE_6` stop at the
   commercial Windows product. If the owner has unwritten plans: (a) a thin
   client of this same Flask backend → the pywebview shell is orthogonal, no
   impact; (b) a cut-down youth build → the `entitlement_service` feature
   scopes + `internal_tools_enabled`-style gating are the right mechanism and
   the shell is unaffected; (c) only a companion that *embeds* or *replaces*
   the control surface would make the window/architecture choices here
   matter. **Assume no bearing unless the owner flags otherwise.**
4. **Dependencies hard to bundle with PyInstaller:**
   - **ctranslate2 + onnxruntime** — native CUDA/CPU libs; need explicit
     `--collect-binaries` / hooks; the CUDA variant still depends on the
     *system* CUDA runtime (cuBLAS/cuDNN), which can't be shipped.
     Historically the #1 PyInstaller pain point in this stack.
   - **Playwright** — deliberately not a bundled-browser model (C.3).
   - **sounddevice / PortAudio** — usually fine (wheel bundles the DLL) but
     needs `_sounddevice_data` collected.
   - **pywebview / pythonnet / WebView2** — pythonnet needs a CLR; WebView2
     is a system component (evergreen on Win11; bootstrapper for old Win10).
   - **faster-whisper assets** — the Silero VAD `.onnx` inside the package is
     easy to miss (`--collect-data faster_whisper`).
   - **`pronouncing` + `cmudict`** — not in `requirements.txt` at all right
     now; must be added to the lock *and* the `.spec` `datas`.
5. **`environment_check.py` / preflight chain** assumes pip metadata +
   `requirements.txt` on disk + Python 3.13.14 exactly. None of that holds in
   a frozen build; Round 15 must branch the startup path on `sys.frozen` so a
   customer is not hard-blocked by a check that cannot pass.
6. **Clean-shutdown semantics change with a window.** Today force-kill =
   unclean marker (intentional). The window's close button, taskbar-close,
   and OS shutdown must all be wired to the clean-shutdown path, or every
   exit is "unclean" and the recovery service cries wolf. Needs care + a
   test.
7. **File downloads inside WebView2** (caption exports, roster PDF, recaps,
   support bundle) — verify or re-route server-side (B.3).

---

## Proposed Round 15 implementation breakdown

One task per commit, full suite green after each, WIP files
(`templates/index.html`, `broadcaster_print_service.py`) still 0 bytes
changed.

| Task | Scope |
|---|---|
| **15A** | Add `pywebview` (pinned) to `requirements.txt` / `requirements-dev.txt` / `environment_check` profiles; add `pronouncing` + `cmudict` to the lock (already installed, currently unlisted). No behaviour change. |
| **15B** | New `csrn_desktop.py` shell — child-process model: `Popen` the existing server path, poll `/api/health`, `webview.create_window(… "http://127.0.0.1:5050/?module=pregame")`, `on_closing` → graceful child shutdown (existing signal handler) + wait for the clean marker. Icon `static/csrn-logo.ico`, size / min-size, `confirm_close`. Keep `host="0.0.0.0"`. Unit-test the health-poll + teardown with a fake server. |
| **15C** | Startup path: when `sys.frozen`, run `ensure_startup_snapshot()` + `mark_startup()` in-process and skip `environment_check`; keep the `.bat` path for source checkouts. Test both branches. |
| **15D** | First-run onboarding: detect a blank Identity Profile (`organization.name == ""` and no schools), serve a setup view that writes through `POST /api/config`, then hand off to `/?module=pregame`. Existing-install path unchanged (test: seeded profile skips onboarding). |
| **15E** | Fix `CSRNProductionSuite.spec`: entry `csrn_desktop.py`, `console=False`, add `rulesets/`, drop `Graphics/`, collect the ASR/native stack + `cmudict` data + `faster_whisper` assets, exclude `run_core_foundation.py` + `pytest`. Post-build smoke test: frozen exe → `/api/health` 200, `/api/diagnostics` 404. |
| **15F** | Playwright Chromium strategy per the owner's C.3 decision (post-install `playwright install` + `PLAYWRIGHT_BROWSERS_PATH`, or bundled Chromium, or graceful-degrade). Test the degrade path. |
| **15G** | Update `csrn-production-suite.iss`: shortcut → the shell exe (still `--installed`), version wiring from `VERSION.txt`, WebView2 bootstrapper `[Run]` step for old Win10, firewall rule for 5050/5051. Document (do not implement) code-signing + the external updater. |
| **15H** | Docs: keep `CSRN_GAME_DAY_LAUNCHER.ps1` / `RUN_CSRN_COMMAND_CENTER.bat` as the *developer* run path; the shell is the *customer* path. Update `OVERNIGHT_SUMMARY.md` + memory. |
