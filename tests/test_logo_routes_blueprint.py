from __future__ import annotations

import io
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.logo_routes import LogoRoutesDependencies, create_logo_blueprint


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any]


class FakeImage:
    def save(self, path: Path) -> None:
        path.write_bytes(b"normalized-image")


class StubLogoService:
    def __init__(self) -> None:
        self.process_code = "OK"
        self.list_result = StubResult("OK", {"logos": [{"id": "logo-one"}]})
        self.calls: list[tuple[str, Any]] = []

    def process_candidate(self, school_id: str, **kwargs: Any) -> StubResult:
        self.calls.append(("process", (school_id, kwargs["original_filename"], kwargs["raw"])))
        if self.process_code != "OK":
            data = {"message": "storage failed"} if self.process_code == "LOGO_STORAGE_FAILED" else {}
            return StubResult(self.process_code, data)
        original = kwargs["write_original"](".png", kwargs["raw"])
        master = kwargs["write_master"](FakeImage())
        scorebug = kwargs["write_scorebug"](FakeImage())
        return StubResult("OK", {"original": original, "master": master, "scorebug": scorebug})

    def list_records(self, **kwargs: Any) -> StubResult:
        self.calls.append(("list", kwargs))
        return self.list_result


@pytest.fixture
def logo_client(tmp_path: Path):
    service = StubLogoService()
    base_dir = tmp_path

    def normalize(value: str) -> str:
        return value.strip().lower().replace(" ", "-")

    def logo_dir(school_id: str) -> Path:
        return base_dir / "data" / "Logos" / normalize(school_id)

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def protected(*args: Any, **kwargs: Any):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)

        return protected

    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(
        create_logo_blueprint(
            LogoRoutesDependencies(
                require_auth=require_auth,
                get_logo_service=lambda: service,
                get_base_dir=lambda: base_dir,
                get_school_logo_dir=logo_dir,
                normalize_school_id=normalize,
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service, base_dir, logo_dir


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_logo_blueprint_registers_preserved_urls(logo_client) -> None:
    _, app, *_ = logo_client
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert {
        "/school-logos/<school_id>/<filename>",
        "/api/schools/<school_id>/logo/process",
        "/api/logos",
    }.issubset(paths)


def test_logo_routes_require_authentication(logo_client) -> None:
    client, _, service, *_ = logo_client
    response = client.get("/api/logos")
    assert response.status_code == 401
    assert service.calls == []


def test_list_logos_maps_filters(logo_client) -> None:
    client, _, service, *_ = logo_client
    response = client.get(
        "/api/logos?school_id=caledonia&designation=Primary&approval_status=Approved",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == [{"id": "logo-one"}]
    assert service.calls[-1] == (
        "list",
        {
            "school_id": "caledonia",
            "designation": "Primary",
            "approval_status": "Approved",
        },
    )


def test_school_logo_file_route_remains_public(logo_client) -> None:
    client, _, _, _, logo_dir = logo_client
    folder = logo_dir("Caledonia")
    folder.mkdir(parents=True)
    (folder / "round-master.png").write_bytes(b"logo")
    response = client.get("/school-logos/Caledonia/round-master.png")
    assert response.status_code == 200
    assert response.data == b"logo"


def test_process_school_logo_requires_upload(logo_client) -> None:
    client, *_ = logo_client
    response = client.post(
        "/api/schools/Caledonia/logo/process",
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "LOGO_FILE_REQUIRED"}


def test_process_school_logo_writes_all_outputs(logo_client) -> None:
    client, _, service, base_dir, logo_dir = logo_client
    response = client.post(
        "/api/schools/Caledonia/logo/process",
        data={"logo": (io.BytesIO(b"source-image"), "crest.png")},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["original"] == "data/Logos/caledonia/original.png"
    assert payload["master"] == "/school-logos/caledonia/round-master.png"
    assert payload["scorebug"] == "/school-logos/caledonia/round-scorebug.png"
    folder = logo_dir("Caledonia")
    assert (folder / "original.png").read_bytes() == b"source-image"
    assert (folder / "round-master.png").read_bytes() == b"normalized-image"
    assert service.calls[-1] == ("process", ("Caledonia", "crest.png", b"source-image"))
    assert folder.is_relative_to(base_dir)


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("SCHOOL_NOT_FOUND", 404),
        ("INVALID_IMAGE", 400),
        ("LOGO_STORAGE_FAILED", 500),
    ],
)
def test_process_school_logo_preserves_error_mappings(
    logo_client,
    code: str,
    status: int,
) -> None:
    client, _, service, *_ = logo_client
    service.process_code = code
    response = client.post(
        "/api/schools/Caledonia/logo/process",
        data={"logo": (io.BytesIO(b"source"), "crest.png")},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert response.status_code == status
    assert response.get_json()["error"] == code
    if code == "LOGO_STORAGE_FAILED":
        assert response.get_json()["message"] == "storage failed"


