"""Hotfix 2026-09-01: DragonFly stopped rendering an HTML <table> roster on
their Angular site, so the Playwright scrape returned an empty roster for
every school. get_roster() now reads DragonFly's public JSON summary API
(schools/<code>/summary), which still carries every team's full roster.

Offline test: a captured-shape summary payload in -> CSRN player records out.
"""
from __future__ import annotations

from contextlib import contextmanager

import dragonfly_service
from dragonfly_service import DragonFlyService


_SUMMARY = {
    "name": "Amory High School",
    "teams": [
        {
            "name": "Football",
            "level": "Varsity",
            "ncaaSportCode": "MFB",
            "totalAthleteCount": 2,
            "roster": [
                {
                    "firstName": "Dyllon",
                    "lastName": "Hall",
                    "rosterInfo": {
                        "height": {"feet": 6, "inches": 0},
                        "weight": 335,
                        "grade": "9",
                        "number": "63",
                        "position": "OL DL",
                    },
                },
                {
                    "firstName": "Jabari",
                    "lastName": "Brandon",
                    "rosterInfo": {
                        "height": {"feet": 5, "inches": 9},
                        "weight": 170,
                        "grade": "12",
                        "number": "17",
                        "position": "LB",
                    },
                },
            ],
        },
        {
            "name": "Football",
            "level": "Junior High",  # excluded from a CSRN program roster
            "ncaaSportCode": "MFB",
            "roster": [
                {"firstName": "Timmy", "lastName": "Small", "rosterInfo": {"grade": "7"}}
            ],
        },
        {
            "name": "Baseball",  # wrong sport
            "level": "Varsity",
            "ncaaSportCode": "MBA",
            "roster": [
                {"firstName": "Not", "lastName": "Football", "rosterInfo": {"number": "1"}}
            ],
        },
    ],
}


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payload):
        self._payload = payload
        self.requested = []

    def get(self, url):
        self.requested.append(url)
        return _FakeResponse(self._payload)


def _patched_service(monkeypatch, payload):
    service = DragonFlyService(timeout_seconds=5)
    fake = _FakeClient(payload)

    @contextmanager
    def _client(self):
        yield fake

    monkeypatch.setattr(DragonFlyService, "_client", _client)
    return service, fake


def test_get_roster_reads_the_json_summary_api(monkeypatch):
    service, fake = _patched_service(monkeypatch, _SUMMARY)

    result = service.get_roster("CCMH5Z", association="MHSAA", sport="FB")

    assert result.code == "OK", result.data
    assert result.data["player_count"] == 2
    # it hit the JSON API, not the Angular site
    assert fake.requested == [
        "https://maxinfosite-api-live.dragonflyathletics.com/schools/CCMH5Z/summary"
    ]

    players = {p["last_name"]: p for p in result.data["players"]}
    assert set(players) == {"Hall", "Brandon"}  # JH + Baseball excluded

    hall = players["Hall"]
    assert hall["number"] == "63"
    assert hall["position"] == "OL DL"
    assert hall["height"] == "6' 0\""
    assert hall["weight"] == "335"
    assert hall["grade"] == "9"
    assert hall["status"] == "active"
    assert hall["source_data"]["provider"] == "dragonfly-public"
    assert hall["source_levels"] == ["Varsity Football"]


def test_get_roster_empty_when_no_matching_team(monkeypatch):
    service, _ = _patched_service(monkeypatch, {"name": "X", "teams": []})
    result = service.get_roster("CCMH5Z", association="MHSAA", sport="FB")
    assert result.code == "DRAGONFLY_ROSTER_EMPTY"


def test_format_height_handles_partial_and_missing():
    assert DragonFlyService._format_height({"feet": 6, "inches": 0}) == "6' 0\""
    assert DragonFlyService._format_height({"feet": 5}) == "5' 0\""
    assert DragonFlyService._format_height({}) == ""
    assert DragonFlyService._format_height(None) == ""
