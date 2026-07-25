from __future__ import annotations

import io
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import qrcode
import qrcode.image.svg
from PIL import Image


@dataclass(frozen=True)
class SupportMediaResult:
    code: str
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class SupportMediaService:
    """Support-media boundary independent of Flask request/response objects."""

    SUPPORTED_HEADSHOT_TYPES = {".png", ".jpg", ".jpeg", ".webp"}
    MIN_HEADSHOT_DIMENSION = 64
    DEFAULT_PORT = 5050
    CONNECTION_GUIDANCE = (
        "For USB tethering, connect the phone by USB, enable USB tethering, "
        "then refresh this panel and use the newly listed address from the "
        "second device. Some phones cannot browse back to the laptop while "
        "serving as the tethering device; use a separate statistician "
        "phone/tablet when that occurs."
    )

    def __init__(
        self,
        *,
        headshots_dir: Path,
        load_rosters: Callable[[], list[dict[str, Any]]],
        save_rosters: Callable[[list[dict[str, Any]]], None],
        hostname: Callable[[], str] = socket.gethostname,
        address_lookup: Callable[..., list[tuple[Any, ...]]] = socket.getaddrinfo,
        local_ip_resolver: Callable[[], str] | None = None,
    ) -> None:
        self._headshots_dir = Path(headshots_dir)
        self._load_rosters = load_rosters
        self._save_rosters = save_rosters
        self._hostname = hostname
        self._address_lookup = address_lookup
        self._local_ip_resolver = local_ip_resolver or self.local_ip

    @staticmethod
    def safe_identifier(value: Any, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "")).strip("-")
        return cleaned or fallback

    @staticmethod
    def local_ip() -> str:
        connection: socket.socket | None = None
        try:
            connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            connection.connect(("8.8.8.8", 80))
            return str(connection.getsockname()[0])
        except OSError:
            return "127.0.0.1"
        finally:
            if connection is not None:
                connection.close()

    def local_addresses(self) -> list[str]:
        addresses: set[str] = set()
        try:
            for info in self._address_lookup(
                self._hostname(),
                None,
                socket.AF_INET,
            ):
                ip = str(info[4][0])
                if ip and not ip.startswith("127."):
                    addresses.add(ip)
        except OSError:
            pass

        primary = str(self._local_ip_resolver() or "")
        if primary and not primary.startswith("127."):
            addresses.add(primary)
        return sorted(addresses)

    def connection_info(self, port: int = DEFAULT_PORT) -> SupportMediaResult:
        normalized_port = self._normalize_port(port)
        addresses = self.local_addresses()
        return SupportMediaResult(
            "OK",
            {
                "connection": {
                    "port": normalized_port,
                    "addresses": [
                        {"ip": ip, "url": f"http://{ip}:{normalized_port}"}
                        for ip in addresses
                    ],
                    "localhost": f"http://127.0.0.1:{normalized_port}",
                    "guidance": self.CONNECTION_GUIDANCE,
                }
            },
        )

    def qr_svg(self, url: Any) -> SupportMediaResult:
        normalized = str(url or "").strip()
        if not re.match(r"^https?://", normalized, flags=re.IGNORECASE):
            return SupportMediaResult("INVALID_URL", {})
        try:
            image = qrcode.make(
                normalized,
                image_factory=qrcode.image.svg.SvgPathImage,
                box_size=8,
                border=2,
            )
            stream = io.BytesIO()
            image.save(stream)
        except Exception as exc:  # library boundary
            return SupportMediaResult(
                "QR_GENERATION_FAILED",
                {"message": str(exc)},
            )
        return SupportMediaResult(
            "OK",
            {
                "svg": stream.getvalue(),
                "mimetype": "image/svg+xml",
                "headers": {"Cache-Control": "no-store"},
            },
        )

    def upload_headshot(
        self,
        roster_id: Any,
        player_id: Any,
        *,
        original_filename: Any,
        raw: bytes | bytearray | None,
    ) -> SupportMediaResult:
        filename = str(original_filename or "").strip()
        if not filename or raw is None:
            return SupportMediaResult("HEADSHOT_FILE_REQUIRED", {})

        extension = Path(filename).suffix.lower()
        if extension not in self.SUPPORTED_HEADSHOT_TYPES:
            return SupportMediaResult("UNSUPPORTED_IMAGE_TYPE", {})

        payload = bytes(raw)
        try:
            image = Image.open(io.BytesIO(payload))
            image.load()
        except Exception:
            return SupportMediaResult("INVALID_IMAGE", {})
        if (
            image.width < self.MIN_HEADSHOT_DIMENSION
            or image.height < self.MIN_HEADSHOT_DIMENSION
        ):
            return SupportMediaResult("IMAGE_TOO_SMALL", {})

        roster_key = str(roster_id or "")
        player_key = str(player_id or "")
        rosters = self._load_rosters()
        roster = next(
            (item for item in rosters if str(item.get("id")) == roster_key),
            None,
        )
        if roster is None:
            return SupportMediaResult("ROSTER_NOT_FOUND", {})
        player = next(
            (
                item
                for item in list(roster.get("players") or [])
                if str(item.get("id")) == player_key
            ),
            None,
        )
        if player is None:
            return SupportMediaResult("PLAYER_NOT_FOUND", {})

        safe_roster = self.safe_identifier(roster_key, "roster")
        safe_player = self.safe_identifier(player_key, "player")
        stored_filename = f"{safe_roster}__{safe_player}{extension}"
        path = self._headshots_dir / stored_filename
        try:
            self._headshots_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        except OSError as exc:
            return SupportMediaResult(
                "HEADSHOT_STORAGE_FAILED",
                {"message": str(exc)},
            )

        url = f"/roster-headshots/{stored_filename}"
        player["headshot"] = url
        player["headshot_source"] = "uploaded"
        player["headshot_original_filename"] = filename
        try:
            self._save_rosters(rosters)
        except Exception as exc:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            return SupportMediaResult(
                "HEADSHOT_STORAGE_FAILED",
                {"message": str(exc)},
            )

        return SupportMediaResult(
            "OK",
            {
                "headshot": url,
                "player": dict(player),
                "filename": stored_filename,
            },
        )

    @classmethod
    def _normalize_port(cls, value: Any) -> int:
        try:
            port = int(value)
        except (TypeError, ValueError):
            return cls.DEFAULT_PORT
        if not 1 <= port <= 65535:
            return cls.DEFAULT_PORT
        return port
