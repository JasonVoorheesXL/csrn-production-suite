from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import json
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from association_import_service import AssociationProfile


Record = dict[str, Any]
Clock = Callable[[], datetime]
Resolver = Callable[..., list[tuple[Any, ...]]]
Fetcher = Callable[[str, int, int], tuple[bytes, str, str]]


@dataclass(frozen=True)
class AssociationSourceResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class _HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table_depth = 0
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        tag = tag.lower()
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._current_table = []
        elif tag == "tr" and self._table_depth == 1:
            self._current_row = []
        elif tag in {"td", "th"} and self._current_row is not None:
            self._current_cell = []
        elif tag == "br" and self._current_cell is not None:
            self._current_cell.append(" ")

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._current_cell is not None:
            value = " ".join("".join(self._current_cell).split())
            if self._current_row is not None:
                self._current_row.append(value)
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None:
            if self._current_table is not None and any(self._current_row):
                self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._table_depth:
            if self._table_depth == 1 and self._current_table is not None:
                self.tables.append(self._current_table)
                self._current_table = None
            self._table_depth -= 1


class AssociationSourceService:
    """Safely load association rows from JSON, CSV, or HTML tables."""

    DEFAULT_MAX_BYTES = 5 * 1024 * 1024
    DEFAULT_MAX_ROWS = 5000
    DEFAULT_TIMEOUT_SECONDS = 15

    def __init__(
        self,
        *,
        fetcher: Fetcher | None = None,
        resolver: Resolver | None = None,
        clock: Clock | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._resolver = resolver or socket.getaddrinfo
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._max_bytes = max(1024, int(max_bytes))
        self._timeout_seconds = max(1, int(timeout_seconds))
        self._fetcher = fetcher or self._default_fetch

    def load(
        self,
        profile_data: Record,
        *,
        supplied_content: bytes | str | None = None,
        supplied_content_type: str = "",
    ) -> AssociationSourceResult:
        try:
            profile = AssociationProfile.from_dict(profile_data)
        except ValueError as exc:
            return AssociationSourceResult(str(exc))

        source_url = profile.source_url
        content_type = supplied_content_type.strip().lower()
        final_url = source_url

        if supplied_content is None:
            url_error = self._validate_public_url(source_url)
            if url_error:
                return AssociationSourceResult(url_error)
            try:
                raw, content_type, final_url = self._fetcher(
                    source_url,
                    self._timeout_seconds,
                    self._max_bytes,
                )
            except ValueError as exc:
                return AssociationSourceResult(str(exc))
            except Exception:
                return AssociationSourceResult("SOURCE_FETCH_FAILED")

            redirect_error = self._validate_public_url(final_url)
            if redirect_error:
                return AssociationSourceResult("UNSAFE_SOURCE_REDIRECT")
        else:
            raw = (
                supplied_content.encode("utf-8")
                if isinstance(supplied_content, str)
                else supplied_content
            )

        if len(raw) > self._max_bytes:
            return AssociationSourceResult("SOURCE_TOO_LARGE")

        parse_result = self._parse(profile, raw)
        if not parse_result.ok:
            return parse_result

        rows = parse_result.data["rows"]
        max_rows = int(
            profile.options.get("max_rows", self.DEFAULT_MAX_ROWS)
            or self.DEFAULT_MAX_ROWS
        )
        if len(rows) > max(1, max_rows):
            return AssociationSourceResult("SOURCE_ROW_LIMIT_EXCEEDED")

        mapped_sources = list(profile.field_mapping)
        missing_source_fields = [
            path
            for path in mapped_sources
            if not any(self._nested_value(row, path) is not None for row in rows)
        ]

        return AssociationSourceResult(
            "OK",
            {
                "profile": {
                    "id": profile.profile_id,
                    "name": profile.name,
                    "association": profile.association,
                    "state": profile.state,
                    "source_type": profile.source_type,
                },
                "rows": rows,
                "row_count": len(rows),
                "source": {
                    "requested_url": source_url,
                    "final_url": final_url,
                    "content_type": content_type,
                    "retrieved_at": self._clock().isoformat(),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "size_bytes": len(raw),
                },
                "warnings": {
                    "missing_source_fields": missing_source_fields,
                },
            },
        )

    def _default_fetch(
        self,
        url: str,
        timeout_seconds: int,
        max_bytes: int,
    ) -> tuple[bytes, str, str]:
        request = Request(
            url,
            headers={
                "User-Agent": "CSRN-Association-Importer/1.0",
                "Accept": (
                    "application/json,text/csv,text/html,"
                    "application/xhtml+xml;q=0.9,*/*;q=0.5"
                ),
            },
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise ValueError("SOURCE_TOO_LARGE")
            content_type = str(
                response.headers.get("Content-Type", "")
            ).split(";", 1)[0].strip().lower()
            return raw, content_type, response.geturl()

    def _validate_public_url(self, url: str) -> str:
        try:
            parsed = urlparse(str(url or "").strip())
        except ValueError:
            return "INVALID_SOURCE_URL"
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return "INVALID_SOURCE_URL"

        hostname = parsed.hostname.rstrip(".").lower()
        if hostname == "localhost" or hostname.endswith(".local"):
            return "UNSAFE_SOURCE_URL"

        try:
            addresses = self._resolve_addresses(hostname, parsed.port)
        except (OSError, ValueError):
            return "SOURCE_HOST_UNRESOLVED"
        if not addresses:
            return "SOURCE_HOST_UNRESOLVED"
        if any(not self._is_public_address(address) for address in addresses):
            return "UNSAFE_SOURCE_URL"
        return ""

    def _resolve_addresses(self, hostname: str, port: int | None) -> set[str]:
        try:
            direct = ipaddress.ip_address(hostname)
        except ValueError:
            direct = None
        if direct is not None:
            return {str(direct)}

        resolved = self._resolver(
            hostname,
            port or 443,
            type=socket.SOCK_STREAM,
        )
        addresses: set[str] = set()
        for item in resolved:
            sockaddr = item[4]
            if sockaddr:
                addresses.add(str(sockaddr[0]))
        return addresses

    @staticmethod
    def _is_public_address(value: str) -> bool:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            return False
        return bool(address.is_global)

    def _parse(
        self,
        profile: AssociationProfile,
        raw: bytes,
    ) -> AssociationSourceResult:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return AssociationSourceResult("SOURCE_ENCODING_UNSUPPORTED")

        try:
            if profile.source_type in {"json", "manifest"}:
                rows = self._parse_json(profile, text)
            elif profile.source_type == "csv":
                rows = self._parse_csv(profile, text)
            elif profile.source_type == "html_table":
                rows = self._parse_html_table(profile, text)
            else:
                return AssociationSourceResult("UNSUPPORTED_SOURCE_TYPE")
        except (csv.Error, json.JSONDecodeError, ValueError, TypeError):
            return AssociationSourceResult("SOURCE_PARSE_FAILED")

        return AssociationSourceResult("OK", {"rows": rows})

    def _parse_json(
        self,
        profile: AssociationProfile,
        text: str,
    ) -> list[Record]:
        payload: Any = json.loads(text)
        rows_path = str(
            profile.options.get(
                "rows_path",
                "schools" if profile.source_type == "manifest" else "",
            )
        ).strip()
        if rows_path:
            payload = self._nested_value(payload, rows_path)
        elif isinstance(payload, dict) and isinstance(payload.get("schools"), list):
            payload = payload["schools"]

        if not isinstance(payload, list):
            raise ValueError("rows must be a list")
        return [dict(item) for item in payload if isinstance(item, dict)]

    @staticmethod
    def _parse_csv(
        profile: AssociationProfile,
        text: str,
    ) -> list[Record]:
        delimiter = str(profile.options.get("delimiter", "")).strip()
        if not delimiter:
            try:
                delimiter = csv.Sniffer().sniff(text[:4096]).delimiter
            except csv.Error:
                delimiter = ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter[0])
        if not reader.fieldnames:
            raise ValueError("CSV headers required")
        return [
            {
                str(key or "").strip(): str(value or "").strip()
                for key, value in row.items()
            }
            for row in reader
            if row
        ]

    @staticmethod
    def _parse_html_table(
        profile: AssociationProfile,
        text: str,
    ) -> list[Record]:
        parser = _HTMLTableParser()
        parser.feed(text)
        table_index = int(profile.options.get("table_index", 0) or 0)
        if table_index < 0 or table_index >= len(parser.tables):
            raise ValueError("table not found")
        table = parser.tables[table_index]
        header_row = int(profile.options.get("header_row", 0) or 0)
        if header_row < 0 or header_row >= len(table):
            raise ValueError("header row not found")

        headers: list[str] = []
        used: dict[str, int] = {}
        for index, value in enumerate(table[header_row], start=1):
            base = value.strip() or f"column_{index}"
            used[base] = used.get(base, 0) + 1
            headers.append(
                base if used[base] == 1 else f"{base}_{used[base]}"
            )

        rows: list[Record] = []
        for values in table[header_row + 1 :]:
            if not any(str(value).strip() for value in values):
                continue
            rows.append(
                {
                    header: values[index].strip() if index < len(values) else ""
                    for index, header in enumerate(headers)
                }
            )
        return rows

    @staticmethod
    def _nested_value(value: Any, path: str) -> Any:
        current = value
        for segment in path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(segment)
        return current
