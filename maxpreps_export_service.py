from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

Record = dict[str, Any]
ObjectLoader = Callable[[], list[Record]]


@dataclass(frozen=True)
class MaxPrepsExportResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class MaxPrepsExportService:
    """Serialize CSRN's existing football statistics into the pipe-delimited
    stat-import format MaxPreps documents at
    https://www.maxpreps.com/utility/stat_import/field_specs.aspx.

    This computes nothing new -- it reads StatisticsService's already
    aggregated per-player rows and writes the subset of MaxPreps' football
    fields CSRN tracks precisely enough to export. See
    docs/MAXPREPS_EXPORT.md for the full field-by-field mapping, including
    every MaxPreps field CSRN does not track and therefore omits rather than
    guesses at.

    One file per TEAM, not one per game: MaxPreps' only upload mechanism is
    each team's own Team Admin "Import Stats" button, so the schema has no
    "Team" column at all -- the receiving account is what scopes a file to
    a side. Jersey is the only field MaxPreps documents as required, and
    player identity after that is by jersey number alone (no name column
    exists in the schema -- MaxPreps matches jerseys against the roster the
    team itself maintains there).
    """

    # MaxPreps field name -> CSRN per-player field name (statistics_service's
    # _player_row shape), for every column CSRN tracks as exactly the stat
    # MaxPreps asks for. Order here is the order written to the file.
    _DIRECT_FIELDS: dict[str, str] = {
        "RushingNum": "rushing_attempts",
        "RushingYards": "rushing_yards",
        "ReceivingNum": "receptions",
        "ReceivingYards": "receiving_yards",
        "PassingComp": "completions",
        "PassingAtt": "pass_attempts",
        "PassingInt": "interceptions_thrown",
        "PassingYards": "passing_yards",
        "PassingTD": "passing_touchdowns",
        "OffensiveFumbles": "fumbles",
        "OffensiveFumblesLost": "fumbles_lost",
        "Sacks": "sacks",
        "INTs": "defensive_interceptions",
        "FumbleRecoveries": "fumble_recoveries",
        "PuntReturnNum": "punt_returns",
        "PuntReturnYards": "punt_return_yards",
        "KickoffReturnNum": "kickoff_returns",
        "KickoffReturnYards": "kickoff_return_yards",
        "PuntNum": "punts",
        "KickoffNum": "kickoffs",
        "RushingTDNum": "rushing_touchdowns",
        "ReceivingTDNum": "receiving_touchdowns",
        "TotalTDNum": "touchdowns",
        "PATKickingMade": "extra_points",
        "PATKickingAtt": "extra_point_attempts",
        "FGMade": "field_goals",
        "FGAttempted": "field_goal_attempts",
        "TotalPoints": "points",
    }

    # Computed from two CSRN fields MaxPreps itself documents as one column
    # -- still arithmetic over existing tracked values, not new tracking.
    _COMPUTED_FIELDS = ("TotalReturnYards", "PATKickingPoints", "TotalConversionPoints")

    FIELD_ORDER: tuple[str, ...] = (
        "RushingNum", "RushingYards",
        "ReceivingNum", "ReceivingYards",
        "PassingComp", "PassingAtt", "PassingInt", "PassingYards", "PassingTD",
        "OffensiveFumbles", "OffensiveFumblesLost",
        "Sacks",
        "INTs",
        "FumbleRecoveries",
        "PuntReturnNum", "PuntReturnYards",
        "KickoffReturnNum", "KickoffReturnYards",
        "TotalReturnYards",
        "PuntNum",
        "KickoffNum",
        "RushingTDNum", "ReceivingTDNum", "TotalTDNum",
        "PATKickingMade", "PATKickingAtt", "PATKickingPoints",
        "TotalConversionPoints",
        "FGMade", "FGAttempted",
        "TotalPoints",
    )

    def __init__(
        self,
        *,
        load_broadcasts: ObjectLoader,
        load_state: Callable[[], dict[str, Any]],
        load_final_state_archive: Callable[[str], dict[str, Any] | None],
        get_statistics_service: Callable[[], Any],
    ) -> None:
        self._load_broadcasts = load_broadcasts
        self._load_state = load_state
        self._load_final_state_archive = load_final_state_archive
        self._get_statistics_service = get_statistics_service

    def generate(self, broadcast_id: str, team: str) -> MaxPrepsExportResult:
        team_key = str(team or "").strip().lower()
        if team_key not in {"home", "visitor"}:
            return MaxPrepsExportResult("INVALID_TEAM")

        broadcast = self._find_broadcast(broadcast_id)
        if broadcast is None:
            return MaxPrepsExportResult("BROADCAST_NOT_FOUND")

        state = self._resolve_game_state(broadcast)
        statistics = self._get_statistics_service().report(state).data.get("statistics", {})
        players = [
            player
            for player in statistics.get("players", [])
            if str(player.get("team", "")) == team_key
            and str(player.get("number", "")).strip()
        ]
        players.sort(key=self._player_sort_key)

        if not players:
            team_name = str(broadcast.get(f"{team_key}_team") or team_key.title())
            return MaxPrepsExportResult(
                "NO_PLAYER_DATA",
                {
                    "message": f"CSRN has no play-by-play stats recorded for "
                    f"{team_name} in this game -- only a final score (or "
                    "nothing was ever live-tracked). A header-only file "
                    "with no data rows is what MaxPreps rejects as "
                    "\"Insufficient data in file: needs at least header "
                    "and one data row\" -- there is nothing to export "
                    "until this game has real play-by-play data.",
                },
            )

        lines = ["Jersey|" + "|".join(self.FIELD_ORDER)]
        for player in players:
            jersey = str(player.get("number", "")).strip()
            row = [jersey] + [str(self._field_value(player, name)) for name in self.FIELD_ORDER]
            lines.append("|".join(row))
        # CRLF, not bare LF: MaxPreps' importer is a classic Windows/ASP.NET
        # text-upload tool and, in live testing, rejected an LF-only file as
        # "Insufficient data... needs at least header and one data row" --
        # it collapsed the whole file into a single row because it splits on
        # \r\n. The field spec page never documents this; found by testing
        # a real upload, not from the written spec.
        content = "\r\n".join(lines) + "\r\n"

        team_name = str(broadcast.get(f"{team_key}_team") or team_key.title())
        filename = self._filename(broadcast, team_key, team_name)

        return MaxPrepsExportResult(
            "OK",
            {"content": content, "filename": filename, "team_name": team_name},
        )

    # -- lookups -----------------------------------------------------

    def _find_broadcast(self, broadcast_id: str) -> Record | None:
        target = str(broadcast_id or "").strip()
        return next(
            (
                item
                for item in self._load_broadcasts()
                if str(item.get("broadcast_id", "")) == target
                and not item.get("archived")
            ),
            None,
        )

    def _resolve_game_state(self, broadcast: Mapping[str, Any]) -> dict[str, Any]:
        broadcast_id = str(broadcast.get("broadcast_id", ""))
        try:
            live = self._load_state()
        except Exception:
            live = {}
        live_is_this_broadcast = (
            isinstance(live, dict) and str(live.get("broadcast_id", "")) == broadcast_id
        )
        # A broadcast_id match alone is not enough: GameOperationsService.
        # end_game() clears history/events/plays from the live authority
        # state once it has confirmed a full final_state_archive was
        # written, but broadcast_id and status stay put. A completed game
        # is therefore still "the live state" by id while carrying zero
        # events/plays -- trusting that produced a real empty export (no
        # data rows at all) for a finished game. Only trust the live state
        # when it actually still has play data; otherwise prefer the
        # archive, which is the durable record for a finished game.
        if live_is_this_broadcast and (live.get("events") or live.get("plays")):
            return live
        live_mirror = broadcast.get("live_state")
        if isinstance(live_mirror, dict) and (live_mirror.get("events") or live_mirror.get("plays")):
            return live_mirror
        try:
            archive = self._load_final_state_archive(broadcast_id)
        except Exception:
            archive = None
        if isinstance(archive, dict):
            return archive
        if live_is_this_broadcast:
            return live
        return live_mirror if isinstance(live_mirror, dict) else {}

    # -- field computation ---------------------------------------------

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(str(value if value not in (None, "") else 0))
        except (TypeError, ValueError):
            return 0

    def _field_value(self, player: Mapping[str, Any], field_name: str) -> int:
        if field_name == "TotalReturnYards":
            return self._safe_int(player.get("kickoff_return_yards")) + self._safe_int(
                player.get("punt_return_yards")
            )
        if field_name == "PATKickingPoints":
            return self._safe_int(player.get("extra_points"))
        if field_name == "TotalConversionPoints":
            return self._safe_int(player.get("two_point_conversions")) * 2
        return self._safe_int(player.get(self._DIRECT_FIELDS[field_name]))

    @staticmethod
    def _player_sort_key(player: Mapping[str, Any]) -> tuple[Any, ...]:
        number = str(player.get("number", ""))
        number_key = int(number) if number.isdigit() else 999999
        return (number_key, str(player.get("name", "")))

    # -- filename --------------------------------------------------------

    @staticmethod
    def _filename(broadcast: Mapping[str, Any], team_key: str, team_name: str) -> str:
        date = str(broadcast.get("date", "") or "")
        base = f"{date}_{team_name}_MaxPreps_Football"
        # MaxPreps: filenames must not contain quotes or parentheses; keep
        # this to the same safe charset the print-sheet filenames already use.
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("_")
        return f"{cleaned or f'{team_key}_MaxPreps_Football'}.txt"
