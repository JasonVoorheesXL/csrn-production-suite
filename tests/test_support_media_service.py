from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image

from support_media_service import SupportMediaService


def image_bytes(width: int = 96, height: int = 96, fmt: str = "PNG") -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (width, height), (20, 40, 60)).save(stream, format=fmt)
    return stream.getvalue()


def build_service(
    tmp_path: Path,
    *,
    rosters: list[dict[str, Any]] | None = None,
    address_lookup=None,
    local_ip: str = "192.168.1.25",
    save_failure: bool = False,
):
    current = rosters if rosters is not None else [
        {
            "id": "roster-1",
            "players": [{"id": "player-1", "number": "12"}],
        }
    ]
    saves: list[list[dict[str, Any]]] = []

    def load_rosters():
        return current

    def save_rosters(items, *, force: bool = False):
        if save_failure:
            raise OSError("save blocked")
        saves.append(items)

    lookup = address_lookup or (
        lambda *_args: [
            (2, 1, 6, "", ("192.168.1.25", 0)),
            (2, 1, 6, "", ("10.0.0.8", 0)),
            (2, 1, 6, "", ("127.0.0.1", 0)),
            (2, 1, 6, "", ("10.0.0.8", 0)),
        ]
    )
    service = SupportMediaService(
        headshots_dir=tmp_path / "headshots",
        load_rosters=load_rosters,
        save_rosters=save_rosters,
        hostname=lambda: "csrn-laptop",
        address_lookup=lookup,
        local_ip_resolver=lambda: local_ip,
    )
    return service, current, saves


def test_safe_identifier_normalizes_unsafe_values() -> None:
    assert SupportMediaService.safe_identifier("Roster 1/Varsity", "roster") == "Roster-1-Varsity"
    assert SupportMediaService.safe_identifier("***", "roster") == "roster"


def test_local_addresses_deduplicates_and_omits_loopback(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    assert service.local_addresses() == ["10.0.0.8", "192.168.1.25"]


def test_local_addresses_recovers_from_lookup_failure(tmp_path: Path) -> None:
    def fail_lookup(*_args):
        raise OSError("offline")

    service, _, _ = build_service(
        tmp_path,
        address_lookup=fail_lookup,
        local_ip="172.20.10.2",
    )
    assert service.local_addresses() == ["172.20.10.2"]


def test_connection_info_builds_urls_and_normalizes_port(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    result = service.connection_info(70000)
    assert result.ok
    connection = result.data["connection"]
    assert connection["port"] == 5050
    assert connection["localhost"] == "http://127.0.0.1:5050"
    assert connection["addresses"][0] == {
        "ip": "10.0.0.8",
        "url": "http://10.0.0.8:5050",
    }
    assert "USB tethering" in connection["guidance"]


def test_qr_svg_rejects_non_http_url(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    assert service.qr_svg("file:///tmp/test").code == "INVALID_URL"
    assert service.qr_svg("").code == "INVALID_URL"


def test_qr_svg_generates_no_cache_svg(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    result = service.qr_svg("http://192.168.1.25:5050")
    assert result.ok
    assert result.data["mimetype"] == "image/svg+xml"
    assert result.data["headers"] == {"Cache-Control": "no-store"}
    assert b"<svg" in result.data["svg"]


def test_upload_headshot_requires_file(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    result = service.upload_headshot(
        "roster-1",
        "player-1",
        original_filename="",
        raw=None,
    )
    assert result.code == "HEADSHOT_FILE_REQUIRED"


def test_upload_headshot_rejects_unsupported_extension(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    result = service.upload_headshot(
        "roster-1",
        "player-1",
        original_filename="player.gif",
        raw=image_bytes(),
    )
    assert result.code == "UNSUPPORTED_IMAGE_TYPE"


def test_upload_headshot_rejects_invalid_image(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    result = service.upload_headshot(
        "roster-1",
        "player-1",
        original_filename="player.png",
        raw=b"not-an-image",
    )
    assert result.code == "INVALID_IMAGE"


def test_upload_headshot_rejects_small_image(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    result = service.upload_headshot(
        "roster-1",
        "player-1",
        original_filename="player.png",
        raw=image_bytes(32, 96),
    )
    assert result.code == "IMAGE_TOO_SMALL"


def test_upload_headshot_reports_missing_roster(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path, rosters=[])
    result = service.upload_headshot(
        "missing",
        "player-1",
        original_filename="player.png",
        raw=image_bytes(),
    )
    assert result.code == "ROSTER_NOT_FOUND"


def test_upload_headshot_reports_missing_player(tmp_path: Path) -> None:
    service, _, _ = build_service(
        tmp_path,
        rosters=[{"id": "roster-1", "players": []}],
    )
    result = service.upload_headshot(
        "roster-1",
        "missing",
        original_filename="player.png",
        raw=image_bytes(),
    )
    assert result.code == "PLAYER_NOT_FOUND"


def test_upload_headshot_saves_file_and_player_metadata(tmp_path: Path) -> None:
    service, current, saves = build_service(tmp_path)
    result = service.upload_headshot(
        "Roster 1",
        "Player/1",
        original_filename="portrait.PNG",
        raw=image_bytes(),
    )
    assert result.code == "ROSTER_NOT_FOUND"

    result = service.upload_headshot(
        "roster-1",
        "player-1",
        original_filename="portrait.PNG",
        raw=image_bytes(),
    )
    assert result.ok
    assert result.data["filename"] == "roster-1__player-1.png"
    path = tmp_path / "headshots" / result.data["filename"]
    assert path.read_bytes() == image_bytes()
    player = current[0]["players"][0]
    assert player["headshot"] == "/roster-headshots/roster-1__player-1.png"
    assert player["headshot_source"] == "uploaded"
    assert player["headshot_original_filename"] == "portrait.PNG"
    assert len(saves) == 1


def test_upload_headshot_downscales_oversized_image(tmp_path: Path) -> None:
    # Reproduces the Ja'kylen Sherrod case: an unprocessed camera original
    # (here 2400x3000, standing in for the real 7000x8400) must not reach
    # disk untouched -- it has to be brought within MAX_HEADSHOT_DIMENSION
    # so it can't blow the frontend's image-load timeout during a live
    # broadcast and silently fall back to the team crest.
    service, current, _ = build_service(tmp_path)
    result = service.upload_headshot(
        "roster-1",
        "player-1",
        original_filename="camera-original.jpg",
        raw=image_bytes(2400, 3000, fmt="JPEG"),
    )
    assert result.ok
    path = tmp_path / "headshots" / result.data["filename"]
    with Image.open(path) as saved:
        assert saved.width <= SupportMediaService.MAX_HEADSHOT_DIMENSION
        assert saved.height <= SupportMediaService.MAX_HEADSHOT_DIMENSION
        # Aspect ratio preserved (2400:3000 == 4:5).
        assert abs((saved.width / saved.height) - (2400 / 3000)) < 0.01
    assert path.stat().st_size < len(image_bytes(2400, 3000, fmt="JPEG"))
    player = current[0]["players"][0]
    assert player["headshot"] == "/roster-headshots/roster-1__player-1.jpg"


def test_upload_headshot_leaves_normal_sized_image_byte_identical(tmp_path: Path) -> None:
    # No re-encoding pass for uploads already within bounds -- avoids
    # needless quality loss on the common case.
    service, _, _ = build_service(tmp_path)
    result = service.upload_headshot(
        "roster-1",
        "player-1",
        original_filename="portrait.jpg",
        raw=image_bytes(400, 400, fmt="JPEG"),
    )
    assert result.ok
    path = tmp_path / "headshots" / result.data["filename"]
    assert path.read_bytes() == image_bytes(400, 400, fmt="JPEG")


def test_upload_headshot_removes_file_when_roster_save_fails(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path, save_failure=True)
    result = service.upload_headshot(
        "roster-1",
        "player-1",
        original_filename="portrait.png",
        raw=image_bytes(),
    )
    assert result.code == "HEADSHOT_STORAGE_FAILED"
    assert not (tmp_path / "headshots" / "roster-1__player-1.png").exists()


