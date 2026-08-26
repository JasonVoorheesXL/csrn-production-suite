from __future__ import annotations

import copy
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Callable


Venue = dict[str, Any]
School = dict[str, Any]
Broadcast = dict[str, Any]
VenueLoader = Callable[[], list[Venue]]
VenueSaver = Callable[[list[Venue]], None]
SchoolLoader = Callable[[], list[School]]
BroadcastLoader = Callable[[], list[Broadcast]]
Clock = Callable[[], float]
TokenFactory = Callable[[], str]


@dataclass(frozen=True)
class VenueResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class VenueService:
    """Venue-domain behavior independent of Flask and persistence details."""

    def __init__(
        self,
        *,
        load_venues: VenueLoader,
        save_venues: VenueSaver,
        load_schools: SchoolLoader | None = None,
        load_broadcasts: BroadcastLoader | None = None,
        clock: Clock | None = None,
        token_factory: TokenFactory | None = None,
    ) -> None:
        self._load_venues = load_venues
        self._save_venues = save_venues
        self._load_schools = load_schools or (lambda: [])
        self._load_broadcasts = load_broadcasts or (lambda: [])
        self._clock = clock or time.time
        self._token_factory = token_factory or (lambda: secrets.token_hex(2))

    @staticmethod
    def normalize_id(value: Any) -> str:
        text = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "").strip())
        return text.strip("-").lower()

    @staticmethod
    def _coordinate(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _boolean(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    def clean_record(
        self,
        incoming: Venue,
        venue_id: str | None = None,
    ) -> Venue:
        source = copy.deepcopy(incoming)
        now = int(self._clock())
        school_id = str(source.get("school_id", "")).strip()[:160]
        sport = str(source.get("sport", "Football")).strip()[:80] or "Football"
        name = str(source.get("name", "")).strip()[:240]
        generated_id = self.normalize_id(
            source.get("id")
            or f"{school_id or name}-{sport}-{self._token_factory()}"
        )
        if not generated_id:
            generated_id = f"venue-{now}-{self._token_factory()}"

        return {
            "id": str(venue_id or generated_id)[:200],
            "school_id": school_id,
            "csrn_school_id": str(source.get("csrn_school_id", "")).strip()[:80],
            "sport": sport,
            "name": name,
            "address1": str(source.get("address1", "")).strip()[:240],
            "address2": str(source.get("address2", "")).strip()[:240],
            "city": str(source.get("city", "")).strip()[:120],
            "state": str(source.get("state", "")).strip().upper()[:40],
            "postal_code": str(source.get("postal_code", "")).strip()[:40],
            "latitude": self._coordinate(source.get("latitude")),
            "longitude": self._coordinate(source.get("longitude")),
            "approval_status": str(
                source.get("approval_status", "candidate")
            ).strip()[:40]
            or "candidate",
            "broadcast_notes": str(source.get("broadcast_notes", "")).strip()[:3000],
            "on_campus_assumed": self._boolean(
                source.get("on_campus_assumed"),
                False,
            ),
            "venue_address_source": str(
                source.get("venue_address_source", "manual")
            ).strip()[:120]
            or "manual",
            "venue_verified": self._boolean(source.get("venue_verified"), False),
            "active": self._boolean(source.get("active"), True),
            "created_at": int(source.get("created_at", now) or now),
            "updated_at": now,
        }

    def list_venues(
        self,
        *,
        school_id: str = "",
        sport: str = "",
        include_inactive: bool = True,
    ) -> VenueResult:
        school_key = str(school_id or "").strip()
        sport_key = str(sport or "").strip().casefold()
        rows: list[Venue] = []
        for venue in self._load_venues():
            if school_key and str(venue.get("school_id", "")) != school_key:
                continue
            if sport_key and str(venue.get("sport", "")).strip().casefold() != sport_key:
                continue
            if not include_inactive and venue.get("active", True) is False:
                continue
            rows.append(copy.deepcopy(venue))
        rows.sort(
            key=lambda item: (
                str(item.get("name", "")).casefold(),
                str(item.get("sport", "")).casefold(),
                str(item.get("id", "")),
            )
        )
        return VenueResult("OK", {"venues": rows})

    def read(self, venue_id: str) -> VenueResult:
        venue = self._find(self._load_venues(), venue_id)
        if venue is None:
            return VenueResult("VENUE_NOT_FOUND")
        return VenueResult("OK", {"venue": copy.deepcopy(venue)})

    def create(self, incoming: Venue) -> VenueResult:
        source = copy.deepcopy(incoming)
        venue = self.clean_record(source)
        if not venue["name"]:
            return VenueResult("VENUE_NAME_REQUIRED")

        venues = self._load_venues()
        duplicate = self._duplicate(venues, venue)
        if duplicate is not None and not self._boolean(
            source.get("confirm_duplicate"),
            False,
        ):
            return VenueResult(
                "DUPLICATE_VENUE",
                {"duplicate_venue": copy.deepcopy(duplicate)},
            )

        base_id = venue["id"]
        candidate_id = base_id
        suffix = 2
        while self._find(venues, candidate_id) is not None:
            candidate_id = f"{base_id}-{suffix}"
            suffix += 1
        venue["id"] = candidate_id

        venues.append(venue)
        self._save_venues(venues)
        return VenueResult("OK", {"venue": copy.deepcopy(venue)})

    def update(self, venue_id: str, incoming: Venue) -> VenueResult:
        venues = self._load_venues()
        current = self._find(venues, venue_id)
        if current is None:
            return VenueResult("VENUE_NOT_FOUND")

        source = copy.deepcopy(incoming)
        replacement = self.clean_record({**current, **source}, str(venue_id))
        if not replacement["name"]:
            return VenueResult("VENUE_NAME_REQUIRED")

        duplicate = self._duplicate(
            venues,
            replacement,
            exclude_id=str(venue_id),
        )
        if duplicate is not None and not self._boolean(
            source.get("confirm_duplicate"),
            False,
        ):
            return VenueResult(
                "DUPLICATE_VENUE",
                {"duplicate_venue": copy.deepcopy(duplicate)},
            )

        for index, venue in enumerate(venues):
            if str(venue.get("id", "")) == str(venue_id):
                venues[index] = replacement
                break
        self._save_venues(venues)
        return VenueResult("OK", {"venue": copy.deepcopy(replacement)})

    def delete(self, venue_id: str) -> VenueResult:
        venues = self._load_venues()
        venue = self._find(venues, venue_id)
        if venue is None:
            return VenueResult("VENUE_NOT_FOUND")

        references = self.references(venue_id)
        if references["schools"] or references["broadcasts"]:
            return VenueResult("VENUE_IN_USE", references)

        remaining = [
            item
            for item in venues
            if str(item.get("id", "")) != str(venue_id)
        ]
        # Deleting a specific, named venue is an intentional, operator-
        # identified action -- distinct from a bulk write accidentally
        # wiping most/all venue entries, which the repository's
        # destructive-write guard exists to catch. Also already gated
        # above: a venue still referenced by a school/broadcast can't
        # reach here at all.
        self._save_venues(remaining, force=True)
        return VenueResult("OK", {"ok": True, "deleted": str(venue_id)})

    def references(self, venue_id: str) -> dict[str, list[dict[str, str]]]:
        target = str(venue_id or "")
        schools = [
            {
                "id": str(school.get("id", "")),
                "name": str(
                    school.get("broadcast_name")
                    or school.get("official_name")
                    or school.get("id", "")
                ),
            }
            for school in self._load_schools()
            if str(school.get("venue_id", "")) == target
        ]
        broadcasts = [
            {
                "id": str(broadcast.get("broadcast_id", "")),
                "name": str(
                    broadcast.get("home_team", "")
                    + " vs "
                    + broadcast.get("visitor_team", "")
                ).strip(" vs"),
            }
            for broadcast in self._load_broadcasts()
            if str(broadcast.get("venue_id", "")) == target
        ]
        return {"schools": schools, "broadcasts": broadcasts}

    def for_school(
        self,
        school: School | None,
        sport: str = "",
    ) -> Venue | None:
        if not school:
            return None
        venues = self._load_venues()
        explicit_id = str(school.get("venue_id", "")).strip()
        if explicit_id:
            explicit = self._find(venues, explicit_id)
            if explicit is not None:
                return copy.deepcopy(explicit)

        school_id = str(school.get("id", "")).strip()
        matches = [
            venue
            for venue in venues
            if str(venue.get("school_id", "")).strip() == school_id
            and venue.get("active", True) is not False
        ]
        sport_key = str(sport or "").strip().casefold()
        if sport_key:
            exact = next(
                (
                    venue
                    for venue in matches
                    if str(venue.get("sport", "")).strip().casefold() == sport_key
                ),
                None,
            )
            if exact is not None:
                return copy.deepcopy(exact)
        return copy.deepcopy(matches[0]) if matches else None

    def migrate_legacy_names(self) -> VenueResult:
        venues = self._load_venues()
        changed = 0
        for venue in venues:
            name = str(venue.get("name", ""))
            school = ""
            if name.endswith(" Football Venue"):
                school = name[: -len(" Football Venue")].strip()
            elif name.endswith(" Football Stadium"):
                school = name[: -len(" Football Stadium")].strip()
            if school:
                venue["name"] = f"{school} HS Football Field"
                venue["updated_at"] = int(self._clock())
                changed += 1
        if changed:
            self._save_venues(venues)
        return VenueResult("OK", {"migrated": changed, "venues": copy.deepcopy(venues)})

    @staticmethod
    def _find(venues: list[Venue], venue_id: str) -> Venue | None:
        target = str(venue_id or "")
        return next(
            (
                venue
                for venue in venues
                if str(venue.get("id", "")) == target
            ),
            None,
        )

    @staticmethod
    def _duplicate(
        venues: list[Venue],
        candidate: Venue,
        *,
        exclude_id: str = "",
    ) -> Venue | None:
        candidate_name = str(candidate.get("name", "")).strip().casefold()
        candidate_school = str(candidate.get("school_id", "")).strip()
        candidate_sport = str(candidate.get("sport", "")).strip().casefold()
        return next(
            (
                venue
                for venue in venues
                if str(venue.get("id", "")) != str(exclude_id)
                and (
                    (
                        candidate_name
                        and str(venue.get("name", "")).strip().casefold()
                        == candidate_name
                    )
                    or (
                        candidate_school
                        and candidate_sport
                        and str(venue.get("school_id", "")).strip()
                        == candidate_school
                        and str(venue.get("sport", "")).strip().casefold()
                        == candidate_sport
                    )
                )
            ),
            None,
        )
