from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

import app as app_module
from logo_service import LogoResult


if not hasattr(app_module, "get_logo_service"):
    pytest.skip(
        "LogoService routes are not integrated yet.",
        allow_module_level=True,
    )


class StubLogoService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.record = {
            "id": "MS-LOW-CAL-primary",
            "school_id": "caledonia",
            "designation": "primary",
            "approval_status": "candidate",
        }
        self.list_result = LogoResult("OK", {"logos": [self.record]})
        self.process_result: LogoResult | None = None

    def list_records(self, **kwargs) -> LogoResult:
        self.calls.append(("list_records", kwargs))
        return self.list_result

    def process_candidate(self, school_id: str, **kwargs) -> LogoResult:
        self.calls.append(
            (
                "process_candidate",
                {
                    "school_id": school_id,
                    "raw": kwargs["raw"],
                    "original_filename": kwargs["original_filename"],
                },
            )
        )
        if self.process_result is not None:
            return self.process_result

        original_path = kwargs["write_original"](".png", kwargs["raw"])
        master_path = kwargs["write_master"](
            Image.new("RGBA", (1024, 1024), (255, 0, 0, 255))
        )
        scorebug_path = kwargs["write_scorebug"](
            Image.new("RGBA", (256, 256), (255, 0, 0, 255))
        )
        return LogoResult(
            "OK",
            {
                "school": {
                    "id": school_id,
                    "primary_logo": master_path,
                },
                "logo": {
                    **self.record,
                    "original_path": original_path,
                    "round_master_path": master_path,
                    "scorebug_path": scorebug_path,
                },
                "primary_color": "#FF0000",
                "secondary_color": "#FFFFFF",
                "preview_url": master_path,
                "message": "Round candidate logo created; review colors and approve before broadcast use.",
            },
        )


@pytest.fixture
def logo_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    service = StubLogoService()
    monkeypatch.setattr(app_module, "LOGO_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setattr(app_module, "BASE_DIR", tmp_path)
    monkeypatch.setattr(app_module, "DATA_DIR", tmp_path / "Data")
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "logo-route-test")

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service, tmp_path


def test_list_logos_preserves_array_contract_and_filters(logo_client) -> None:
    client, service, _ = logo_client
    response = client.get(
        "/api/logos?school_id=caledonia&designation=primary"
        "&approval_status=candidate"
    )
    assert response.status_code == 200
    assert response.get_json() == [service.record]
    assert service.calls == [
        (
            "list_records",
            {
                "school_id": "caledonia",
                "designation": "primary",
                "approval_status": "candidate",
            },
        )
    ]


def test_process_logo_requires_uploaded_file(logo_client) -> None:
    client, service, _ = logo_client
    response = client.post("/api/schools/caledonia/logo/process", data={})
    assert response.status_code == 400
    assert response.get_json() == {"error": "LOGO_FILE_REQUIRED"}
    assert service.calls == []


def test_process_logo_writes_derivatives_and_preserves_response_contract(
    logo_client,
) -> None:
    client, service, root = logo_client
    raw = b"uploaded-logo"
    response = client.post(
        "/api/schools/caledonia/logo/process",
        data={"logo": (io.BytesIO(raw), "warrior.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["primary_color"] == "#FF0000"
    assert payload["preview_url"] == (
        "/school-logos/caledonia/round-master.png"
    )
    folder = root / "Data" / "Logos" / "caledonia"
    assert (folder / "original.png").read_bytes() == raw
    assert Image.open(folder / "round-master.png").size == (1024, 1024)
    assert Image.open(folder / "round-scorebug.png").size == (256, 256)
    assert service.calls[0][0] == "process_candidate"
    assert service.calls[0][1]["school_id"] == "caledonia"
    assert service.calls[0][1]["original_filename"] == "warrior.png"


def test_process_logo_maps_service_errors(logo_client) -> None:
    client, service, _ = logo_client

    service.process_result = LogoResult("SCHOOL_NOT_FOUND")
    missing = client.post(
        "/api/schools/missing/logo/process",
        data={"logo": (io.BytesIO(b"image"), "mark.png")},
        content_type="multipart/form-data",
    )
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "SCHOOL_NOT_FOUND"}

    service.process_result = LogoResult("INVALID_IMAGE")
    invalid = client.post(
        "/api/schools/caledonia/logo/process",
        data={"logo": (io.BytesIO(b"broken"), "mark.png")},
        content_type="multipart/form-data",
    )
    assert invalid.status_code == 400
    assert invalid.get_json() == {"error": "INVALID_IMAGE"}

    service.process_result = LogoResult(
        "LOGO_STORAGE_FAILED",
        {"message": "disk unavailable"},
    )
    failed = client.post(
        "/api/schools/caledonia/logo/process",
        data={"logo": (io.BytesIO(b"image"), "mark.png")},
        content_type="multipart/form-data",
    )
    assert failed.status_code == 500
    assert failed.get_json() == {
        "error": "LOGO_STORAGE_FAILED",
        "message": "disk unavailable",
    }
