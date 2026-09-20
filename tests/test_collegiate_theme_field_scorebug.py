from pathlib import Path

import production_template_service as service


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_collegiate_is_approved_for_production_template_host():
    assert "collegiate_traditional" in service.APPROVED_PACKAGE_IDS
    assert '"collegiate_traditional"' in read("static/csrn-production-theme-adapter.js")
    assert "collegiate_traditional: Object.freeze" in read("static/csrn-production-theme-runtime.js")
    assert '<option value="collegiate_traditional">Collegiate Tech</option>' in read("templates/index.html")
    assert 'collegiate_traditional: "Collegiate Tech"' in read("static/csrn-pregame-theme-selector.js")


def test_collegiate_football_uses_field_position_panel_not_legacy_down_box():
    js = read("static/csrn-broadcast-layout-engine.js")
    css = read("static/csrn-broadcast-layout-engine.css")
    assert "function collegiateFootballScorebug" in js
    assert "function collegiateField" in js
    assert "function collegiateScoreClockRow" in js
    assert "function collegiateFieldSpotLabel" in js
    assert 'data-module="game.field"' in js
    assert "bl-college-ticker-copy" in js
    assert "bl-college-score-clock-row" in js
    assert 'data-bind="game.possessionLogo"' in js
    assert 'data-bind="game.possessionText"' in js
    assert 'data-college-rail="${side}"' in js
    assert "bl-college-endzone" in js
    assert "bl-college-five-yard-lines" in js
    assert "bl-college-hashmarks" in js
    assert "bl-college-first-down" in js
    assert "bl-college-line-scrimmage" in js
    assert "bl-college-drive-start" in js
    assert 'scorebug:{zone:"full-safe",width:1840,height:1000' in js
    assert "function collegiateStage" in js
    assert "bl-collegiate-tech" in css
    assert "bl-college-score-clock-row" in css
    assert "bl-college-rail-card" in css
    assert "bl-player-leader.has-photo" in css
    assert "bl-college-endzone" in css
    assert "bl-college-five-yard-lines" in css
    assert "bl-college-hashmarks" in css
    assert "grid-template-columns:minmax(0,1fr)" in css
    assert "backdrop-filter:blur" in css
    assert 'content:"1ST DOWN"' in css
    assert "font-variant-numeric:tabular-nums" in css


def test_collegiate_video_board_supports_player_highlight_and_sponsor_modes():
    js = read("static/csrn-broadcast-layout-engine.js")
    css = read("static/csrn-broadcast-layout-engine.css")
    runtime = read("static/csrn-production-theme-runtime.js")

    # Video board content is threaded from renderPackage() -> componentFrame()
    # -> the collegiate scorebug renderer -> collegiateStage(), the same
    # shape Friday Night Stadium's own boardMarkup()/videoContent() split
    # uses, so it fits into the existing options.videoMode plumbing.
    assert "componentFrame(component, manifest, state, sport, options.videoMode)" in js
    assert "function componentFrame(component, manifest, state, sport, videoMode)" in js
    assert "collegiate(state, sport, videoMode)" in js
    assert "collegiateFootballScorebug(state, sport, videoMode)" in js
    assert "function collegiateVideoBoardContent(state, mode)" in js
    # T1 (docs/PHASE_C_THEME_SPORT_DISPATCH_PLAN.md): collegiateStage() grew
    # a sport param so the stage-field background can swap per sport
    # (baseball/softball ballpark photos vs. football's), defaulting to
    # "football" so every pre-T1 call site is unaffected.
    assert 'function collegiateStage(state, videoMode, sport = "football")' in js
    assert 'data-video-mode="highlight"' in js
    assert 'data-video-mode="sponsor"' in js
    assert 'data-video-mode="player"' in js
    assert "function collegiateSponsorLockup" in js
    assert "bl-college-sponsor-lockup" in js

    # Registered into the shared runtime's video-board mode/host dispatch so
    # the overlay actually calls into the above instead of leaving Collegiate
    # on the legacy separate-zone player/highlight/sponsor components.
    assert 'isCollegiateFamily(alias);' in runtime  # Neon shares Collegiate's video board
    assert "collegiate_traditional: \".bl-college-stage\"" in runtime
    assert "eyebrow: textValue(graphic.eyebrow" in runtime
    assert "sponsorName: textValue(graphic.sponsor_name" in runtime
    assert "sponsorLogo: textValue(graphic.sponsor_logo" in runtime


def test_collegiate_player_spotlight_is_sized_up_and_never_truncates():
    js = read("static/csrn-broadcast-layout-engine.js")
    css = read("static/csrn-broadcast-layout-engine.css")

    # Sizing pass, scoped to the player card specifically (.bl-college-player)
    # so it doesn't also inflate the highlight/sponsor cards that share the same
    # base .bl-college-video-copy/.bl-college-player-portrait classes.
    #
    # Values updated (commit 9095cf6, "Checkpoint: owner's in-progress work"):
    # that checkpoint restructured the player card's eyebrow line out of
    # .bl-college-video-copy into its own full-width .bl-college-player-eyebrow
    # banner (see collegiateVideoBoardContent()'s "player" branch and its
    # accompanying comment in csrn-broadcast-layout-engine.js) and re-tuned
    # the portrait/name/detail sizing to match -- portrait 177->354px,
    # portrait-b 48->96px, video-copy strong 51->64px, span 27->32px. The old
    # ".bl-college-video-copy small{font-size:24px}" rule is gone because
    # that element no longer has a <small> in the player card at all (the
    # eyebrow moved out); its role is now covered by the eyebrow assertion
    # below instead of a video-copy-scoped one.
    assert ".bl-college-player .bl-college-player-portrait{width:354px;height:354px}" in css
    assert ".bl-college-player .bl-college-player-portrait b{font-size:96px}" in css
    assert ".bl-college-player-eyebrow{font-size:32px" in css
    assert ".bl-college-player .bl-college-video-copy strong{font-size:64px}" in css
    assert ".bl-college-player .bl-college-video-copy span{font-size:32px}" in css

    # A long real name at 51px can exceed the card width -- auto-fit shrinks it
    # (never below the pre-1.5x 34px) instead of letting the ellipsis cut it off,
    # the same pattern fitNeonTeamNames() already uses elsewhere in this file.
    assert "function fitCollegiatePlayerName(root)" in js
    assert 'if (manifest.componentRendererFamily === "collegiate") {\n      fitCollegiatePlayerName(root);' in js
    assert "size > 34 && guard < 40" in js
    assert ".bl-college-video-copy strong{min-width:0" in css

    assert "bl-college-video-replacement" in css
    assert "bl-college-player-portrait" in css
    assert "bl-college-sponsor-lockup" in css


def test_collegiate_runtime_patches_live_field_state_without_rerender():
    runtime = read("static/csrn-production-theme-runtime.js")
    assert "function productionFieldState" in runtime
    assert 'isCollegiateFamily(alias)' in runtime
    assert 'tickerSelector: ".bl-college-ticker-copy"' in runtime
    assert '[data-bind="game.ballSpot"]' in runtime
    assert '[data-bind="game.possessionLogo"]' in runtime
    assert '[data-bind="game.possessionText"]' in runtime
    assert "function collegiateFieldSpotLabel" in runtime
    assert "--first-x" in runtime
    assert "dataset.hasFirstDown" in runtime
