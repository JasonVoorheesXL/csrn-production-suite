from __future__ import annotations

import copy
import secrets
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable


Sponsor = dict[str, Any]
Asset = dict[str, Any]
SponsorLoader = Callable[[], list[Sponsor]]
SponsorSaver = Callable[[list[Sponsor]], None]
AssetLoader = Callable[[], list[Asset]]
Clock = Callable[[], float]
Today = Callable[[], date]
TokenFactory = Callable[[], str]


@dataclass(frozen=True)
class SponsorResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class SponsorService:
    """Sponsor-domain behavior independent of Flask and file uploads."""

    TRANSIENT_FIELDS = frozenset({"effective_status", "contract_expired"})

    def __init__(
        self,
        *,
        load_sponsors: SponsorLoader,
        save_sponsors: SponsorSaver,
        load_assets: AssetLoader,
        clock: Clock | None = None,
        today: Today | None = None,
        token_factory: TokenFactory | None = None,
    ) -> None:
        self._load_sponsors = load_sponsors
        self._save_sponsors = save_sponsors
        self._load_assets = load_assets
        self._clock = clock or time.time
        self._today = today or date.today
        self._token_factory = token_factory or (lambda: secrets.token_hex(3))

    def contract_state(self, record: Sponsor) -> str:
        """Return the effective status while preserving the stored status."""
        contract_end = str(record.get("contract_end", "")).strip()
        if contract_end:
            try:
                if date.fromisoformat(contract_end[:10]) < self._today():
                    return "Expired"
            except ValueError:
                pass
        return str(record.get("status", "Prospect"))

    def clean_record(
        self,
        data: Sponsor,
        sponsor_id: str | None = None,
    ) -> Sponsor:
        source = {
            key: value
            for key, value in copy.deepcopy(data).items()
            if key not in self.TRANSIENT_FIELDS
        }
        now = int(self._clock())
        lead_ins = source.get("lead_ins", [])
        if isinstance(lead_ins, str):
            lead_ins = [item.strip() for item in lead_ins.split(",") if item.strip()]
        elif not isinstance(lead_ins, list):
            lead_ins = []

        return {
            "id": sponsor_id
            or str(source.get("id") or f"sponsor-{now}-{self._token_factory()}"),
            "name": str(source.get("name", "")).strip()[:160],
            "category": str(source.get("category", "Local Business"))[:80],
            "status": str(source.get("status", "Prospect"))[:40],
            "contact_name": str(source.get("contact_name", "")).strip()[:160],
            "email": str(source.get("email", "")).strip()[:200],
            "phone": str(source.get("phone", "")).strip()[:80],
            "website": str(source.get("website", "")).strip()[:300],
            "contract_start": str(source.get("contract_start", ""))[:20],
            "contract_end": str(source.get("contract_end", ""))[:20],
            "package": str(source.get("package", "General Sponsor"))[:120],
            "lead_ins": [str(item).strip()[:120] for item in lead_ins if str(item).strip()][
                :12
            ],
            "asset_id": str(source.get("asset_id", ""))[:120],
            "logo_url": str(source.get("logo_url", ""))[:500],
            "notes": str(source.get("notes", ""))[:3000],
            "active": bool(source.get("active", True)),
            "created_at": int(source.get("created_at", now) or now),
            "updated_at": now,
        }

    def decorate(self, record: Sponsor) -> Sponsor:
        decorated = copy.deepcopy(record)
        decorated["effective_status"] = self.contract_state(decorated)
        decorated["contract_expired"] = decorated["effective_status"] == "Expired"
        return decorated

    def logo_assets(self) -> list[Asset]:
        return [
            copy.deepcopy(asset)
            for asset in self._load_assets()
            if asset.get("active", True)
            and asset.get("category") == "Sponsor"
            and asset.get("asset_type") == "Logo"
        ]

    def list_payload(self) -> dict[str, Any]:
        assets = {
            str(asset.get("id", "")): asset
            for asset in self._load_assets()
        }
        sponsors: list[Sponsor] = []
        for source in self._load_sponsors():
            sponsor = self.decorate(source)
            linked = assets.get(str(sponsor.get("asset_id", "")))
            if linked and linked.get("file_url"):
                sponsor["logo_url"] = linked.get("file_url", "")
                sponsor["asset_name"] = linked.get("name", "")
            sponsors.append(sponsor)
        return {"sponsors": sponsors, "logo_assets": self.logo_assets()}

    def create(self, incoming: Sponsor) -> SponsorResult:
        incoming = copy.deepcopy(incoming)
        record = self.clean_record(incoming)
        if not record["name"]:
            return SponsorResult("SPONSOR_NAME_REQUIRED")

        sponsors = self._load_sponsors()
        duplicate = self._duplicate_by_name(sponsors, record["name"])
        if duplicate is not None and not bool(incoming.get("confirm_duplicate", False)):
            return SponsorResult(
                "DUPLICATE_SPONSOR",
                {"duplicate_sponsor": self.decorate(duplicate)},
            )

        sponsors.append(record)
        self._save_sponsors(sponsors)
        return SponsorResult("OK", {"sponsor": copy.deepcopy(record)})

    def update(self, sponsor_id: str, incoming: Sponsor) -> SponsorResult:
        incoming = copy.deepcopy(incoming)
        sponsors = self._load_sponsors()
        current = self._find(sponsors, sponsor_id)
        if current is None:
            return SponsorResult("SPONSOR_NOT_FOUND")

        candidate_name = str(incoming.get("name", "")).strip()
        if candidate_name:
            duplicate = self._duplicate_by_name(
                sponsors,
                candidate_name,
                exclude_id=sponsor_id,
            )
            if duplicate is not None and not bool(
                incoming.get("confirm_duplicate", False)
            ):
                return SponsorResult(
                    "DUPLICATE_SPONSOR",
                    {"duplicate_sponsor": self.decorate(duplicate)},
                )

        replacement = self.clean_record({**current, **incoming}, sponsor_id)
        for index, item in enumerate(sponsors):
            if str(item.get("id", "")) == str(sponsor_id):
                sponsors[index] = replacement
                break
        self._save_sponsors(sponsors)
        return SponsorResult("OK", {"sponsor": copy.deepcopy(replacement)})

    def delete(self, sponsor_id: str) -> SponsorResult:
        sponsors = self._load_sponsors()
        if self._find(sponsors, sponsor_id) is None:
            return SponsorResult("SPONSOR_NOT_FOUND")
        self._save_sponsors(
            [
                sponsor
                for sponsor in sponsors
                if str(sponsor.get("id", "")) != str(sponsor_id)
            ],
            # Deleting a specific, named sponsor is an intentional,
            # operator-identified action -- distinct from a bulk write
            # accidentally wiping most/all sponsor entries, which the
            # repository's destructive-write guard exists to catch.
            force=True,
        )
        return SponsorResult("OK", {"ok": True})

    def link_asset(self, sponsor_id: str, asset_id: str) -> SponsorResult:
        asset_id = str(asset_id or "").strip()
        asset = self._asset_by_id(asset_id) if asset_id else None
        if asset_id and (
            asset is None
            or asset.get("category") != "Sponsor"
            or asset.get("asset_type") != "Logo"
        ):
            return SponsorResult("INVALID_SPONSOR_LOGO_ASSET")

        sponsors = self._load_sponsors()
        sponsor = self._find(sponsors, sponsor_id)
        if sponsor is None:
            return SponsorResult("SPONSOR_NOT_FOUND")

        sponsor["asset_id"] = asset_id
        sponsor["logo_url"] = asset.get("file_url", "") if asset else ""
        sponsor["updated_at"] = int(self._clock())
        self._save_sponsors(sponsors)
        return SponsorResult(
            "OK",
            {
                "sponsor": copy.deepcopy(sponsor),
                "asset": copy.deepcopy(asset) if asset else None,
            },
        )

    def active_sponsor_by_id(self, sponsor_id: str) -> Sponsor | None:
        sponsor_id = str(sponsor_id or "").strip()
        if not sponsor_id:
            return None
        source = self._find(self._load_sponsors(), sponsor_id)
        if source is None:
            return None
        sponsor = self.decorate(source)
        if sponsor.get("active", True) is False:
            return None
        if self.contract_state(sponsor) != "Active":
            return None

        asset = self._asset_by_id(str(sponsor.get("asset_id", "")))
        if asset and asset.get("active", True) and asset.get("file_url"):
            sponsor["logo_url"] = asset.get("file_url", "")
            sponsor["asset_name"] = asset.get("name", "")
        return sponsor

    def apply_to_graphic(
        self,
        graphic: dict[str, Any],
        incoming: dict[str, Any],
    ) -> SponsorResult:
        updated = copy.deepcopy(graphic)
        sponsor_id = str(
            incoming.get("sponsor_id", updated.get("sponsor_id", "")) or ""
        ).strip()
        updated["sponsor_id"] = sponsor_id
        warning = ""

        if sponsor_id:
            sponsor = self.active_sponsor_by_id(sponsor_id)
            if sponsor is None:
                updated["sponsor_id"] = ""
                updated["sponsor_name"] = ""
                updated["sponsor_logo"] = ""
                updated["sponsor_lead_in"] = ""
                warning = "SPONSOR_EXPIRED_OR_INACTIVE"
            else:
                lead_ins = sponsor.get("lead_ins", [])
                updated["sponsor_name"] = str(sponsor.get("name", ""))[:240]
                updated["sponsor_logo"] = str(sponsor.get("logo_url", ""))[:500]
                updated["sponsor_lead_in"] = str(
                    lead_ins[0]
                    if lead_ins
                    else incoming.get("sponsor_lead_in") or "Presented by:"
                )[:120]
        else:
            updated["sponsor_name"] = str(
                incoming.get("sponsor_name", updated.get("sponsor_name", "")) or ""
            )[:240]
            updated["sponsor_logo"] = str(
                incoming.get("sponsor_logo", updated.get("sponsor_logo", "")) or ""
            )[:500]
            updated["sponsor_lead_in"] = str(
                incoming.get(
                    "sponsor_lead_in",
                    updated.get("sponsor_lead_in", ""),
                )
                or ""
            )[:120]

        return SponsorResult(
            "OK",
            {"graphic": updated, "warning": warning},
        )

    @staticmethod
    def _find(sponsors: list[Sponsor], sponsor_id: str) -> Sponsor | None:
        target = str(sponsor_id or "")
        return next(
            (
                sponsor
                for sponsor in sponsors
                if str(sponsor.get("id", "")) == target
            ),
            None,
        )

    @staticmethod
    def _duplicate_by_name(
        sponsors: list[Sponsor],
        name: str,
        *,
        exclude_id: str = "",
    ) -> Sponsor | None:
        target = str(name or "").strip().casefold()
        if not target:
            return None
        return next(
            (
                sponsor
                for sponsor in sponsors
                if str(sponsor.get("id", "")) != str(exclude_id)
                and str(sponsor.get("name", "")).strip().casefold() == target
            ),
            None,
        )

    def _asset_by_id(self, asset_id: str) -> Asset | None:
        target = str(asset_id or "").strip()
        if not target:
            return None
        return next(
            (
                copy.deepcopy(asset)
                for asset in self._load_assets()
                if str(asset.get("id", "")) == target
            ),
            None,
        )
