from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Callable


State = dict[str, Any]
Record = dict[str, Any]
StateFactory = Callable[[], State]
RecordLoader = Callable[[], list[Record]]
IdentityBuilder = Callable[[Record | None, str], Record]
SponsorApplier = Callable[[Record, Record], str]
Clock = Callable[[], float]


@dataclass(frozen=True)
class GraphicsResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class GraphicsService:
    """Primary identification graphic behavior independent of Flask."""

    PRIMARY_CHANNELS = {
        "lower_third": "lower_third",
        "player": "player_graphic",
        "personnel": "personnel_graphic",
    }

    def __init__(
        self,
        *,
        default_state: StateFactory,
        load_rosters: RecordLoader,
        load_schools: RecordLoader,
        load_personnel: RecordLoader,
        build_identity: IdentityBuilder,
        apply_sponsor: SponsorApplier,
        clock: Clock | None = None,
    ) -> None:
        self._default_state = default_state
        self._load_rosters = load_rosters
        self._load_schools = load_schools
        self._load_personnel = load_personnel
        self._build_identity = build_identity
        self._apply_sponsor = apply_sponsor
        self._clock = clock or time.time

    def _graphic_default(self, key: str) -> Record:
        defaults = self._default_state()
        value = defaults.get(key)
        return copy.deepcopy(value if isinstance(value, dict) else {})

    @staticmethod
    def _duration(value: Any, fallback: Any = 0) -> int:
        try:
            return max(0, min(120, int(value if value is not None else fallback or 0)))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _boolean(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def player_display(player: Record | None) -> str:
        if not player:
            return ""
        full_name = " ".join(
            [
                str(player.get("first_name", "")).strip(),
                str(player.get("last_name", "")).strip(),
            ]
        ).strip()
        return str(player.get("preferred_name", "")).strip() or full_name

    @staticmethod
    def normalize_position(value: Any) -> str:
        text = str(value or "").strip()
        if text.lower() == "athlete":
            return "ATH"
        return text or "ATH"

    @classmethod
    def event_position(cls, player: Record | None, *, defensive: bool = False) -> str:
        if not player:
            return "ATH"
        primary = cls.normalize_position(player.get("position"))
        secondary = (
            cls.normalize_position(player.get("secondary_position"))
            if player.get("secondary_position")
            else ""
        )
        value = (secondary or primary) if defensive else (primary or secondary)
        if "/" in value:
            value = value.split("/", 1)[0].strip()
        return value or "ATH"

    def activate_primary(self, state: State, active: str) -> State:
        updated = copy.deepcopy(state)
        for channel, key in self.PRIMARY_CHANNELS.items():
            if channel == active:
                continue
            item = dict(updated.get(key) or {})
            item["visible"] = False
            item["expires_at"] = 0
            updated[key] = item
        updated["primary_graphic_channel"] = active
        return updated

    def update_lower_third(self, state: State, incoming: Record) -> GraphicsResult:
        updated = copy.deepcopy(state)
        data = copy.deepcopy(incoming or {})
        action = str(data.get("action", "update")).lower()
        current = dict(updated.get("lower_third") or {})
        lower = self._graphic_default("lower_third")
        lower.update(current)

        if action == "clear":
            lower = self._graphic_default("lower_third")
        else:
            for key in (
                "eyebrow",
                "headline",
                "secondary",
                "footer",
                "logo_source",
                "accent_source",
                "custom_accent",
            ):
                if key in data:
                    lower[key] = str(data.get(key, ""))[:180]

            lower["duration"] = self._duration(
                data.get("duration"),
                lower.get("duration", 0),
            )
            if action == "hide":
                lower["visible"] = False
                lower["expires_at"] = 0
            elif action in {"show", "update"}:
                updated = self.activate_primary(updated, "lower_third")
                lower["visible"] = self._boolean(
                    data.get("visible"),
                    action == "show",
                )
                if lower["visible"] and lower["duration"] > 0:
                    lower["expires_at"] = int(self._clock()) + lower["duration"]
                elif lower["visible"]:
                    lower["expires_at"] = 0
            lower["updated_at"] = int(self._clock())

        updated["lower_third"] = lower
        return GraphicsResult("OK", {"state": updated, "graphic": copy.deepcopy(lower)})

    @staticmethod
    def _find(records: list[Record], record_id: str, *, key: str = "id") -> Record | None:
        target = str(record_id or "")
        return next(
            (
                record
                for record in records
                if str(record.get(key, "")) == target
            ),
            None,
        )

    def _roster_player(self, roster_id: str, player_id: str) -> tuple[Record | None, Record | None]:
        roster = self._find(self._load_rosters(), roster_id)
        players = roster.get("players", []) if isinstance(roster, dict) else []
        player = self._find(players if isinstance(players, list) else [], player_id)
        return roster, player

    def _school(self, school_id: Any) -> Record | None:
        return self._find(self._load_schools(), str(school_id or ""))

    def _person(self, personnel_id: str) -> Record | None:
        return self._find(self._load_personnel(), personnel_id)

    def update_player(self, state: State, incoming: Record) -> GraphicsResult:
        updated = copy.deepcopy(state)
        data = copy.deepcopy(incoming or {})
        action = str(data.get("action", "update")).lower()
        current = dict(updated.get("player_graphic") or {})
        graphic = self._graphic_default("player_graphic")
        graphic.update(current)
        sponsor_warning = ""

        if action == "clear":
            graphic = self._graphic_default("player_graphic")
        else:
            for key in (
                "graphic_type",
                "roster_id",
                "player_id",
                "eyebrow",
                "play_detail",
            ):
                if key in data:
                    graphic[key] = str(data.get(key, ""))[:240]

            sponsor_warning = self._apply_sponsor(graphic, data)
            roster_id = str(
                data.get("roster_id", graphic.get("roster_id", ""))
            ).strip()
            player_id = str(
                data.get("player_id", graphic.get("player_id", ""))
            ).strip()
            roster, player = self._roster_player(roster_id, player_id)
            if roster and player:
                school = self._school(roster.get("school_id"))
                full_name = " ".join(
                    [
                        str(player.get("first_name", "")).strip(),
                        str(player.get("last_name", "")).strip(),
                    ]
                ).strip()
                display_name = (
                    str(player.get("preferred_name", "")).strip() or full_name
                )
                identity = (
                    self._build_identity(
                        school,
                        str(roster.get("sport", "Football")),
                    )
                    if school
                    else {}
                )
                graphic.update(
                    {
                        "school_id": roster.get("school_id", ""),
                        "full_name": full_name,
                        "display_name": display_name,
                        "number": str(player.get("number", "")),
                        "position": str(player.get("position", "")),
                        "secondary_position": str(
                            player.get("secondary_position", "")
                        ),
                        "grade": str(player.get("grade", "")),
                        "height": str(player.get("height", "")),
                        "weight": str(player.get("weight", "")),
                        "headshot": str(player.get("headshot", "")),
                        "team_logo": str(identity.get("logo", "")),
                        "team_name": str(
                            (school or {}).get("broadcast_name")
                            or (school or {}).get("official_name")
                            or roster.get("school_id", "")
                        ),
                        "team_color": str(
                            identity.get("primary_color")
                            or (school or {}).get("primary_color")
                            or "#C9203B"
                        ),
                    }
                )

            graphic["duration"] = self._duration(
                data.get("duration"),
                graphic.get("duration", 0),
            )
            if action == "hide":
                graphic["visible"] = False
                graphic["expires_at"] = 0
            elif action in {"show", "update"}:
                if not graphic.get("player_id"):
                    return GraphicsResult("PLAYER_REQUIRED")
                updated = self.activate_primary(updated, "player")
                graphic["visible"] = self._boolean(
                    data.get("visible"),
                    action == "show",
                )
                if graphic["visible"] and graphic["duration"] > 0:
                    graphic["expires_at"] = int(self._clock()) + graphic["duration"]
                elif graphic["visible"]:
                    graphic["expires_at"] = 0
            graphic["updated_at"] = int(self._clock())

        updated["player_graphic"] = graphic
        return GraphicsResult(
            "OK",
            {
                "state": updated,
                "graphic": copy.deepcopy(graphic),
                "sponsor_warning": sponsor_warning,
            },
        )

    def update_personnel(self, state: State, incoming: Record) -> GraphicsResult:
        updated = copy.deepcopy(state)
        data = copy.deepcopy(incoming or {})
        action = str(data.get("action", "update")).lower()
        graphic = self._graphic_default("personnel_graphic")
        graphic.update(updated.get("personnel_graphic") or {})
        sponsor_warning = ""

        if action == "clear":
            graphic = self._graphic_default("personnel_graphic")
        else:
            personnel_id = str(
                data.get("personnel_id", graphic.get("personnel_id", ""))
            ).strip()
            person = self._person(personnel_id)
            if person:
                school = self._school(person.get("school_id"))
                identity = (
                    self._build_identity(school, "Football") if school else {}
                )
                full_name = str(
                    person.get("full_name") or person.get("name") or ""
                ).strip()
                display_name = (
                    str(person.get("preferred_name", "")).strip() or full_name
                )
                graphic.update(
                    {
                        "personnel_id": personnel_id,
                        "full_name": full_name,
                        "display_name": display_name,
                        "title": str(
                            person.get("title") or person.get("role") or ""
                        ),
                        "role": str(person.get("role", "")),
                        "organization": str(
                            person.get("organization")
                            or (school or {}).get("broadcast_name")
                            or (school or {}).get("official_name")
                            or ""
                        ),
                        "headshot": str(person.get("headshot", "")),
                        "logo": str(
                            identity.get("logo") or "/static/csrn-logo.png"
                        ),
                        "accent": str(
                            identity.get("primary_color") or "#C9203B"
                        ),
                    }
                )

            for key in ("graphic_type", "eyebrow"):
                if key in data:
                    graphic[key] = str(data.get(key, ""))[:240]

            sponsor_warning = self._apply_sponsor(graphic, data)
            graphic["duration"] = self._duration(
                data.get("duration"),
                graphic.get("duration", 0),
            )
            if action == "hide":
                graphic["visible"] = False
                graphic["expires_at"] = 0
            elif action in {"show", "update"}:
                if not graphic.get("personnel_id"):
                    return GraphicsResult("PERSONNEL_REQUIRED")
                updated = self.activate_primary(updated, "personnel")
                graphic["visible"] = True
                graphic["expires_at"] = (
                    int(self._clock()) + graphic["duration"]
                    if graphic["duration"]
                    else 0
                )
            graphic["updated_at"] = int(self._clock())

        updated["personnel_graphic"] = graphic
        return GraphicsResult(
            "OK",
            {
                "state": updated,
                "graphic": copy.deepcopy(graphic),
                "sponsor_warning": sponsor_warning,
            },
        )

    def show_automation_player(
        self,
        state: State,
        roster: Record | None,
        player: Record | None,
        graphic_type: str,
        duration: Any,
        *,
        defensive: bool = False,
        eyebrow: str = "",
        play_detail: str = "",
    ) -> GraphicsResult:
        updated = copy.deepcopy(state)
        normalized_duration = self._duration(duration)
        if not roster or not player or normalized_duration <= 0:
            return GraphicsResult("OK", {"state": updated, "applied": False})

        school = self._school(roster.get("school_id"))
        identity = (
            self._build_identity(
                school,
                str(roster.get("sport", "Football")),
            )
            if school
            else {}
        )
        full_name = " ".join(
            [
                str(player.get("first_name", "")).strip(),
                str(player.get("last_name", "")).strip(),
            ]
        ).strip()
        now = int(self._clock())
        graphic = self._graphic_default("player_graphic")
        graphic.update(
            {
                "visible": True,
                "graphic_type": str(graphic_type or "player_id"),
                "eyebrow": str(
                    eyebrow
                    or (
                        "TOUCHDOWN"
                        if str(graphic_type) == "touchdown"
                        else "PLAYER PROFILE"
                    )
                ),
                "roster_id": str(roster.get("id", "")),
                "player_id": str(player.get("id", "")),
                "school_id": str(roster.get("school_id", "")),
                "full_name": full_name,
                "display_name": self.player_display(player),
                "number": str(player.get("number", "")),
                "position": self.event_position(player, defensive=defensive),
                "secondary_position": "",
                "grade": str(player.get("grade", "")),
                "height": str(player.get("height", "")),
                "weight": str(player.get("weight", "")),
                "headshot": str(player.get("headshot", "")),
                "team_logo": str(identity.get("logo", "")),
                "team_name": str(
                    (school or {}).get("broadcast_name")
                    or (school or {}).get("official_name")
                    or ""
                ),
                "team_color": str(
                    identity.get("primary_color")
                    or (school or {}).get("primary_color")
                    or "#C9203B"
                ),
                "play_detail": str(play_detail or ""),
                "duration": normalized_duration,
                "expires_at": now + normalized_duration,
                "updated_at": now,
            }
        )
        updated = self.activate_primary(updated, "player")
        updated["player_graphic"] = graphic
        return GraphicsResult(
            "OK",
            {
                "state": updated,
                "graphic": copy.deepcopy(graphic),
                "applied": True,
            },
        )
