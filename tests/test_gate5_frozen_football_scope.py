from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_player_spotlight_is_selectable_previewed_and_submitted() -> None:
    command_center = (ROOT / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    assert '<option value="player_spotlight">Player Spotlight</option>' in command_center
    assert 'id="pgPlayDetail"' in command_center
    assert 'id="pgpPlayDetail" class="pgp-play-detail"' in command_center
    assert "player_spotlight:'PLAYER SPOTLIGHT'" in command_center
    assert "play_detail:document.getElementById('pgPlayDetail').value.trim()" in command_center
    assert (
        "document.getElementById('pgpPlayDetail').textContent="
        "document.getElementById('pgPlayDetail')?.value.trim()||''"
        in command_center
    )


def test_program_visual_controls_expose_highlight_spotlight_and_queue() -> None:
    command_center = (ROOT / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'id="pvhRoster"' in command_center
    assert 'id="pvhPlayer"' in command_center
    assert 'id="pvhDetail"' in command_center
    assert 'id="pvhDuration"' in command_center
    assert (
        'id="pvhDuration"><option value="5">5 seconds</option>'
        '<option value="8" selected>8 seconds</option>'
        '<option value="12">12 seconds</option>'
        '<option value="15">15 seconds</option>'
        '<option value="30">30 seconds</option>'
        in command_center
    )
    assert (
        'id="pgDuration"><option value="0">Persistent</option>'
        '<option value="5">5 seconds</option>'
        '<option value="8">8 seconds</option>'
        '<option value="12">12 seconds</option>'
        '<option value="15">15 seconds</option>'
        '<option value="30">30 seconds</option>'
        in command_center
    )
    assert "showProgramPlayerHighlight()" in command_center
    assert 'id="phvRoster"' in command_center
    assert 'id="phvPlayer"' in command_center
    assert 'id="phvMedia"' in command_center
    assert 'id="phvDuration"' in command_center
    assert "showProgramPlayerHighlightVideo()" in command_center
    assert 'id="spsSponsor"' in command_center
    assert 'id="spsMedia"' in command_center
    assert 'id="spsDuration"' in command_center
    assert "showSponsorSpotlight()" in command_center
    assert 'id="graphicsQueueList"' in command_center
    assert "cancelGraphicsQueueItem(" in command_center


def test_sponsor_spotlight_stays_below_the_scorebug() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    assert 'id="sponsorSpotlight"' in overlay
    assert 'id="sponsorSpotlightImage"' in overlay
    assert 'id="sponsorSpotlightVideo"' in overlay
    assert "#sponsorSpotlight,#playerHighlight{" in overlay
    assert "#scorebug,#eventTicker{z-index:100}" in overlay
    assert "sponsorSpotlight.media_type==='video'" in overlay
    assert '<link rel="stylesheet" href="/themes/current.css">' in overlay
    assert "const OVERLAY_SCHEMA_REVISION='gate6-logo-fallback-v1';" in overlay
    assert (
        "s.overlay_revision&&s.overlay_revision!==OVERLAY_SCHEMA_REVISION"
        in overlay
    )
    assert (
        "#sponsorSpotlight.scorebug-active,"
        "#playerHighlight.scorebug-active{bottom:176px}"
        in overlay
    )
    assert (
        "#sponsorSpotlight.scorebug-active.graphic-mode,"
        "#playerHighlight.scorebug-active.graphic-mode{bottom:310px}"
        in overlay
    )
    assert (
        ".sponsor-spotlight-media{position:absolute;inset:190px 3vw 2vh;"
        "box-sizing:border-box"
        in overlay
    )
    assert "width:auto!important;height:100%!important" in overlay
    assert "object-fit:contain!important;object-position:center" in overlay
    assert ".sponsor-spotlight-copy{position:absolute" in overlay
    assert "left:0;right:0;top:0" in overlay
    assert (
        "sponsorSpotlightEl.classList.toggle('scorebug-active',"
        "Boolean(s.scorebug_visible))"
        in overlay
    )


def test_graphics_routes_expose_spotlight_and_queue_coordinator() -> None:
    routes = (ROOT / "routes" / "graphics_routes.py").read_text(
        encoding="utf-8"
    )
    assert '@routes.post("/api/graphics/sponsor-spotlight")' in routes
    assert '@routes.post("/api/graphics/player-highlight")' in routes
    assert '@routes.post("/api/graphics/queue")' in routes
    assert "update_sponsor_spotlight(" in routes
    assert "update_player_highlight(" in routes
    assert "update_queue(" in routes


def test_asset_manager_exposes_placement_and_identity_associations() -> None:
    command_center = (ROOT / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'id="assetPlacement"' in command_center
    assert 'value="sponsor_feature_still"' in command_center
    assert 'value="sponsor_feature_video"' in command_center
    assert 'value="player_highlight_video"' in command_center
    assert 'id="assetSponsorId"' in command_center
    assert 'id="assetRosterId"' in command_center
    assert 'id="assetPlayerId"' in command_center
    assert 'id="assetSeason"' in command_center


def test_player_highlight_video_uses_protected_feature_stage() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    assert 'id="playerHighlight"' in overlay
    assert 'id="playerHighlightVideo" muted playsinline' in overlay
    assert "const playerHighlight=s.player_highlight||{}" in overlay
    assert "playerHighlightEl.classList.toggle('scorebug-active'" in overlay
    assert "playerHighlightVideo.play().catch(()=>{})" in overlay
    assert 'class="sponsor-spotlight-media player-highlight-media"' in overlay
    assert ".player-highlight-media video{" in overlay
    assert "function fitPlayerHighlightVideo()" in overlay
    assert "video.videoWidth/video.videoHeight" in overlay
    assert "Math.min(availableWidth,availableHeight*ratio)" in overlay
    assert "requestAnimationFrame(fitPlayerHighlightVideo)" in overlay
    assert "addEventListener('loadedmetadata',fitPlayerHighlightVideo)" in overlay
    assert "object-fit:contain!important" in overlay


def test_roster_player_owns_highlight_preparation_workflow() -> None:
    command_center = (ROOT / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'id="playerHighlightsPanel"' in command_center
    assert 'id="playerHighlightUpload"' in command_center
    assert "uploadRosterPlayerHighlight(this.files[0])" in command_center
    assert "placement:'player_highlight_video'" in command_center
    assert "roster_id:rosterId" in command_center
    assert "player_id:playerId" in command_center
    assert "unlinkRosterPlayerHighlight" in command_center
    assert "deleteRosterPlayerHighlight" in command_center
    assert "/api/assets/storage" in command_center


def test_broadcaster_penalty_buttons_use_context_free_labels() -> None:
    command_center = (ROOT / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "Penalty Caledonia" not in command_center
    assert "Penalty Visitor" not in command_center
    assert (
        """onclick="openPenalty('home','broadcaster')">Penalty</button>"""
        in command_center
    )
    assert (
        """onclick="openPenalty('visitor','broadcaster')">Penalty</button>"""
        in command_center
    )


def test_broadcast_planning_exposes_record_policy_and_special_designations() -> None:
    command_center = (ROOT / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    service = (ROOT / "broadcast_service.py").read_text(encoding="utf-8")
    assert 'id="contestType"' in command_center
    assert 'id="regionGame"' in command_center
    assert 'id="homeOverallTies"' in command_center
    assert 'id="visitorRegionTies"' in command_center
    assert 'id="designationHomecoming"' in command_center
    assert 'id="designationChampionship"' in command_center
    assert "home_pregame_record: readPlanningRecord('home','Overall')" in command_center
    assert "special_designations: readSpecialDesignations()" in command_center
    assert '"record_policy": "official" if contest_type == "official" else "non_record"' in service
    assert '"ties"' in service
    assert "def _latest_primary_records(" in service
    assert "def _apply_completion_records(" in service


def test_gate5_record_policy_and_scorebug_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    command = (root / "templates" / "index.html").read_text(encoding="utf-8")
    overlay = (root / "templates" / "overlay.html").read_text(encoding="utf-8")
    assert "Official overall and region win/loss/tie records will not be updated" in command
    assert "region.checked=false;region.disabled=true" in command
    assert "id=\"homeRecord\"" in overlay
    assert "id=\"visitorRecord\"" in overlay
    assert "scorebugRecord(s,'home')" in overlay
    assert "official&&Boolean(state.region_game)" in overlay
    assert "gate6-logo-fallback-v1" in overlay
