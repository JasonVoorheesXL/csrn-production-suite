from __future__ import annotations

import copy
import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


Asset = dict[str, Any]
AssetLoader = Callable[[], list[Asset]]
AssetSaver = Callable[[list[Asset]], None]
Clock = Callable[[], float]


ALLOWED_ASSET_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".gif",
    ".mp4",
    ".webm",
    ".mp3",
    ".wav",
    ".pdf",
}


@dataclass(frozen=True)
class AssetResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class AssetService:
    """Asset-domain behavior independent of Flask and physical upload storage."""

    PLACEMENTS = {
        "flexible",
        "sponsor_feature_still",
        "sponsor_feature_video",
        "lower_third_sponsor",
        "scorebug_sponsor",
        "player_highlight_video",
        "full_screen_master",
    }

    @classmethod
    def normalize_placement(cls, value: Any) -> str:
        placement = str(value or "flexible").strip().lower()
        return placement if placement in cls.PLACEMENTS else "flexible"

    def __init__(
        self,
        *,
        load_assets: AssetLoader,
        save_assets: AssetSaver,
        clock: Clock | None = None,
    ) -> None:
        self._load_assets = load_assets
        self._save_assets = save_assets
        self._clock = clock or time.time

    @staticmethod
    def normalize_id(value: Any) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "").strip())
        return cleaned.strip("-") or "asset"

    @staticmethod
    def extension_allowed(filename: Any) -> bool:
        return Path(str(filename or "")).suffix.lower() in ALLOWED_ASSET_EXTENSIONS

    @staticmethod
    def file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _boolean(value: Any, default: bool = True) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    @classmethod
    def migrate_record(cls, item: Asset) -> Asset:
        source = copy.deepcopy(item if isinstance(item, dict) else {})
        now = int(time.time())
        created_at = int(source.get("created_at", now) or now)
        updated_at = int(source.get("updated_at", created_at) or created_at)
        return {
            "id": str(source.get("id") or cls.normalize_id(source.get("name") or "asset")),
            "name": str(source.get("name", "")).strip(),
            "category": str(source.get("category", "Other")).strip() or "Other",
            "asset_type": str(source.get("asset_type", "Other")).strip() or "Other",
            "placement": cls.normalize_placement(source.get("placement")),
            "sponsor_id": str(source.get("sponsor_id", "")).strip(),
            "roster_id": str(source.get("roster_id", "")).strip(),
            "player_id": str(source.get("player_id", "")).strip(),
            "season": str(source.get("season", "")).strip(),
            "file_url": str(source.get("file_url", "")).strip(),
            "source_url": str(source.get("source_url", "")).strip(),
            "rights_status": str(source.get("rights_status", "Unverified")).strip() or "Unverified",
            "rights_owner": str(source.get("rights_owner", "")).strip(),
            "notes": str(source.get("notes", "")).strip(),
            "active": cls._boolean(source.get("active"), True),
            "sha256": str(source.get("sha256", "")).strip(),
            "original_filename": str(source.get("original_filename", "")).strip(),
            "created_at": created_at,
            "updated_at": updated_at,
        }

    def _records(self) -> list[Asset]:
        source = self._load_assets()
        records = [self.migrate_record(item) for item in source if isinstance(item, dict)]
        if records != source:
            self._save_assets(records)
        return records

    @staticmethod
    def _find(records: list[Asset], asset_id: str) -> Asset | None:
        target = str(asset_id or "").strip()
        return next(
            (record for record in records if str(record.get("id", "")).strip() == target),
            None,
        )

    def clean_record(
        self,
        incoming: Asset,
        existing_id: str = "",
        *,
        existing: Asset | None = None,
    ) -> Asset:
        source = copy.deepcopy(existing or {})
        source.update(copy.deepcopy(incoming or {}))
        now = int(self._clock())
        asset_id = str(existing_id or source.get("id") or f"asset-{now * 1000}")
        return {
            "id": asset_id,
            "name": str(source.get("name", "")).strip(),
            "category": str(source.get("category", "Other")).strip() or "Other",
            "asset_type": str(source.get("asset_type", "Other")).strip() or "Other",
            "placement": self.normalize_placement(source.get("placement")),
            "sponsor_id": str(source.get("sponsor_id", "")).strip(),
            "roster_id": str(source.get("roster_id", "")).strip(),
            "player_id": str(source.get("player_id", "")).strip(),
            "season": str(source.get("season", "")).strip(),
            "file_url": str(source.get("file_url", "")).strip(),
            "source_url": str(source.get("source_url", "")).strip(),
            "rights_status": str(source.get("rights_status", "Unverified")).strip() or "Unverified",
            "rights_owner": str(source.get("rights_owner", "")).strip(),
            "notes": str(source.get("notes", "")).strip(),
            "active": self._boolean(source.get("active"), True),
            "sha256": str(source.get("sha256", "")).strip(),
            "original_filename": str(source.get("original_filename", "")).strip(),
            "created_at": int(source.get("created_at", now) or now),
            "updated_at": now,
        }

    def list_records(
        self,
        *,
        include_inactive: bool = True,
        category: str = "",
        asset_type: str = "",
        rights_status: str = "",
        placement: str = "",
    ) -> AssetResult:
        category_key = str(category or "").strip().casefold()
        type_key = str(asset_type or "").strip().casefold()
        rights_key = str(rights_status or "").strip().casefold()
        placement_key = str(placement or "").strip().casefold()
        rows: list[Asset] = []
        for record in self._records():
            if not include_inactive and not record.get("active", True):
                continue
            if category_key and str(record.get("category", "")).casefold() != category_key:
                continue
            if type_key and str(record.get("asset_type", "")).casefold() != type_key:
                continue
            if rights_key and str(record.get("rights_status", "")).casefold() != rights_key:
                continue
            if placement_key and str(record.get("placement", "")).casefold() != placement_key:
                continue
            rows.append(copy.deepcopy(record))
        rows.sort(
            key=lambda record: (
                str(record.get("name", "")).casefold(),
                str(record.get("id", "")),
            )
        )
        return AssetResult("OK", {"assets": rows})

    def list_payload(self, **filters: Any) -> dict[str, Any]:
        return self.list_records(**filters).data

    def read(self, asset_id: str) -> AssetResult:
        record = self._find(self._records(), asset_id)
        if record is None:
            return AssetResult("ASSET_NOT_FOUND")
        return AssetResult("OK", {"asset": copy.deepcopy(record)})

    def create(self, incoming: Asset) -> AssetResult:
        record = self.clean_record(incoming)
        if not record["name"]:
            return AssetResult("ASSET_NAME_REQUIRED")
        records = self._records()
        base_id = self.normalize_id(record["id"])
        candidate = base_id
        suffix = 2
        while self._find(records, candidate) is not None:
            candidate = f"{base_id}-{suffix}"
            suffix += 1
        record["id"] = candidate
        records.append(record)
        self._save_assets(records)
        return AssetResult("OK", {"asset": copy.deepcopy(record)})

    def update(self, asset_id: str, incoming: Asset) -> AssetResult:
        records = self._records()
        current = self._find(records, asset_id)
        if current is None:
            return AssetResult("ASSET_NOT_FOUND")
        replacement = self.clean_record(
            incoming,
            str(asset_id),
            existing=current,
        )
        if not replacement["name"]:
            return AssetResult("ASSET_NAME_REQUIRED")
        for index, record in enumerate(records):
            if str(record.get("id", "")) == str(asset_id):
                records[index] = replacement
                break
        self._save_assets(records)
        return AssetResult("OK", {"asset": copy.deepcopy(replacement)})

    def delete(self, asset_id: str) -> AssetResult:
        records = self._records()
        if self._find(records, asset_id) is None:
            return AssetResult("ASSET_NOT_FOUND")
        self._save_assets(
            [record for record in records if str(record.get("id", "")) != str(asset_id)]
        )
        return AssetResult("OK", {"ok": True, "deleted": str(asset_id)})

    def duplicate_by_hash(
        self,
        sha256: Any,
        *,
        exclude_id: str = "",
    ) -> Asset | None:
        target = str(sha256 or "").strip().lower()
        if not target:
            return None
        excluded = str(exclude_id or "").strip()
        return next(
            (
                copy.deepcopy(record)
                for record in self._records()
                if str(record.get("id", "")) != excluded
                and record.get("active", True)
                and str(record.get("sha256", "")).strip().lower() == target
            ),
            None,
        )

    def attach_file(
        self,
        asset_id: str,
        *,
        file_url: str,
        sha256: str,
        original_filename: str,
    ) -> AssetResult:
        records = self._records()
        record = self._find(records, asset_id)
        if record is None:
            return AssetResult("ASSET_NOT_FOUND")
        record.update(
            {
                "file_url": str(file_url or "").strip(),
                "sha256": str(sha256 or "").strip(),
                "original_filename": str(original_filename or "").strip(),
                "updated_at": int(self._clock()),
            }
        )
        self._save_assets(records)
        return AssetResult("OK", {"asset": copy.deepcopy(record)})

    def reuse_duplicate(
        self,
        pending_asset_id: str,
        duplicate_asset_id: str,
    ) -> AssetResult:
        records = self._records()
        pending = self._find(records, pending_asset_id)
        duplicate = self._find(records, duplicate_asset_id)
        if pending is None:
            return AssetResult("ASSET_NOT_FOUND")
        if duplicate is None:
            return AssetResult("DUPLICATE_ASSET_NOT_FOUND")
        records = [
            record
            for record in records
            if str(record.get("id", "")) != str(pending_asset_id)
        ]
        self._save_assets(records)
        return AssetResult(
            "OK",
            {
                "asset": copy.deepcopy(duplicate),
                "duplicate_asset": copy.deepcopy(duplicate),
                "duplicate_reused": True,
                "pending_asset_removed": True,
            },
        )

    def replace_duplicate(
        self,
        pending_asset_id: str,
        duplicate_asset_id: str,
        *,
        file_url: str,
        sha256: str,
        original_filename: str,
    ) -> AssetResult:
        records = self._records()
        pending = self._find(records, pending_asset_id)
        duplicate = self._find(records, duplicate_asset_id)
        if pending is None:
            return AssetResult("ASSET_NOT_FOUND")
        if duplicate is None:
            return AssetResult("DUPLICATE_ASSET_NOT_FOUND")
        duplicate.update(
            {
                "file_url": str(file_url or "").strip(),
                "sha256": str(sha256 or "").strip(),
                "original_filename": str(original_filename or "").strip(),
                "updated_at": int(self._clock()),
            }
        )
        records = [
            record
            for record in records
            if str(record.get("id", "")) != str(pending_asset_id)
        ]
        self._save_assets(records)
        return AssetResult(
            "OK",
            {
                "asset": copy.deepcopy(duplicate),
                "duplicate_asset": copy.deepcopy(duplicate),
                "duplicate_replaced": True,
                "pending_asset_removed": True,
            },
        )
