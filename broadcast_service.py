from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


Broadcast = dict[str, Any]
School = dict[str, Any]
State = dict[str, Any]
BroadcastLoader = Callable[[], list[Broadcast]]
BroadcastSaver = Callable[[list[Broadcast]], None]
SchoolLookup = Callable[[str], School | None]
VenueResolver = Callable[[School | None, str], dict[str, Any] | None]
IdentityBuilder = Callable[[School | None, str], dict[str, Any]]
LogoCertification = Callable[[School], Any]
MonogramBuilder = Callable[[str], str]
ConfigLoader = Callable[[], dict[str, Any]]
StateLoader = Callable[[], State]
StateSaver = Callable[[State], None]
DefaultStateFactory = Callable[[], State]
DetailWriter = Callable[[Broadcast, bool], None]
DetailDeleter = Callable[[str], None]
Clock = Callable[[], float]
YearProvider = Callable[[], str]


@dataclass(frozen=True)
class BroadcastResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class BroadcastService:
    """Broadcast planning and lifecycle behavior independent of Flask."""

    _CREW_KEYS = (
        "play_by_play",
        "color_analyst",
        "sideline_reporter",
        "statistician",
        "producer",
    )
    _EDITABLE_KEYS = (
        "sport",
        "season",
        "classification",
        "week",
        "level",
        "division",
        "date",
        "scheduled_start",
        "venue",
        "venue_id",
        "visual_mode",
        "crew",
        "contest_type",
        "record_policy",
        "region_game",
        "special_designations",
        "home_classification",
        "home_region",
        "visitor_classification",
        "visitor_region",
        "home_pregame_record",
        "home_pregame_region_record",
        "visitor_pregame_record",
        "visitor_pregame_region_record",
        "record_tracking",
    )
    _STATE_SYNC_KEYS = _EDITABLE_KEYS + (
        "home_school_id",
        "visitor_school_id",
        "home_team",
        "visitor_team",
        "home_identity",
        "visitor_identity",
    )
    _VALID_STATUSES = {"planned", "live", "completed"}
    _VALID_CONTEST_TYPES = {"official", "scrimmage", "exhibition"}
    _VALID_SPECIAL_DESIGNATIONS = {
        "homecoming",
        "senior_night",
        "rivalry",
        "playoff",
        "championship",
    }

    def __init__(
        self,
        *,
        load_broadcasts: BroadcastLoader,
        save_broadcasts: BroadcastSaver,
        get_school: SchoolLookup,
        resolve_venue: VenueResolver,
        build_identity: IdentityBuilder,
        logo_certification: LogoCertification,
        school_monogram: MonogramBuilder,
        load_config: ConfigLoader,
        load_state: StateLoader,
        save_state: StateSaver,
        default_state: DefaultStateFactory,
        write_detail: DetailWriter | None = None,
        delete_detail: DetailDeleter | None = None,
        clock: Clock | None = None,
        year_provider: YearProvider | None = None,
    ) -> None:
        self._load_broadcasts = load_broadcasts
        self._save_broadcasts = save_broadcasts
        self._get_school = get_school
        self._resolve_venue = resolve_venue
        self._build_identity = build_identity
        self._logo_certification = logo_certification
        self._school_monogram = school_monogram
        self._load_config = load_config
        self._load_state = load_state
        self._save_state = save_state
        self._default_state = default_state
        self._write_detail = write_detail or (lambda _record, _existing_only: None)
        self._delete_detail = delete_detail or (lambda _broadcast_id: None)
        self._clock = clock or time.time
        self._year_provider = year_provider or (lambda: time.strftime("%Y"))

    @staticmethod
    def football_week_code(value: Any) -> str:
        text = str(value or "1").strip().upper().replace("WEEK", "").strip()
        try:
            return f"W{int(text):02d}"
        except ValueError:
            cleaned = "".join(character for character in text if character.isalnum())
            return f"W{(cleaned[:3] or '01')}"

    def next_id(
        self,
        sport: str,
        season: str,
        classification: str,
        week: Any,
    ) -> str:
        sport_text = str(sport or "")
        sport_code = {
            "football": "FB",
            "basketball": "BB",
            "baseball": "BSB",
            "softball": "SB",
        }.get(sport_text.lower(), sport_text[:3].upper() or "EVT")
        season_code = "".join(
            character for character in str(season or "") if character.isdigit()
        )[:4] or self._year_provider()
        class_code = (
            str(classification or "OPEN")
            .upper()
            .replace("CLASS", "")
            .replace(" ", "")
        )
        prefix = (
            f"{sport_code}-{season_code}-{class_code}-"
            f"{self.football_week_code(week)}-"
        )
        used: list[int] = []
        for item in self._load_broadcasts():
            value = str(item.get("broadcast_id", ""))
            if not value.startswith(prefix):
                continue
            try:
                used.append(int(value.rsplit("-", 1)[1]))
            except (ValueError, IndexError):
                continue
        return f"{prefix}{max(used, default=0) + 1:03d}"

    def list_records(self, *, include_archived: bool = False) -> BroadcastResult:
        rows = [
            copy.deepcopy(item)
            for item in self._load_broadcasts()
            if include_archived or not item.get("archived")
        ]
        rows.sort(
            key=lambda item: (
                str(item.get("date", "")),
                str(item.get("scheduled_start", "")),
            ),
            reverse=True,
        )
        return BroadcastResult("OK", {"broadcasts": rows})

    def read(self, broadcast_id: str) -> BroadcastResult:
        item = self._find(self._load_broadcasts(), broadcast_id)
        if item is None:
            return BroadcastResult("NOT_FOUND")
        return BroadcastResult("OK", {"broadcast": copy.deepcopy(item)})

    def create(self, incoming: Broadcast) -> BroadcastResult:
        data = copy.deepcopy(incoming or {})
        config = self._load_config()
        defaults = config.get("broadcast_defaults", {})
        if not isinstance(defaults, dict):
            defaults = {}

        sport = str(data.get("sport", defaults.get("sport", "Football")) or "Football")
        home_school_id = str(data.get("home_school_id", "")).strip()
        visitor_school_id = str(data.get("visitor_school_id", "")).strip()
        home_school = self._get_school(home_school_id) if home_school_id else None
        visitor_school = self._get_school(visitor_school_id) if visitor_school_id else None

        home_name = (
            str((home_school or {}).get("broadcast_name", "")).strip()
            if home_school
            else str(data.get("home_team", "")).strip()
        ) or "Home"
        visitor_name = (
            str((visitor_school or {}).get("broadcast_name", "")).strip()
            if visitor_school
            else str(data.get("visitor_team", "")).strip()
        ) or "Visitor"
        classification = str(
            data.get("classification")
            or (home_school or {}).get("classification")
            or (visitor_school or {}).get("classification")
            or "Open"
        ).strip()
        season = str(data.get("season") or self._year_provider()).strip()
        week = str(data.get("week") or "1").strip()
        venue = self._resolve_venue(home_school, sport)
        venue_name = str(
            data.get("venue")
            or (venue or {}).get("name")
            or defaults.get("venue", "Caledonia High School")
        ).strip()
        venue_id = str((venue or {}).get("id", ""))
        broadcast_id = self.next_id(sport, season, classification, week)
        now = int(self._clock())
        crew_incoming = data.get("crew", {})
        if not isinstance(crew_incoming, dict):
            crew_incoming = {}
        crew = {
            key: str(crew_incoming.get(key, ""))
            for key in self._CREW_KEYS
        }
        visual_mode = data.get(
            "visual_mode",
            defaults.get("visual_mode", "graphic"),
        )
        home_identity = self._build_identity(home_school, sport)
        visitor_identity = self._build_identity(visitor_school, sport)
        contest_type = self._contest_type(data.get("contest_type"))
        region_game = (
            bool(data.get("region_game", False))
            if contest_type == "official"
            else False
        )
        primary_school_id = str(defaults.get("home_school_id", "") or "").strip()
        primary_side = self._primary_side(
            primary_school_id,
            home_school_id,
            visitor_school_id,
        )
        latest_primary = self._latest_primary_records(
            primary_school_id,
            sport,
            season,
        )
        home_pregame = self.normalize_record(data.get("home_pregame_record"))
        home_region_pregame = self.normalize_record(
            data.get("home_pregame_region_record")
        )
        visitor_pregame = self.normalize_record(
            data.get("visitor_pregame_record")
        )
        visitor_region_pregame = self.normalize_record(
            data.get("visitor_pregame_region_record")
        )
        if primary_side == "home" and latest_primary:
            home_pregame = copy.deepcopy(latest_primary["overall"])
            home_region_pregame = copy.deepcopy(latest_primary["region"])
        elif primary_side == "visitor" and latest_primary:
            visitor_pregame = copy.deepcopy(latest_primary["overall"])
            visitor_region_pregame = copy.deepcopy(latest_primary["region"])

        record: Broadcast = {
            "broadcast_id": broadcast_id,
            "created_at": now,
            "updated_at": now,
            "status": "planned",
            "sport": sport,
            "season": season,
            "classification": classification,
            "week": week,
            "level": data.get("level", "Varsity"),
            "division": data.get("division", "Boys"),
            "date": data.get("date", ""),
            "scheduled_start": data.get("scheduled_start", "07:00 PM"),
            "home_school_id": home_school_id,
            "visitor_school_id": visitor_school_id,
            "home_team": home_name,
            "visitor_team": visitor_name,
            "home_identity": home_identity,
            "visitor_identity": visitor_identity,
            "venue_id": venue_id,
            "venue": venue_name,
            "graphics_profile": "CSRN Default",
            "obs_profile": config.get("obs", {}).get(
                "profile",
                "CSRN Production",
            )
            if isinstance(config.get("obs", {}), dict)
            else "CSRN Production",
            "visual_mode": visual_mode,
            "crew": crew,
            "production_type": str(data.get("production_type", "game") or "game"),
            "contest_type": contest_type,
            "record_policy": "official" if contest_type == "official" else "non_record",
            "region_game": region_game,
            "special_designations": self.normalize_designations(
                data.get("special_designations")
            ),
            "home_classification": self._snapshot_value(
                data.get("home_classification"), home_school, "classification"
            ),
            "home_region": self._snapshot_value(
                data.get("home_region"), home_school, "region"
            ),
            "visitor_classification": self._snapshot_value(
                data.get("visitor_classification"), visitor_school, "classification"
            ),
            "visitor_region": self._snapshot_value(
                data.get("visitor_region"), visitor_school, "region"
            ),
            "home_pregame_record": home_pregame,
            "home_pregame_region_record": home_region_pregame,
            "visitor_pregame_record": visitor_pregame,
            "visitor_pregame_region_record": visitor_region_pregame,
            "record_tracking": {
                "primary_school_id": primary_school_id,
                "primary_side": primary_side,
                "home_source": "automatic" if primary_side == "home" and latest_primary else "manual",
                "visitor_source": "automatic" if primary_side == "visitor" and latest_primary else "manual",
            },
        }

        items = self._load_broadcasts()
        items.append(record)
        self._save_broadcasts(items)
        self._write_detail(copy.deepcopy(record), False)
        return BroadcastResult(
            "OK",
            {
                "broadcast": copy.deepcopy(record),
                "warnings": self._branding_warnings(home_school, visitor_school),
            },
        )

    def update(self, broadcast_id: str, incoming: Broadcast) -> BroadcastResult:
        data = copy.deepcopy(incoming or {})
        items = self._load_broadcasts()
        item = self._find(items, broadcast_id)
        if item is None:
            return BroadcastResult("NOT_FOUND")

        home_id = str(
            data.get("home_school_id", item.get("home_school_id", "")) or ""
        )
        visitor_id = str(
            data.get("visitor_school_id", item.get("visitor_school_id", "")) or ""
        )
        home = self._get_school(home_id) if home_id else None
        visitor = self._get_school(visitor_id) if visitor_id else None
        home_changed = home_id != str(item.get("home_school_id", "") or "")
        visitor_changed = visitor_id != str(item.get("visitor_school_id", "") or "")

        for key in self._EDITABLE_KEYS:
            if key in data:
                item[key] = copy.deepcopy(data[key])

        sport = str(item.get("sport", "Football") or "Football")
        item.update(
            {
                "home_school_id": home_id,
                "visitor_school_id": visitor_id,
                "home_team": (
                    (home or {}).get("broadcast_name")
                    or data.get("home_team")
                    or item.get("home_team")
                ),
                "visitor_team": (
                    (visitor or {}).get("broadcast_name")
                    or data.get("visitor_team")
                    or item.get("visitor_team")
                ),
                "home_identity": (
                    self._build_identity(home, sport)
                    if home
                    else copy.deepcopy(item.get("home_identity", {}))
                ),
                "visitor_identity": (
                    self._build_identity(visitor, sport)
                    if visitor
                    else copy.deepcopy(item.get("visitor_identity", {}))
                ),
                "updated_at": int(self._clock()),
            }
        )
        for side, school, changed in (
            ("home", home, home_changed),
            ("visitor", visitor, visitor_changed),
        ):
            for suffix, school_key in (
                ("classification", "classification"),
                ("region", "region"),
            ):
                key = f"{side}_{suffix}"
                if key in data:
                    item[key] = str(data.get(key, "") or "").strip()
                elif changed:
                    item[key] = self._snapshot_value(None, school, school_key)
            for key in (
                f"{side}_pregame_record",
                f"{side}_pregame_region_record",
            ):
                if key in data:
                    item[key] = self.normalize_record(data.get(key))
                else:
                    item[key] = self.normalize_record(item.get(key))
        if "contest_type" in data:
            item["contest_type"] = self._contest_type(data.get("contest_type"))
        else:
            item["contest_type"] = self._contest_type(item.get("contest_type"))
        item["record_policy"] = (
            "official" if item["contest_type"] == "official" else "non_record"
        )
        item["region_game"] = (
            bool(data.get("region_game", item.get("region_game", False)))
            if item["contest_type"] == "official"
            else False
        )
        if "special_designations" in data:
            item["special_designations"] = self.normalize_designations(
                data.get("special_designations")
            )
        else:
            item["special_designations"] = self.normalize_designations(
                item.get("special_designations")
            )
        config = self._load_config()
        defaults = config.get("broadcast_defaults", {}) if isinstance(config, Mapping) else {}
        if not isinstance(defaults, Mapping):
            defaults = {}
        primary_school_id = str(defaults.get("home_school_id", "") or "").strip()
        primary_side = self._primary_side(primary_school_id, home_id, visitor_id)
        tracking = item.get("record_tracking", {})
        if not isinstance(tracking, Mapping):
            tracking = {}
        latest_primary = self._latest_primary_records(
            primary_school_id,
            str(item.get("sport", "Football") or "Football"),
            str(item.get("season", "") or ""),
        )
        primary_changed = (primary_side == "home" and home_changed) or (
            primary_side == "visitor" and visitor_changed
        )
        if primary_side and primary_changed and latest_primary:
            item[f"{primary_side}_pregame_record"] = copy.deepcopy(
                latest_primary["overall"]
            )
            item[f"{primary_side}_pregame_region_record"] = copy.deepcopy(
                latest_primary["region"]
            )
        item["record_tracking"] = {
            "primary_school_id": primary_school_id,
            "primary_side": primary_side,
            "home_source": "automatic" if primary_side == "home" and primary_changed and latest_primary else str(tracking.get("home_source", "manual")),
            "visitor_source": "automatic" if primary_side == "visitor" and primary_changed and latest_primary else str(tracking.get("visitor_source", "manual")),
        }
        self._save_broadcasts(items)
        self._write_detail(copy.deepcopy(item), False)
        self._sync_active_state(item)
        return BroadcastResult(
            "OK",
            {
                "broadcast": copy.deepcopy(item),
                "warnings": self._branding_warnings(home, visitor),
            },
        )

    def set_status(self, broadcast_id: str, status: Any) -> BroadcastResult:
        normalized = str(status or "").lower()
        if normalized == "prepared":
            normalized = "planned"
        if normalized not in self._VALID_STATUSES:
            return BroadcastResult("INVALID_STATUS")

        items = self._load_broadcasts()
        item = self._find(items, broadcast_id)
        if item is None:
            return BroadcastResult("NOT_FOUND")
        item["status"] = normalized
        item["updated_at"] = int(self._clock())
        self._save_broadcasts(items)
        self._write_detail(copy.deepcopy(item), True)
        return BroadcastResult("OK", {"broadcast": copy.deepcopy(item)})

    def update_linked_status(
        self,
        broadcast_id: str,
        status: str,
        extra: dict[str, Any] | None = None,
    ) -> BroadcastResult:
        target = str(broadcast_id or "").strip()
        if not target:
            return BroadcastResult("NO_BROADCAST_ID")
        items = self._load_broadcasts()
        item = self._find(items, target)
        if item is None:
            return BroadcastResult("NOT_FOUND")

        now = int(self._clock())
        item["status"] = str(status or "")
        item["updated_at"] = now
        if status == "live":
            item.setdefault("started_at", now)
        if status == "completed":
            item["completed_at"] = now
        if extra:
            item.update(copy.deepcopy(extra))
        if status == "completed" and extra and {
            "final_home_score",
            "final_visitor_score",
        }.issubset(extra):
            self._apply_completion_records(item)
        self._save_broadcasts(items)
        self._write_detail(copy.deepcopy(item), False)
        return BroadcastResult("OK", {"broadcast": copy.deepcopy(item)})

    def resume_record(self, broadcast_id: str) -> BroadcastResult:
        target = str(broadcast_id or "").strip()
        if not target:
            return BroadcastResult("NO_BROADCAST_ID")
        items = self._load_broadcasts()
        item = self._find(items, target)
        if item is None:
            return BroadcastResult("NOT_FOUND")
        item["status"] = "live"
        item["updated_at"] = int(self._clock())
        item.pop("completed_at", None)
        item.pop("final_home_score", None)
        item.pop("final_visitor_score", None)
        item.pop("home_postgame_record", None)
        item.pop("home_postgame_region_record", None)
        item.pop("visitor_postgame_record", None)
        item.pop("visitor_postgame_region_record", None)
        item.pop("record_tracking_applied", None)
        self._save_broadcasts(items)
        self._write_detail(copy.deepcopy(item), False)
        return BroadcastResult("OK", {"broadcast": copy.deepcopy(item)})

    def delete(self, broadcast_id: str) -> BroadcastResult:
        items = self._load_broadcasts()
        item = self._find(items, broadcast_id)
        if item is None:
            return BroadcastResult("NOT_FOUND")
        remaining = [
            row
            for row in items
            if str(row.get("broadcast_id", "")) != str(broadcast_id)
        ]
        self._save_broadcasts(remaining)
        self._delete_detail(str(broadcast_id))

        state = self._load_state()
        if str(state.get("broadcast_id", "")) == str(broadcast_id):
            self._save_state(copy.deepcopy(self._default_state()))
        return BroadcastResult("OK", {"deleted": str(broadcast_id)})

    def _sync_active_state(self, broadcast: Broadcast) -> None:
        state = self._load_state()
        if str(state.get("broadcast_id", "")) != str(
            broadcast.get("broadcast_id", "")
        ):
            return
        for key in self._STATE_SYNC_KEYS:
            if key in broadcast:
                state[key] = copy.deepcopy(broadcast[key])
        self._save_state(state)

    @staticmethod
    def normalize_record(value: Any) -> dict[str, int]:
        incoming = value if isinstance(value, Mapping) else {}
        normalized: dict[str, int] = {}
        for key in ("wins", "losses", "ties"):
            try:
                normalized[key] = max(0, int(incoming.get(key, 0) or 0))
            except (TypeError, ValueError):
                normalized[key] = 0
        return normalized

    @classmethod
    def normalize_designations(cls, value: Any) -> list[str]:
        incoming = value if isinstance(value, (list, tuple, set)) else []
        result: list[str] = []
        for item in incoming:
            normalized = str(item or "").strip().lower().replace(" ", "_")
            if normalized in cls._VALID_SPECIAL_DESIGNATIONS and normalized not in result:
                result.append(normalized)
        return result

    @classmethod
    def _contest_type(cls, value: Any) -> str:
        normalized = str(value or "official").strip().lower()
        return normalized if normalized in cls._VALID_CONTEST_TYPES else "official"

    @staticmethod
    def _snapshot_value(incoming: Any, school: School | None, key: str) -> str:
        return str(incoming or (school or {}).get(key, "") or "").strip()

    @staticmethod
    def _primary_side(primary_school_id: str, home_id: str, visitor_id: str) -> str:
        if primary_school_id and primary_school_id == home_id:
            return "home"
        if primary_school_id and primary_school_id == visitor_id:
            return "visitor"
        return ""

    def _latest_primary_records(
        self,
        primary_school_id: str,
        sport: str,
        season: str,
    ) -> dict[str, dict[str, int]] | None:
        if not primary_school_id:
            return None
        candidates: list[tuple[int, dict[str, int], dict[str, int]]] = []
        for row in self._load_broadcasts():
            if str(row.get("status", "")) != "completed":
                continue
            if str(row.get("sport", "")).casefold() != str(sport).casefold():
                continue
            if str(row.get("season", "")) != str(season):
                continue
            side = self._primary_side(
                primary_school_id,
                str(row.get("home_school_id", "") or ""),
                str(row.get("visitor_school_id", "") or ""),
            )
            if not side:
                continue
            overall_key = f"{side}_postgame_record"
            region_key = f"{side}_postgame_region_record"
            if not isinstance(row.get(overall_key), Mapping):
                continue
            candidates.append(
                (
                    int(row.get("completed_at", row.get("updated_at", 0)) or 0),
                    self.normalize_record(row.get(overall_key)),
                    self.normalize_record(row.get(region_key)),
                )
            )
        if not candidates:
            return None
        _, overall, region = max(candidates, key=lambda item: item[0])
        return {"overall": overall, "region": region}

    @staticmethod
    def _advance_record(record: dict[str, int], outcome: str) -> dict[str, int]:
        result = copy.deepcopy(record)
        key = {"win": "wins", "loss": "losses", "tie": "ties"}[outcome]
        result[key] += 1
        return result

    def _apply_completion_records(self, item: Broadcast) -> None:
        tracking = item.get("record_tracking", {})
        if not isinstance(tracking, Mapping):
            tracking = {}
        primary_side = str(tracking.get("primary_side", "") or "")
        if primary_side not in {"home", "visitor"}:
            item["record_tracking_applied"] = False
            return
        overall = self.normalize_record(item.get(f"{primary_side}_pregame_record"))
        region = self.normalize_record(
            item.get(f"{primary_side}_pregame_region_record")
        )
        if item.get("record_policy") == "official":
            home_score = int(item.get("final_home_score", 0) or 0)
            visitor_score = int(item.get("final_visitor_score", 0) or 0)
            if home_score == visitor_score:
                outcome = "tie"
            elif (primary_side == "home" and home_score > visitor_score) or (
                primary_side == "visitor" and visitor_score > home_score
            ):
                outcome = "win"
            else:
                outcome = "loss"
            overall = self._advance_record(overall, outcome)
            if item.get("region_game"):
                region = self._advance_record(region, outcome)
            item["record_tracking_applied"] = True
        else:
            item["record_tracking_applied"] = False
        item[f"{primary_side}_postgame_record"] = overall
        item[f"{primary_side}_postgame_region_record"] = region

    def _branding_warnings(
        self,
        home: School | None,
        visitor: School | None,
    ) -> list[str]:
        warnings: list[str] = []
        for side, school in (("Home", home), ("Visitor", visitor)):
            if school is None or self._certified(school):
                continue
            name = str(
                school.get("broadcast_name")
                or school.get("official_name", "")
            )
            monogram = self._school_monogram(name)
            warnings.append(
                f"{side} has no certified logo; {monogram} monogram will be used."
            )
        return warnings

    def _certified(self, school: School) -> bool:
        result = self._logo_certification(school)
        if isinstance(result, (tuple, list)):
            return bool(result[0]) if result else False
        return bool(result)

    @staticmethod
    def _find(
        items: list[Broadcast],
        broadcast_id: str,
    ) -> Broadcast | None:
        target = str(broadcast_id or "")
        return next(
            (
                item
                for item in items
                if str(item.get("broadcast_id", "")) == target
            ),
            None,
        )
