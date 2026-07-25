from __future__ import annotations

from pathlib import Path

from tools.apply_phase_4_22 import apply


LEGACY_APP = '''from game_operations_service import GameOperationsService


@app.get("/roster-headshots/<filename>")
def roster_headshot_file(filename: str):
    return send_from_directory(HEADSHOTS_DIR, filename)

@app.post("/api/rosters/<roster_id>/players/<player_id>/headshot")
@require_auth
def upload_player_headshot(roster_id: str, player_id: str):
    upload = request.files.get("headshot")
    raw = upload.read()
    rosters = load_rosters()
    save_rosters(rosters)
    return jsonify({"headshot": "legacy", "player": {}})


def activate_primary_graphic(state: dict[str, Any], active: str) -> None:
    pass


def local_addresses() -> list[str]:
    addresses = set()
    primary = local_ip()
    addresses.add(primary)
    return sorted(addresses)

@app.get("/api/statistics")
@require_auth
def statistics_report():
    return jsonify({})


@app.get("/api/connection-info")
@require_auth
def connection_info():
    addresses = local_addresses()
    return jsonify({"addresses": addresses})

@app.get("/api/connection-qr")
@require_auth
def connection_qr():
    url = str(request.args.get("url", "") or "")
    image = qrcode.make(url)
    return Response(b"legacy")

@app.post("/api/toggle-scorebug")
@require_auth
def toggle_scorebug():
    return jsonify({})


def local_ip() -> str:
    try:
        return "192.168.1.25"
    except OSError:
        return "127.0.0.1"

if __name__ == "__main__":
    pass
'''


def test_phase_4_22_migration_integrates_support_media_service(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from support_media_service import SupportMediaService" in migrated
    assert "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None" in migrated
    assert "get_support_media_service().upload_headshot" in migrated
    assert "get_support_media_service().connection_info" in migrated
    assert "get_support_media_service().qr_svg" in migrated
    assert "return get_support_media_service().local_addresses()" in migrated
    assert "return SupportMediaService.local_ip()" in migrated
    assert "raw = upload.read()\n    rosters = load_rosters()" not in migrated
    assert "image = qrcode.make(url)" not in migrated
    assert apply(target) is False
