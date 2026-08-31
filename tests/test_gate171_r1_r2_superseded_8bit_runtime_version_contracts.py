from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_gate170_history_tracks_current_authoritative_runtime_without_losing_8bit_contracts():
    js = read("static/csrn-production-theme-runtime.js")
    css = read("static/csrn-production-theme-runtime.css")
    assert "csrn-production-theme-binding-v46" in js
    assert "installEightBitAssetPathShim" in js
    assert 'raw.startsWith("8bit-gameday/") ? `/static/${raw}` : raw' in js
    assert "font-size:66px!important" in css
    assert "font-size:57px!important" in css
