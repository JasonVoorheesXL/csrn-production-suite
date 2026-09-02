"""Round 25: DragonFly school disambiguation picker (C/D backend).

When resolve_school can't pick confidently, preview_school returns
DRAGONFLY_SCHOOL_AMBIGUOUS + a candidate list instead of guessing. The
operator picks one; every route accepts an optional dragonfly_school_code
that skips resolution entirely, and a successful roster apply persists the
pick onto the CSRN school record so it never flips again.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest
from flask import Flask

import dragonfly_service as dfs
from dragonfly_service import DragonFlyService
from dragonfly_sync_service import DragonFlySyncService
from routes.association_routes import (
    AssociationRoutesDependencies,
    association_error_status,
    create_association_blueprint,
)


# ==========================================================================
# offline httpx fake: routes /directory/ and /schools/<code>/summary
# ==========================================================================


def _dir_record(name, city, code, mhsaa_class=None):
    return {
        "name": name,
        "city": city,
        "shortCode": code,
        "stateCode": "MS",
        "orgId": "org-" + code,
        "address": "",
        "media": [],
        "heraldry": {},
        "competitionLevels": {"mhsaaClass": mhsaa_class},
    }


def _fb_summary(name, code, mhsaa_class="3A", athletes=40, city="Testville"):
    return {
        "name": name,
        "shortCode": code,
        "stateCode": "MS",
        "id": "id-" + code,
        "address": {"address1": "1 Main St", "city": city, "state": "MS", "zip": "00000"},
        "competitionLevels": {"mhsaaClass": mhsaa_class, "mhsaaRegion": "1"},
        "heraldry": {"mascot": "Tigers", "colors": [{"code": "#111111"}, {"code": "#eeeeee"}]},
        "media": [{"purpose": "logo600", "$url": "https://x/logo.png"}],
        "teams": [
            {"name": "Football", "level": "Varsity", "ncaaSportCode": "MFB",
             "totalAthleteCount": athletes,
             "roster": [
                 {"firstName": "Sam", "lastName": "Player",
                  "rosterInfo": {"number": "7", "position": "QB", "grade": "11",
                                 "height": {"feet": 6, "inches": 0}, "weight": 180}},
             ]},
        ],
    }


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._p


class _FakeClient:
    def __init__(self, directory, summaries):
        self._directory = directory
        self._summaries = summaries
        self.gets: list[str] = []

    def get(self, url):
        self.gets.append(url)
        if "/directory/" in url:
            return _Resp(self._directory)
        m = re.search(r"/schools/([^/]+)/summary", url)
        if m:
            return _Resp(self._summaries.get(m.group(1), {"teams": []}))
        raise AssertionError(f"unexpected URL: {url}")

    @property
    def directory_gets(self):
        return [g for g in self.gets if "/directory/" in g]


def _install_fake(monkeypatch, directory, summaries):
    fake = _FakeClient(directory, summaries)

    @contextmanager
    def _client(self):
        yield fake

    monkeypatch.setattr(DragonFlyService, "_client", _client)
    return fake


# --------------------------------------------------------------------------
# C -- preview_school: ambiguous -> DRAGONFLY_SCHOOL_AMBIGUOUS + candidates
# --------------------------------------------------------------------------


_TIE_DIRECTORY = {
    "currentPage": 1,
    "totalPages": 1,
    "results": [
        _dir_record("North Central High School", "Alpha", "NC1", "3A"),
        _dir_record("South Central High School", "Beta", "SC1", "3A"),
        _dir_record("Central Elementary School", "Gamma", "CE1", None),
    ],
}
_TIE_SUMMARIES = {
    "NC1": _fb_summary("North Central High School", "NC1", "3A", 42, "Alpha"),
    "SC1": _fb_summary("South Central High School", "SC1", "3A", 38, "Beta"),
    "CE1": {"name": "Central Elementary School", "teams": []},
}


def test_preview_school_returns_ambiguous_with_a_candidate_list(monkeypatch):
    _install_fake(monkeypatch, _TIE_DIRECTORY, _TIE_SUMMARIES)
    service = DragonFlyService(timeout_seconds=5)

    result = service.preview_school("Central", association="MHSAA", state="MS", sport="FB")

    assert result.code == "DRAGONFLY_SCHOOL_AMBIGUOUS"
    codes = {c["shortCode"] for c in result.data["candidates"]}
    assert {"NC1", "SC1"} <= codes
    by_code = {c["shortCode"]: c for c in result.data["candidates"]}
    assert by_code["NC1"]["class"] == "3a"
    assert by_code["NC1"]["fields_sport"] is True
    assert by_code["CE1"]["fields_sport"] is False  # elementary, no varsity FB
    assert set(by_code["NC1"]) >= {"name", "city", "class", "shortCode", "fields_sport"}
    assert result.data["query"]["school_name"] == "Central"
    assert result.data["query"]["sport"] == "FB"


def test_preview_school_code_bypass_never_touches_the_directory(monkeypatch):
    fake = _install_fake(
        monkeypatch,
        {"totalPages": 1, "results": []},
        {"AMORYHS": _fb_summary("Amory High School", "AMORYHS", "3A", 77, "Amory")},
    )
    service = DragonFlyService(timeout_seconds=5)

    result = service.preview_school(
        "does not matter", association="MHSAA", state="MS", sport="FB",
        dragonfly_school_code="AMORYHS",
    )

    assert result.code == "OK"
    assert result.data["player_count"] == 1
    assert result.data["school"]["official_name"] == "Amory High School"
    assert result.data["school"]["source_data"]["dragonfly_school_code"] == "AMORYHS"
    assert result.data["resolution"]["bypassed_directory_search"] is True
    assert fake.directory_gets == []  # the whole point


def test_ambiguity_candidates_shape():
    matches = [
        {"name": "A HS", "city": "X", "shortCode": "A1",
         "competitionLevels": {"mhsaaClass": "4A"},
         "dragonfly_level": "hs", "match_score": 540, "fields_requested_sport": 4},
        {"name": "A Elementary", "city": "X", "shortCode": "A2",
         "competitionLevels": {"mhsaaClass": None},
         "dragonfly_level": "other", "match_score": 60},
    ]
    out = DragonFlyService._ambiguity_candidates(matches)
    assert out[0] == {
        "name": "A HS", "city": "X", "class": "4a", "shortCode": "A1",
        "level": "hs", "match_score": 540, "fields_sport": True,
    }
    assert out[1]["class"] is None
    assert out[1]["fields_sport"] is None  # no sport signal computed


def test_summary_as_directory_record_maps_the_fields():
    rec = DragonFlyService._summary_as_directory_record(
        {"name": "Foo HS", "shortCode": "F1", "stateCode": "MS", "id": "abc",
         "address": {"address1": "9 Rd", "city": "Fo"},
         "competitionLevels": {"mhsaaClass": "2A"}}
    )
    assert rec["name"] == "Foo HS"
    assert rec["shortCode"] == "F1"
    assert rec["city"] == "Fo"
    assert rec["orgId"] == "abc"
    assert rec["address"] == "9 Rd"
    assert rec["competitionLevels"]["mhsaaClass"] == "2A"


# --------------------------------------------------------------------------
# C -- sync service: stored code is reused; a roster apply persists the pick
# --------------------------------------------------------------------------


@dataclass
class _StubDFResult:
    code: str
    data: dict = field(default_factory=dict)

    @property
    def ok(self):
        return self.code == "OK"


class _StubDragonfly:
    def __init__(self, result):
        self._result = result
        self.calls: list[dict] = []

    def preview_school(self, school_name, **kwargs):
        self.calls.append({"school_name": school_name, **kwargs})
        return self._result


def _good_preview_data():
    return {
        "school": {"official_name": "Test HS", "source_data": {"dragonfly_school_code": ""}},
        "players": [{"first_name": "Sam", "last_name": "Player", "grade": "11", "number": "7"}],
        "player_count": 1,
        "warnings": [],
        "source": {},
    }


def test_sync_preview_reuses_a_code_stored_on_the_csrn_school(monkeypatch):
    stub = _StubDragonfly(_StubDFResult("OK", _good_preview_data()))
    schools = [
        {"id": "s1", "official_name": "Test HS",
         "source_data": {"dragonfly_school_code": "STOREDCODE"}}
    ]
    rosters = [
        {"id": "r1", "school_id": "s1", "sport": "Football", "season": "2026",
         "level": "Varsity", "division": "Boys", "players": []}
    ]
    sync = DragonFlySyncService(
        dragonfly_service=stub,
        load_schools=lambda: schools,
        load_rosters=lambda: rosters,
        save_rosters=lambda x: None,
    )

    sync.preview("Test HS", school_id="s1")

    assert stub.calls[-1]["dragonfly_school_code"] == "STOREDCODE"


def test_replace_roster_stamps_the_operator_pick_onto_the_school(monkeypatch):
    preview_data = _good_preview_data()
    preview_data["roster"] = {
        "existing_roster_id": "r1",
        "added": [{"player": {"first_name": "Sam", "last_name": "Player", "grade": "11", "number": "7"}}],
        "changed": [],
        "matched": [],
        "ambiguous": [],
    }
    preview_data["school"] = {"official_name": "Test HS", "differences": {}}
    stub = _StubDragonfly(_StubDFResult("OK", preview_data))

    schools = [{"id": "s1", "official_name": "Test HS", "source_data": {}}]
    rosters = [{
        "id": "r1", "school_id": "s1",
        "sport": "Football", "season": "2026", "level": "Varsity", "division": "Boys",
        "players": [
            {"first_name": "Old", "last_name": "One", "grade": "12"},
            {"first_name": "Old", "last_name": "Two", "grade": "12"},
        ],
    }]
    saved_schools: list[list] = []

    sync = DragonFlySyncService(
        dragonfly_service=stub,
        load_schools=lambda: schools,
        load_rosters=lambda: rosters,
        save_rosters=lambda x: None,
        save_schools=lambda s: saved_schools.append(s),
    )

    result = sync.replace_roster(
        "Test HS", approved=True, school_id="s1", dragonfly_school_code="PICKED99"
    )

    assert result.ok, result.code
    assert saved_schools, "save_schools was never called"
    stamped = next(s for s in saved_schools[-1] if s["id"] == "s1")
    assert stamped["source_data"]["dragonfly_school_code"] == "PICKED99"


def test_stamp_is_a_safe_noop_without_save_schools():
    sync = DragonFlySyncService(
        dragonfly_service=_StubDragonfly(_StubDFResult("OK", {})),
        load_schools=lambda: [{"id": "s1", "source_data": {}}],
        load_rosters=lambda: [],
        save_rosters=lambda x: None,
    )
    sync._stamp_dragonfly_code("s1", "CODE")  # must not raise


# --------------------------------------------------------------------------
# D backend -- the routes: 409 + candidates on ambiguous, code passthrough
# --------------------------------------------------------------------------


def test_association_error_status_maps_ambiguous_to_409():
    assert association_error_status("DRAGONFLY_SCHOOL_AMBIGUOUS") == 409


class _RouteStubDF:
    def __init__(self):
        self.last_kwargs: dict = {}
        self.result = _StubDFResult(
            "DRAGONFLY_SCHOOL_AMBIGUOUS",
            {
                "candidates": [
                    {"name": "North Central HS", "city": "Alpha", "class": "3A",
                     "shortCode": "NC1", "fields_sport": True},
                ],
                "query": {"school_name": "Central", "sport": "FB"},
            },
        )

    def preview_school(self, school_name, **kwargs):
        self.last_kwargs = {"school_name": school_name, **kwargs}
        return self.result


@pytest.fixture
def route_client():
    df = _RouteStubDF()

    def passthrough_auth(fn):
        return fn

    app = Flask(__name__)
    app.register_blueprint(
        create_association_blueprint(
            AssociationRoutesDependencies(
                require_auth=passthrough_auth,
                get_profile_service=lambda: None,
                get_workflow_service=lambda: None,
                get_import_service=lambda: None,
                get_supplement_service=lambda: None,
                get_dragonfly_service=lambda: df,
                get_dragonfly_sync_service=lambda: None,
                get_school_service=lambda: None,
                load_mhsaa_profile=lambda: {},
                load_mhsaa_manifest=lambda: {},
                load_mhsaa_branding_manifest=lambda: {},
                load_mhsaa_enrichment_manifest=lambda: {},
            )
        )
    )
    with app.test_client() as client:
        yield client, df


def test_preview_route_returns_409_with_candidates_on_ambiguous(route_client):
    client, _ = route_client
    response = client.post(
        "/api/imports/dragonfly/preview", json={"school_name": "Central"}
    )
    assert response.status_code == 409
    body = response.get_json()
    assert body["error"] == "DRAGONFLY_SCHOOL_AMBIGUOUS"
    assert body["candidates"][0]["shortCode"] == "NC1"
    assert body["query"]["school_name"] == "Central"


def test_preview_route_forwards_dragonfly_school_code(route_client):
    client, df = route_client
    df.result = _StubDFResult("OK", {"school": {}, "players": [], "player_count": 0})
    response = client.post(
        "/api/imports/dragonfly/preview",
        json={"school_name": "Amory", "dragonfly_school_code": "CCMH5Z"},
    )
    assert response.status_code == 200
    assert df.last_kwargs["dragonfly_school_code"] == "CCMH5Z"


# --------------------------------------------------------------------------
# D -- the picker UI wiring in templates/index.html
# --------------------------------------------------------------------------


def _index_html() -> str:
    from pathlib import Path

    return (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(
        encoding="utf-8"
    )


def test_index_html_has_the_school_picker_wiring():
    html = _index_html()
    # the picker renderer + its "Use this school" action
    assert "function renderDragonFlySchoolPicker(" in html
    assert "function dragonflyUsePickedSchool(" in html
    assert "association-team-picker" in html  # reuses the existing picker style
    # both panels catch DRAGONFLY_SCHOOL_AMBIGUOUS and show the picker
    assert html.count("DRAGONFLY_SCHOOL_AMBIGUOUS") >= 2
    assert "renderDragonFlySchoolPicker(\n        document.getElementById('dragonflyRosterResults')" in html
    assert "renderDragonFlySchoolPicker(\n        document.getElementById('dragonflySchoolInfoResults')" in html
    # the pick is resubmitted as dragonfly_school_code
    assert "dragonfly_school_code: dragonflyRosterSchoolCode" in html
    assert "dragonfly_school_code: dragonflySchoolInfoSchoolCode" in html
    # radio-select, mirroring the "ambiguous players" review affordance
    assert 'name="dfSchoolPick"' in html
    assert "'✓ fields Football'" in html and "'✗ no Football team'" in html


def test_index_html_clears_the_pick_when_the_roster_changes():
    html = _index_html()
    assert "dragonflyRosterSchoolCode='';document.getElementById('rosterEmpty')" in html
