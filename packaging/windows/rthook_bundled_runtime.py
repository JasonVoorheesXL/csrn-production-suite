"""PyInstaller runtime hook: point Playwright and Hugging Face at the
assets bundled next to the frozen executable (Round 15F -- "bundle both,
no first-run download").

Runs before any application code. Keeps app modules untouched:
``broadcaster_print_service.py`` / ``dragonfly_service.py`` (Playwright) and
``caption_worker.py`` (faster-whisper) just read the environment.
"""

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    _bundle = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))

    # Playwright: use the Chromium bundled at <bundle>/ms-playwright and do
    # not try to download one.
    _chromium = _bundle / "ms-playwright"
    if _chromium.is_dir():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(_chromium))
    os.environ.setdefault("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "1")

    # faster-whisper / Hugging Face: use the CTranslate2 model bundled at
    # <bundle>/models/faster-whisper-small.en, fully offline.
    _model = _bundle / "models" / "faster-whisper-small.en"
    if _model.is_dir():
        # caption_worker passes settings.model_name straight to WhisperModel;
        # a directory path makes it load locally instead of resolving a repo
        # id. The caption profile's `caption_model` still overrides this.
        os.environ.setdefault("CSRN_WHISPER_MODEL_DIR", str(_model))
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
