"""Operator guides shipped with the app (2026-10-31).

The PDFs live in static/guides/ because static/ is what the Windows installer
ships. The Station Setup Guide is for every station; statistician guides are
per sport, and a station is offered the ones for the sports it has switched on
in Settings > Sports. A switched-on sport without its own guide yet is listed
as coming soon rather than pointed at another sport's guide.

To add a guide: drop the PDF in static/guides/ and add a line to GUIDES.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import sport_families

GUIDES: tuple[dict[str, str], ...] = (
    {
        "id": "station-setup",
        "title": "Station Setup Guide",
        "sport": "",
        "file": "station-setup-guide.pdf",
        "summary": "Install, first-run setup, your station's name and logo, schools, rosters, "
        "sponsors, OBS and your first game.",
    },
    {
        "id": "obs-setup",
        "title": "OBS Setup Guide",
        "sport": "",
        "file": "obs-setup-guide.pdf",
        "summary": "Import the ready-made scene collection, add your camera, background and sound, "
        "and connect OBS to the app.",
    },
    {
        "id": "statistician-football",
        "title": "Statistician Guide: Football",
        "sport": "football",
        "file": "statistician-guide-football.pdf",
        "summary": "A complete football game on the Statistician screen, play by play.",
    },
)

URL_PREFIX = "/static/guides/"


def guides_for(sports_on: Iterable[str], guides_dir: Path) -> list[dict[str, Any]]:
    """The guides to offer: every all-station guide, then one statistician
    entry per switched-on sport (a link when its PDF is present, otherwise
    coming soon)."""
    rows: list[dict[str, Any]] = []

    def entry(guide: dict[str, str]) -> dict[str, Any] | None:
        if not (guides_dir / guide["file"]).is_file():
            return None
        return {**guide, "url": URL_PREFIX + guide["file"], "available": True}

    for guide in GUIDES:
        if not guide["sport"]:
            row = entry(guide)
            if row:
                rows.append(row)
    for sport in sports_on:
        found = [row for guide in GUIDES if guide["sport"] == sport if (row := entry(guide))]
        if found:
            rows.extend(found)
            continue
        label = sport_families.LABELS.get(sport, sport.title())
        rows.append(
            {
                "id": f"statistician-{sport}",
                "title": f"Statistician Guide: {label}",
                "sport": sport,
                "summary": f"The {label.lower()} statistician guide is coming in a future update.",
                "url": "",
                "available": False,
            }
        )
    return rows
