from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from dragonfly_service import DragonFlyService
from persistence_engine import DestructiveWriteBlocked
from roster_service import RosterService


Record = dict[str, Any]
RecordLoader = Callable[[], list[Record]]
RecordSaver = Callable[[list[Record]], None]


@dataclass(frozen=True)
class DragonFlySyncResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class DragonFlySyncService:
    """Non-destructive comparison between DragonFly and CSRN data."""

    COMPARE_PLAYER_FIELDS = (
        "number",
        "position",
        "grade",
        "height",
        "weight",
    )

    SCHOOL_COMPARE_FIELDS = (
        "official_name",
        "mascot",
        "classification",
        "region",
        "primary_color",
        "secondary_color",
    )

    def __init__(
        self,
        *,
        dragonfly_service: DragonFlyService,
        load_schools: RecordLoader,
        load_rosters: RecordLoader,
        save_rosters: RecordSaver,
    ) -> None:
        self.dragonfly_service = dragonfly_service
        self._load_schools = load_schools
        self._load_rosters = load_rosters
        self._save_rosters = save_rosters

    @staticmethod
    def _norm(value: Any) -> str:
        return " ".join(str(value or "").strip().casefold().split())

    @staticmethod
    def _player_name(player: Record) -> str:
        return " ".join(
            part
            for part in (
                str(player.get("first_name", "")).strip(),
                str(player.get("last_name", "")).strip(),
            )
            if part
        ).strip()

    @classmethod
    def _player_key(cls, player: Record) -> str:
        name = cls._norm(cls._player_name(player))
        grade = cls._normalize_grade(player.get("grade", ""))
        return f"{name}|{grade}"

    @staticmethod
    def _normalize_grade(value: Any) -> str:
        raw = str(value or "").strip().casefold()

        aliases = {
            "freshman": "9",
            "freshmen": "9",
            "9th": "9",
            "sophomore": "10",
            "10th": "10",
            "junior": "11",
            "11th": "11",
            "senior": "12",
            "12th": "12",
        }

        if raw in aliases:
            return aliases[raw]

        match = re.search(r"\d+", raw)
        return match.group(0) if match else raw

    @staticmethod
    def _find_school(
        schools: list[Record],
        *,
        school_id: str = "",
        school_name: str = "",
    ) -> Record | None:
        if school_id:
            exact = next(
                (
                    school
                    for school in schools
                    if str(school.get("id", "")) == school_id
                ),
                None,
            )
            if exact is not None:
                return exact

        target = DragonFlySyncService._norm(school_name)
        if not target:
            return None

        return next(
            (
                school
                for school in schools
                if target
                in {
                    DragonFlySyncService._norm(
                        school.get("official_name", "")
                    ),
                    DragonFlySyncService._norm(
                        school.get("broadcast_name", "")
                    ),
                    DragonFlySyncService._norm(
                        school.get("short_name", "")
                    ),
                }
            ),
            None,
        )

    @staticmethod
    def _find_roster(
        rosters: list[Record],
        *,
        school_id: str,
        sport: str,
        season: str,
        level: str,
        division: str,
    ) -> Record | None:
        return next(
            (
                roster
                for roster in rosters
                if str(roster.get("school_id", "")) == school_id
                and str(roster.get("sport", "")).casefold()
                == sport.casefold()
                and str(roster.get("season", "")) == season
                and str(roster.get("level", "")).casefold()
                == level.casefold()
                and str(roster.get("division", "")).casefold()
                == division.casefold()
            ),
            None,
        )

    @classmethod
    def _player_changes(
        cls,
        existing: Record,
        incoming: Record,
    ) -> dict[str, Record]:
        changes: dict[str, Record] = {}

        for field_name in cls.COMPARE_PLAYER_FIELDS:
            old_value = existing.get(field_name, "")
            new_value = incoming.get(field_name, "")

            if field_name == "grade":
                old_compare = cls._normalize_grade(old_value)
                new_compare = cls._normalize_grade(new_value)
            else:
                old_compare = cls._norm(old_value)
                new_compare = cls._norm(new_value)

            if old_compare != new_compare:
                changes[field_name] = {
                    "csrn": copy.deepcopy(old_value),
                    "dragonfly": copy.deepcopy(new_value),
                }

        return changes

    @classmethod
    def _school_changes(
        cls,
        existing: Record,
        incoming: Record,
    ) -> dict[str, Record]:
        changes: dict[str, Record] = {}

        for field_name in cls.SCHOOL_COMPARE_FIELDS:
            old_value = existing.get(field_name, "")
            new_value = incoming.get(field_name, "")

            if cls._norm(old_value) != cls._norm(new_value):
                changes[field_name] = {
                    "csrn": copy.deepcopy(old_value),
                    "dragonfly": copy.deepcopy(new_value),
                    "action": "review_only",
                }

        return changes

    @staticmethod
    def _build_import_player(
        incoming: Record,
        existing_ids: set[str],
    ) -> Record:
        first_name = str(incoming.get("first_name", "")).strip()
        last_name = str(incoming.get("last_name", "")).strip()
        number = str(incoming.get("number", "")).strip()

        base_id = RosterService.normalize_player_id(
            f"{number}-{first_name}-{last_name}"
        )
        player_id = base_id
        suffix = 2

        while player_id in existing_ids:
            player_id = f"{base_id}-{suffix}"
            suffix += 1

        existing_ids.add(player_id)

        return {
            "id": player_id,
            "number": number,
            "first_name": first_name,
            "last_name": last_name,
            "preferred_name": str(
                incoming.get("preferred_name", "")
            ).strip(),
            "position": str(
                incoming.get("position", "")
            ).strip(),
            "secondary_position": str(
                incoming.get("secondary_position", "")
            ).strip(),
            "grade": str(incoming.get("grade", "")).strip(),
            "height": str(incoming.get("height", "")).strip(),
            "weight": str(incoming.get("weight", "")).strip(),
            "captain": bool(incoming.get("captain", False)),
            "starter": bool(incoming.get("starter", False)),
            "status": (
                "inactive"
                if str(
                    incoming.get("status", "active")
                ).casefold() == "inactive"
                else "active"
            ),
            "pronunciation": str(
                incoming.get("pronunciation", "")
            ).strip(),
            "pronunciation_verified": bool(
                incoming.get("pronunciation_verified", False)
            ),
            "headshot": str(
                incoming.get("headshot", "")
            ).strip(),
            "source_data": copy.deepcopy(
                incoming.get("source_data", {})
            ),
            "source_levels": copy.deepcopy(
                incoming.get("source_levels", [])
            ),
            "import_warnings": copy.deepcopy(
                incoming.get("import_warnings", [])
            ),
        }

    def replace_roster(
        self,
        school_name: str,
        *,
        approved: bool = False,
        school_id: str = "",
        association: str = "MHSAA",
        city: str = "",
        state: str = "MS",
        sport: str = "FB",
        csrn_sport: str = "Football",
        season: str = "2026",
        level: str = "Varsity",
        division: str = "Boys",
    ) -> DragonFlySyncResult:
        if not approved:
            return DragonFlySyncResult(
                "DRAGONFLY_SYNC_APPROVAL_REQUIRED",
                {"database_modified": False},
            )

        preview_result = self.preview(
            school_name,
            school_id=school_id,
            association=association,
            city=city,
            state=state,
            sport=sport,
            csrn_sport=csrn_sport,
            season=season,
            level=level,
            division=division,
        )

        if not preview_result.ok:
            return preview_result

        if preview_result.data["roster"].get("ambiguous"):
            return DragonFlySyncResult(
                "DRAGONFLY_SYNC_AMBIGUOUS_PLAYERS",
                {
                    "preview": preview_result.data,
                    "database_modified": False,
                },
            )

        target_roster_id = str(
            preview_result.data["roster"].get(
                "existing_roster_id",
                "",
            )
        ).strip()

        if not target_roster_id:
            return DragonFlySyncResult(
                "CSRN_ROSTER_NOT_FOUND",
                {
                    "preview": preview_result.data,
                    "database_modified": False,
                },
            )

        rosters = self._load_rosters()
        target = next(
            (
                roster
                for roster in rosters
                if str(roster.get("id", ""))
                == target_roster_id
            ),
            None,
        )

        if target is None:
            return DragonFlySyncResult(
                "CSRN_ROSTER_NOT_FOUND",
                {
                    "preview": preview_result.data,
                    "database_modified": False,
                },
            )

        incoming_players = (
            preview_result.data["roster"]["added"]
            + preview_result.data["roster"]["changed"]
            + preview_result.data["roster"]["matched"]
        )

        # The preview groups have different shapes. Pull each incoming record.
        source_players: list[Record] = []

        for item in preview_result.data["roster"]["added"]:
            source_players.append(
                copy.deepcopy(item["player"])
            )

        for item in preview_result.data["roster"]["changed"]:
            source_players.append(
                copy.deepcopy(item["incoming"])
            )

        for item in preview_result.data["roster"]["matched"]:
            source_players.append(
                copy.deepcopy(item["incoming"])
            )

        if not source_players:
            return DragonFlySyncResult(
                "DRAGONFLY_ROSTER_EMPTY",
                {
                    "preview": preview_result.data,
                    "database_modified": False,
                },
            )

        player_ids: set[str] = set()
        new_players = [
            self._build_import_player(player, player_ids)
            for player in source_players
        ]

        previous_count = len(
            target.get("players", [])
            if isinstance(target.get("players"), list)
            else []
        )

        target["players"] = new_players

        # Intentionally do not modify school identity/branding metadata.
        # roster_repository.py's guard now blocks an empty replacement (this
        # method already self-guards that case above) or a >=75% player-
        # count drop -- a real possibility here since this replaces the
        # whole roster with a fresh scrape. Surface it as a normal result
        # code instead of letting DestructiveWriteBlocked crash the request.
        new_count = len(new_players)
        try:
            self._save_rosters(rosters)
        except DestructiveWriteBlocked as exc:
            return DragonFlySyncResult(
                "DRAGONFLY_ROSTER_DROP_BLOCKED",
                {
                    "preview": preview_result.data,
                    "database_modified": False,
                    "previous_player_count": previous_count,
                    "player_count": new_count,
                    "message": str(exc),
                },
            )

        return DragonFlySyncResult(
            "OK",
            {
                "roster_id": target_roster_id,
                "previous_player_count": previous_count,
                "player_count": len(new_players),
                "school_metadata_modified": False,
                "database_modified": True,
                "source_warnings": copy.deepcopy(
                    preview_result.data.get(
                        "source_warnings",
                        [],
                    )
                ),
                "school_differences": copy.deepcopy(
                    preview_result.data["school"].get(
                        "differences",
                        {},
                    )
                ),
            },
        )

    def preview_school_info(
        self,
        school_name: str,
        *,
        school_id: str = "",
        association: str = "MHSAA",
        city: str = "",
        state: str = "MS",
    ) -> DragonFlySyncResult:
        source = self.dragonfly_service.preview_school(
            school_name,
            association=association,
            city=city,
            state=state,
            sport="FB",
        )

        if not source.ok:
            return DragonFlySyncResult(
                source.code,
                copy.deepcopy(source.data),
            )

        schools = self._load_schools()
        existing = self._find_school(
            schools,
            school_id=school_id,
            school_name=school_name,
        )

        if existing is None:
            return DragonFlySyncResult(
                "CSRN_SCHOOL_NOT_FOUND",
                {
                    "dragonfly": copy.deepcopy(
                        source.data.get("school", {})
                    ),
                    "database_modified": False,
                },
            )

        incoming = copy.deepcopy(
            source.data.get("school", {})
        )

        protected_review_only = {
            "classification",
            "region",
            "district",
        }

        branding_review_only = {
            "primary_color",
            "secondary_color",
            "primary_logo",
        }

        safe_fill_fields = {
            "mascot",
            "nickname",
            "city",
            "state",
        }

        differences: dict[str, Record] = {}
        safe_updates: dict[str, Any] = {}
        review_candidates: dict[str, Record] = {}

        for field_name in (
            "official_name",
            "mascot",
            "nickname",
            "city",
            "state",
            "classification",
            "region",
            "district",
            "primary_color",
            "secondary_color",
            "primary_logo",
        ):
            old_value = existing.get(field_name, "")
            new_value = incoming.get(field_name, "")

            if self._norm(old_value) == self._norm(new_value):
                continue

            differences[field_name] = {
                "csrn": copy.deepcopy(old_value),
                "dragonfly": copy.deepcopy(new_value),
            }

            if field_name in protected_review_only:
                review_candidates[field_name] = {
                    "csrn": copy.deepcopy(old_value),
                    "dragonfly": copy.deepcopy(new_value),
                    "reason": "PROTECTED_COMPETITION_FIELD",
                }
                continue

            if field_name in branding_review_only:
                review_candidates[field_name] = {
                    "csrn": copy.deepcopy(old_value),
                    "dragonfly": copy.deepcopy(new_value),
                    "reason": "PROTECTED_BRANDING_FIELD",
                }
                continue

            if field_name in safe_fill_fields:
                if not str(old_value or "").strip() and str(
                    new_value or ""
                ).strip():
                    safe_updates[field_name] = copy.deepcopy(
                        new_value
                    )
                else:
                    review_candidates[field_name] = {
                        "csrn": copy.deepcopy(old_value),
                        "dragonfly": copy.deepcopy(new_value),
                        "reason": "EXISTING_VALUE_PRESENT",
                    }

        incoming_address = incoming.get("school_address")
        existing_address = existing.get("school_address")

        incoming_address = (
            incoming_address
            if isinstance(incoming_address, dict)
            else {}
        )
        existing_address = (
            existing_address
            if isinstance(existing_address, dict)
            else {}
        )

        address_update = copy.deepcopy(existing_address)
        address_changed = False

        for key in (
            "address1",
            "address2",
            "city",
            "state",
            "postal_code",
        ):
            old_value = existing_address.get(key, "")
            new_value = incoming_address.get(key, "")

            if (
                not str(old_value or "").strip()
                and str(new_value or "").strip()
            ):
                address_update[key] = copy.deepcopy(new_value)
                address_changed = True

        if address_changed:
            safe_updates["school_address"] = address_update

        existing_source = copy.deepcopy(
            existing.get("source_data") or {}
        )
        incoming_source = copy.deepcopy(
            incoming.get("source_data") or {}
        )

        merged_source = copy.deepcopy(existing_source)
        merged_source.update(
            {
                "dragonfly_provider": "dragonfly-public",
                "dragonfly_association": incoming_source.get(
                    "association",
                    association,
                ),
                "dragonfly_org_id": incoming_source.get(
                    "dragonfly_org_id",
                    "",
                ),
                "dragonfly_school_code": incoming_source.get(
                    "dragonfly_school_code",
                    "",
                ),
                "dragonfly_source_url": incoming_source.get(
                    "source_url",
                    "",
                ),
                "dragonfly_retrieved_at": incoming_source.get(
                    "retrieved_at",
                    "",
                ),
            }
        )
        safe_updates["source_data"] = merged_source

        return DragonFlySyncResult(
            "OK",
            {
                "school_id": existing.get("id", ""),
                "school_name": (
                    existing.get("broadcast_name")
                    or existing.get("official_name")
                    or school_name
                ),
                "safe_updates": safe_updates,
                "review_candidates": review_candidates,
                "differences": differences,
                "dragonfly": incoming,
                "database_modified": False,
            },
        )

    def apply_safe_school_info(
        self,
        school_name: str,
        *,
        approved: bool = False,
        school_id: str = "",
        association: str = "MHSAA",
        city: str = "",
        state: str = "MS",
        school_service: Any = None,
    ) -> DragonFlySyncResult:
        if not approved:
            return DragonFlySyncResult(
                "DRAGONFLY_SYNC_APPROVAL_REQUIRED",
                {"database_modified": False},
            )

        if school_service is None:
            return DragonFlySyncResult(
                "SCHOOL_SERVICE_REQUIRED",
                {"database_modified": False},
            )

        preview = self.preview_school_info(
            school_name,
            school_id=school_id,
            association=association,
            city=city,
            state=state,
        )

        if not preview.ok:
            return preview

        target_school_id = str(
            preview.data.get("school_id", "")
        ).strip()

        updates = copy.deepcopy(
            preview.data.get("safe_updates", {})
        )

        if not updates:
            return DragonFlySyncResult(
                "OK",
                {
                    "school_id": target_school_id,
                    "updated_fields": [],
                    "review_candidates": copy.deepcopy(
                        preview.data.get(
                            "review_candidates",
                            {},
                        )
                    ),
                    "database_modified": False,
                },
            )

        result = school_service.update(
            target_school_id,
            updates,
        )

        if not result.ok:
            return DragonFlySyncResult(
                result.code,
                {"database_modified": False},
            )

        return DragonFlySyncResult(
            "OK",
            {
                "school_id": target_school_id,
                "updated_fields": sorted(updates.keys()),
                "review_candidates": copy.deepcopy(
                    preview.data.get(
                        "review_candidates",
                        {},
                    )
                ),
                "school": copy.deepcopy(
                    result.data.get("school", {})
                ),
                "database_modified": True,
            },
        )

    def preview(
        self,
        school_name: str,
        *,
        school_id: str = "",
        association: str = "MHSAA",
        city: str = "",
        state: str = "MS",
        sport: str = "FB",
        csrn_sport: str = "Football",
        season: str = "2026",
        level: str = "Varsity",
        division: str = "Boys",
    ) -> DragonFlySyncResult:
        source = self.dragonfly_service.preview_school(
            school_name,
            association=association,
            city=city,
            state=state,
            sport=sport,
        )

        if not source.ok:
            return DragonFlySyncResult(
                source.code,
                copy.deepcopy(source.data),
            )

        schools = self._load_schools()

        existing_school = self._find_school(
            schools,
            school_id=school_id,
            school_name=school_name,
        )

        if existing_school is None:
            return DragonFlySyncResult(
                "CSRN_SCHOOL_NOT_FOUND",
                {
                    "dragonfly": copy.deepcopy(source.data),
                    "database_modified": False,
                },
            )

        rosters = self._load_rosters()

        existing_roster = self._find_roster(
            rosters,
            school_id=str(existing_school.get("id", "")),
            sport=csrn_sport,
            season=season,
            level=level,
            division=division,
        )

        incoming_players = copy.deepcopy(
            source.data.get("players", [])
        )

        existing_players = (
            copy.deepcopy(existing_roster.get("players", []))
            if existing_roster is not None
            else []
        )

        existing_by_key: dict[str, list[Record]] = {}

        for player in existing_players:
            key = self._player_key(player)
            existing_by_key.setdefault(key, []).append(player)

        incoming_keys: set[str] = set()

        added: list[Record] = []
        matched: list[Record] = []
        changed: list[Record] = []
        ambiguous: list[Record] = []

        for incoming in incoming_players:
            key = self._player_key(incoming)
            incoming_keys.add(key)

            matches = existing_by_key.get(key, [])

            if not matches:
                added.append(
                    {
                        "player": incoming,
                        "reason": "NO_EXISTING_MATCH",
                    }
                )
                continue

            if len(matches) > 1:
                ambiguous.append(
                    {
                        "incoming": incoming,
                        "existing_matches": matches,
                        "reason": "MULTIPLE_EXISTING_MATCHES",
                    }
                )
                continue

            existing = matches[0]
            field_changes = self._player_changes(
                existing,
                incoming,
            )

            if field_changes:
                changed.append(
                    {
                        "existing": existing,
                        "incoming": incoming,
                        "changes": field_changes,
                    }
                )
            else:
                matched.append(
                    {
                        "existing": existing,
                        "incoming": incoming,
                    }
                )

        source_missing: list[Record] = []

        for existing in existing_players:
            key = self._player_key(existing)

            if key not in incoming_keys:
                source_missing.append(
                    {
                        "player": existing,
                        "action": "review_only",
                        "reason": "NOT_PRESENT_IN_DRAGONFLY",
                    }
                )

        school_changes = self._school_changes(
            existing_school,
            source.data.get("school", {}),
        )

        return DragonFlySyncResult(
            "OK",
            {
                "school": {
                    "csrn": copy.deepcopy(existing_school),
                    "dragonfly": copy.deepcopy(
                        source.data.get("school", {})
                    ),
                    "differences": school_changes,
                    "automatic_updates": False,
                },
                "roster": {
                    "existing_roster_id": (
                        existing_roster.get("id", "")
                        if existing_roster
                        else ""
                    ),
                    "existing_player_count": len(existing_players),
                    "dragonfly_player_count": len(incoming_players),
                    "added": added,
                    "matched": matched,
                    "changed": changed,
                    "ambiguous": ambiguous,
                    "source_missing": source_missing,
                    "summary": {
                        "added": len(added),
                        "matched": len(matched),
                        "changed": len(changed),
                        "ambiguous": len(ambiguous),
                        "source_missing": len(source_missing),
                    },
                },
                "source_warnings": copy.deepcopy(
                    source.data.get("warnings", [])
                ),
                "database_modified": False,
            },
        )
