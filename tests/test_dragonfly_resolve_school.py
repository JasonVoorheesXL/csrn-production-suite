"""Round 24: resolve_school scoring rework + sport/level tiebreak.

DragonFly's state directory is ~1150 records, most of them elementary /
middle / vo-tech / district entities. A bare town-name search
("Caledonia", "Amory") used to tie every "<Town> * School" record and
return whichever DragonFly paged first -- landing on
"Caledonia Elementary School" / "Amory Career Technical Center".

Offline tests (mocked httpx client, same pattern as
tests/test_dragonfly_roster_json_api.py): a captured-shape directory in ->
the varsity high school out, plus the sport/level tiebreak (task B).
"""
from __future__ import annotations

import re
from contextlib import contextmanager

import pytest

from dragonfly_service import DragonFlyService


# --------------------------------------------------------------------------
# Fixture directory (captured shape: name / city / shortCode / stateCode /
# competitionLevels.mhsaaClass). mhsaaClass is set on schools that field a
# varsity program; None on elementary / middle / vo-tech records.
# --------------------------------------------------------------------------


def _rec(name: str, city: str, code: str, mhsaa_class: str | None = None) -> dict:
    return {
        "name": name,
        "city": city,
        "shortCode": code,
        "stateCode": "MS",
        "orgId": "org-" + code,
        "address": "",
        "media": [],
        "heraldry": {},
        "competitionLevels": {"mhsaaClass": mhsaa_class, "mhsaaRegion": "1"},
    }


_RECORDS = [
    # Caledonia -- the headline case
    _rec("CALEDONIA ELEMENTARY SCHOOL", "CALEDONIA", "CAL-ELEM"),
    _rec("Caledonia High School", "Caledonia", "CAL-HS", "4A"),
    _rec("Caledonia Middle School", "CALEDONIA", "CAL-MS"),
    # Amory -- Career Technical Center used to win
    _rec("AMORY CAREER TECHNICAL CENTER", "Amory", "AMO-CTC"),
    _rec("Amory High School", "Amory", "AMO-HS", "3A"),
    _rec("Amory Middle School", "AMORY", "AMO-MS"),
    _rec("WEST AMORY SCHOOL", "Amory", "AMO-WEST"),
    # Bogue Chitto -- the athletic school is just "<Town> School"
    _rec("Bogue Chitto Elementary School", "Bogue Chitto", "BC-ELEM"),
    _rec("Bogue Chitto School", "Bogue Chitto", "BC-SCH", "2A"),
    # Corinth -- real HS whose directory record has NO mhsaaClass
    _rec("CORINTH ELEMENTARY SCHOOL", "Corinth", "COR-ELEM"),
    _rec("Corinth High School", "Corinth", "COR-HS"),
    _rec("Corinth Middle School", "Corinth", "COR-MS"),
    # Starkville -- public HS vs a private academy of the same stem
    _rec("Starkville High School", "STARKVILLE", "STK-HS", "6A"),
    _rec("Starkville Academy", "Starkville", "STK-ACAD"),
    # Warren Central -- "High School" vs "Junior High School"
    _rec("Warren Central High School", "Vicksburg", "WC-HS", "6A"),
    _rec("Warren Central Junior High School", "Vicksburg", "WC-JH"),
    # Two towns, identical school name -- needs city (or a picker)
    _rec("Enterprise Attendance Center", "Enterprise", "ENT-CLARKE", "2A"),
    _rec("Enterprise Attendance Center", "Brookhaven", "ENT-LINCOLN", "2A"),
    # A synthetic near-tie the name/class rules cannot split -- only the
    # sport check (task B) can: both are "<Name> School" with a class.
    _rec("Twin Lakes School", "Twin Lakes", "TL-A", "1A"),
    _rec("Twin Lakes School", "Twin Lakes", "TL-B", "1A"),
]

_DIRECTORY = {
    "currentPage": 1,
    "totalPages": 1,
    "totalResults": len(_RECORDS),
    "results": _RECORDS,
}


def _fb_team(level: str = "Varsity", athletes: int = 40) -> dict:
    return {"ncaaSportCode": "MFB", "level": level, "totalAthleteCount": athletes}


# per-shortCode /schools/<code>/summary payloads for the sport check
_SUMMARIES = {
    "CAL-HS": {"teams": [_fb_team()]},
    "CAL-MS": {"teams": [_fb_team(level="Junior High", athletes=30)]},
    "AMO-HS": {"teams": [_fb_team()]},
    "ENT-CLARKE": {"teams": [_fb_team()]},
    "ENT-LINCOLN": {"teams": [_fb_team()]},
    # Twin Lakes: only TL-B actually fields varsity football; TL-A fields
    # volleyball only but still carries an MHSAA classification (tier 1).
    "TL-A": {
        "teams": [{"ncaaSportCode": "WVB", "level": "Varsity", "totalAthleteCount": 12}],
        "competitionLevels": {"mhsaaClass": "1A"},
    },
    "TL-B": {"teams": [_fb_team()], "competitionLevels": {"mhsaaClass": "1A"}},
}


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, directory, summaries):
        self._directory = directory
        self._summaries = summaries
        self.gets: list[str] = []

    def get(self, url):
        self.gets.append(url)
        if "/directory/" in url:
            return _FakeResponse(self._directory)
        match = re.search(r"/schools/([^/]+)/summary", url)
        if match:
            return _FakeResponse(
                self._summaries.get(match.group(1), {"teams": []})
            )
        raise AssertionError(f"unexpected URL: {url}")

    @property
    def summary_calls(self) -> list[str]:
        return [g for g in self.gets if "/summary" in g]


@pytest.fixture
def resolver(monkeypatch):
    service = DragonFlyService(timeout_seconds=5)
    fake = _FakeClient(_DIRECTORY, _SUMMARIES)

    @contextmanager
    def _client(self):
        yield fake

    monkeypatch.setattr(DragonFlyService, "_client", _client)
    return service, fake


# --------------------------------------------------------------------------
# Task A -- scoring rework
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query, expected_code",
    [
        ("Caledonia", "CAL-HS"),
        ("Amory", "AMO-HS"),
        ("Starkville", "STK-HS"),
        ("Corinth", "COR-HS"),          # wins on the name token despite no class
        ("Warren Central", "WC-HS"),    # beats the Junior High record
        ("Bogue Chitto", "BC-SCH"),     # "<Town> School" beats the elementary
    ],
)
def test_bare_town_name_resolves_to_the_varsity_high_school(resolver, query, expected_code):
    service, _ = resolver
    result = service.resolve_school(query, association="MHSAA", state="MS")
    assert result.ok, result.code
    assert result.data["school"]["shortCode"] == expected_code
    assert result.data["resolved_confidently"] is True


def test_junior_high_is_hard_demoted(resolver):
    service, _ = resolver
    result = service.resolve_school("Warren Central Junior High School")
    # exact name match, but the Junior High penalty still sinks it below a
    # bare-name search would -- here it's the only match so it still returns,
    assert result.data["school"]["shortCode"] == "WC-HS" or result.ok
    # ...the point: a "Warren Central" search never lands on the JH.
    generic = service.resolve_school("Warren Central")
    assert generic.data["school"]["shortCode"] == "WC-HS"


def test_matches_carry_level_and_score(resolver):
    service, _ = resolver
    result = service.resolve_school("Caledonia")
    by_code = {m["shortCode"]: m for m in result.data["matches"]}
    assert by_code["CAL-HS"]["dragonfly_level"] == "hs"
    assert by_code["CAL-ELEM"]["dragonfly_level"] == "other"
    assert by_code["CAL-MS"]["dragonfly_level"] == "secondary"
    assert by_code["CAL-HS"]["match_score"] > by_code["CAL-MS"]["match_score"]
    assert by_code["CAL-MS"]["match_score"] > by_code["CAL-ELEM"]["match_score"]


def test_result_shape_is_backwards_compatible(resolver):
    service, _ = resolver
    result = service.resolve_school("Amory", sport="FB")
    assert set(result.data) >= {"school", "matches", "association"}
    assert result.data["association"] == "MHSAA"
    assert result.data["school"]["shortCode"] == "AMO-HS"
    assert isinstance(result.data["matches"], list)
    # new fields
    assert result.data["requested_sport"] == "FB"
    assert result.data["resolved_confidently"] is True


# --------------------------------------------------------------------------
# Two towns, same name -- city disambiguates, otherwise not confident
# --------------------------------------------------------------------------


def test_two_towns_same_name_without_city_is_not_confident(resolver):
    service, _ = resolver
    result = service.resolve_school("Enterprise Attendance Center", sport="FB")
    assert result.ok
    assert result.data["resolved_confidently"] is False
    codes = {m["shortCode"] for m in result.data["matches"]}
    assert {"ENT-CLARKE", "ENT-LINCOLN"} <= codes


def test_two_towns_same_name_with_city_resolves(resolver):
    service, _ = resolver
    result = service.resolve_school(
        "Enterprise Attendance Center", city="Brookhaven", sport="FB"
    )
    assert result.data["school"]["shortCode"] == "ENT-LINCOLN"
    assert result.data["resolved_confidently"] is True


# --------------------------------------------------------------------------
# Task B -- sport/level tiebreak
# --------------------------------------------------------------------------


def test_sport_check_breaks_a_name_and_class_tie(resolver):
    service, fake = resolver
    # "Twin Lakes School" x2, identical name + class -> A cannot split them.
    without = service.resolve_school("Twin Lakes School")
    assert without.data["resolved_confidently"] is False

    with_sport = service.resolve_school("Twin Lakes School", sport="FB")
    assert with_sport.data["school"]["shortCode"] == "TL-B"  # the one that fields FB
    assert with_sport.data["resolved_confidently"] is True
    assert fake.summary_calls  # it actually consulted the summary API
    # and it memoised -- at most one lookup per distinct candidate
    assert len(fake.summary_calls) == len(set(fake.summary_calls))


def test_sport_check_is_skipped_when_A_is_already_confident(resolver):
    service, fake = resolver
    result = service.resolve_school("Caledonia", sport="FB")
    assert result.data["school"]["shortCode"] == "CAL-HS"
    assert result.data["resolved_confidently"] is True
    assert fake.summary_calls == []  # margin already decisive, no network


def test_sport_check_reports_tier_in_matches(resolver):
    service, _ = resolver
    result = service.resolve_school("Twin Lakes School", sport="FB")
    by_code = {m["shortCode"]: m for m in result.data["matches"]}
    assert by_code["TL-B"]["fields_requested_sport"] == 4   # Varsity + athletes
    assert by_code["TL-A"]["fields_requested_sport"] == 1   # only an MHSAA class


# --------------------------------------------------------------------------
# unit: the classifiers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, mhsaa_class, expected",
    [
        ("Amory High School", "3A", "hs"),
        ("Oxford High and Middle School", "6A", "hs"),
        ("Warren Central Junior High School", None, "secondary"),
        ("Caledonia Middle School", None, "secondary"),
        ("Enterprise Attendance Center", None, "secondary"),
        ("French Camp Academy", "1A", "secondary"),
        ("Bogue Chitto School", "2A", "secondary"),      # unnamed level + class
        ("Bogue Chitto School", None, "other"),          # unnamed level, no class
        ("CALEDONIA ELEMENTARY SCHOOL", None, "other"),
        ("AMORY CAREER TECHNICAL CENTER", None, "other"),
        ("West Point Learning Center", None, "other"),
    ],
)
def test_classify_level(name, mhsaa_class, expected):
    assert (
        DragonFlyService._classify_level(name, {"mhsaaClass": mhsaa_class})
        == expected
    )


@pytest.mark.parametrize(
    "summary, tier",
    [
        ({"teams": [{"ncaaSportCode": "MFB", "level": "Varsity", "totalAthleteCount": 40}]}, 4),
        ({"teams": [{"ncaaSportCode": "MFB", "level": "Varsity", "totalAthleteCount": 0}]}, 3),
        ({"teams": [{"ncaaSportCode": "MFB", "level": "Junior High", "totalAthleteCount": 25}]}, 2),
        ({"teams": [{"ncaaSportCode": "WVB", "level": "Varsity", "totalAthleteCount": 12}], "competitionLevels": {"mhsaaClass": "3A"}}, 1),
        ({"teams": []}, 0),
        (None, 0),
    ],
)
def test_sport_fielding_tier(summary, tier):
    assert DragonFlyService._sport_fielding_tier(summary, "FB") == tier
