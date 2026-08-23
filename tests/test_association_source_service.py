from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from association_source_service import AssociationSourceService


def profile(
    source_type: str,
    *,
    field_mapping: dict[str, str] | None = None,
    options: dict[str, Any] | None = None,
    source_url: str = "https://association.example/schools",
) -> dict[str, Any]:
    return {
        "id": f"test-{source_type}",
        "name": f"Test {source_type}",
        "association": "TAHSAA",
        "state": "MS",
        "source_type": source_type,
        "source_url": source_url,
        "field_mapping": field_mapping
        or {
            "name": "official_name",
            "broadcast": "broadcast_name",
        },
        "defaults": {"state": "MS"},
        "options": options or {},
    }


def public_resolver(*args, **kwargs):
    del args, kwargs
    return [
        (
            2,
            1,
            6,
            "",
            ("93.184.216.34", 443),
        )
    ]


def fixed_clock() -> datetime:
    return datetime(2026, 7, 24, 19, 30, tzinfo=timezone.utc)


def test_remote_json_source_returns_rows_and_audit_metadata() -> None:
    raw = json.dumps(
        {
            "schools": [
                {"name": "North High School", "broadcast": "North"},
                {"name": "South High School", "broadcast": "South"},
            ]
        }
    ).encode("utf-8")

    def fetcher(url: str, timeout: int, max_bytes: int):
        assert url == "https://association.example/schools"
        assert timeout == 15
        assert max_bytes == 5 * 1024 * 1024
        return raw, "application/json", url

    service = AssociationSourceService(
        fetcher=fetcher,
        resolver=public_resolver,
        clock=fixed_clock,
    )
    result = service.load(
        profile("json", options={"rows_path": "schools"})
    )

    assert result.ok
    assert result.data["row_count"] == 2
    assert result.data["rows"][0]["name"] == "North High School"
    assert result.data["source"]["content_type"] == "application/json"
    assert result.data["source"]["retrieved_at"] == (
        "2026-07-24T19:30:00+00:00"
    )
    assert result.data["source"]["size_bytes"] == len(raw)
    assert len(result.data["source"]["sha256"]) == 64
    assert result.data["warnings"]["missing_source_fields"] == []


def test_supplied_json_root_list_is_supported() -> None:
    service = AssociationSourceService(clock=fixed_clock)
    result = service.load(
        profile("json"),
        supplied_content=json.dumps(
            [{"name": "North High School", "broadcast": "North"}]
        ),
        supplied_content_type="application/json",
    )

    assert result.ok
    assert result.data["row_count"] == 1
    assert result.data["rows"][0]["broadcast"] == "North"


def test_manifest_defaults_to_schools_collection() -> None:
    service = AssociationSourceService(clock=fixed_clock)
    result = service.load(
        profile("manifest"),
        supplied_content=json.dumps(
            {
                "classification": "5A",
                "schools": [
                    {"name": "North High School", "broadcast": "North"}
                ],
            }
        ),
    )

    assert result.ok
    assert result.data["row_count"] == 1


def test_csv_source_uses_headers_and_trims_values() -> None:
    service = AssociationSourceService(clock=fixed_clock)
    result = service.load(
        profile(
            "csv",
            field_mapping={
                "School": "official_name",
                "Broadcast": "broadcast_name",
            },
        ),
        supplied_content=(
            "School,Broadcast,Class\n"
            " North High School , North ,5A\n"
            "South High School,South,5A\n"
        ),
        supplied_content_type="text/csv",
    )

    assert result.ok
    assert result.data["row_count"] == 2
    assert result.data["rows"][0] == {
        "School": "North High School",
        "Broadcast": "North",
        "Class": "5A",
    }


def test_html_table_source_selects_table_and_header_row() -> None:
    html = """
    <html><body>
      <table><tr><th>Ignore</th></tr><tr><td>Value</td></tr></table>
      <table>
        <tr><th>School</th><th>Broadcast</th><th>City</th></tr>
        <tr><td>North High School</td><td>North</td><td>North City</td></tr>
        <tr><td>South High School</td><td>South</td><td>South City</td></tr>
      </table>
    </body></html>
    """
    service = AssociationSourceService(clock=fixed_clock)
    result = service.load(
        profile(
            "html_table",
            field_mapping={
                "School": "official_name",
                "Broadcast": "broadcast_name",
            },
            options={"table_index": 1, "header_row": 0},
        ),
        supplied_content=html,
        supplied_content_type="text/html",
    )

    assert result.ok
    assert result.data["row_count"] == 2
    assert result.data["rows"][1]["City"] == "South City"


def test_private_and_local_source_urls_are_rejected() -> None:
    service = AssociationSourceService(resolver=public_resolver)

    localhost = service.load(
        profile("json", source_url="http://localhost/schools")
    )
    private_ip = service.load(
        profile("json", source_url="http://127.0.0.1/schools")
    )
    file_url = service.load(
        profile("json", source_url="file:///tmp/schools.json")
    )

    assert localhost.code == "UNSAFE_SOURCE_URL"
    assert private_ip.code == "UNSAFE_SOURCE_URL"
    assert file_url.code == "INVALID_SOURCE_URL"


def test_redirect_to_private_address_is_rejected() -> None:
    def fetcher(url: str, timeout: int, max_bytes: int):
        del url, timeout, max_bytes
        return b"[]", "application/json", "http://127.0.0.1/private"

    service = AssociationSourceService(
        fetcher=fetcher,
        resolver=public_resolver,
    )
    result = service.load(profile("json"))

    assert result.code == "UNSAFE_SOURCE_REDIRECT"


def test_source_size_and_row_limits_are_enforced() -> None:
    service = AssociationSourceService(max_bytes=1024)
    too_large = service.load(
        profile("json"),
        supplied_content=b"x" * 1025,
    )
    too_many_rows = service.load(
        profile("json", options={"max_rows": 1}),
        supplied_content=json.dumps(
            [
                {"name": "North", "broadcast": "North"},
                {"name": "South", "broadcast": "South"},
            ]
        ),
    )

    assert too_large.code == "SOURCE_TOO_LARGE"
    assert too_many_rows.code == "SOURCE_ROW_LIMIT_EXCEEDED"


def test_parse_and_encoding_failures_return_stable_codes() -> None:
    service = AssociationSourceService()

    malformed = service.load(
        profile("json"),
        supplied_content="{not-json",
    )
    unsupported_encoding = service.load(
        profile("json"),
        supplied_content=b"\xff\xfe\xfd",
    )

    assert malformed.code == "SOURCE_PARSE_FAILED"
    assert unsupported_encoding.code == "SOURCE_ENCODING_UNSUPPORTED"


def test_missing_mapped_source_fields_are_reported_as_warnings() -> None:
    service = AssociationSourceService()
    result = service.load(
        profile(
            "json",
            field_mapping={
                "school.name": "official_name",
                "school.broadcast": "broadcast_name",
                "school.city": "city",
            },
        ),
        supplied_content=json.dumps(
            [
                {
                    "school": {
                        "name": "North High School",
                        "broadcast": "North",
                    }
                }
            ]
        ),
    )

    assert result.ok
    assert result.data["warnings"]["missing_source_fields"] == [
        "school.city"
    ]


