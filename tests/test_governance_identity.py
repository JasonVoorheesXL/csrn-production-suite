from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.13.0-alpha.8f"
TITLE = "Player Identity Repair and Source Alignment"
BUILD = "V1.13A8F-SOURCE-ALIGNMENT"


def test_canonical_identity_is_synchronized() -> None:
    required_version_files = (
        "VERSION.txt",
        "README.md",
        "README.txt",
        "ROADMAP.md",
        "CHANGELOG.txt",
        "CHANGELOG.md",
        "CSRN_PROJECT_BIBLE.md",
    )
    for relative in required_version_files:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert VERSION in text, relative

    required_build_files = (
        "VERSION.txt",
        "README.md",
        "README.txt",
        "ROADMAP.md",
        "CHANGELOG.txt",
        "CHANGELOG.md",
        "BUILD_JOURNAL.md",
        "CSRN_PROJECT_BIBLE.md",
        "app.py",
    )
    for relative in required_build_files:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert BUILD in text, relative

    version_text = (ROOT / "VERSION.txt").read_text(encoding="utf-8")
    assert TITLE in version_text

    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert f"Version {VERSION} — {TITLE}" in app_text
