from pathlib import Path
import hashlib

ROOT=Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT/rel).read_text(encoding="utf-8")

def sha(rel):
    return hashlib.sha256((ROOT/rel).read_bytes()).hexdigest().upper()

def test_runtime_normalizes_only_8bit_document_relative_image_paths():
    js=read("static/csrn-production-theme-runtime.js")
    assert 'installEightBitAssetPathShim' in js
    assert 'raw.startsWith("8bit-gameday/") ? `/static/${raw}` : raw' in js
    assert '__csrnEightBitAssetPathShimInstalled' in js

def test_asset_path_shim_remains_active_under_current_runtime_binding():
    js=read("static/csrn-production-theme-runtime.js")
    assert 'csrn-production-theme-binding-v46' in js

def test_canonical_athlete_assets_are_packaged():
    expected={'football-athletes.png': '97213E78E4E19349A57969C3B0BA0C213AFA443D155CEE768918CCEEAE1CA53A', 'basketball-athletes.png': '44C4CA5601AD3FB1A0BB9185861DC6FA3EE9B02048979AE8F4AE7F3D5644F57B', 'baseball-athletes.png': '932AEEFF1E4D17D11318DF7FE1BE2901A2927E0D260A2764091F4D56B571026C', 'softball-athletes.png': '868700C27899492234A8BE0CF09C9FC1BF8744C29A7EE4341AEB0C0D2124D658'}
    for name,digest in expected.items():
        rel=f"static/8bit-gameday/athletes/{name}"
        assert (ROOT/rel).is_file()
        assert sha(rel)==digest

def test_r1_r3_history_is_superseded_by_r2_cache_pin():
    overlay=read("templates/overlay.html")
    assert '/static/csrn-production-theme-runtime.css?v=18.5-r11' in overlay
    assert '/static/csrn-production-theme-runtime.js?v=18.5-r11' in overlay






