"""Coverage for MaxPrepsExportService -- the football stat-import .txt
serializer built from statistics_service.py's already-aggregated per-player
rows. See docs/MAXPREPS_EXPORT.md for the full field-by-field mapping this
pins against MaxPreps' own documented schema.
"""
from __future__ import annotations

from typing import Any

from maxpreps_export_service import MaxPrepsExportService
from statistics_service import StatisticsService


BROADCAST_ID = "FB-TEST-MAXPREPS"


def game_state() -> dict[str, Any]:
    return {
        "broadcast_id": BROADCAST_ID,
        "sport": "Football",
        "season": "2026",
        "date": "2026-10-04",
        "venue": "Test Field",
        "status": "completed",
        "home_team": "Home Eagles",
        "visitor_team": "Visitor Hawks",
        "home_score": 24,
        "visitor_score": 7,
        "events": [
            # The two touchdown plays below (p2, p4) each carry a paired
            # scoring event, same as a real CSRN broadcast records them --
            # "points"/scorer bookkeeping lives on events, not plays.
            {
                "id": "e0a",
                "broadcast_id": BROADCAST_ID,
                "event": "TD",
                "team": "home",
                "score_delta": 6,
                "play_id": "p2",
                "automation": {"player_name": "Home Twenty Two", "player_number": "22"},
            },
            {
                "id": "e0b",
                "broadcast_id": BROADCAST_ID,
                "event": "TD",
                "team": "home",
                "score_delta": 6,
                "play_id": "p4",
                "automation": {"player_name": "Home Eighty Four", "player_number": "84"},
            },
            # Interception thrown by visitor QB #11, picked by home #5.
            {
                "id": "e1",
                "broadcast_id": BROADCAST_ID,
                "event": "TURNOVER",
                "team": "home",
                "automation": {
                    "turnover_type": "interception",
                    "turnover_player_name": "Home Five",
                    "turnover_player_number": "5",
                    "return_yards": 9,
                },
            },
            {
                "id": "e2",
                "broadcast_id": BROADCAST_ID,
                "event": "XP",
                "team": "home",
                "score_delta": 1,
                "automation": {"player_name": "Home Kicker", "player_number": "9"},
            },
            {
                "id": "e3",
                "broadcast_id": BROADCAST_ID,
                "event": "FG",
                "team": "home",
                "score_delta": 3,
                "automation": {"player_name": "Home Kicker", "player_number": "9"},
            },
            {
                "id": "e4",
                "broadcast_id": BROADCAST_ID,
                "event": "2PT",
                "team": "home",
                "score_delta": 2,
                "conversion_outcome": "good",
                "automation": {"player_name": "Home Twenty Two", "player_number": "22"},
            },
        ],
        "plays": [
            {
                "play_id": "p1",
                "broadcast_id": BROADCAST_ID,
                "play_type": "run",
                "offense": "home",
                "defense": "visitor",
                "yards": 8,
                "player_name": "Home Twenty Two",
                "player_number": "22",
            },
            {
                "play_id": "p2",
                "broadcast_id": BROADCAST_ID,
                "play_type": "run",
                "offense": "home",
                "defense": "visitor",
                "yards": 2,
                "touchdown": True,
                "player_name": "Home Twenty Two",
                "player_number": "22",
            },
            {
                "play_id": "p3",
                "broadcast_id": BROADCAST_ID,
                "play_type": "pass",
                "offense": "home",
                "defense": "visitor",
                "yards": 15,
                "pass_outcome": "complete",
                "passer_name": "Home Seven",
                "passer_number": "7",
                "receiver_name": "Home Eighty Four",
                "receiver_number": "84",
            },
            {
                "play_id": "p4",
                "broadcast_id": BROADCAST_ID,
                "play_type": "pass",
                "offense": "home",
                "defense": "visitor",
                "yards": 3,
                "touchdown": True,
                "pass_outcome": "complete",
                "passer_name": "Home Seven",
                "passer_number": "7",
                "receiver_name": "Home Eighty Four",
                "receiver_number": "84",
            },
            {
                "play_id": "p5",
                "broadcast_id": BROADCAST_ID,
                "play_type": "pass",
                "offense": "visitor",
                "defense": "home",
                "yards": 0,
                "pass_outcome": "interception",
                "passer_name": "Visitor Eleven",
                "passer_number": "11",
            },
            {
                "play_id": "p6",
                "broadcast_id": BROADCAST_ID,
                "play_type": "pass",
                "offense": "visitor",
                "defense": "home",
                "yards": 0,
                "pass_outcome": "sack",
                "sacker_name": "Home Fifty One",
                "sacker_number": "51",
            },
            {
                "play_id": "p7",
                "broadcast_id": BROADCAST_ID,
                "play_type": "punt",
                "offense": "visitor",
                "defense": "home",
                "kicking_team": "home",
                "kicker_name": "Home Kicker",
                "kicker_number": "9",
                "return_yards": 12,
                "returner_name": "Visitor Twenty Three",
                "returner_number": "23",
                "result": "Punt return",
            },
            {
                "play_id": "p8",
                "broadcast_id": BROADCAST_ID,
                "play_type": "kickoff",
                "offense": "visitor",
                "defense": "home",
                "kicking_team": "home",
                "kicker_name": "Home Kicker",
                "kicker_number": "9",
                "return_yards": 20,
                "returner_name": "Visitor Twenty Three",
                "returner_number": "23",
                "result": "Kickoff return",
            },
        ],
    }


def build_service(state: dict[str, Any], *, broadcasts: list[dict[str, Any]] | None = None) -> MaxPrepsExportService:
    statistics_service = StatisticsService(now=lambda: 1_700_000_000.0)
    records = broadcasts if broadcasts is not None else [{"broadcast_id": BROADCAST_ID, "home_team": "Home Eagles", "visitor_team": "Visitor Hawks", "date": "2026-10-04"}]
    return MaxPrepsExportService(
        load_broadcasts=lambda: records,
        load_state=lambda: state,
        load_final_state_archive=lambda broadcast_id: None,
        get_statistics_service=lambda: statistics_service,
    )


def test_invalid_team_is_refused() -> None:
    result = build_service(game_state()).generate(BROADCAST_ID, "both")
    assert result.code == "INVALID_TEAM"


def test_unknown_broadcast_is_refused() -> None:
    result = build_service(game_state()).generate("NOPE", "home")
    assert result.code == "BROADCAST_NOT_FOUND"


def test_header_line_matches_maxpreps_field_order_exactly() -> None:
    result = build_service(game_state()).generate(BROADCAST_ID, "home")
    assert result.ok
    header = result.data["content"].splitlines()[0]
    assert header == "Jersey|" + "|".join(MaxPrepsExportService.FIELD_ORDER)


def test_home_team_export_matches_hand_computed_stats() -> None:
    result = build_service(game_state()).generate(BROADCAST_ID, "home")
    assert result.ok
    lines = result.data["content"].splitlines()
    rows = {line.split("|")[0]: line.split("|")[1:] for line in lines[1:]}
    fields = list(MaxPrepsExportService.FIELD_ORDER)

    def value(jersey: str, field_name: str) -> str:
        return rows[jersey][fields.index(field_name)]

    # #22: 2 carries (8 + 2 yards), 1 rushing/total TD, 1 two-point conversion (-> 2 conversion pts).
    assert value("22", "RushingNum") == "2"
    assert value("22", "RushingYards") == "10"
    assert value("22", "RushingTDNum") == "1"
    assert value("22", "TotalTDNum") == "1"
    assert value("22", "TotalConversionPoints") == "2"

    # #7: 2/2 passing, 18 yards, 1 passing TD (does not inflate his own TotalTDNum).
    assert value("7", "PassingComp") == "2"
    assert value("7", "PassingAtt") == "2"
    assert value("7", "PassingYards") == "18"
    assert value("7", "PassingTD") == "1"
    assert value("7", "TotalTDNum") == "0"

    # #84: 2 receptions, 18 yards, 1 receiving/total TD.
    assert value("84", "ReceivingNum") == "2"
    assert value("84", "ReceivingYards") == "18"
    assert value("84", "ReceivingTDNum") == "1"
    assert value("84", "TotalTDNum") == "1"

    # #5: 1 interception (defensive), 9 return yards -- not exported (commingled
    # INTYards field), confirmed absent from FIELD_ORDER by the header check above.
    assert value("5", "INTs") == "1"

    # #51: 1 sack.
    assert value("51", "Sacks") == "1"

    # #9 (home kicker/punter): 1 XP made/att, 1 FG made/att, 1 punt, 1 kickoff.
    assert value("9", "PATKickingMade") == "1"
    assert value("9", "PATKickingAtt") == "1"
    assert value("9", "PATKickingPoints") == "1"
    assert value("9", "FGMade") == "1"
    assert value("9", "FGAttempted") == "1"
    assert value("9", "PuntNum") == "1"
    assert value("9", "KickoffNum") == "1"

    # Team point total sanity: #22 scored a rushing TD (6) + a 2pt conversion
    # (2) = 8; #7 threw a TD (0 self-points); #84 scored a receiving TD (6);
    # #9 made an XP (1) + FG (3) = 4. Matches scoring events' own deltas.
    assert value("22", "TotalPoints") == "8"
    assert value("84", "TotalPoints") == "6"
    assert value("9", "TotalPoints") == "4"


def test_visitor_team_export_matches_hand_computed_stats() -> None:
    result = build_service(game_state()).generate(BROADCAST_ID, "visitor")
    assert result.ok
    lines = result.data["content"].splitlines()
    rows = {line.split("|")[0]: line.split("|")[1:] for line in lines[1:]}
    fields = list(MaxPrepsExportService.FIELD_ORDER)

    def value(jersey: str, field_name: str) -> str:
        return rows[jersey][fields.index(field_name)]

    # #11: threw 1 INT (and was sacked once, on a play with no attributed
    # passer of record for the sack itself).
    assert value("11", "PassingInt") == "1"

    # #23: 1 punt return (12 yards) + 1 kickoff return (20 yards) ->
    # TotalReturnYards is the documented sum of both.
    assert value("23", "PuntReturnNum") == "1"
    assert value("23", "PuntReturnYards") == "12"
    assert value("23", "KickoffReturnNum") == "1"
    assert value("23", "KickoffReturnYards") == "20"
    assert value("23", "TotalReturnYards") == "32"


def test_jersey_is_the_only_column_maxpreps_requires_and_is_always_present() -> None:
    result = build_service(game_state()).generate(BROADCAST_ID, "home")
    for line in result.data["content"].splitlines()[1:]:
        jersey = line.split("|")[0]
        assert jersey.strip() != ""


def test_filename_has_no_quotes_or_parentheses_and_ends_txt() -> None:
    result = build_service(game_state()).generate(BROADCAST_ID, "home")
    filename = result.data["filename"]
    assert filename.endswith(".txt")
    assert '"' not in filename and "(" not in filename and ")" not in filename


def test_falls_back_to_final_state_archive_when_live_state_is_a_different_broadcast() -> None:
    state = game_state()
    service = MaxPrepsExportService(
        load_broadcasts=lambda: [
            {"broadcast_id": BROADCAST_ID, "home_team": "Home Eagles", "visitor_team": "Visitor Hawks", "date": "2026-10-04"}
        ],
        load_state=lambda: {"broadcast_id": "SOME-OTHER-LIVE-GAME"},
        load_final_state_archive=lambda broadcast_id: state if broadcast_id == BROADCAST_ID else None,
        get_statistics_service=lambda: StatisticsService(now=lambda: 1_700_000_000.0),
    )
    result = service.generate(BROADCAST_ID, "home")
    assert result.ok
    assert "22|" in result.data["content"]


def test_falls_back_to_archive_when_the_live_state_matches_by_id_but_was_cleared_post_game() -> None:
    """Regression for a real failed upload (Itawamba vs Caledonia,
    2026-10-04): GameOperationsService.end_game() clears history/events/
    plays from the live authority state once it has archived them, but
    broadcast_id and status stay put. A completed game is therefore still
    "the live state" by id while actually carrying zero plays -- trusting
    that produced a real export with a header and NO data rows at all,
    which is exactly the "Insufficient data... needs at least header and
    one data row" MaxPreps rejected it for. Must prefer the archive
    whenever the id-matching live state has no events/plays of its own.
    """
    state = game_state()
    cleared_live_state = {
        "broadcast_id": BROADCAST_ID,
        "status": "completed",
        "events": [],
        "plays": [],
    }
    service = MaxPrepsExportService(
        load_broadcasts=lambda: [
            {"broadcast_id": BROADCAST_ID, "home_team": "Home Eagles", "visitor_team": "Visitor Hawks", "date": "2026-10-04"}
        ],
        load_state=lambda: cleared_live_state,
        load_final_state_archive=lambda broadcast_id: state if broadcast_id == BROADCAST_ID else None,
        get_statistics_service=lambda: StatisticsService(now=lambda: 1_700_000_000.0),
    )
    result = service.generate(BROADCAST_ID, "home")
    assert result.ok
    lines = result.data["content"].splitlines()
    assert len(lines) > 1, "export must not be header-only for a completed, archived game"
    assert "22|" in result.data["content"]
