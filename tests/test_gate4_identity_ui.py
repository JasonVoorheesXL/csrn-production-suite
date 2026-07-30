from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_command_center_ids_are_unique() -> None:
    source = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    assert duplicates == []


def test_player_identity_never_falls_back_to_csrn_branding() -> None:
    command_center = (ROOT / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    preview = command_center[
        command_center.index("function renderPlayerGraphicPreview()") :
        command_center.index(
            "function playerGraphicPayload(action)",
            command_center.index("function renderPlayerGraphicPreview()"),
        )
    ]

    assert "player-silhouette.svg" in preview
    assert "identityMonogramData" in preview
    assert "school.primary_logo" in preview
    assert "p?.headshot||teamLogo||'/static/player-silhouette.svg'" in preview
    assert "wm.src=teamLogo||monogram" in preview
    assert "join(' / ')||'ATH'" in preview
    assert "toUpperCase()==='ATHLETE'?'ATH':value" in preview
    assert "csrn-logo.png" not in preview

    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    assert 'src="/static/player-silhouette.svg"' in overlay
    assert "guardPlayerIdentityFallbacks" in overlay
    assert "identityMonogramData('TEAM')" in overlay
    assert "join(' / ')||'ATH'" in overlay
    assert "toUpperCase()==='ATHLETE'?'ATH':value" in overlay


def test_roster_rows_show_media_and_missing_headshot_status() -> None:
    command_center = (ROOT / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    roster = command_center[
        command_center.index("function renderRosterPlayers()") :
        command_center.index(
            "function newRosterPlayer()",
            command_center.index("function renderRosterPlayers()"),
        )
    ]

    assert "roster-player-thumb" in roster
    assert "Headshot missing" in roster
    assert "player-silhouette.svg" in roster


def test_player_preview_uses_full_width_below_controls() -> None:
    style = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    assert ".player-graphics-workspace{grid-template-columns:1fr!important}" in style
    assert "@media(max-width:700px)" in style


def test_neutral_player_silhouette_is_versioned() -> None:
    silhouette = ROOT / "static" / "player-silhouette.svg"
    assert silhouette.is_file()
    assert "Neutral player silhouette" in silhouette.read_text(encoding="utf-8")
