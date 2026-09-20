from pathlib import Path
from PIL import Image
import hashlib

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_adaptive_assets_exist_for_all_sports() -> None:
    root = ROOT/"static"/"neon-r2"
    for sport in ("football","basketball","baseball","softball"):
        assert Image.open(root/f"{sport}-neutral.png").size == (1024,640)
        assert Image.open(root/f"{sport}-left-mask.png").getchannel("A").getbbox() is not None
        assert Image.open(root/f"{sport}-right-mask.png").getchannel("A").getbbox() is not None


def test_football_has_no_possession_glyph_or_html_field_numbers() -> None:
    js = (ROOT/"static"/"csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    css = (ROOT/"static"/"csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    football = js[js.index("function footballState"):js.index("function footballFieldData")]
    assert "possession(s)" not in football
    final = css.split("Gate 15.1 R32")[-1]
    assert "content:none !important" in final
    assert "visibility:hidden !important" in final


def test_team_swap_control_exists_without_clash_mirroring() -> None:
    lab = (ROOT/"static"/"csrn-layout-lab.html").read_text(encoding="utf-8")
    js = (ROOT/"static"/"csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    css = (ROOT/"static"/"csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert 'id="swapTeams"' in lab
    assert "teamOrderSwapped" in lab
    assert "data-team-swap" not in js
    assert 'data-team-swap="true"' not in css


def test_diamond_info_is_crisp_without_glow() -> None:
    css = (ROOT/"static"/"csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    final = css.split("Gate 15.1 R32")[-1]
    assert "text-shadow:none !important" in final
    assert "box-shadow:none !important" in final
    assert "filter:none !important" in final
    assert "-webkit-text-stroke:0 !important" in final


def test_baseball_asset_is_valid() -> None:
    image = Image.open(ROOT/"static"/"neon-r2"/"baseball-neutral.png")
    assert image.size == (1024,640)


