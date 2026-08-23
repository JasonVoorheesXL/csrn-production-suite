from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys
import mimetypes
from pathlib import Path
import threading
from time import perf_counter
from typing import Any, Callable
from urllib.parse import quote, unquote, urlsplit

from flask import Blueprint, jsonify, redirect, request, send_from_directory

from runtime_diagnostics_service import get_runtime_diagnostics, new_request_id


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]

_MEDIA_ACTIVITY_LOCK = threading.Lock()
_ACTIVE_MEDIA_REQUESTS = 0
_MEDIA_SERVER_LOCK = threading.Lock()
_MEDIA_SERVER: ThreadingHTTPServer | None = None
_EXPECTED_MEDIA_DISCONNECTS = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)
_MEDIA_SERVER_PORT = 5051
_MEDIA_SERVER_DIRECTORIES: dict[str, Path] = {}
_ISOLATED_MEDIA_EXTENSIONS = {".mp4", ".webm", ".mp3", ".wav"}


def _is_expected_media_disconnect(exc: BaseException | None) -> bool:
    return isinstance(exc, _EXPECTED_MEDIA_DISCONNECTS)


class _IsolatedMediaHTTPServer(ThreadingHTTPServer):
    """Range-capable media server that treats browser/CEF disconnects as normal."""

    def handle_error(self, request: Any, client_address: Any) -> None:
        exc = sys.exc_info()[1]
        if _is_expected_media_disconnect(exc):
            get_runtime_diagnostics().record(
                "SERVER_MEDIA_SOCKET_ABORT",
                status="EXPECTED_DISCONNECT",
                client=str(client_address),
                error_type=type(exc).__name__ if exc is not None else "",
                error_message=str(exc)[:240] if exc is not None else "",
                thread=threading.current_thread().name,
            )
            return
        super().handle_error(request, client_address)


def _parse_byte_range(value: str, size: int) -> tuple[int, int] | None:
    if not value.startswith("bytes=") or "," in value or size <= 0:
        return None
    spec = value[6:].strip()
    if "-" not in spec:
        return None
    start_text, end_text = spec.split("-", 1)
    try:
        if start_text:
            start = int(start_text)
            end = int(end_text) if end_text else size - 1
        else:
            suffix = int(end_text)
            if suffix <= 0:
                return None
            start = max(0, size - suffix)
            end = size - 1
    except ValueError:
        return None
    if start < 0 or start >= size or end < start:
        return None
    return start, min(end, size - 1)


def _is_isolated_media_asset(filename: str) -> bool:
    return Path(str(filename or "")).suffix.lower() in _ISOLATED_MEDIA_EXTENSIONS


def _build_media_handler():
    class IsolatedMediaHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_HEAD(self) -> None:
            self._serve(send_body=False)

        def do_GET(self) -> None:
            self._serve(send_body=True)

        def _serve(self, *, send_body: bool) -> None:
            request_id = new_request_id()
            started = perf_counter()
            active_media = _media_request_started()
            range_header = str(self.headers.get("Range", "") or "")
            try:
                path = urlsplit(self.path).path
                prefix = ""
                root: Path | None = None
                for candidate_prefix, candidate_root in tuple(_MEDIA_SERVER_DIRECTORIES.items()):
                    if path.startswith(candidate_prefix):
                        prefix = candidate_prefix
                        root = candidate_root
                        break
                if root is None:
                    self.send_error(404)
                    return
                filename = unquote(path[len(prefix):])
                if not filename or Path(filename).name != filename:
                    self.send_error(404)
                    return
                target = (root / filename).resolve()
                if target.parent != root or not target.is_file():
                    self.send_error(404)
                    return

                file_size = target.stat().st_size
                byte_range = _parse_byte_range(range_header, file_size) if range_header else None
                if range_header and byte_range is None:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return

                start, end = byte_range if byte_range else (0, file_size - 1)
                length = max(0, end - start + 1)
                status = 206 if byte_range else 200
                content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                get_runtime_diagnostics().record(
                    "SERVER_MEDIA_BEGIN", request_id=request_id, route="isolated-media:5051",
                    method=self.command, media_kind=("sponsor_advertisement_video" if prefix == "/sponsor-ad-files/" else "managed_asset_media"),
                    range_request=bool(byte_range), range_header=range_header[:120],
                    file_size_bytes=file_size, active_media_requests=active_media,
                    thread=threading.current_thread().name,
                )
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(length))
                if byte_range:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Cache-Control", "private, max-age=300")
                self.end_headers()
                if send_body and length:
                    with target.open("rb") as handle:
                        handle.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk = handle.read(min(1024 * 1024, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                get_runtime_diagnostics().record(
                    "SERVER_MEDIA_END", request_id=request_id, route="isolated-media:5051",
                    method=self.command, media_kind=("sponsor_advertisement_video" if prefix == "/sponsor-ad-files/" else "managed_asset_media"), http_status=status,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    file_size_bytes=file_size, response_content_length=length,
                    range_request=bool(byte_range), active_media_requests=max(0, active_media - 1),
                    thread=threading.current_thread().name,
                )
            except _EXPECTED_MEDIA_DISCONNECTS:
                get_runtime_diagnostics().record(
                    "SERVER_MEDIA_END", request_id=request_id, route="isolated-media:5051",
                    method=self.command, media_kind="isolated_media", http_status=499,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    range_request=bool(range_header), response_aborted=True,
                    thread=threading.current_thread().name,
                )
            except Exception as exc:
                get_runtime_diagnostics().record(
                    "SERVER_MEDIA_END", request_id=request_id, route="isolated-media:5051",
                    method=self.command, media_kind="isolated_media", http_status=500,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    error_type=type(exc).__name__, error_message=str(exc)[:240],
                    thread=threading.current_thread().name,
                )
            finally:
                _media_request_finished()

    return IsolatedMediaHandler


def _ensure_media_server(sponsor_directory: Path, asset_directory: Path | None = None) -> int:
    global _MEDIA_SERVER
    sponsor_root = sponsor_directory.resolve()
    asset_root = asset_directory.resolve() if asset_directory is not None else None
    with _MEDIA_SERVER_LOCK:
        _MEDIA_SERVER_DIRECTORIES["/sponsor-ad-files/"] = sponsor_root
        if asset_root is not None:
            _MEDIA_SERVER_DIRECTORIES["/asset-files/"] = asset_root
        if _MEDIA_SERVER is not None:
            return _MEDIA_SERVER_PORT
        handler = _build_media_handler()
        server = _IsolatedMediaHTTPServer(("0.0.0.0", _MEDIA_SERVER_PORT), handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, name="csrn-isolated-media-server", daemon=True)
        thread.start()
        _MEDIA_SERVER = server
        get_runtime_diagnostics().record(
            "SERVER_MEDIA_ISOLATION_READY", port=_MEDIA_SERVER_PORT,
            sponsor_media_directory=str(sponsor_root),
            asset_media_directory=str(asset_root or ""), thread=thread.name,
        )
        return _MEDIA_SERVER_PORT


def start_isolated_media_server(sponsor_directory: Path, asset_directory: Path | None = None) -> int:
    """Start and verify the dedicated local-media server before game control starts."""
    return _ensure_media_server(sponsor_directory, asset_directory)


def _media_request_started() -> int:
    global _ACTIVE_MEDIA_REQUESTS
    with _MEDIA_ACTIVITY_LOCK:
        _ACTIVE_MEDIA_REQUESTS += 1
        return _ACTIVE_MEDIA_REQUESTS


def _media_request_finished() -> int:
    global _ACTIVE_MEDIA_REQUESTS
    with _MEDIA_ACTIVITY_LOCK:
        _ACTIVE_MEDIA_REQUESTS = max(0, _ACTIVE_MEDIA_REQUESTS - 1)
        return _ACTIVE_MEDIA_REQUESTS


@dataclass(frozen=True)
class AssetRoutesDependencies:
    require_auth: RouteDecorator
    get_asset_service: Callable[[], Any]
    get_upload_dir: Callable[[], Path]
    extension_allowed: Callable[[str], bool]
    normalize_asset_id: Callable[[str], str]
    clock: Callable[[], float]
    token_hex: Callable[[int], str]


def create_asset_blueprint(
    dependencies: AssetRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("asset_routes", __name__)

    def sponsor_ad_dir() -> Path:
        return dependencies.get_upload_dir().parent / "SponsorAdvertisements"

    def storage_for_asset(asset: Any) -> tuple[Path, str]:
        placement = str((asset or {}).get("placement", "flexible") or "flexible").strip().lower()
        if placement == "sponsor_advertisement_video":
            return sponsor_ad_dir(), "/sponsor-ad-files/"
        return dependencies.get_upload_dir(), "/asset-files/"

    def managed_path(file_url: Any) -> Path | None:
        value = str(file_url or "").strip()
        for prefix, directory in (
            ("/asset-files/", dependencies.get_upload_dir()),
            ("/sponsor-ad-files/", sponsor_ad_dir()),
        ):
            if not value.startswith(prefix):
                continue
            filename = value[len(prefix):]
            if not filename or Path(filename).name != filename:
                return None
            resolved_dir = directory.resolve()
            candidate = (resolved_dir / filename).resolve()
            return candidate if candidate.parent == resolved_dir else None
        return None

    def file_is_referenced(file_url: str, *, exclude_id: str = "") -> bool:
        rows = dependencies.get_asset_service().list_records().data.get("assets", [])
        return any(
            str(row.get("id", "")) != str(exclude_id)
            and str(row.get("file_url", "")).strip() == str(file_url or "").strip()
            for row in rows
        )

    def remove_unreferenced_managed_file(
        file_url: str,
        *,
        exclude_id: str = "",
    ) -> bool:
        target = managed_path(file_url)
        if target is None or file_is_referenced(file_url, exclude_id=exclude_id):
            return False
        if not target.exists() or not target.is_file():
            return False
        target.unlink()
        return True

    @routes.get("/api/assets")
    @dependencies.require_auth
    def list_assets():
        include_inactive = str(
            request.args.get("include_inactive", "true")
        ).strip().lower() not in {"0", "false", "no", "off"}
        result = dependencies.get_asset_service().list_records(
            include_inactive=include_inactive,
            category=str(request.args.get("category", "")),
            asset_type=str(request.args.get("asset_type", "")),
            rights_status=str(request.args.get("rights_status", "")),
            placement=str(request.args.get("placement", "")),
        )
        return jsonify(result.data)

    @routes.get("/api/assets/storage")
    @dependencies.require_auth
    def asset_storage():
        rows = dependencies.get_asset_service().list_records().data.get("assets", [])
        referenced = {
            str(row.get("file_url", "")).strip()
            for row in rows
            if managed_path(row.get("file_url")) is not None
        }
        locations = (
            (dependencies.get_upload_dir(), "/asset-files/"),
            (sponsor_ad_dir(), "/sponsor-ad-files/"),
        )
        files: list[tuple[Path, str]] = []
        for directory, prefix in locations:
            if directory.exists():
                files.extend((path, prefix) for path in directory.iterdir() if path.is_file())
        orphan_files = [
            path
            for path, prefix in files
            if f"{prefix}{path.name}" not in referenced
        ]
        sponsor_files = [path for path, prefix in files if prefix == "/sponsor-ad-files/"]
        payload = {
            "managed_file_count": len(files),
            "managed_bytes": sum(path.stat().st_size for path, _ in files),
            "orphan_count": len(orphan_files),
            "orphan_bytes": sum(path.stat().st_size for path in orphan_files),
        }
        if sponsor_files:
            payload["sponsor_ad_file_count"] = len(sponsor_files)
            payload["sponsor_ad_bytes"] = sum(path.stat().st_size for path in sponsor_files)
        return jsonify(payload)

    @routes.post("/api/assets")
    @dependencies.require_auth
    def create_asset():
        result = dependencies.get_asset_service().create(
            request.get_json(silent=True) or {}
        )
        if result.code == "ASSET_NAME_REQUIRED":
            return jsonify({"error": "Asset name is required."}), 400
        return jsonify({"asset": result.data["asset"]})

    @routes.put("/api/assets/<asset_id>")
    @dependencies.require_auth
    def update_asset(asset_id: str):
        result = dependencies.get_asset_service().update(
            asset_id,
            request.get_json(silent=True) or {},
        )
        if result.code == "ASSET_NOT_FOUND":
            return jsonify({"error": "Asset not found."}), 404
        if result.code == "ASSET_NAME_REQUIRED":
            return jsonify({"error": "Asset name is required."}), 400
        return jsonify({"asset": result.data["asset"]})

    @routes.delete("/api/assets/<asset_id>")
    @dependencies.require_auth
    def delete_asset(asset_id: str):
        service = dependencies.get_asset_service()
        current = service.read(asset_id)
        result = service.delete(asset_id)
        if result.code == "ASSET_NOT_FOUND":
            return jsonify({"error": "Asset not found."}), 404
        file_url = str(current.data.get("asset", {}).get("file_url", ""))
        media_deleted = remove_unreferenced_managed_file(file_url)
        return jsonify({"ok": True, "media_deleted": media_deleted})

    @routes.post("/api/assets/<asset_id>/upload")
    @dependencies.require_auth
    def upload_asset(asset_id: str):
        upload = request.files.get("asset")
        if not upload or not upload.filename:
            return jsonify({"error": "Choose a file to upload."}), 400

        suffix = Path(upload.filename).suffix.lower()
        if not dependencies.extension_allowed(upload.filename):
            return jsonify({"error": "Unsupported asset file type."}), 400

        duplicate_action = str(
            request.form.get("duplicate_action", "prompt")
        ).lower()
        service = dependencies.get_asset_service()
        current_result = service.read(asset_id)
        if current_result.code == "ASSET_NOT_FOUND":
            return jsonify(
                {"error": "Save the asset record before uploading."}
            ), 404

        current_asset = current_result.data.get("asset", {})
        upload_dir, url_prefix = storage_for_asset(current_asset)
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_id = dependencies.normalize_asset_id(asset_id)
        temp = upload_dir / (
            f".upload-{dependencies.token_hex(8)}{suffix}"
        )
        upload.save(temp)
        sha256 = service.file_hash(temp)
        duplicate = service.duplicate_by_hash(
            sha256,
            exclude_id=asset_id,
        )
        if duplicate:
            duplicate_dir, _ = storage_for_asset(duplicate)
            if duplicate_dir.resolve() != upload_dir.resolve():
                duplicate = None

        if duplicate and duplicate_action == "prompt":
            temp.unlink(missing_ok=True)
            return jsonify(
                {"error": "DUPLICATE_ASSET", "duplicate_asset": duplicate}
            ), 409

        if duplicate and duplicate_action == "reuse":
            temp.unlink(missing_ok=True)
            result = service.reuse_duplicate(
                asset_id,
                str(duplicate.get("id", "")),
            )
            return jsonify(
                {
                    "file_url": result.data["asset"].get("file_url", ""),
                    **result.data,
                }
            )

        if duplicate and duplicate_action == "replace":
            existing_url = str(duplicate.get("file_url", ""))
            existing_target = managed_path(existing_url)
            if existing_target is not None and existing_target.parent == upload_dir.resolve():
                target = existing_target
                replacement_url = existing_url
            else:
                target = upload_dir / f"{duplicate['id']}{suffix}"
                replacement_url = f"{url_prefix}{target.name}"
            temp.replace(target)
            result = service.replace_duplicate(
                asset_id,
                str(duplicate.get("id", "")),
                file_url=replacement_url,
                sha256=sha256,
                original_filename=upload.filename,
            )
            return jsonify(
                {
                    "file_url": result.data["asset"]["file_url"],
                    **result.data,
                }
            )

        filename = f"{safe_id}-{int(dependencies.clock())}{suffix}"
        target = upload_dir / filename
        temp.replace(target)
        previous_url = str(
            current_result.data.get("asset", {}).get("file_url", "")
        )
        result = service.attach_file(
            asset_id,
            file_url=f"{url_prefix}{filename}",
            sha256=sha256,
            original_filename=upload.filename,
        )
        if previous_url and previous_url != result.data["asset"]["file_url"]:
            remove_unreferenced_managed_file(previous_url, exclude_id=asset_id)
        return jsonify(
            {
                "file_url": result.data["asset"]["file_url"],
                "duplicate_asset": duplicate,
                "duplicate_kept": bool(duplicate),
            }
        )

    @routes.get("/asset-files/<filename>")
    def asset_file(filename: str):
        if not filename or Path(filename).name != filename:
            return jsonify({"error": "MEDIA_NOT_FOUND"}), 404
        target = dependencies.get_upload_dir() / filename
        if not target.is_file():
            return jsonify({"error": "MEDIA_NOT_FOUND"}), 404
        if not _is_isolated_media_asset(filename):
            return send_from_directory(dependencies.get_upload_dir(), filename)
        try:
            port = _ensure_media_server(sponsor_ad_dir(), dependencies.get_upload_dir())
        except OSError as exc:
            get_runtime_diagnostics().record(
                "SERVER_MEDIA_ISOLATION_FAILED", error_type=type(exc).__name__,
                error_message=str(exc)[:240], fallback="blocked_to_protect_control_plane",
            )
            return jsonify({"error": "MEDIA_SERVER_UNAVAILABLE"}), 503
        host = request.host.split(":", 1)[0] or "127.0.0.1"
        media_url = f"http://{host}:{port}/asset-files/{quote(filename)}"
        get_runtime_diagnostics().record(
            "SERVER_MEDIA_REDIRECT", route="/asset-files/<filename>",
            media_kind="managed_asset_media", media_port=port,
            thread=threading.current_thread().name,
        )
        return redirect(media_url, code=307)

    @routes.get("/sponsor-ad-files/<filename>")
    def sponsor_ad_file(filename: str):
        if not filename or Path(filename).name != filename:
            return jsonify({"error": "MEDIA_NOT_FOUND"}), 404
        target = sponsor_ad_dir() / filename
        if not target.is_file():
            return jsonify({"error": "MEDIA_NOT_FOUND"}), 404
        try:
            port = _ensure_media_server(sponsor_ad_dir(), dependencies.get_upload_dir())
        except OSError as exc:
            get_runtime_diagnostics().record(
                "SERVER_MEDIA_ISOLATION_FAILED", error_type=type(exc).__name__,
                error_message=str(exc)[:240], fallback="blocked_to_protect_control_plane",
            )
            return jsonify({"error": "MEDIA_SERVER_UNAVAILABLE"}), 503
        host = request.host.split(":", 1)[0] or "127.0.0.1"
        media_url = f"http://{host}:{port}/sponsor-ad-files/{quote(filename)}"
        get_runtime_diagnostics().record(
            "SERVER_MEDIA_REDIRECT", route="/sponsor-ad-files/<filename>",
            media_kind="sponsor_advertisement_video", media_port=port,
            thread=threading.current_thread().name,
        )
        return redirect(media_url, code=307)

    return routes

