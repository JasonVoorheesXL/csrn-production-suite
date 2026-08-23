from __future__ import annotations

import io
from typing import Any

import pytest

import app as app_module
from personnel_service import PersonnelResult


if not hasattr(app_module, "get_personnel_service"):
    pytest.skip(
        "PersonnelService routes are not integrated yet.",
        allow_module_level=True,
    )


PERSONNEL_ID = "jason"


class StubPersonnelService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.personnel = {
            "id": PERSONNEL_ID,
            "full_name": "Jason Voorhees",
            "role": "Play-by-Play",
            "category": "Broadcast Talent",
            "status": "active",
        }
        self.list_result = PersonnelResult(
            "OK",
            {"personnel": [self.personnel]},
        )
        self.create_result = PersonnelResult(
            "OK",
            {"personnel": self.personnel},
        )
        self.update_result = PersonnelResult(
            "OK",
            {"personnel": self.personnel},
        )
        self.delete_result = PersonnelResult(
            "OK",
            {"ok": True, "deleted": PERSONNEL_ID},
        )
        self.attach_result = PersonnelResult(
            "OK",
            {
                "personnel": self.personnel,
                "path": "/personnel-headshots/jason.png",
            },
        )
        self.social_result = PersonnelResult(
            "OK",
            {
                "normalized": "https://x.com/csrn",
                "valid": True,
                "message": "",
            },
        )

    def list_records(self, **kwargs) -> PersonnelResult:
        self.calls.append(("list_records", kwargs))
        return self.list_result

    def create(self, incoming: dict[str, Any]) -> PersonnelResult:
        self.calls.append(("create", incoming))
        return self.create_result

    def update(
        self,
        personnel_id: str,
        incoming: dict[str, Any],
    ) -> PersonnelResult:
        self.calls.append(("update", (personnel_id, incoming)))
        return self.update_result

    def delete(self, personnel_id: str) -> PersonnelResult:
        self.calls.append(("delete", personnel_id))
        return self.delete_result

    def attach_headshot(
        self,
        personnel_id: str,
        path: str,
    ) -> PersonnelResult:
        self.calls.append(("attach_headshot", (personnel_id, path)))
        return self.attach_result

    def validate_social(self, platform: str, value: str) -> PersonnelResult:
        self.calls.append(("validate_social", (platform, value)))
        return self.social_result


@pytest.fixture
def personnel_client(monkeypatch: pytest.MonkeyPatch, tmp_path):
    service = StubPersonnelService()
    monkeypatch.setattr(app_module, "PERSONNEL_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setattr(app_module, "PERSONNEL_HEADSHOTS_DIR", tmp_path)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "SECRET_KEY",
        "personnel-route-test",
    )

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service, tmp_path


def test_list_personnel_preserves_array_contract_and_filters(personnel_client) -> None:
    client, service, _ = personnel_client
    response = client.get(
        "/api/broadcasters?include_inactive=false&category=Broadcast%20Talent"
        "&role=Play-by-Play&school_id=caledonia"
    )
    assert response.status_code == 200
    assert response.get_json() == [service.personnel]
    assert service.calls == [
        (
            "list_records",
            {
                "include_inactive": False,
                "category": "Broadcast Talent",
                "role": "Play-by-Play",
                "school_id": "caledonia",
            },
        )
    ]


def test_create_personnel_preserves_success_and_validation_contracts(
    personnel_client,
) -> None:
    client, service, _ = personnel_client
    payload = {"full_name": "Jason Voorhees", "role": "Play-by-Play"}
    created = client.post("/api/broadcasters", json=payload)
    assert created.status_code == 201
    assert created.get_json() == service.personnel

    service.create_result = PersonnelResult("STAFF_NAME_REQUIRED")
    missing = client.post("/api/broadcasters", json={})
    assert missing.status_code == 400
    assert missing.get_json() == {"error": "STAFF_NAME_REQUIRED"}

    service.create_result = PersonnelResult(
        "INVALID_SOCIAL_URL",
        {"fields": {"x": "Expected a valid x URL"}},
    )
    invalid = client.post("/api/broadcasters", json=payload)
    assert invalid.status_code == 400
    assert invalid.get_json()["fields"] == {
        "x": "Expected a valid x URL"
    }


def test_update_personnel_preserves_success_and_missing_contracts(
    personnel_client,
) -> None:
    client, service, _ = personnel_client
    payload = {"role": "Producer"}
    updated = client.put(f"/api/broadcasters/{PERSONNEL_ID}", json=payload)
    assert updated.status_code == 200
    assert updated.get_json() == service.personnel
    assert service.calls == [("update", (PERSONNEL_ID, payload))]

    service.update_result = PersonnelResult("BROADCASTER_NOT_FOUND")
    missing = client.put("/api/broadcasters/missing", json=payload)
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "BROADCASTER_NOT_FOUND"}


def test_delete_personnel_preserves_success_and_missing_contracts(
    personnel_client,
) -> None:
    client, service, _ = personnel_client
    deleted = client.delete(f"/api/broadcasters/{PERSONNEL_ID}")
    assert deleted.status_code == 200
    assert deleted.get_json() == {"ok": True}

    service.delete_result = PersonnelResult("BROADCASTER_NOT_FOUND")
    missing = client.delete("/api/broadcasters/missing")
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "BROADCASTER_NOT_FOUND"}


def test_headshot_upload_links_saved_file_through_service(personnel_client) -> None:
    client, service, directory = personnel_client
    response = client.post(
        f"/api/personnel/{PERSONNEL_ID}/headshot",
        data={"file": (io.BytesIO(b"image-data"), "portrait.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert response.get_json() == {"path": "/personnel-headshots/jason.png"}
    assert (directory / "jason.png").read_bytes() == b"image-data"
    assert service.calls == [
        (
            "attach_headshot",
            (PERSONNEL_ID, "/personnel-headshots/jason.png"),
        )
    ]


def test_headshot_upload_preserves_validation_and_missing_contracts(
    personnel_client,
) -> None:
    client, service, directory = personnel_client
    missing_file = client.post(
        f"/api/personnel/{PERSONNEL_ID}/headshot",
        data={},
    )
    assert missing_file.status_code == 400
    assert missing_file.get_json() == {"error": "FILE_REQUIRED"}

    unsupported = client.post(
        f"/api/personnel/{PERSONNEL_ID}/headshot",
        data={"file": (io.BytesIO(b"bad"), "portrait.txt")},
        content_type="multipart/form-data",
    )
    assert unsupported.status_code == 400
    assert unsupported.get_json() == {"error": "UNSUPPORTED_IMAGE"}

    service.attach_result = PersonnelResult("PERSONNEL_NOT_FOUND")
    not_found = client.post(
        "/api/personnel/missing/headshot",
        data={"file": (io.BytesIO(b"image"), "portrait.jpg")},
        content_type="multipart/form-data",
    )
    assert not_found.status_code == 404
    assert not_found.get_json() == {"error": "PERSONNEL_NOT_FOUND"}
    assert not (directory / "missing.jpg").exists()


def test_validate_social_delegates_and_preserves_payload(personnel_client) -> None:
    client, service, _ = personnel_client
    response = client.post(
        "/api/validate-social",
        json={"platform": "x", "value": "@csrn"},
    )
    assert response.status_code == 200
    assert response.get_json() == service.social_result.data
    assert service.calls == [("validate_social", ("x", "@csrn"))]


