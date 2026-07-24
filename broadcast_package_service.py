from __future__ import annotations

import copy
from dataclasses import dataclass, field
from time import time
from typing import Any, Callable


Package = dict[str, Any]
PackageLoader = Callable[[], list[Package]]
PackageSaver = Callable[[list[Package]], None]
ObjectLoader = Callable[[], list[dict[str, Any]]]
ConfigLoader = Callable[[], dict[str, Any]]
StateLoader = Callable[[], dict[str, Any]]
StateSaver = Callable[[dict[str, Any]], None]
SponsorStateResolver = Callable[[dict[str, Any]], str]
Clock = Callable[[], float]


@dataclass(frozen=True)
class PackageResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class BroadcastPackageService:
    """Broadcast-package business logic independent of Flask routes."""

    def __init__(
        self,
        *,
        load_packages: PackageLoader,
        save_packages: PackageSaver,
        load_broadcasts: ObjectLoader,
        load_rosters: ObjectLoader,
        load_personnel: ObjectLoader,
        load_sponsors: ObjectLoader,
        load_config: ConfigLoader,
        sponsor_contract_state: SponsorStateResolver,
        load_state: StateLoader,
        save_state: StateSaver,
        clock: Clock = time,
    ) -> None:
        self._load_packages = load_packages
        self._save_packages = save_packages
        self._load_broadcasts = load_broadcasts
        self._load_rosters = load_rosters
        self._load_personnel = load_personnel
        self._load_sponsors = load_sponsors
        self._load_config = load_config
        self._sponsor_contract_state = sponsor_contract_state
        self._load_state = load_state
        self._save_state = save_state
        self._clock = clock

    def health(self, package: Package) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        def add(key: str, label: str, ok: bool, note: str) -> None:
            checks.append(
                {
                    "key": key,
                    "label": label,
                    "ok": bool(ok),
                    "note": note,
                }
            )

        broadcast = next(
            (
                item
                for item in self._load_broadcasts()
                if item.get("broadcast_id") == package.get("broadcast_id")
            ),
            None,
        )
        add(
            "broadcast",
            "Broadcast",
            bool(broadcast),
            "Linked game record found." if broadcast else "Select a broadcast.",
        )

        schools_ready = bool(
            broadcast
            and broadcast.get("home_school_id")
            and broadcast.get("visitor_school_id")
        )
        add(
            "schools",
            "Schools",
            schools_ready,
            "Home and visitor schools linked."
            if schools_ready
            else "Both schools are required.",
        )

        roster_ids = set(package.get("roster_ids") or [])
        rosters_ready = bool(
            roster_ids
            and any(item.get("id") in roster_ids for item in self._load_rosters())
        )
        add(
            "rosters",
            "Rosters",
            rosters_ready,
            "At least one roster linked." if roster_ids else "No roster linked.",
        )

        personnel_ids = set(package.get("personnel_ids") or [])
        personnel_ready = bool(
            personnel_ids
            and any(
                item.get("id") in personnel_ids
                for item in self._load_personnel()
            )
        )
        add(
            "personnel",
            "Personnel",
            personnel_ready,
            "Broadcast personnel linked."
            if personnel_ids
            else "No personnel selected.",
        )

        sponsor_ids = set(package.get("sponsor_ids") or [])
        valid_sponsors = [
            item
            for item in self._load_sponsors()
            if item.get("id") in sponsor_ids
            and self._sponsor_contract_state(item) == "Active"
            and item.get("active", True)
        ]
        add(
            "sponsors",
            "Sponsors",
            bool(valid_sponsors) or not sponsor_ids,
            "Active sponsors verified."
            if valid_sponsors
            else (
                "No sponsors assigned."
                if not sponsor_ids
                else "Assigned sponsors are unavailable or expired."
            ),
        )

        config = self._load_config()
        add(
            "graphics",
            "Graphics",
            bool(package.get("graphics_profile", "CSRN Default")),
            "Graphics profile configured.",
        )
        add(
            "obs",
            "OBS",
            bool(config.get("obs", {}).get("required_scene")),
            "OBS profile and required scene configured.",
        )

        score = (
            round(sum(1 for check in checks if check["ok"]) / len(checks) * 100)
            if checks
            else 0
        )
        return {
            "score": score,
            "ready": all(check["ok"] for check in checks),
            "checks": checks,
        }

    def record(
        self,
        data: Package,
        existing: Package | None = None,
    ) -> Package:
        timestamp = self._clock()
        now = int(timestamp)
        record = copy.deepcopy(existing or {})
        record.update(
            {
                "id": record.get("id") or f"pkg-{int(timestamp * 1000)}",
                "name": str(
                    data.get("name")
                    or record.get("name")
                    or "Untitled Broadcast Package"
                ).strip(),
                "broadcast_id": str(
                    data.get("broadcast_id")
                    or record.get("broadcast_id")
                    or ""
                ).strip(),
                "status": str(
                    data.get("status")
                    or record.get("status")
                    or "Planning"
                ),
                "roster_ids": list(
                    data.get("roster_ids")
                    if "roster_ids" in data
                    else record.get("roster_ids", [])
                ),
                "personnel_ids": list(
                    data.get("personnel_ids")
                    if "personnel_ids" in data
                    else record.get("personnel_ids", [])
                ),
                "sponsor_ids": list(
                    data.get("sponsor_ids")
                    if "sponsor_ids" in data
                    else record.get("sponsor_ids", [])
                ),
                "lineups": copy.deepcopy(
                    data.get("lineups")
                    if "lineups" in data
                    else record.get("lineups", {})
                ),
                "graphics_profile": str(
                    data.get("graphics_profile")
                    or record.get("graphics_profile")
                    or "CSRN Default"
                ),
                "notes": str(
                    data.get("notes")
                    if "notes" in data
                    else record.get("notes", "")
                ),
                "locked": bool(
                    data.get("locked")
                    if "locked" in data
                    else record.get("locked", False)
                ),
                "updated_at": now,
                "created_at": record.get("created_at", now),
            }
        )
        record["health"] = self.health(record)
        return record

    def list_packages(self) -> list[Package]:
        items: list[Package] = []
        for package in self._load_packages():
            item = copy.deepcopy(package)
            item["health"] = self.health(item)
            items.append(item)
        return sorted(
            items,
            key=lambda item: item.get("updated_at", 0),
            reverse=True,
        )

    def create(self, data: Package) -> PackageResult:
        record = self.record(data)
        items = self._load_packages()
        items.append(record)
        self._save_packages(items)
        return PackageResult("OK", {"package": record})

    def update(self, package_id: str, data: Package) -> PackageResult:
        items = self._load_packages()
        index = next(
            (
                offset
                for offset, item in enumerate(items)
                if item.get("id") == package_id
            ),
            None,
        )
        if index is None:
            return PackageResult("NOT_FOUND")
        if items[index].get("locked") and not data.get("unlock"):
            return PackageResult("PACKAGE_LOCKED")

        items[index] = self.record(data, items[index])
        self._save_packages(items)
        return PackageResult("OK", {"package": items[index]})

    def delete(self, package_id: str) -> PackageResult:
        items = self._load_packages()
        package = next(
            (item for item in items if item.get("id") == package_id),
            None,
        )
        if package is None:
            return PackageResult("NOT_FOUND")
        if package.get("locked"):
            return PackageResult("PACKAGE_LOCKED")

        self._save_packages(
            [item for item in items if item.get("id") != package_id]
        )
        return PackageResult("OK", {"deleted": package_id})

    def duplicate(self, package_id: str) -> PackageResult:
        source = next(
            (
                item
                for item in self._load_packages()
                if item.get("id") == package_id
            ),
            None,
        )
        if source is None:
            return PackageResult("NOT_FOUND")

        data = copy.deepcopy(source)
        data.pop("id", None)
        data["name"] = f"{source.get('name', 'Broadcast Package')} Copy"
        data["locked"] = False
        data["status"] = "Planning"

        record = self.record(data)
        items = self._load_packages()
        items.append(record)
        self._save_packages(items)
        return PackageResult("OK", {"package": record})

    def load(self, package_id: str) -> PackageResult:
        items = self._load_packages()
        package = next(
            (item for item in items if item.get("id") == package_id),
            None,
        )
        if package is None:
            return PackageResult("NOT_FOUND")

        broadcast = next(
            (
                item
                for item in self._load_broadcasts()
                if item.get("broadcast_id") == package.get("broadcast_id")
            ),
            None,
        )
        if broadcast is None:
            return PackageResult("BROADCAST_NOT_FOUND")

        state = self._load_state()
        state.update(
            {
                "broadcast_created": True,
                "broadcast_id": broadcast.get("broadcast_id", ""),
                "sport": broadcast.get("sport", "Football"),
                "season": broadcast.get("season", ""),
                "week": broadcast.get("week", "1"),
                "classification": broadcast.get("classification", ""),
                "level": broadcast.get("level", "Varsity"),
                "division": broadcast.get("division", "Boys"),
                "home_school_id": broadcast.get("home_school_id", ""),
                "visitor_school_id": broadcast.get("visitor_school_id", ""),
                "home_team": broadcast.get("home_team", "Home"),
                "visitor_team": broadcast.get("visitor_team", "Visitor"),
                "home_identity": copy.deepcopy(
                    broadcast.get("home_identity", {})
                ),
                "visitor_identity": copy.deepcopy(
                    broadcast.get("visitor_identity", {})
                ),
                "venue": broadcast.get("venue", ""),
                "venue_id": broadcast.get("venue_id", ""),
                "date": broadcast.get("date", ""),
                "scheduled_start": broadcast.get("scheduled_start", ""),
                "visual_mode": broadcast.get("visual_mode", "graphic"),
                "crew": copy.deepcopy(broadcast.get("crew", {})),
                "status": broadcast.get("status", "planned"),
                "broadcast_package_id": package_id,
                "package_roster_ids": list(package.get("roster_ids", [])),
                "package_personnel_ids": list(
                    package.get("personnel_ids", [])
                ),
                "package_sponsor_ids": list(package.get("sponsor_ids", [])),
                "package_lineups": copy.deepcopy(package.get("lineups", {})),
                "graphics_profile": package.get(
                    "graphics_profile",
                    "CSRN Default",
                ),
            }
        )
        self._save_state(state)

        package["status"] = "Loaded"
        package["last_loaded_at"] = int(self._clock())
        package["health"] = self.health(package)
        self._save_packages(items)

        return PackageResult(
            "OK",
            {
                "package": package,
                "state": state,
                "health": package["health"],
            },
        )
