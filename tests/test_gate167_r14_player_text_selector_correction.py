from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(p): return (ROOT/p).read_text(encoding="utf-8")

def test_r14_targets_shared_player_video_mode():
    css=read("static/csrn-production-theme-runtime.css")
    assert '#csrnProductionThemeLayout [data-video-mode="player"] > small' in css
    assert '#csrnProductionThemeLayout [data-video-mode="player"] > strong' in css
    assert '#csrnProductionThemeLayout [data-video-mode="player"] > span' in css
    assert 'font-size:44px!important' in css
    assert 'font-size:86px!important' in css
    assert 'font-size:52px!important' in css

def test_r14_runtime_recognizes_shared_player_mode():
    js=read("static/csrn-production-theme-runtime.js")
    assert "[data-video-mode='player']" in js
    assert "videoMode:activeVideoMode" in js
    assert "themeVideoModeFor(alias, runtime)" in js
