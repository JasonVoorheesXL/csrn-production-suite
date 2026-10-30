"""Issues 7-9 from the 10-game simulation (2026-10-30).

7. Penalty picker: a search box that knows what stat crews call a foul ("12 men
   on the field", "substitution infraction", "illegal procedure", "KCI"), and
   the fouls that were missing from the list.
8. The wrong-arrow warning ignores a TEAM run losing a yard or two: that is how
   stat crews write a victory-formation kneel (D6: three of them in a row).
9. The no-ball-carrier question offers Kneel.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from penalty_service import PenaltyService
from tests.test_rules_service import base_state, build_service

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")


def _catalog() -> dict[str, list[str]]:
    block = re.search(r"penaltyCatalog=\{(.*?)\};", HTML, re.S).group(1)
    units = {}
    for unit, body in re.findall(r"'?([A-Za-z ]+)'?:\[(\[.*?\])\]", block):
        units[unit.strip()] = re.findall(r"\['([^']+)',\d+\]", body)
    return units


def test_the_missing_fouls_are_in_the_list_and_the_rule_tables() -> None:
    catalog = _catalog()
    assert {"Illegal Procedure", "Illegal Substitution"} <= set(catalog["Offensive"])
    assert "Illegal Substitution" in catalog["Defensive"]
    assert {"Illegal Procedure", "Illegal Substitution", "Face Mask", "Unsportsmanlike Conduct"} <= set(catalog["Special Teams"])
    nfhs = json.loads((ROOT / "rulesets" / "football" / "us-nfhs.json").read_text(encoding="utf-8"))
    for key in ("Offensive/Illegal Procedure", "Special Teams/Illegal Substitution", "Special Teams/Face Mask"):
        assert key in json.dumps(nfhs), key
    assert PenaltyService.RULES[("Special Teams", "Illegal Procedure")]["yards"] == 5


def test_every_alias_points_at_a_penalty_in_the_list() -> None:
    names = {n for ns in _catalog().values() for n in ns}
    aliases = re.search(r"const PENALTY_ALIASES=(\[.*?\]\]\]);", HTML).group(1)
    for target in re.findall(r"'([A-Z][^']+)'", aliases):
        assert target in names, target


def test_the_search_boxes_are_wired() -> None:
    for needle in ('id="penaltySearch"', 'oninput="searchPenalty(this.value)"', 'id="playFlagSearch"',
                   "function findPenalty(query,units,preferUnit)", "function searchFlagPenalty(query)",
                   "['12 men',['Illegal Participation']]", "['substitution',['Illegal Substitution']]",
                   "['procedure',['Illegal Procedure']]", "['encroach',['Encroachment','Offside']]",
                   "document.getElementById('penaltySearch').value=''"):
        assert needle in HTML, needle


# ---------------------------------------------------------------- 8. kneels
def _team_loss(service, start: str, end: str):
    return service.play({"team": "home", "play_type": "run", "start_spot": start, "end_spot": end,
                         "direction_check": True})


def test_three_team_kneels_in_a_row_do_not_trip_the_wrong_arrow_warning() -> None:
    # D6: Lumen Christi ran out the clock with three TEAM runs for -1.
    state = base_state()
    state.update(ball_spot="RIGHT 34", down="1st", distance="10")
    service, current, *_ = build_service(state)
    for start, end in (("RIGHT 34", "RIGHT 35"), ("RIGHT 35", "RIGHT 36"), ("RIGHT 36", "RIGHT 37")):
        assert _team_loss(service, start, end).code == "OK"
    assert len(current["plays"]) == 3


def test_real_losses_still_trip_it() -> None:
    state = base_state()
    state.update(ball_spot="RIGHT 40", down="1st", distance="10")
    service, current, *_ = build_service(state)
    for start, end in (("RIGHT 40", "RIGHT 44"), ("RIGHT 44", "RIGHT 47")):
        assert service.play({"team": "home", "play_type": "run", "player_number": "22", "start_spot": start,
                             "end_spot": end, "direction_check": True}).code == "OK"
    third = service.play({"team": "home", "play_type": "run", "player_number": "22", "start_spot": "RIGHT 47",
                          "end_spot": "50", "direction_check": True})
    assert third.code == "DIRECTION_SUSPECT"


# ---------------------------------------------------------------- 9. Kneel answer
def test_the_no_carrier_question_offers_kneel() -> None:
    assert "[{label:'Kneel',value:'kneel',cls:'primary'},{label:'Record as TEAM',value:'team'}" in HTML
    assert "if(choice==='kneel'){payload.kneel=true;document.getElementById('playKneel').checked=true}" in HTML
