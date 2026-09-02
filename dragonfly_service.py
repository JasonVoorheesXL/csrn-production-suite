from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx


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

    SPORT_CODES = {
        "football": "FB",
        "fb": "FB",
        "basketball": "BB",
        "baseball": "BA",
        "softball": "SB",
        "soccer": "SC",
        "volleyball": "VB",
    }

    # DragonFly's public JSON API tags each team with an `ncaaSportCode`
    # (e.g. "MFB" for football). Map CSRN's short sport code onto the
    # DragonFly code(s) that count as the same sport for roster import.
    NCAA_SPORT_CODES = {
        "FB": {"MFB"},
        "BB": {"MBB", "WBB"},
        "BA": {"MBA"},
        "SB": {"WSB"},
        "SC": {"MSO", "WSO"},
        "VB": {"MVB", "WVB"},
    }

    # Team levels CSRN pulls into a high-school program roster (Varsity + JV;
    # Junior High / 7th-8th grade / Freshman are excluded by default).
    ROSTER_LEVELS = {"varsity", "jv", "junior varsity"}

    # --- resolve_school() level classification + scoring (Round 24) ---------
    # DragonFly's state directory lists ~1150 records per association, most of
    # them elementary / middle / vocational / district entities that never
    # field a varsity team. A bare town-name search ("Caledonia", "Amory")
    # used to tie every "<Town> * School" record and return whichever paged
    # first. These weights make the varsity high school win.
    _LEVEL_OTHER_TOKENS = (
        "elementary", "intermediate school", "primary school",
        "career technical", "technical center", "vocational", "voc comp",
        "voc tech", "voc school", "alternative", "learning center",
        "school district", "head start", "early childhood", "pre-k",
        "prekindergarten", "kindergarten",
    )
    _JUNIOR_HIGH_TOKENS = ("junior high", "jr high", "jr. high")
    _LEVEL_HS_TOKENS = ("high school", "high and middle", "senior high")

    _LEVEL_SCORES = {"hs": 400, "secondary": 120, "other": 0}
    _JUNIOR_HIGH_PENALTY = 150
    _EXACT_NAME_BONUS = 200
    _SUBSTRING_BONUS = 50
    _MHSAA_CLASS_BONUS = 80
    # An exact city match is a strong cross-town disambiguator (two towns can
    # both have a "<Name> Attendance Center"), so it alone clears the margin.
    # It applies equally to same-town siblings, so it never distorts the
    # level ranking within one town.
    _CITY_EXACT_BONUS = 160
    _CITY_PARTIAL_BONUS = 40
    _STATE_BONUS = 10
    # A leader must beat the runner-up by at least this to be "confident";
    # otherwise the sport/level check (task B) breaks the tie.
    _CONFIDENCE_MARGIN = 150

    @staticmethod
    def _mhsaa_class(competition_levels: Any) -> str:
        if not isinstance(competition_levels, dict):
            return ""
        value = str(competition_levels.get("mhsaaClass") or "").strip().lower()
        return "" if value in {"", "undefined", "none", "n/a"} else value

    @classmethod
    def _classify_level(
        cls, name: Any, competition_levels: Any = None
    ) -> str:
        """Rough school-level from the directory record: "hs" (varsity high
        school), "secondary" (junior high / middle / attendance center /
        academy / classified-but-unnamed), or "other" (elementary / vo-tech /
        district / etc.)."""
        text = cls._normalize_text(name)
        if any(token in text for token in cls._LEVEL_OTHER_TOKENS):
            return "other"
        if any(token in text for token in cls._JUNIOR_HIGH_TOKENS):
            return "secondary"
        if any(token in text for token in cls._LEVEL_HS_TOKENS):
            return "hs"
        if "middle school" in text:
            return "secondary"
        if cls._mhsaa_class(competition_levels):
            return "secondary"
        if "attendance center" in text or "academy" in text:
            return "secondary"
        return "other"

    @classmethod
    def _sport_fielding_tier(cls, summary: Any, sport_code: str) -> int:
        """How strongly a school's /schools/<code>/summary says it fields the
        requested sport: 4 = Varsity team with athletes, 3 = Varsity team,
        2 = the sport at any level, 1 = has an MHSAA classification, 0 = no
        signal. Used only to break a near-tie (task B)."""
        if not isinstance(summary, dict):
            return 0
        accepted = cls.NCAA_SPORT_CODES.get(sport_code, set()) | {sport_code}
        teams = summary.get("teams")
        teams = teams if isinstance(teams, list) else []
        any_level = varsity = varsity_with_athletes = False
        for team in teams:
            if not isinstance(team, dict):
                continue
            if str(team.get("ncaaSportCode", "")).strip().upper() not in accepted:
                continue
            any_level = True
            if str(team.get("level", "")).strip().casefold() == "varsity":
                varsity = True
                try:
                    if int(team.get("totalAthleteCount") or 0) > 0:
                        varsity_with_athletes = True
                except (TypeError, ValueError):
                    pass
        if varsity_with_athletes:
            return 4
        if varsity:
            return 3
        if any_level:
            return 2
        if cls._mhsaa_class(summary.get("competitionLevels")):
            return 1
        return 0

    def _cached_summary(
        self, short_code: Any, cache: dict[str, Any], client: httpx.Client
    ) -> Any:
        """Best-effort GET /schools/<code>/summary, memoised per resolve_school
        call. Never raises -- a failed lookup just yields no sport signal."""
        code = self._clean_code(short_code)
        if not code:
            return None
        if code not in cache:
            try:
                response = client.get(f"{self.API_BASE}/schools/{code}/summary")
                response.raise_for_status()
                payload = response.json()
                cache[code] = payload if isinstance(payload, dict) else None
            except Exception:
                cache[code] = None
        return cache[code]

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
    def _format_height(height: Any) -> str:
        """DragonFly gives height as ``{"feet": 6, "inches": 0}``; CSRN wants
        the ``6' 0"`` string the roster importer already parses. Empty/partial
        data -> "" (downstream raises MISSING_HEIGHT, same as before)."""
        if not isinstance(height, dict):
            return ""
        feet = height.get("feet")
        inches = height.get("inches")
        try:
            feet_int = int(feet)
        except (TypeError, ValueError):
            return ""
        try:
            inches_int = int(inches)
        except (TypeError, ValueError):
            inches_int = 0
        return f"{feet_int}' {inches_int}\""

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
        sport: str = "",
    ) -> DragonFlyResult:
        association = self._clean_code(association).upper()
        target_name = self._normalize_text(school_name)
        target_city = self._normalize_text(city)
        target_state = str(state or "").strip().upper()
        sport_code = self.normalize_sport(sport) if str(sport or "").strip() else ""

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

                        competition = record.get("competitionLevels")
                        level = self._classify_level(
                            record.get("name"), competition
                        )

                        score = self._LEVEL_SCORES.get(level, 0)

                        if name_exact:
                            score += self._EXACT_NAME_BONUS
                        elif name_contains:
                            score += self._SUBSTRING_BONUS

                        if self._mhsaa_class(competition):
                            score += self._MHSAA_CLASS_BONUS

                        if target_city:
                            if record_city == target_city:
                                score += self._CITY_EXACT_BONUS
                            elif (
                                target_city in record_city
                                or record_city in target_city
                            ):
                                score += self._CITY_PARTIAL_BONUS

                        if target_state and record_state == target_state:
                            score += self._STATE_BONUS

                        if any(
                            token in record_name
                            for token in self._JUNIOR_HIGH_TOKENS
                        ):
                            score -= self._JUNIOR_HIGH_PENALTY

                        candidate = copy.deepcopy(record)
                        candidate["_match_score"] = score
                        candidate["_level"] = level
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
                    key=lambda item: int(item.get("_match_score", 0)),
                    reverse=True,
                )

                # --- Task B: break a near-tie by which candidate actually
                #     fields the requested sport (Varsity, then any level,
                #     then MHSAA classification, then the name-based level).
                sport_checked = False
                if sport_code and len(candidates) > 1:
                    top_score = int(candidates[0].get("_match_score", 0))
                    near_top = [
                        candidate
                        for candidate in candidates
                        if top_score - int(candidate.get("_match_score", 0))
                        <= self._CONFIDENCE_MARGIN
                    ]
                    if len(near_top) > 1:
                        sport_checked = True
                        summary_cache: dict[str, Any] = {}
                        for candidate in near_top:
                            candidate["_sport_tier"] = self._sport_fielding_tier(
                                self._cached_summary(
                                    candidate.get("shortCode", ""),
                                    summary_cache,
                                    client,
                                ),
                                sport_code,
                            )
                        near_top.sort(
                            key=lambda c: (
                                int(c.get("_sport_tier", 0)),
                                int(c.get("_match_score", 0)),
                            ),
                            reverse=True,
                        )
                        near_ids = {id(c) for c in near_top}
                        candidates = near_top + [
                            candidate
                            for candidate in candidates
                            if id(candidate) not in near_ids
                        ]

                if len(candidates) == 1:
                    resolved_confidently = True
                elif sport_checked and int(
                    candidates[0].get("_sport_tier", 0)
                ) > int(candidates[1].get("_sport_tier", 0)):
                    resolved_confidently = True
                else:
                    resolved_confidently = (
                        int(candidates[0].get("_match_score", 0))
                        - int(candidates[1].get("_match_score", 0))
                        >= self._CONFIDENCE_MARGIN
                    )

                def _bare(item: Record) -> Record:
                    return {
                        key: value
                        for key, value in item.items()
                        if not key.startswith("_")
                    }

                def _public(item: Record) -> Record:
                    out = _bare(item)
                    out["dragonfly_level"] = item.get("_level", "")
                    out["match_score"] = int(item.get("_match_score", 0))
                    if "_sport_tier" in item:
                        out["fields_requested_sport"] = int(item["_sport_tier"])
                    return out

                return DragonFlyResult(
                    "OK",
                    {
                        "school": _bare(candidates[0]),
                        "matches": [_public(item) for item in candidates[:10]],
                        "association": association,
                        "requested_sport": sport_code,
                        "resolved_confidently": resolved_confidently,
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

        # Public site URL (kept for source attribution / operator reference).
        url = (
            f"{self.SITE_BASE}/sites/{association}/"
            f"{school_code}/roster?sport={sport_code}"
        )
        # The rosters are read from DragonFly's public JSON API, not scraped
        # off the Angular site (which stopped rendering an HTML <table> in
        # 2026 -- the old Playwright scrape now returns an empty roster for
        # every school). `schools/<code>/summary` already carries every
        # team's full roster with height / weight / grade / number / position.
        summary_url = f"{self.API_BASE}/schools/{school_code}/summary"
        accepted_codes = self.NCAA_SPORT_CODES.get(sport_code, set()) | {
            sport_code
        }
        sport_word = ""
        for word, code in self.SPORT_CODES.items():
            if code == sport_code and not word.isupper():
                sport_word = word
                break

        try:
            with self._client() as client:
                response = client.get(summary_url)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return DragonFlyResult(
                "DRAGONFLY_ROSTER_FETCH_FAILED",
                {"source_url": summary_url, "detail": str(exc)},
            )

        if not isinstance(payload, dict):
            return DragonFlyResult(
                "DRAGONFLY_ROSTER_FETCH_FAILED",
                {"source_url": summary_url, "detail": "summary payload not an object"},
            )

        teams = payload.get("teams")
        teams = teams if isinstance(teams, list) else []

        raw_entries: list[dict[str, Any]] = []
        available_levels: list[str] = []

        for team in teams:
            if not isinstance(team, dict):
                continue

            team_code = str(team.get("ncaaSportCode", "")).strip().upper()
            team_name = str(team.get("name", "")).strip()
            level = str(team.get("level", "")).strip()

            is_sport = (
                team_code in accepted_codes
                or (bool(sport_word) and sport_word in team_name.casefold())
            )
            if not is_sport:
                continue

            source_level = " ".join(part for part in (level, team_name) if part)
            if source_level:
                available_levels.append(source_level)

            # CSRN high-school program roster: Varsity + JV only.
            if level.casefold() not in self.ROSTER_LEVELS:
                continue

            roster = team.get("roster")
            roster = roster if isinstance(roster, list) else []

            for member in roster:
                if not isinstance(member, dict):
                    continue

                info = member.get("rosterInfo")
                info = info if isinstance(info, dict) else {}

                name = " ".join(
                    part
                    for part in (
                        str(member.get("firstName", "")).strip(),
                        str(member.get("lastName", "")).strip(),
                    )
                    if part
                )

                raw_entries.append(
                    {
                        "level": source_level,
                        "values": [
                            name,
                            str(info.get("number", "")).strip(),
                            str(info.get("position", "")).strip(),
                            self._format_height(info.get("height")),
                            str(info.get("weight", "")).strip(),
                            str(info.get("grade", "")).strip(),
                        ],
                    }
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
            sport=sport,
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
