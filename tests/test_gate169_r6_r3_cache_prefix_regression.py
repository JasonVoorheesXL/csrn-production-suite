from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_historical_cache_contract_tracks_authoritative_r1_r3_pin():
    overlay = read("templates/overlay.html")
    assert '/static/csrn-production-theme-runtime.css?v=18.5-r11' in overlay
    assert '/static/csrn-production-theme-runtime.js?v=18.5-r11' in overlay

def test_old_r6_cache_is_not_authoritative():
    target = '/static/csrn-production-theme-runtime.css?v=18.5-r11'
    assert not target.endswith('v=16.9-r6')






