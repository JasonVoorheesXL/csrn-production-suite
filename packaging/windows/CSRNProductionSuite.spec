# PyInstaller specification for the commercial Windows runtime.
#
# Round 15F changes vs. the original scaffold:
#   * entry point is csrn_desktop.py (the pywebview shell), not app.py --
#     the shell re-execs itself `--serve-only` to run Waitress (Round 15D);
#   * console=False (GUI shell);
#   * bundle rulesets/ (Round 14 found it was missing -> the Round 7
#     ruleset engine silently fell back to literals in a frozen build);
#   * the nonexistent Graphics/ datas entry is removed;
#   * the live-caption native stack (ctranslate2, onnxruntime, av,
#     faster_whisper, sounddevice, tokenizers) + cmudict/pronouncing data
#     are collected explicitly -- these are the flagged PyInstaller pain
#     points and MUST be verified by importing them from a built onedir,
#     not just the dev venv (see docs/packaging.md);
#   * the whisper small.en model and Playwright's Chromium are bundled
#     (the "bundle both, no first-run download" decision) from paths given
#     by env vars so a plain dev `pyinstaller` still succeeds without them;
#   * run_core_foundation.py (a second, debug Flask entry point that cannot
#     be runtime-gated) and pytest are excluded.
#
# Code signing is deliberately deferred this round -- unsigned artefacts
# must not be represented as signed production releases.

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH).parents[1]


def _tree(source: Path, target: str):
    """A (src, dest) datas entry, or None when src is absent."""
    return (str(source), target) if source.exists() else None


def _env_tree(var: str, target: str):
    raw = os.environ.get(var, "").strip()
    if not raw:
        print(f"[spec] {var} not set -- '{target}' will NOT be bundled.")
        return None
    source = Path(raw)
    if not source.exists():
        print(f"[spec] {var}={raw} does not exist -- '{target}' will NOT be bundled.")
        return None
    return (str(source), target)


datas = []
binaries = []
hiddenimports = ["webview"]

for package in (
    "ctranslate2",
    "onnxruntime",
    "av",
    "faster_whisper",
    "sounddevice",
    "tokenizers",
):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

datas += collect_data_files("cmudict")  # ships cmudict.dict as package data
datas += collect_data_files("pronouncing")

# Repo assets the app resolves relative to its module root.
for entry in (
    _tree(ROOT / "templates", "templates"),
    _tree(ROOT / "static", "static"),
    _tree(ROOT / "rulesets", "rulesets"),
    _tree(ROOT / "VERSION.txt", "."),
    # Bundled (no first-run download): set these in the release build env.
    #   CSRN_WHISPER_MODEL_DIR  -> a CTranslate2 faster-whisper small.en dir
    #   CSRN_BUNDLED_CHROMIUM_DIR -> a `playwright install chromium` browsers dir
    _env_tree("CSRN_WHISPER_MODEL_DIR", "models/faster-whisper-small.en"),
    _env_tree("CSRN_BUNDLED_CHROMIUM_DIR", "ms-playwright"),
):
    if entry is not None:
        datas.append(entry)

analysis = Analysis(
    [str(ROOT / "csrn_desktop.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        str(ROOT / "packaging" / "windows" / "rthook_bundled_runtime.py"),
    ],
    excludes=["pytest", "run_core_foundation"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="CSRNProductionSuite",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "static" / "csrn-logo.ico"),
)
collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CSRNProductionSuite",
)
