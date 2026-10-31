"""Night Game Glass in the console (2026-10-31): the stylesheet is loaded last,
the saved look paints before first render, the header logo sits in a shape
frame and follows the organization logo, and Settings has an Appearance
section whose uploads offer a cleaned logo.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "csrn-console-glass.css").read_text(encoding="utf-8")
HEAD = HTML[: HTML.index("</head>")]


def test_stylesheet_is_loaded_after_every_other_head_style() -> None:
    link = HEAD.index('<link rel="stylesheet" href="/static/csrn-console-glass.css">')
    assert link > HEAD.rindex("</style>")
    assert '<html lang="en" class="csrn-glass" data-logo-shape="circle">' in HTML
    # The last saved look is applied before the body paints.
    assert "localStorage.getItem('csrn.consoleAppearance.v1')" in HEAD[link:]


def test_header_logo_sits_in_a_shape_frame() -> None:
    assert '<span class="header-logo-frame"><img class="header-logo"' in HTML
    for shape in ("circle", "square", "diamond", "glass"):
        assert f'html[data-logo-shape="{shape}"] .header-logo-frame' in CSS
    # A % padding resolves against the header's width and swallowed the logo.
    glass = re.search(r'html\[data-logo-shape="glass"\] \.header-logo-frame \{([^}]*)\}', CSS).group(1)
    assert "padding: 9px" in glass


def test_fixed_colors_stay_fixed_and_the_brand_color_is_a_variable() -> None:
    for token in ("--csrn-ink: #0A0E13", "--csrn-amber: #F2B544", "--csrn-green: #5FD08A", "--csrn-text: #E8EDF3"):
        assert token in CSS
    assert "--accent: var(--csrn-accent-button);" in CSS
    assert "button.primary, .button.primary, button.active {\n  background: var(--csrn-accent-button);" in CSS
    # Glass only when switched on.
    assert "html.csrn-glass .event-confirm-sheet" in CSS
    assert ".event-confirm-sheet, .duplicate-dialog {\n  background: var(--csrn-surface);" in CSS


def test_settings_has_an_appearance_section_wired_to_the_api() -> None:
    for needle in (
        'id="appearanceSwatches"', 'id="appearanceShapes"', 'id="appearanceGlass"', 'id="appearanceBlur"',
        'onclick="saveAppearance()"', 'onclick="cleanOrganizationLogo()"', 'onclick="useCleanedLogo()"',
        "api('/api/appearance',{...appearanceDraft})", "api('/api/appearance/clean-logo',{logo_path:path})",
    ):
        assert needle in HTML, needle
    assert HTML.index("<h2>Appearance</h2>") < HTML.index("<h2>Default Broadcast Settings</h2>")


def test_uploading_a_logo_offers_the_cleaned_version() -> None:
    upload = HTML[HTML.index("async function uploadOrganizationLogo(input){"):]
    upload = upload[: upload.index("\n}\n")]
    assert "cleanOrganizationLogo({auto:true});" in upload


def test_button_shade_rule_matches_the_server() -> None:
    import appearance_service

    assert "for(let i=0;i<60&&appearanceWhiteContrast(shade)<4.5;i++){rgb=rgb.map(c=>Math.round(c*0.93))" in HTML
    assert appearance_service.button_shade("#E3A92B") == "#926D1C"
