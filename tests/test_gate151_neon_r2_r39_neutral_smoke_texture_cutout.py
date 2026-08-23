from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/"static"/"neon-r2"


def test_manifest_declares_r40_blacklight_deployment() -> None:
    js=(ROOT/"static"/"csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    assert 'artworkColorMode:"adaptive-blacklight-field-football"' in js
    assert "n2-r40 field-base" in js
    assert "n2-r40 field-home-primary" in js
    assert "n2-r40 field-visitor-primary" in js


def test_smoke_assets_exist_and_are_neutral_grayscale() -> None:
    names=(
      "football-neutral-smoke-master.png",
      "football-neutral-home-smoke-mask.png",
      "football-neutral-visitor-smoke-mask.png",
      "football-neutral-smoke-luminance.png",
      "football-neutral-smoke-texture.png",
      "football-neutral-smoke-shadows.png",
      "football-neutral-smoke-highlights.png",
    )
    for name in names:
        assert Image.open(ASSETS/name).convert("RGBA").size==(1024,640)

    grayscale_layers=(
      "football-neutral-smoke-luminance.png",
      "football-neutral-smoke-texture.png",
      "football-neutral-smoke-shadows.png",
      "football-neutral-smoke-highlights.png",
    )
    for name in grayscale_layers:
        image=Image.open(ASSETS/name).convert("RGBA")
        visible=False
        for red,green,blue,alpha in image.getdata():
            if alpha:
                visible=True
                assert red==green==blue
        assert visible


def test_smoke_masks_are_wispy_and_constrained() -> None:
    for name in (
      "football-neutral-home-smoke-mask.png",
      "football-neutral-visitor-smoke-mask.png",
    ):
        alpha=Image.open(ASSETS/name).convert("RGBA").getchannel("A")
        assert alpha.getbbox() is not None
        total=alpha.width*alpha.height
        visible=sum(1 for value in alpha.getdata() if value>8)
        coverage=visible/total
        assert 0.001 <= coverage <= 0.25


def test_runtime_smoke_color_comes_only_from_team_variables() -> None:
    css=(ROOT/"static"/"csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    final=css.split("Gate 15.1 R40")[-1]
    assert "background-color:var(--n2-left-raw)" in final
    assert "background-color:var(--n2-right-raw)" in final
    assert "var(--n2-r40-field-home-primary)" in final
    assert "var(--n2-r40-field-visitor-primary)" in final
    assert "mix-blend-mode:screen" in final
    assert "background-image:var(--n2-r40-field)" in final


