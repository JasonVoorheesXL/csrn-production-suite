from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
from playwright.sync_api import sync_playwright


Record = dict[str, Any]


@dataclass(frozen=True)
class DragonFlyResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class DragonFlyService:
    """Read-only DragonFly public-data provider for CSRN."""

    API_BASE = "https://maxinfosite-api-live.dragonflyathletics.com"
    SITE_BASE = "https://go.dragonflyathletics.com"

    ROSTER_TABLE_SELECTOR = "team-roster table.roster-table"
    ROSTER_ROW_SELECTOR = "tr.table-rows"

    SPORT_CODES = {
        "football": "FB",
        "fb": "FB",
        "basketball": "BB",
        "baseball": "BA",
        "softball": "SB",
        "soccer": "SC",
        "volleyball": "VB",
    }

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.timeout_seconds = max(5.0, float(timeout_seconds))

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return " ".join(str(value or "").strip().casefold().split())

    @staticmethod
    def _clean_code(value: Any) -> str:
        return re.sub(r"[^A-Za-z0-9_-]", "", str(value or "").strip())

    @classmethod
    def normalize_sport(cls, sport: str) -> str:
        value = str(sport or "").strip()
        if not value:
            return "FB"
        return cls.SPORT_CODES.get(value.casefold(), value.upper())

    @staticmethod
    def _split_name(full_name: str) -> tuple[str, str]:
        parts = str(full_name or "").strip().split()
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": "CSRN-DragonFly-Importer/0.1",
                "Accept": "application/json,text/plain,*/*",
            },
        )

    def resolve_school(
        self,
        school_name: str,
        *,
        association: str = "MHSAA",
        city: str = "",
        state: str = "MS",
    ) -> DragonFlyResult:
        association = self._clean_code(association).upper()
        target_name = self._normalize_text(school_name)
        target_city = self._normalize_text(city)
        target_state = str(state or "").strip().upper()

        if not target_name:
            return DragonFlyResult("SCHOOL_NAME_REQUIRED")

        first_page_url = (
            f"{self.API_BASE}/states/{association}/directory/1"
        )

        try:
            with self._client() as client:
                first_response = client.get(first_page_url)
                first_response.raise_for_status()
                first_payload = first_response.json()

                if not isinstance(first_payload, dict):
                    return DragonFlyResult(
                        "DRAGONFLY_DIRECTORY_INVALID"
                    )

                total_pages = int(first_payload.get("totalPages", 1) or 1)

                candidates: list[Record] = []

                for page_number in range(1, total_pages + 1):
                    if page_number == 1:
                        payload = first_payload
                    else:
                        response = client.get(
                            f"{self.API_BASE}/states/"
                            f"{association}/directory/{page_number}"
                        )
                        response.raise_for_status()
                        payload = response.json()

                    results = (
                        payload.get("results", [])
                        if isinstance(payload, dict)
                        else []
                    )

                    for record in results:
                        if not isinstance(record, dict):
                            continue

                        record_name = self._normalize_text(
                            record.get("name")
                        )
                        record_city = self._normalize_text(
                            record.get("city")
                        )
                        record_state = str(
                            record.get("stateCode", "")
                        ).strip().upper()

                        name_exact = record_name == target_name
                        name_contains = (
                            target_name in record_name
                            or record_name in target_name
                        )

                        if not (name_exact or name_contains):
                            continue

                        score = 0
                        if name_exact:
                            score += 100
                        elif name_contains:
                            score += 50

                        if target_city:
                            if record_city == target_city:
                                score += 25
                            elif (
                                target_city in record_city
                                or record_city in target_city
                            ):
                                score += 10

                        if target_state and record_state == target_state:
                            score += 10

                        candidate = copy.deepcopy(record)
                        candidate["_match_score"] = score
                        candidates.append(candidate)

                if not candidates:
                    return DragonFlyResult(
                        "DRAGONFLY_SCHOOL_NOT_FOUND",
                        {
                            "query": {
                                "school_name": school_name,
                                "city": city,
                                "state": target_state,
                                "association": association,
                            }
                        },
                    )

                candidates.sort(
                    key=lambda item: int(
                        item.get("_match_score", 0)
                    ),
                    reverse=True,
                )

                best = candidates[0]
                best.pop("_match_score", None)

                return DragonFlyResult(
                    "OK",
                    {
                        "school": best,
                        "matches": [
                            {
                                key: value
                                for key, value in item.items()
                                if key != "_match_score"
                            }
                            for item in candidates[:10]
                        ],
                        "association": association,
                    },
                )

        except (httpx.HTTPError, ValueError, TypeError):
            return DragonFlyResult(
                "DRAGONFLY_DIRECTORY_FETCH_FAILED"
            )

    def get_school_summary(
        self,
        school_code: str,
    ) -> DragonFlyResult:
        school_code = self._clean_code(school_code)
        if not school_code:
            return DragonFlyResult("DRAGONFLY_SCHOOL_CODE_REQUIRED")

        url = (
            f"{self.API_BASE}/schools/{school_code}/summary"
        )

        try:
            with self._client() as client:
                response = client.get(url)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return DragonFlyResult(
                "DRAGONFLY_SUMMARY_FETCH_FAILED"
            )

        if not isinstance(payload, dict):
            return DragonFlyResult("DRAGONFLY_SUMMARY_INVALID")

        return DragonFlyResult(
            "OK",
            {
                "summary": payload,
                "source_url": url,
                "retrieved_at": self._now_iso(),
            },
        )

    @staticmethod
    def normalize_school_record(
        directory_record: Record,
        summary: Record | None = None,
        *,
        association: str = "MHSAA",
    ) -> Record:
        summary = summary or {}

        colors = (
            directory_record.get("heraldry", {}).get("colors", [])
            if isinstance(
                directory_record.get("heraldry"),
                dict,
            )
            else []
        )

        primary_color = ""
        secondary_color = ""

        if isinstance(colors, list):
            color_codes = [
                str(item.get("code", "")).strip()
                for item in colors
                if isinstance(item, dict)
                and str(item.get("code", "")).strip()
            ]
            if color_codes:
                primary_color = color_codes[0]
            if len(color_codes) > 1:
                secondary_color = color_codes[1]

        heraldry = directory_record.get("heraldry")
        mascot = (
            str(heraldry.get("mascot", "")).strip()
            if isinstance(heraldry, dict)
            else ""
        )

        competition = directory_record.get("competitionLevels")
        competition = (
            competition if isinstance(competition, dict) else {}
        )

        media = directory_record.get("media")
        media = media if isinstance(media, list) else []

        logo_url = ""
        for item in media:
            if not isinstance(item, dict):
                continue
            candidate = str(item.get("$url", "")).strip()
            if candidate:
                logo_url = candidate
                if str(item.get("purpose", "")).lower() == "logo600":
                    break

        official_name = str(
            directory_record.get("name", "")
        ).strip()

        city = str(directory_record.get("city", "")).strip()
        state = str(
            directory_record.get("stateCode", "")
        ).strip().upper()

        return {
            "official_name": official_name,
            "broadcast_name": official_name,
            "short_name": official_name,
            "preferred_scorebug_name": official_name,
            "mascot": mascot,
            "nickname": mascot,
            "city": city,
            "state": state,
            "classification": str(
                competition.get("mhsaaClass", "")
            ).strip(),
            "region": str(
                competition.get("mhsaaRegion", "")
            ).strip(),
            "district": "",
            "school_address": {
                "address1": str(
                    directory_record.get("address", "")
                ).strip(),
                "address2": "",
                "city": city,
                "state": state,
                "postal_code": "",
            },
            "primary_color": primary_color or "#808080",
            "secondary_color": secondary_color or "#FFFFFF",
            "primary_logo": logo_url,
            "source_data": {
                "provider": "dragonfly-public",
                "association": association,
                "dragonfly_org_id": str(
                    directory_record.get("orgId", "")
                ).strip(),
                "dragonfly_school_code": str(
                    directory_record.get("shortCode", "")
                ).strip(),
                "source_url": (
                    f"{DragonFlyService.SITE_BASE}/sites/"
                    f"{association}/"
                    f"{directory_record.get('shortCode', '')}"
                ),
                "retrieved_at": DragonFlyService._now_iso(),
            },
            "dragonfly_raw": {
                "directory": copy.deepcopy(directory_record),
                "summary": copy.deepcopy(summary),
            },
        }

    def get_roster(
        self,
        school_code: str,
        *,
        association: str = "MHSAA",
        sport: str = "FB",
    ) -> DragonFlyResult:
        association = self._clean_code(association).upper()
        school_code = self._clean_code(school_code)
        sport_code = self.normalize_sport(sport)

        if not school_code:
            return DragonFlyResult("DRAGONFLY_SCHOOL_CODE_REQUIRED")

        url = (
            f"{self.SITE_BASE}/sites/{association}/"
            f"{school_code}/roster?sport={sport_code}"
        )

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(
                    viewport={"width": 1400, "height": 1000}
                )

                page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=60000,
                )

                tables = page.locator(self.ROSTER_TABLE_SELECTOR)

                if tables.count() == 0:
                    page.get_by_text(
                        "SCHEDULES",
                        exact=True,
                    ).last.click(timeout=15000)

                    page.wait_for_timeout(2500)

                    page.get_by_text(
                        "ROSTER",
                        exact=True,
                    ).last.click(timeout=15000)

                    try:
                        page.wait_for_selector(
                            self.ROSTER_TABLE_SELECTOR,
                            timeout=20000,
                        )
                    except Exception:
                        pass

                tables = page.locator(self.ROSTER_TABLE_SELECTOR)

                raw_entries: list[dict[str, Any]] = []
                available_levels: list[str] = []

                for table_index in range(tables.count()):
                    table = tables.nth(table_index)

                    heading = table.evaluate(
                        """table => {
                            const prev = table.previousElementSibling;
                            return prev ? (prev.innerText || '').trim() : '';
                        }"""
                    )

                    heading = str(heading or "").strip()
                    if heading:
                        available_levels.append(heading)

                    heading_upper = heading.upper()

                    # CSRN high-school program roster:
                    # include Varsity and JV; exclude Junior High by default.
                    if not (
                        heading_upper.startswith("VARSITY ")
                        or heading_upper.startswith("JV ")
                        or heading_upper.startswith("JUNIOR VARSITY ")
                    ):
                        continue

                    rows = table.locator(self.ROSTER_ROW_SELECTOR)

                    for index in range(rows.count()):
                        cells = rows.nth(index).locator("td")
                        values = [
                            cells.nth(cell_index).inner_text().strip()
                            for cell_index in range(cells.count())
                        ]

                        raw_entries.append(
                            {
                                "level": heading,
                                "values": values,
                            }
                        )

                browser.close()

        except Exception as exc:
            return DragonFlyResult(
                "DRAGONFLY_ROSTER_FETCH_FAILED",
                {
                    "source_url": url,
                    "detail": str(exc),
                },
            )

        players: list[Record] = []
        warnings: list[Record] = []

        merged_players: dict[str, Record] = {}

        for index, entry in enumerate(raw_entries):
            values = entry.get("values", [])
            source_level = str(entry.get("level", "")).strip()

            if len(values) < 6:
                warnings.append(
                    {
                        "type": "MALFORMED_ROSTER_ROW",
                        "row": index + 1,
                        "raw": values,
                        "level": source_level,
                    }
                )
                continue

            name = values[0].strip()
            number = values[1].strip()
            position_raw = values[2].strip()
            height_raw = values[3].strip()
            weight = values[4].strip()
            grade = values[5].strip()

            height = (
                ""
                if height_raw in {"' \"", "'\"", "’ \""}
                else height_raw
            )

            first_name, last_name = self._split_name(name)

            player_warnings: list[str] = []

            if not number:
                player_warnings.append("MISSING_JERSEY_NUMBER")
            if not position_raw:
                player_warnings.append("MISSING_POSITION")
            if not height:
                player_warnings.append("MISSING_HEIGHT")
            if not weight:
                player_warnings.append("MISSING_WEIGHT")

            try:
                numeric_weight = int(weight) if weight else 0
            except ValueError:
                numeric_weight = 0
                if weight:
                    player_warnings.append("INVALID_WEIGHT")

            if numeric_weight and numeric_weight >= 400:
                player_warnings.append("UNUSUAL_WEIGHT")

            player: Record = {
                "number": number,
                "first_name": first_name,
                "last_name": last_name,
                "preferred_name": "",
                "position": position_raw.upper(),
                "secondary_position": "",
                "grade": grade,
                "height": height,
                "weight": weight,
                "captain": False,
                "starter": False,
                "status": "active",
                "pronunciation": "",
                "pronunciation_verified": False,
                "headshot": "",
                "source_data": {
                    "provider": "dragonfly-public",
                    "association": association,
                    "dragonfly_school_code": school_code,
                    "sport": sport_code,
                    "source_url": url,
                    "retrieved_at": self._now_iso(),
                    "raw": {
                        "name": name,
                        "number": number,
                        "position": position_raw,
                        "height": height_raw,
                        "weight": weight,
                        "grade": grade,
                    },
                },
                "import_warnings": player_warnings,
            }

            player["source_levels"] = [source_level] if source_level else []

            identity_key = " ".join(
                part.casefold()
                for part in (first_name, last_name, grade)
                if part
            )

            existing = merged_players.get(identity_key)

            if existing is None:
                merged_players[identity_key] = player
            else:
                existing_levels = existing.setdefault("source_levels", [])
                if source_level and source_level not in existing_levels:
                    existing_levels.append(source_level)

                # Prefer populated fields from either roster level.
                for field_name in (
                    "number",
                    "position",
                    "height",
                    "weight",
                    "grade",
                ):
                    if not str(existing.get(field_name, "")).strip() and str(
                        player.get(field_name, "")
                    ).strip():
                        existing[field_name] = player[field_name]

                # Preserve raw records from all source levels.
                existing_source = existing.setdefault("source_data", {})
                raw_records = existing_source.setdefault("raw_records", [])

                if not raw_records:
                    raw_existing = existing_source.get("raw")
                    if isinstance(raw_existing, dict):
                        raw_records.append(copy.deepcopy(raw_existing))

                raw_records.append(
                    {
                        **copy.deepcopy(player["source_data"]["raw"]),
                        "level": source_level,
                    }
                )

                existing_warnings = set(
                    existing.get("import_warnings", [])
                )
                incoming_warnings = set(player_warnings)

                # Recompute missing-field warnings after merge.
                combined_warnings = existing_warnings | incoming_warnings

                for warning_name, field_name in (
                    ("MISSING_JERSEY_NUMBER", "number"),
                    ("MISSING_POSITION", "position"),
                    ("MISSING_HEIGHT", "height"),
                    ("MISSING_WEIGHT", "weight"),
                ):
                    if str(existing.get(field_name, "")).strip():
                        combined_warnings.discard(warning_name)

                existing["import_warnings"] = sorted(combined_warnings)

        players = list(merged_players.values())

        for player in players:
            player_name = (
                f"{player.get('first_name', '')} "
                f"{player.get('last_name', '')}"
            ).strip()

            if player.get("import_warnings"):
                warnings.append(
                    {
                        "type": "PLAYER_DATA_WARNING",
                        "player": player_name,
                        "warnings": player["import_warnings"],
                        "source_levels": player.get("source_levels", []),
                    }
                )

        if not players:
            return DragonFlyResult(
                "DRAGONFLY_ROSTER_EMPTY",
                {
                    "source_url": url,
                    "raw_row_count": len(raw_entries),
                },
            )

        return DragonFlyResult(
            "OK",
            {
                "players": players,
                "player_count": len(players),
                "warnings": warnings,
                "source": {
                    "provider": "dragonfly-public",
                    "association": association,
                    "school_code": school_code,
                    "sport": sport_code,
                    "source_url": url,
                    "retrieved_at": self._now_iso(),
                },
            },
        )

    def preview_school(
        self,
        school_name: str,
        *,
        association: str = "MHSAA",
        city: str = "",
        state: str = "MS",
        sport: str = "FB",
    ) -> DragonFlyResult:
        resolution = self.resolve_school(
            school_name,
            association=association,
            city=city,
            state=state,
        )
        if not resolution.ok:
            return resolution

        directory_record = resolution.data["school"]
        school_code = str(
            directory_record.get("shortCode", "")
        ).strip()

        summary_result = self.get_school_summary(school_code)
        summary = (
            summary_result.data.get("summary", {})
            if summary_result.ok
            else {}
        )

        roster_result = self.get_roster(
            school_code,
            association=association,
            sport=sport,
        )

        if not roster_result.ok:
            return DragonFlyResult(
                roster_result.code,
                {
                    "school": self.normalize_school_record(
                        directory_record,
                        summary,
                        association=association,
                    ),
                    "resolution": resolution.data,
                    "roster_error": roster_result.data,
                },
            )

        return DragonFlyResult(
            "OK",
            {
                "school": self.normalize_school_record(
                    directory_record,
                    summary,
                    association=association,
                ),
                "players": roster_result.data["players"],
                "player_count": roster_result.data["player_count"],
                "warnings": roster_result.data["warnings"],
                "resolution": resolution.data,
                "source": roster_result.data["source"],
                "database_modified": False,
            },
        )
