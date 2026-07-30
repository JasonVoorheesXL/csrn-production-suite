from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_player_highlight_is_selectable_previewed_and_submitted() -> None:
    command_center = (ROOT / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    assert '<option value="player_highlight">Player Highlight</option>' in command_center
    assert 'id="pgPlayDetail"' in command_center
    assert 'id="pgpPlayDetail" class="pgp-play-detail"' in command_center
    assert "player_highlight:'PLAYER HIGHLIGHT'" in command_center
    assert "play_detail:document.getElementById('pgPlayDetail').value.trim()" in command_center
    assert (
        "document.getElementById('pgpPlayDetail').textContent="
        "document.getElementById('pgPlayDetail')?.value.trim()||''"
        in command_center
    )
