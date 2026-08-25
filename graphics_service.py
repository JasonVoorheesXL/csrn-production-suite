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
        "highlight": "player_highlight",
        "personnel": "personnel_graphic",
        "sponsor": "sponsor_spotlight",
    }
    APPROVED_RIGHTS = {
        "Owned",
        "Licensed",
        "Permission Granted",
        "Public Domain",
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
        load_assets: RecordLoader | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._default_state = default_state
        self._load_rosters = load_rosters
        self._load_schools = load_schools
        self._load_personnel = load_personnel
        self._build_identity = build_identity
        self._apply_sponsor = apply_sponsor
        self._load_assets = load_assets or (lambda: [])
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

    @staticmethod
    def _active(graphic: Record, now: int) -> bool:
        if not graphic.get("visible"):
            return False
        try:
            expires_at = int(graphic.get("expires_at", 0) or 0)
        except (TypeError, ValueError):
            expires_at = 0
        return not expires_at or expires_at > now

    def reconcile_queue(self, state: State) -> GraphicsResult:
        updated = copy.deepcopy(state)
        now = int(self._clock())
        changed = False

        for key in ("player_graphic", "player_highlight", "sponsor_spotlight"):
            graphic = dict(updated.get(key) or {})
            if graphic.get("visible") and not self._active(graphic, now):
                graphic["visible"] = False
                graphic["expires_at"] = 0
                updated[key] = graphic
                changed = True

        queue = [
            copy.deepcopy(item)
            for item in list(updated.get("graphics_queue") or [])
            if isinstance(item, dict)
        ][-20:]
        primary_active = any(
            self._active(dict(updated.get(key) or {}), now)
            for key in self.PRIMARY_CHANNELS.values()
        )
        if not primary_active and queue:
            item = queue.pop(0)
            if item.get("channel") == "player":
                graphic = copy.deepcopy(dict(item.get("graphic") or {}))
                duration = self._duration(graphic.get("duration"), 8)
                graphic["visible"] = True
                graphic["duration"] = duration
                graphic["expires_at"] = now + duration if duration else 0
                graphic["updated_at"] = now
                updated = self.activate_primary(updated, "player")
                updated["player_graphic"] = graphic
                changed = True
        if queue != list(updated.get("graphics_queue") or []):
            changed = True
        updated["graphics_queue"] = queue
        return GraphicsResult(
            "OK",
            {"state": updated, "changed": changed},
        )

    def update_queue(self, state: State, incoming: Record) -> GraphicsResult:
        updated = copy.deepcopy(state)
        action = str((incoming or {}).get("action", "")).strip().lower()
        queue = [
            copy.deepcopy(item)
            for item in list(updated.get("graphics_queue") or [])
            if isinstance(item, dict)
        ]
        if action == "cancel":
            item_id = str((incoming or {}).get("id", "")).strip()
            queue = [item for item in queue if str(item.get("id", "")) != item_id]
        elif action == "clear":
            queue = []
        elif action == "advance":
            for key in self.PRIMARY_CHANNELS.values():
                graphic = dict(updated.get(key) or {})
                graphic["visible"] = False
                graphic["expires_at"] = 0
                updated[key] = graphic
        else:
            return GraphicsResult("INVALID_QUEUE_ACTION")
        updated["graphics_queue"] = queue
        return self.reconcile_queue(updated)

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
        if action in {"hide", "clear"}:
            updated = self.reconcile_queue(updated).data["state"]
            graphic = copy.deepcopy(updated.get("player_graphic") or graphic)
        return GraphicsResult(
            "OK",
            {
                "state": updated,
                "graphic": copy.deepcopy(graphic),
                "sponsor_warning": sponsor_warning,
            },
        )

    def update_sponsor_spotlight(
        self,
        state: State,
        incoming: Record,
    ) -> GraphicsResult:
        updated = copy.deepcopy(state)
        data = copy.deepcopy(incoming or {})
        action = str(data.get("action", "update")).lower()
        spotlight = self._graphic_default("sponsor_spotlight")
        spotlight.update(updated.get("sponsor_spotlight") or {})
        sponsor_warning = ""

        if action == "clear":
            spotlight = self._graphic_default("sponsor_spotlight")
        else:
            sponsor_warning = self._apply_sponsor(spotlight, data)
            if action in {"show", "update"} and not spotlight.get("sponsor_id"):
                return GraphicsResult(
                    "SPONSOR_REQUIRED",
                    {"sponsor_warning": sponsor_warning},
                )

            asset_id = str(
                data.get("media_asset_id", spotlight.get("media_asset_id", ""))
                or ""
            ).strip()
            asset = self._find(self._load_assets(), asset_id)
            if asset_id:
                placement = str(
                    (asset or {}).get("placement", "flexible") or "flexible"
                )
                asset_type = str((asset or {}).get("asset_type", ""))
                sponsor_id = str(spotlight.get("sponsor_id", "") or "")
                asset_sponsor_id = str((asset or {}).get("sponsor_id", "") or "")
                if (
                    not asset
                    or asset.get("active", True) is False
                    or str(asset.get("category", "")).casefold() != "sponsor"
                    or asset_type.casefold()
                    not in {"logo", "background", "overlay", "video"}
                    or not str(asset.get("file_url", "")).strip()
                    or placement
                    not in {
                        "flexible",
                        "sponsor_feature_still",
                        "sponsor_feature_video",
                        "sponsor_advertisement_video",
                    }
                    or (
                        placement in {"sponsor_feature_video", "sponsor_advertisement_video"}
                        and asset_type.casefold() != "video"
                    )
                    or (
                        placement == "sponsor_advertisement_video"
                        and str((asset or {}).get("rights_status", "")) not in self.APPROVED_RIGHTS
                    )
                    or (
                        placement == "sponsor_feature_still"
                        and asset_type.casefold() == "video"
                    )
                    or (
                        asset_sponsor_id
                        and sponsor_id
                        and asset_sponsor_id != sponsor_id
                    )
                ):
                    return GraphicsResult("SPONSOR_MEDIA_NOT_APPROVED")
                media_url = str(asset.get("file_url", ""))[:500]
                spotlight.update(
                    {
                        "media_asset_id": asset_id,
                        "media_name": str(asset.get("name", ""))[:240],
                        "media_url": media_url,
                        "media_type": (
                            "video"
                            if asset_type.casefold() == "video"
                            or media_url.lower().split("?", 1)[0].endswith(
                                (".mp4", ".webm")
                            )
                            else "image"
                        ),
                        "presentation_mode": (
                            "advertisement"
                            if placement == "sponsor_advertisement_video"
                            else "spotlight"
                        ),
                        "audio_enabled": placement == "sponsor_advertisement_video",
                    }
                )
            elif spotlight.get("sponsor_logo"):
                spotlight.update(
                    {
                        "media_asset_id": "",
                        "media_name": str(spotlight.get("sponsor_name", "")),
                        "media_url": str(spotlight.get("sponsor_logo", "")),
                        "media_type": "image",
                        "presentation_mode": "spotlight",
                        "audio_enabled": False,
                    }
                )

            if action in {"show", "update"} and not spotlight.get("media_url"):
                return GraphicsResult("SPONSOR_MEDIA_REQUIRED")
            if "caption" in data:
                spotlight["caption"] = str(data.get("caption", ""))[:180]
            if "lead_in" in data:
                spotlight["lead_in"] = str(data.get("lead_in", ""))[:120]
            spotlight["duration"] = self._duration(
                data.get("duration"),
                spotlight.get("duration", 0),
            )
            if action == "hide":
                spotlight["visible"] = False
                spotlight["expires_at"] = 0
            elif action in {"show", "update"}:
                updated = self.activate_primary(updated, "sponsor")
                spotlight["visible"] = True
                spotlight["expires_at"] = (
                    int(self._clock()) + spotlight["duration"]
                    if spotlight["duration"]
                    else 0
                )
            spotlight["updated_at"] = int(self._clock())

        updated["sponsor_spotlight"] = spotlight
        if action in {"hide", "clear"}:
            updated = self.reconcile_queue(updated).data["state"]
            spotlight = copy.deepcopy(updated.get("sponsor_spotlight") or spotlight)
        return GraphicsResult(
            "OK",
            {
                "state": updated,
                "graphic": copy.deepcopy(spotlight),
                "sponsor_warning": sponsor_warning,
            },
        )

    def update_player_highlight(
        self,
        state: State,
        incoming: Record,
    ) -> GraphicsResult:
        updated = copy.deepcopy(state)
        data = copy.deepcopy(incoming or {})
        action = str(data.get("action", "update")).lower()
        highlight = self._graphic_default("player_highlight")
        highlight.update(updated.get("player_highlight") or {})

        if action == "clear":
            highlight = self._graphic_default("player_highlight")
        else:
            roster_id = str(
                data.get("roster_id", highlight.get("roster_id", ""))
            ).strip()
            player_id = str(
                data.get("player_id", highlight.get("player_id", ""))
            ).strip()
            roster, player = self._roster_player(roster_id, player_id)
            if roster and player:
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
                highlight.update(
                    {
                        "roster_id": roster_id,
                        "player_id": player_id,
                        "school_id": str(roster.get("school_id", "")),
                        "full_name": full_name,
                        "display_name": self.player_display(player),
                        "number": str(player.get("number", "")),
                        "position": self.normalize_position(player.get("position")),
                        "grade": str(player.get("grade", "")),
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
            if "detail" in data:
                highlight["detail"] = str(data.get("detail", ""))[:180]

            asset_id = str(
                data.get("media_asset_id", highlight.get("media_asset_id", ""))
                or ""
            ).strip()
            asset = self._find(self._load_assets(), asset_id)
            if asset_id:
                asset_roster_id = str((asset or {}).get("roster_id", "") or "")
                asset_player_id = str((asset or {}).get("player_id", "") or "")
                if (
                    not asset
                    or asset.get("active", True) is False
                    or str(asset.get("category", "")).casefold() != "player"
                    or str(asset.get("asset_type", "")).casefold() != "video"
                    or str(asset.get("rights_status", "")) not in self.APPROVED_RIGHTS
                    or str(asset.get("placement", "flexible") or "flexible")
                    != "player_highlight_video"
                    or not str(asset.get("file_url", "")).strip()
                    or (asset_roster_id and asset_roster_id != roster_id)
                    or (asset_player_id and asset_player_id != player_id)
                ):
                    return GraphicsResult("PLAYER_HIGHLIGHT_MEDIA_NOT_APPROVED")
                highlight.update(
                    {
                        "media_asset_id": asset_id,
                        "media_name": str(asset.get("name", ""))[:240],
                        "media_url": str(asset.get("file_url", ""))[:500],
                        "media_type": "video",
                    }
                )

            highlight["duration"] = self._duration(
                data.get("duration"),
                highlight.get("duration", 0),
            )
            if action == "hide":
                highlight["visible"] = False
                highlight["expires_at"] = 0
            elif action in {"show", "update"}:
                if not highlight.get("player_id"):
                    return GraphicsResult("PLAYER_REQUIRED")
                if not highlight.get("media_url"):
                    return GraphicsResult("PLAYER_HIGHLIGHT_MEDIA_REQUIRED")
                if highlight["duration"] <= 0:
                    return GraphicsResult("PLAYER_HIGHLIGHT_DURATION_REQUIRED")
                updated = self.activate_primary(updated, "highlight")
                highlight["visible"] = True
                highlight["expires_at"] = int(self._clock()) + highlight["duration"]
            highlight["updated_at"] = int(self._clock())

        updated["player_highlight"] = highlight
        if action in {"hide", "clear"}:
            updated = self.reconcile_queue(updated).data["state"]
            highlight = copy.deepcopy(updated.get("player_highlight") or highlight)
        return GraphicsResult(
            "OK",
            {
                "state": updated,
                "graphic": copy.deepcopy(highlight),
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
        sponsor_id: str = "",
        passer_name: str = "",
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
                # Pass-reception touchdowns only -- the QB gets a text
                # credit alongside the receiver's card, not his own photo.
                "passer_name": str(passer_name or "").strip(),
                "duration": normalized_duration,
                "expires_at": now + normalized_duration,
                "updated_at": now,
            }
        )
        if str(sponsor_id or "").strip():
            self._apply_sponsor(graphic, {"sponsor_id": sponsor_id})

        active_player = dict(updated.get("player_graphic") or {})
        active_highlight = dict(updated.get("player_highlight") or {})
        if (
            (
                self._active(active_player, now)
                and str(active_player.get("graphic_type", ""))
                in {"player_spotlight", "player_highlight"}
            )
            or self._active(active_highlight, now)
        ):
            queue = [
                copy.deepcopy(item)
                for item in list(updated.get("graphics_queue") or [])
                if isinstance(item, dict)
            ][-19:]
            queue.append(
                {
                    "id": (
                        f"GQ-{now}-{str(player.get('id', 'player'))}-"
                        f"{len(queue) + 1}"
                    ),
                    "channel": "player",
                    "label": str(graphic.get("eyebrow", "PLAYER EVENT")),
                    "player_name": str(graphic.get("display_name", "")),
                    "queued_at": now,
                    "graphic": copy.deepcopy(graphic),
                }
            )
            updated["graphics_queue"] = queue
            return GraphicsResult(
                "OK",
                {
                    "state": updated,
                    "graphic": copy.deepcopy(graphic),
                    "applied": False,
                    "queued": True,
                },
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
