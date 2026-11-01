"""AI writer and pregame preview (Social Publishing, 2026-11-01). The AI writer
is exercised against a fake Anthropic client: no network, no key."""
from __future__ import annotations

import copy
from types import SimpleNamespace as NS

import pytest

import ai_writer
import app as app_module
import pregame_story as pg
from tests.test_postgame_story import BROADCAST, BROADCAST_ID, ROSTERS, statistics

KEY = "sk-ant-api03-" + "x" * 40


class MemoryVault:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, key: str) -> str:
        return self.values.get(key, "")

    def set(self, key: str, value: str) -> None:
        if value:
            self.values[key] = value
        else:
            self.values.pop(key, None)


class FakeClient:
    """Stands in for anthropic.Anthropic: records each request, replays responses."""

    def __init__(self, responses: list, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self._responses = list(responses)
        self._error = error
        self.beta = NS(messages=NS(create=self._create))
        self.models = NS(retrieve=self._retrieve)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._responses.pop(0)

    def _retrieve(self, model):
        if self._error:
            raise self._error
        return NS(id=model)


def text_block(text: str, citations=None):
    return NS(type="text", text=text, citations=citations)


def response(blocks, stop="end_turn"):
    return NS(content=blocks, stop_reason=stop, model="claude-opus-5-5")


def writer_with(client: FakeClient) -> ai_writer.AiWriter:
    vault = MemoryVault()
    vault.set(ai_writer.KEY_NAME, KEY)
    return ai_writer.AiWriter(vault=vault, client_factory=lambda key: client)


# -- the key ---------------------------------------------------------------------

def test_key_is_checked_stored_hinted_and_removed() -> None:
    writer = ai_writer.AiWriter(vault=MemoryVault(), client_factory=lambda key: FakeClient([]))
    assert writer.status()["configured"] is False
    assert writer.set_key("not-a-key").code == "AI_KEY_FORMAT"
    result = writer.set_key(f"  {KEY}  ")
    assert result.ok and result.data["configured"] and result.data["key_hint"] == "…xxxx"
    assert KEY not in str(writer.status())
    assert writer.remove_key().data["configured"] is False


def test_test_maps_errors_to_codes_without_echoing_the_key() -> None:
    class AuthenticationError(Exception):
        pass

    bad = writer_with(FakeClient([], error=AuthenticationError(f"invalid x-api-key {KEY}")))
    result = bad.test()
    assert result.code == "AI_KEY_INVALID" and KEY not in result.data["message"]
    assert writer_with(FakeClient([])).test().ok
    assert ai_writer.AiWriter(vault=MemoryVault()).test().code == "AI_NOT_CONFIGURED"


# -- writing -----------------------------------------------------------------------

def test_write_sends_the_facts_with_web_search_and_cleans_the_answer() -> None:
    cite = NS(url="https://www.ahsfhs.org/Mississippi/teams/caledonia", title="Caledonia Football")
    client = FakeClient([
        response([text_block("**West Point rolls past Caledonia, 41-16**\n\nKingston Branham ran for 157 yards. "
                             "Read more at https://example.com/story (here).", citations=[cite])]),
    ])
    result = writer_with(client).write("postgame", "FINAL: West Point 41, Caledonia 16", station="CSRN",
                                       home="West Point", visitor="Caledonia")
    assert result.ok
    assert result.data["headline"] == "West Point rolls past Caledonia, 41-16"
    assert "http" not in result.data["story"] and "example.com" not in result.data["story"]
    assert result.data["sources"] == [{"url": cite.url, "title": "Caledonia Football"}]
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["extra_body"] == {"fallbacks": "default"}
    assert call["tools"][0]["type"] == "web_search_20260209"
    assert "FINAL: West Point 41, Caledonia 16" in call["messages"][0]["content"]
    assert "no links" in call["system"].lower() and "CSRN" in call["system"]


def test_pregame_research_points_at_ahsfhs_and_continues_a_paused_turn() -> None:
    found = NS(type="web_search_tool_result", content=[NS(url="https://www.ahsfhs.org/x", title="Series history")])
    client = FakeClient([response([found], stop="pause_turn"), response([text_block("Preview\n\nLafayette visits.")])])
    result = writer_with(client).write("pregame", "GAME: Lafayette at Caledonia", station="CSRN",
                                       home="Caledonia", visitor="Lafayette", opponent="Lafayette")
    # Pages found before the pause count too (nothing was cited, so all are listed).
    assert result.ok and result.data["sources"] == [{"url": "https://www.ahsfhs.org/x", "title": "Series history"}]
    assert len(client.calls) == 2 and client.calls[1]["messages"][1]["role"] == "assistant"
    task = client.calls[0]["messages"][0]["content"]
    assert "ahsfhs.org" in task and "head-to-head history between Caledonia and Lafayette" in task
    assert client.calls[0]["tools"][0]["max_uses"] == 8


def test_refusals_and_failures_come_back_as_codes() -> None:
    assert writer_with(FakeClient([response([], stop="refusal")])).write("postgame", "x", station="S").code == "AI_REFUSED"
    assert writer_with(FakeClient([response([text_block("   ")])])).write("postgame", "x", station="S").code == "AI_EMPTY"

    class APIConnectionError(Exception):
        pass

    assert writer_with(FakeClient([], error=APIConnectionError("down"))).write("postgame", "x", station="S").code == "AI_UNREACHABLE"
    assert ai_writer.AiWriter(vault=MemoryVault()).write("postgame", "x", station="S").code == "AI_NOT_CONFIGURED"


# -- the built-in pregame writer -----------------------------------------------------

GAMES = [
    {"broadcast_id": "G1", "status": "completed", "date": "2026-10-02", "home_team": "West Point", "visitor_team": "Starkville",
     "home_school_id": "west-point", "visitor_school_id": "starkville", "final_home_score": 28, "final_visitor_score": 14},
    {"broadcast_id": "G2", "status": "completed", "date": "2026-10-09", "home_team": "Columbus", "visitor_team": "West Point",
     "home_school_id": "columbus", "visitor_school_id": "west-point", "final_home_score": 7, "final_visitor_score": 35},
    {"broadcast_id": "G3", "status": "completed", "date": "2025-10-24", "home_team": "West Point", "visitor_team": "Caledonia",
     "home_school_id": "west-point", "visitor_school_id": "caledonia", "final_home_score": 20, "final_visitor_score": 17},
    {"broadcast_id": "G4", "status": "completed", "date": "2026-11-06", "home_team": "West Point", "visitor_team": "Amory",
     "home_school_id": "west-point", "visitor_school_id": "amory", "final_home_score": 1, "final_visitor_score": 0},
]
PREGAME = {**BROADCAST, "status": "planned", "scheduled_start": "7:00 PM", "region_game": True, "home_region": "1",
           "home_classification": "5A", "special_designations": ["homecoming"],
           "home_pregame_record": {"wins": 6, "losses": 2, "ties": 0}, "home_pregame_region_record": {"wins": 2, "losses": 0},
           "visitor_pregame_record": {"wins": 3, "losses": 5, "ties": 0}}


def test_records_and_kickoff_read_the_way_a_paper_prints_them() -> None:
    assert pg.record_text({"wins": 7, "losses": 2, "ties": 0}) == "7-2"
    assert pg.record_text({"wins": 0, "losses": 0}) == ""
    assert pg.kickoff_text("7:00 PM") == "7 p.m." and pg.kickoff_text("6:30 pm") == "6:30 p.m."


def test_pregame_preview_uses_only_stored_facts() -> None:
    facts = pg.build_facts(broadcast=PREGAME, games=GAMES, storylines=["A win clinches a home playoff game"],
                           roster_for_team=lambda team: ROSTERS[team])
    home = facts["teams"]["home"]
    assert [r["opponent"] for r in home["results"]] == ["Caledonia", "Starkville", "Columbus"]  # G4 is after this game
    assert facts["meetings"][0]["ours"] == 20 and home["streak"] == ("W", 3)
    out = pg.write_story(facts, sponsor_name="Main Street Hardware", station_name="WSN")
    story = out["story"]
    assert story.startswith("West Point (6-2, 2-0 Region 1) hosts Caledonia (3-5) at 7 p.m. Friday at Hamblin Stadium in a Class 5A, Region 1 game.")
    assert "It is homecoming at West Point." in story
    assert "West Point is coming off a 35-7 win at Columbus on Oct. 9. West Point has won three straight." in story
    assert "The teams met Oct. 24, 2025, when West Point won 20-17." in story
    assert "A win clinches a home playoff game." in story
    assert "http" not in out["post_text"] and "WSN coverage is brought to you by Main Street Hardware." in out["post_text"]
    sheet = pg.fact_sheet(facts)
    assert "Games the station covered: Oct. 24 at West Point L 17-20" in sheet
    unknown = pg.fact_sheet(pg.build_facts(broadcast=PREGAME, games=GAMES[:2]))
    assert "The station has not covered this team this season; research its results." in unknown


# -- the service and routes ----------------------------------------------------------

@pytest.fixture
def story_client(monkeypatch: pytest.MonkeyPatch):
    broadcasts = [copy.deepcopy(BROADCAST), *copy.deepcopy(GAMES)]
    rosters = [{"school_id": "west-point", "players": ROSTERS["home"]}, {"school_id": "caledonia", "players": ROSTERS["visitor"]}]
    monkeypatch.setattr(app_module, "SOCIAL_MEDIA_PREVIEW_SERVICE", None, raising=False)
    monkeypatch.setattr(app_module, "AI_WRITER", None, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setattr(app_module, "load_broadcasts", lambda: copy.deepcopy(broadcasts))
    monkeypatch.setattr(app_module, "load_state", lambda: {})
    monkeypatch.setattr(app_module, "load_broadcast_live_state", lambda broadcast_id: None)
    monkeypatch.setattr(app_module, "load_final_state_archive",
                        lambda broadcast_id: {"events": [{"id": "e"}], "plays": [{"id": "p"}]} if broadcast_id == BROADCAST_ID else None)
    monkeypatch.setattr(app_module, "build_statistics", lambda state: statistics())
    monkeypatch.setattr(app_module, "load_rosters", lambda: copy.deepcopy(rosters))
    monkeypatch.setattr(app_module, "load_config", lambda: {"organization": {"short_name": "WSN"}})
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "ai-writer-route-test")
    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client
    app_module.SOCIAL_MEDIA_PREVIEW_SERVICE = None
    app_module.AI_WRITER = None


def test_ai_story_falls_back_to_the_built_in_writer_without_a_key(story_client, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "AI_WRITER", ai_writer.AiWriter(vault=MemoryVault()))
    data = story_client.post(f"/api/broadcasts/{BROADCAST_ID}/ai-story", json={"kind": "postgame"}).get_json()
    assert data["story"]["writer"] == "built-in" and data["fallback"]["code"] == "AI_NOT_CONFIGURED"
    assert data["story"]["headline"].endswith("21-10")


def test_ai_story_keeps_the_apps_scoring_closing_and_player_of_the_game(story_client, monkeypatch) -> None:
    client = FakeClient([response([text_block("Green Wave hold off Cavaliers\n\nFirst paragraph.\n\nSecond paragraph.")])])
    monkeypatch.setattr(app_module, "AI_WRITER", writer_with(client))
    data = story_client.post(f"/api/broadcasts/{BROADCAST_ID}/ai-story",
                             json={"kind": "postgame", "player": "home:2", "sponsor": "none"}).get_json()
    story = data["story"]
    assert story["writer"] == "ai" and story["headline"] == "Green Wave hold off Cavaliers"
    assert story["story"].endswith("WSN Player of the Game: Kingston Branham of West Point.")
    assert "SCORING\nQ1 West Point" in story["post_text"] and "http" not in story["post_text"]
    assert "GAME LOG FROM THE STATION'S STATISTICIAN" in client.calls[0]["messages"][0]["content"]
    assert "Player of the Game" not in client.calls[0]["messages"][0]["content"]


def test_pregame_routes(story_client, monkeypatch) -> None:
    data = story_client.get(f"/api/broadcasts/{BROADCAST_ID}/pregame-story").get_json()
    assert data["kind"] == "pregame" and data["story"]["writer"] == "built-in"
    client = FakeClient([response([text_block("Preview headline\n\nPreview body.")])])
    monkeypatch.setattr(app_module, "AI_WRITER", writer_with(client))
    ai = story_client.post(f"/api/broadcasts/{BROADCAST_ID}/ai-story", json={"kind": "pregame"}).get_json()
    assert ai["story"]["writer"] == "ai" and ai["story"]["story"] == "Preview body."
    assert "head-to-head history between West Point and Caledonia" in client.calls[0]["messages"][0]["content"]


def test_key_routes_never_return_the_key(story_client, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "AI_WRITER", ai_writer.AiWriter(vault=MemoryVault(), client_factory=lambda key: FakeClient([])))
    assert story_client.get("/api/ai-writer").get_json()["configured"] is False
    assert story_client.post("/api/ai-writer/key", json={"api_key": "nope"}).status_code == 400
    saved = story_client.post("/api/ai-writer/key", json={"api_key": KEY})
    assert saved.status_code == 200 and KEY not in saved.get_data(as_text=True)
    assert story_client.post("/api/ai-writer/test", json={}).status_code == 200
    assert story_client.delete("/api/ai-writer/key", json={}).get_json()["configured"] is False


def test_ai_routes_need_login() -> None:
    with app_module.app.test_client() as client:
        assert client.get("/api/ai-writer").status_code == 401
        assert client.post(f"/api/broadcasts/{BROADCAST_ID}/ai-story", json={}).status_code == 401


# -- notes, revising, the search report, the verified key ---------------------------------

ARTICLE = """Lafayette holds off Caledonia, 28-21

Lafayette ran for 400 yards.

Caledonia kept fighting.

---

Notes:

- No season records or standings: The web search reached its limit.
- I left out Hugh Trost's 53-yard kickoff return: The game log doesn't say which team
  he plays for.
"""


def test_notes_are_split_off_the_story() -> None:
    client = FakeClient([response([text_block(ARTICLE)])])
    result = writer_with(client).write("postgame", "x", station="S")
    assert result.data["story"] == "Lafayette ran for 400 yards.\n\nCaledonia kept fighting."
    assert result.data["notes"] == ["No season records or standings: The web search reached its limit.",
                                    "I left out Hugh Trost's 53-yard kickoff return: The game log doesn't say which team he plays for."]
    assert "NOTES FOR THE STATION" in client.calls[0]["system"]


def test_revise_replays_the_story_and_notes_then_the_answers() -> None:
    client = FakeClient([response([text_block("Lafayette holds off Caledonia\n\nRevised story.")])])
    writer = writer_with(client)
    assert writer.revise("postgame", "FACTS", previous="Old", instructions="  ", station="S").code == "AI_NOTHING_TO_REVISE"
    result = writer.revise("postgame", "FACTS", previous="Head\n\nOld story.", notes=["Which team is Trost on?"],
                           instructions="Hugh Trost plays for Lafayette.", station="S")
    assert result.ok and result.data["story"] == "Revised story." and result.data["notes"] == []
    roles = [m["role"] for m in client.calls[0]["messages"]]
    assert roles == ["user", "assistant", "user"]
    assert "FACTS" in client.calls[0]["messages"][0]["content"]
    assert client.calls[0]["messages"][1]["content"] == "Head\n\nOld story.\n\nNOTES FOR THE STATION\n- Which team is Trost on?"
    assert "Hugh Trost plays for Lafayette." in client.calls[0]["messages"][2]["content"]


def test_search_report_explains_an_empty_search() -> None:
    blocks = [NS(type="server_tool_use", name="web_search"),
              NS(type="web_search_tool_result", content=NS(type="web_search_tool_result_error", error_code="max_uses_exceeded")),
              NS(type="server_tool_use", name="web_search"),
              NS(type="web_search_tool_result", content={"type": "web_search_tool_result_error", "error_code": "unavailable"}),
              text_block("Head\n\nBody.")]
    result = writer_with(FakeClient([response(blocks)])).write("postgame", "x", station="S")
    assert result.data["search"] == {"searches": 2, "results": 0, "errors": ["max_uses_exceeded", "unavailable"]}


def test_a_key_is_verified_once_it_works_and_unverified_when_it_changes() -> None:
    vault = MemoryVault()
    writer = ai_writer.AiWriter(vault=vault, client_factory=lambda key: FakeClient([response([text_block("H\n\nB.")])]))
    writer.set_key(KEY)
    assert writer.status() == {**writer.status(), "configured": True, "verified": False}
    assert writer.test().ok and writer.status()["verified"] is True
    writer.set_key(KEY.replace("x", "y"))
    assert writer.status()["verified"] is False
    assert writer.write("postgame", "x", station="S").ok and writer.status()["verified"] is True

    class AuthenticationError(Exception):
        pass

    bad = ai_writer.AiWriter(vault=vault, client_factory=lambda key: FakeClient([], error=AuthenticationError("no")))
    assert bad.test().code == "AI_KEY_INVALID" and bad.status()["verified"] is False


def test_revise_route_keeps_the_story_when_it_fails(story_client, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "AI_WRITER", ai_writer.AiWriter(vault=MemoryVault()))
    failed = story_client.post(f"/api/broadcasts/{BROADCAST_ID}/ai-story",
                               json={"kind": "postgame", "previous": "H\n\nMine.", "instructions": "Fix it"})
    assert failed.status_code == 502 and "Your story was left as it was." in failed.get_json()["message"]
    client = FakeClient([response([text_block("New head\n\nNew body.\n\nNOTES FOR THE STATION\n- Check the mascot.")])])
    monkeypatch.setattr(app_module, "AI_WRITER", writer_with(client))
    data = story_client.post(f"/api/broadcasts/{BROADCAST_ID}/ai-story", json={
        "kind": "postgame", "player": "home:2", "instructions": "Commodores is right.", "notes": ["Mascot?"],
        "previous": "Old head\n\nOld body.\n\nThe WSN Player of the Game: Kingston Branham of West Point.",
    }).get_json()
    assert data["revised"] is True and data["notes"] == ["Check the mascot."]
    assert data["story"]["story"] == "New body.\n\nThe WSN Player of the Game: Kingston Branham of West Point."
    sent = client.calls[0]["messages"][1]["content"]
    assert "Player of the Game" not in sent and sent.endswith("NOTES FOR THE STATION\n- Mascot?")


def test_game_log_names_the_team_on_returns_and_takeaways() -> None:
    import postgame_story as ps
    from tests.test_postgame_story import facts

    story = ps.write_story(facts())["story"]
    assert "Caledonia's Michael Brewer Jr. intercepted a pass" in story


def test_out_of_credit_is_its_own_message_and_each_run_reports_its_cost() -> None:
    class BadRequestError(Exception):
        message = "Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing."

    broke = writer_with(FakeClient([], error=BadRequestError()))
    assert broke.write("postgame", "x", station="S").code == "AI_NO_CREDIT"
    usage = NS(input_tokens=10_000, output_tokens=1_500, cache_read_input_tokens=0, cache_creation_input_tokens=0,
               server_tool_use=NS(web_search_requests=3))
    reply = response([text_block("H\n\nBody.")])
    reply.usage = usage
    result = writer_with(FakeClient([reply])).write("postgame", "x", station="S")
    assert result.data["cost_usd"] == round(10_000 * 4 / 1e6 + 1_500 * 20 / 1e6 + 3 * 0.01, 4)  # 0.1 -> "about 10¢"


def test_no_credit_falls_back_with_a_billing_message(story_client, monkeypatch) -> None:
    class BadRequestError(Exception):
        message = "Your credit balance is too low to access the Anthropic API."

    monkeypatch.setattr(app_module, "AI_WRITER", writer_with(FakeClient([], error=BadRequestError())))
    data = story_client.post(f"/api/broadcasts/{BROADCAST_ID}/ai-story", json={"kind": "postgame"}).get_json()
    assert data["fallback"]["code"] == "AI_NO_CREDIT" and "console.anthropic.com" in data["fallback"]["message"]
    assert data["story"]["writer"] == "built-in"


def test_player_pickers_list_the_best_performers_first() -> None:
    from tests.test_postgame_story import facts

    home = [c["name"] for c in facts()["players"] if c["team"] == "home"]
    assert home[:3] == ["Kingston Branham", "Jaylen Hall", "Marcus Hall"]


def test_single_player_of_the_game_strip_names_the_station() -> None:
    import postgame_card
    import postgame_story as ps
    from tests.test_postgame_story import facts

    found = facts()
    one = postgame_card.render_card_html(found, headline="x", station_name="CSRN",
                                         player_of_game=ps.players_of_the_game(found, "visitor:1"))
    assert ">CSRN Player of the Game<" in one


def _pregame_facts_for_card():
    results = [{"date": "2026-10-02", "home": True, "ours": 27, "theirs": 8, "opponent": "Columbus", "opponent_id": "c"},
               {"date": "2026-10-09", "home": False, "ours": 14, "theirs": 21, "opponent": "Pontotoc", "opponent_id": "p"}]
    team = lambda name, leaders, res: {"name": name, "record": "7-2", "region_record": "3-1", "classification": "5A", "region": "3",
                                       "results": res, "leaders": leaders, "streak": ("W", 1), "mascot": "", "school_id": name}
    leader = {"category": "rushing", "player": {"name": "Tyler Long"}, "row": {"rushing_yards": 1595, "rushing_touchdowns": 8}, "games": 2}
    return {"broadcast_id": "g", "sport": "football", "date": "2026-10-30", "weekday": "Friday", "kickoff": "7 p.m.", "venue": "Cavalier Field",
            "region_game": True, "designations": ["homecoming"], "meetings": [], "storylines": ["Senior night <tonight>"], "home_id": "h",
            "teams": {"home": team("Caledonia", [leader], results), "visitor": team("Lafayette", [], [])}}


def test_pregame_card_has_the_matchup_details_in_every_theme() -> None:
    import postgame_card
    import pregame_card

    assert pregame_card.leader_line({"category": "rushing", "row": {"rushing_yards": 1595, "rushing_touchdowns": 8}}) == "1,595 rush yds, 8 TD"
    for theme in postgame_card.THEMES:
        html = pregame_card.render_card_html(_pregame_facts_for_card(), headline="Caledonia hosts Lafayette", station_name="CSRN", theme=theme)
        assert f'class="theme-{theme} logo-round"' in html
        for expected in ("Kickoff 7 p.m.", "Region 3 game", "Homecoming", "Region record", "5A · Region 3", "Points per game", "20.5",
                         "Players to Watch", "Tyler Long", "Recent Results", "27-8 vs. Columbus", "Live on", "from games on CSRN", "Senior night &lt;tonight&gt;"):
            assert expected in html, (theme, expected)


def test_pregame_card_with_nothing_but_the_matchup_stays_a_full_card() -> None:
    import pregame_card

    facts = _pregame_facts_for_card()
    for team in facts["teams"].values():
        team.update(results=[], leaders=[], record="", region_record="", classification="", region="")
    facts.update(storylines=[], region_game=False, designations=[], kickoff="")
    html = pregame_card.render_card_html(facts, headline="Preview", station_name="CSRN")
    assert " sparse" in html and 'class="lower' not in html and "from games on" not in html


GRAPHIC_JSON = """{"home": {"record": "6-3", "region_record": "3-1", "points_per_game": "28.4", "points_allowed": "not known",
"results": ["W 27-8 vs. Columbus", "see https://example.com/x", "27-8 no mark"], "players": [{"name": "Sam Rivers", "line": "595 rush yds, 8 TD"}]},
"visitor": {"record": "bad", "region_record": "", "results": [], "players": []}, "last_meeting": "New Hope won 28-14 in 2025"}"""


def test_graphic_data_is_split_out_of_the_story_and_notes() -> None:
    answer = f"Preview\n\nThe story.\n\nNOTES FOR THE STATION\n- Check the record.\n\nGRAPHIC DATA\n```json\n{GRAPHIC_JSON}\n```"
    client = FakeClient([response([text_block(answer)])])
    result = writer_with(client).write("pregame", "facts", station="CSRN", home="New Hope", visitor="Caledonia", opponent="New Hope")
    assert result.ok and result.data["story"] == "The story." and result.data["notes"] == ["Check the record."]
    assert result.data["graphic"]["home"]["record"] == "6-3"
    assert ai_writer.split_graphic_data("Story only")[1] is None
    assert ai_writer.split_graphic_data("Story\n\nGRAPHIC DATA\n{broken")[0] == "Story"


def test_numbers_are_cleaned_and_replace_what_the_card_shows() -> None:
    import json

    import pregame_card

    numbers = pregame_card.clean_numbers(json.loads(GRAPHIC_JSON))
    home = numbers["home"]
    assert home["record"] == "6-3" and home["points_per_game"] == "28.4" and home["points_allowed"] == ""
    assert home["results"] == ["W 27-8 vs. Columbus"]                      # links and unmarked lines dropped
    assert numbers["visitor"]["record"] == ""
    assert pregame_card.clean_numbers({"home": {"players": ["Sam Rivers: 595 rush yds"]}})["home"]["players"] == [{"name": "Sam Rivers", "line": "595 rush yds"}]
    assert not pregame_card.has_numbers(pregame_card.clean_numbers({}))
    facts = _pregame_facts_for_card()
    html = pregame_card.render_card_html(facts, headline="H", station_name="CSRN", numbers=numbers)
    for expected in ("6-3", "28.4", "Sam Rivers", "New Hope won 28-14 in 2025", "public sources and games on CSRN, reviewed by CSRN"):
        assert expected in html
    assert "Tyler Long" not in html and "from games on CSRN.</p>" not in html
    assert "Tyler Long" in pregame_card.render_card_html(facts, headline="H", station_name="CSRN")
    assert pregame_card.app_numbers(facts)["home"]["results"][0] == "W 27-8 vs. Columbus"


def test_a_completed_game_without_a_saved_final_still_counts_in_the_preview() -> None:
    import pregame_story

    def game(game_id, date, opponent, **extra):
        return {"broadcast_id": game_id, "date": date, "status": "completed", "home_school_id": "cal", "home_team": "Caledonia",
                "visitor_school_id": opponent, "visitor_team": opponent.title(), **extra}

    games = [game("old", "2026-10-23", "west-point", final_home_score=16, final_visitor_score=41),
             game("skipped-end-game", "2026-10-30", "lafayette"),
             game("rehearsal", "2026-10-23", "west-point"),
             game("no-plays", "2026-10-31", "amory"),
             {**game("planned", "2026-11-01", "pontotoc"), "status": "planned"}]
    states = {"skipped-end-game": {"home_score": 21, "visitor_score": 28, "plays": [{}]}, "rehearsal": {"home_score": 99, "visitor_score": 0, "plays": [{}]},
              "planned": {"home_score": 5, "visitor_score": 5, "plays": [{}]}}
    filled = pregame_story.fill_missing_finals(games, lambda g: states.get(g["broadcast_id"]))
    by_id = {g["broadcast_id"]: g for g in filled}
    assert (by_id["skipped-end-game"]["final_home_score"], by_id["skipped-end-game"]["final_visitor_score"]) == (21, 28)
    assert "final_home_score" not in by_id["rehearsal"] and "final_home_score" not in by_id["no-plays"] and "final_home_score" not in by_id["planned"]
    next_game = {"broadcast_id": "next", "date": "2026-11-06", "status": "planned", "home_school_id": "nh", "home_team": "New Hope",
                 "visitor_school_id": "cal", "visitor_team": "Caledonia", "special_designations": ["senior_night", "rivalry"]}
    facts = pregame_story.build_facts(broadcast=next_game, games=filled)
    assert [r["opponent"] for r in facts["teams"]["visitor"]["results"]] == ["West-Point", "Lafayette"]
    story = pregame_story.write_story(facts)["story"]
    assert "28-21 loss to Lafayette on Oct. 30" in story and "lost two straight" in story
    assert "It is senior night at New Hope. It is a rivalry game." in story

