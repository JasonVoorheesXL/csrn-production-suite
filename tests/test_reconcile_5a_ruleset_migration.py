"""Round 7 Task B step 5 (consumer 2): app.reconcile_5a_csrn_ids() takes the
reserved IDs and the id format from the us-ms-mhsaa ruleset instead of
literals -- output must be identical.
"""

from __future__ import annotations

import app
import ruleset_service


def _schools():
    return [
        {"official_name": "New Hope High School", "state": "MS", "classification": "5A"},
        {"official_name": "Caledonia High School", "state": "MS", "classification": "5A"},
        {"official_name": "West Point High School", "state": "MS", "classification": "5A"},
        {"official_name": "Center Hill High School", "state": "MS", "classification": "5A"},
        {"official_name": "Somewhere 6A", "state": "MS", "classification": "6A"},  # ignored
        {"official_name": "Alabama 5A", "state": "AL", "classification": "5A"},    # ignored
    ]


def test_reserved_ids_and_ordering_are_byte_identical_to_the_old_literals():
    schools = _schools()
    changed = app.reconcile_5a_csrn_ids(schools)
    assert changed is True
    by_name = {s["official_name"]: s.get("csrn_id") for s in schools}
    assert by_name["Caledonia High School"] == "MS5A-001"   # reserved
    assert by_name["New Hope High School"] == "MS5A-002"     # reserved
    assert by_name["Center Hill High School"] == "MS5A-003"  # then alphabetical
    assert by_name["West Point High School"] == "MS5A-004"
    assert by_name["Somewhere 6A"] is None                   # not 5A
    assert by_name["Alabama 5A"] is None                     # not MS

    # idempotent
    assert app.reconcile_5a_csrn_ids(schools) is False


def test_the_reserved_mapping_comes_from_the_ruleset():
    cls_rules = ruleset_service.resolve(
        country="US", region="MS", association="MHSAA", sport="football"
    )["classification"]
    assert cls_rules["reserved_ids"] == {"MS5A-001": "caledonia", "MS5A-002": "new-hope"}
    fmt, reserved = app._five_a_classification_rules()
    assert fmt == "{state}{class}-{seq:03d}"
    assert reserved == [("MS5A-001", "caledonia"), ("MS5A-002", "new-hope")]
    assert fmt.format_map({"state": "MS", "class": "5A", "seq": 1}) == "MS5A-001"


def test_falls_back_to_literals_if_the_ruleset_engine_is_unavailable(monkeypatch):
    def boom(**_kw):
        raise RuntimeError("no rulesets")

    monkeypatch.setattr(ruleset_service, "resolve", boom)
    fmt, reserved = app._five_a_classification_rules()
    assert fmt == "{state}{class}-{seq:03d}"
    assert reserved == [("MS5A-001", "caledonia"), ("MS5A-002", "new-hope")]

    schools = _schools()
    app.reconcile_5a_csrn_ids(schools)
    assert {s["official_name"]: s.get("csrn_id") for s in schools}["Caledonia High School"] == "MS5A-001"


def test_no_5a_schools_is_a_noop():
    assert app.reconcile_5a_csrn_ids([{"official_name": "X", "state": "MS", "classification": "6A"}]) is False
