from __future__ import annotations

import base64
import hashlib
import json
import socket
import time
import uuid
from dataclasses import dataclass
from typing import Any

import websocket


class OBSConnectionError(RuntimeError):
    pass


@dataclass
class OBSReadOnlyResult:
    reachable: bool = False
    authenticated: bool = False
    obs_version: str = ""
    websocket_version: str = ""
    rpc_version: int | None = None
    active_profile: str = ""
    active_scene_collection: str = ""
    current_program_scene: str = ""
    scenes: list[str] | None = None
    inputs: list[dict[str, Any]] | None = None
    required_scene_exists: bool = False
    browser_source_exists: bool = False
    browser_source_in_required_scene: bool = False
    browser_source_enabled: bool = False
    browser_scene_item_id: int | None = None
    program_visual_scene_exists: bool = False
    graphic_source_exists: bool = False
    graphic_source_enabled: bool = False
    graphic_scene_item_id: int | None = None
    camera_source_exists: bool = False
    camera_source_enabled: bool = False
    camera_scene_item_id: int | None = None
    profile_matches: bool = False
    scene_collection_matches: bool = False
    error: str = ""
    checked_at: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "reachable": self.reachable,
            "authenticated": self.authenticated,
            "obs_version": self.obs_version,
            "websocket_version": self.websocket_version,
            "rpc_version": self.rpc_version,
            "active_profile": self.active_profile,
            "active_scene_collection": self.active_scene_collection,
            "current_program_scene": self.current_program_scene,
            "scenes": self.scenes or [],
            "inputs": self.inputs or [],
            "required_scene_exists": self.required_scene_exists,
            "browser_source_exists": self.browser_source_exists,
            "browser_source_in_required_scene": self.browser_source_in_required_scene,
            "browser_source_enabled": self.browser_source_enabled,
            "browser_scene_item_id": self.browser_scene_item_id,
            "program_visual_scene_exists": self.program_visual_scene_exists,
            "graphic_source_exists": self.graphic_source_exists,
            "graphic_source_enabled": self.graphic_source_enabled,
            "graphic_scene_item_id": self.graphic_scene_item_id,
            "camera_source_exists": self.camera_source_exists,
            "camera_source_enabled": self.camera_source_enabled,
            "camera_scene_item_id": self.camera_scene_item_id,
            "profile_matches": self.profile_matches,
            "scene_collection_matches": self.scene_collection_matches,
            "error": self.error,
            "checked_at": self.checked_at,
        }


class OBSReadOnlyClient:
    """Minimal OBS WebSocket 5.x client restricted to read-only requests."""

    READ_ONLY_REQUESTS = {
        "GetVersion",
        "GetProfileList",
        "GetSceneCollectionList",
        "GetCurrentProgramScene",
        "GetSceneList",
        "GetInputList",
        "GetSceneItemList",
    }

    def __init__(self, host: str, port: int, password: str = "", timeout: float = 3.0):
        self.host = host.strip() or "127.0.0.1"
        self.port = int(port)
        self.password = password or ""
        self.timeout = timeout
        self.ws: websocket.WebSocket | None = None

    def __enter__(self) -> "OBSReadOnlyClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def connect(self) -> None:
        url = f"ws://{self.host}:{self.port}"
        try:
            self.ws = websocket.create_connection(
                url,
                timeout=self.timeout,
                enable_multithread=False,
                suppress_origin=True,
            )
            hello = self._receive_until_op(0)
            hello_data = hello.get("d", {})
            identify_data: dict[str, Any] = {"rpcVersion": 1}

            authentication = hello_data.get("authentication")
            if authentication:
                if not self.password:
                    raise OBSConnectionError("OBS WebSocket requires a password.")
                identify_data["authentication"] = self._authentication_response(
                    self.password,
                    authentication.get("salt", ""),
                    authentication.get("challenge", ""),
                )

            self._send({"op": 1, "d": identify_data})
            identified = self._receive_until_op(2)
            if identified.get("op") != 2:
                raise OBSConnectionError("OBS did not complete WebSocket identification.")
        except (OSError, socket.error, websocket.WebSocketException, ValueError) as exc:
            self.close()
            raise OBSConnectionError(str(exc)) from exc

    def close(self) -> None:
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None

    @staticmethod
    def _authentication_response(password: str, salt: str, challenge: str) -> str:
        secret = base64.b64encode(
            hashlib.sha256((password + salt).encode("utf-8")).digest()
        ).decode("utf-8")
        return base64.b64encode(
            hashlib.sha256((secret + challenge).encode("utf-8")).digest()
        ).decode("utf-8")

    def _send(self, payload: dict[str, Any]) -> None:
        if self.ws is None:
            raise OBSConnectionError("OBS WebSocket is not connected.")
        self.ws.send(json.dumps(payload))

    def _receive(self) -> dict[str, Any]:
        if self.ws is None:
            raise OBSConnectionError("OBS WebSocket is not connected.")
        raw = self.ws.recv()
        if not raw:
            raise OBSConnectionError("OBS WebSocket closed the connection.")
        return json.loads(raw)

    def _receive_until_op(self, expected_op: int) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            message = self._receive()
            if message.get("op") == expected_op:
                return message
        raise OBSConnectionError("Timed out waiting for OBS WebSocket response.")

    def request(self, request_type: str, request_data: dict[str, Any] | None = None) -> dict[str, Any]:
        if request_type not in self.READ_ONLY_REQUESTS:
            raise OBSConnectionError(f"Blocked non-read-only OBS request: {request_type}")

        request_id = str(uuid.uuid4())
        self._send({
            "op": 6,
            "d": {
                "requestType": request_type,
                "requestId": request_id,
                "requestData": request_data or {},
            },
        })

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            message = self._receive()
            if message.get("op") != 7:
                continue
            data = message.get("d", {})
            if data.get("requestId") != request_id:
                continue
            status = data.get("requestStatus", {})
            if not status.get("result", False):
                comment = status.get("comment") or f"OBS request failed: {request_type}"
                raise OBSConnectionError(comment)
            return data.get("responseData", {})
        raise OBSConnectionError(f"Timed out waiting for {request_type}.")


def validate_obs_read_only(settings: dict[str, Any]) -> dict[str, Any]:
    result = OBSReadOnlyResult(checked_at=int(time.time()))
    if not settings.get("websocket_enabled", False):
        result.error = "OBS WebSocket integration is disabled in Settings."
        return result.as_dict()

    try:
        with OBSReadOnlyClient(
            host=str(settings.get("host", "127.0.0.1")),
            port=int(settings.get("port", 4455)),
            password=str(settings.get("password", "")),
            timeout=3.5,
        ) as client:
            result.reachable = True
            result.authenticated = True

            version = client.request("GetVersion")
            result.obs_version = str(version.get("obsVersion", ""))
            result.websocket_version = str(version.get("obsWebSocketVersion", ""))
            result.rpc_version = version.get("rpcVersion")

            profiles = client.request("GetProfileList")
            result.active_profile = str(profiles.get("currentProfileName", ""))

            collections = client.request("GetSceneCollectionList")
            result.active_scene_collection = str(
                collections.get("currentSceneCollectionName", "")
            )

            current_scene = client.request("GetCurrentProgramScene")
            result.current_program_scene = str(
                current_scene.get("currentProgramSceneName", "")
            )

            scene_data = client.request("GetSceneList")
            result.scenes = [
                str(scene.get("sceneName", ""))
                for scene in scene_data.get("scenes", [])
                if scene.get("sceneName")
            ]

            input_data = client.request("GetInputList")
            result.inputs = input_data.get("inputs", [])

            expected_profile = str(settings.get("profile", "")).strip()
            expected_collection = str(settings.get("scene_collection", "")).strip()
            required_scene = str(
                settings.get("required_scene", "10.01 - FOOTBALL SCOREBUG")
            ).strip()
            browser_source = str(
                settings.get("browser_source", "BRWSR - Football Scorebug")
            ).strip()
            program_visual_scene = str(
                settings.get("program_visual_scene", "10.02 - PROGRAM VISUAL")
            ).strip()
            graphic_source = str(
                settings.get("graphic_source", "IMG - Broadcast Background")
            ).strip()
            camera_source = str(
                settings.get("camera_source", "CAM - Primary Camera")
            ).strip()

            result.profile_matches = (
                not expected_profile or result.active_profile == expected_profile
            )
            result.scene_collection_matches = (
                not expected_collection
                or result.active_scene_collection == expected_collection
            )
            result.required_scene_exists = required_scene in (result.scenes or [])
            result.browser_source_exists = any(
                str(item.get("inputName", "")) == browser_source
                and str(item.get("inputKind", "")).lower() == "browser_source"
                for item in (result.inputs or [])
            )
            if result.required_scene_exists:
                scene_items = client.request(
                    "GetSceneItemList", {"sceneName": required_scene}
                ).get("sceneItems", [])
                browser_item = next(
                    (
                        item for item in scene_items
                        if str(item.get("sourceName", "")) == browser_source
                    ),
                    None,
                )
                if browser_item:
                    result.browser_source_in_required_scene = True
                    result.browser_source_enabled = bool(
                        browser_item.get("sceneItemEnabled", False)
                    )
                    result.browser_scene_item_id = int(browser_item["sceneItemId"])

            result.program_visual_scene_exists = program_visual_scene in (result.scenes or [])
            if result.program_visual_scene_exists:
                visual_items = client.request(
                    "GetSceneItemList", {"sceneName": program_visual_scene}
                ).get("sceneItems", [])
                graphic_item = next(
                    (item for item in visual_items if str(item.get("sourceName", "")) == graphic_source),
                    None,
                )
                camera_item = next(
                    (item for item in visual_items if str(item.get("sourceName", "")) == camera_source),
                    None,
                )
                if graphic_item:
                    result.graphic_source_exists = True
                    result.graphic_source_enabled = bool(graphic_item.get("sceneItemEnabled", False))
                    result.graphic_scene_item_id = int(graphic_item["sceneItemId"])
                if camera_item:
                    result.camera_source_exists = True
                    result.camera_source_enabled = bool(camera_item.get("sceneItemEnabled", False))
                    result.camera_scene_item_id = int(camera_item["sceneItemId"])
    except OBSConnectionError as exc:
        result.error = str(exc)
    except Exception as exc:
        result.error = f"Unexpected OBS validation error: {exc}"

    return result.as_dict()


class OBSControlledClient(OBSReadOnlyClient):
    """OBS client permitting only the approved scorebug visibility command."""

    READ_ONLY_REQUESTS = OBSReadOnlyClient.READ_ONLY_REQUESTS | {"SetSceneItemEnabled"}


def set_scorebug_visibility(settings: dict[str, Any], visible: bool) -> dict[str, Any]:
    """Validate the configured environment, then toggle only the scorebug item."""
    validation = validate_obs_read_only(settings)
    required = (
        validation.get("reachable")
        and validation.get("authenticated")
        and validation.get("profile_matches")
        and validation.get("scene_collection_matches")
        and validation.get("required_scene_exists")
        and validation.get("browser_source_exists")
        and validation.get("browser_source_in_required_scene")
        and validation.get("browser_scene_item_id") is not None
    )
    if not required:
        raise OBSConnectionError(
            validation.get("error")
            or "OBS validation failed; the scorebug command was not sent."
        )

    scene_name = str(settings.get("required_scene", "")).strip()
    scene_item_id = int(validation["browser_scene_item_id"])
    with OBSControlledClient(
        host=str(settings.get("host", "127.0.0.1")),
        port=int(settings.get("port", 4455)),
        password=str(settings.get("password", "")),
        timeout=3.5,
    ) as client:
        client.request(
            "SetSceneItemEnabled",
            {
                "sceneName": scene_name,
                "sceneItemId": scene_item_id,
                "sceneItemEnabled": bool(visible),
            },
        )

    validation["browser_source_enabled"] = bool(visible)
    validation["command_sent"] = True
    validation["command"] = "SHOW" if visible else "HIDE"
    return validation


def set_program_visual_mode(settings: dict[str, Any], mode: str) -> dict[str, Any]:
    """Select the approved graphic or optional camera source in Program Visual."""
    if mode not in {"graphic", "camera"}:
        raise OBSConnectionError("Program visual mode must be graphic or camera.")
    validation = validate_obs_read_only(settings)
    base_ready = (
        validation.get("reachable")
        and validation.get("authenticated")
        and validation.get("profile_matches")
        and validation.get("scene_collection_matches")
        and validation.get("program_visual_scene_exists")
        and validation.get("graphic_source_exists")
        and validation.get("graphic_scene_item_id") is not None
    )
    if not base_ready:
        raise OBSConnectionError(
            validation.get("error")
            or "Program Visual or its broadcast graphic did not validate."
        )
    if mode == "camera" and not (
        validation.get("camera_source_exists")
        and validation.get("camera_scene_item_id") is not None
    ):
        raise OBSConnectionError(
            "Camera mode is unavailable because CAM - Primary Camera is not configured."
        )

    scene_name = str(settings.get("program_visual_scene", "10.02 - PROGRAM VISUAL")).strip()
    desired_id = int(
        validation["graphic_scene_item_id"] if mode == "graphic"
        else validation["camera_scene_item_id"]
    )
    other_id = (
        validation.get("camera_scene_item_id") if mode == "graphic"
        else validation.get("graphic_scene_item_id")
    )
    with OBSControlledClient(
        host=str(settings.get("host", "127.0.0.1")),
        port=int(settings.get("port", 4455)),
        password=str(settings.get("password", "")),
        timeout=3.5,
    ) as client:
        client.request("SetSceneItemEnabled", {
            "sceneName": scene_name,
            "sceneItemId": desired_id,
            "sceneItemEnabled": True,
        })
        if other_id is not None:
            client.request("SetSceneItemEnabled", {
                "sceneName": scene_name,
                "sceneItemId": int(other_id),
                "sceneItemEnabled": False,
            })

    validation["graphic_source_enabled"] = mode == "graphic"
    validation["camera_source_enabled"] = mode == "camera"
    validation["visual_mode"] = mode
    validation["command_sent"] = True
    return validation
