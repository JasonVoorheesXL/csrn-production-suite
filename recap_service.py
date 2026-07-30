from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Mapping


LoadMapping = Callable[[], Mapping[str, Any]]
Clock = Callable[[], float]
SocialDraftCallback = Callable[[Mapping[str, Any]], Any]


@dataclass(frozen=True)
class RecapResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code in {
            "OK",
            "RECAP_GENERATED",
            "RECAP_UPDATED",
            "RECAP_APPROVED",
            "RECAP_DELETED",
            "SOCIAL_DRAFT_CREATED",
        }


class GroundedGameRecapService:
    """Deterministic recap generation from recorded CSRN game data only.

    The service does not estimate missing statistics, attribute plays to a player
    without a recorded name, infer weather, or synthesize scoring events. Missing
    fields are listed in the grounding report and omitted from the narrative.
    """

    SCHEMA = 1
    MAX_RECAPS = 250
    MAX_AUDIT = 2000
    APPROVAL_PHRASE = "APPROVE GROUNDED RECAP"
    DELETE_PHRASE = "DELETE GAME RECAP"
    EDITABLE_FIELDS = {"headline", "lead", "body", "closing", "social_summary", "article_style", "sponsor_id", "sponsor_name"}
    SCORING_CODES = {
        "TD",
        "TOUCHDOWN",
        "FG",
        "FIELD_GOAL",
        "SAFETY",
        "PAT",
        "EXTRA_POINT",
        "TWO_POINT",
        "2PT",
    }
    TURNOVER_CODES = {
        "TURNOVER",
        "INTERCEPTION",
        "FUMBLE",
        "FUMBLE_LOST",
    }
    WEATHER_DELAY_CODES = {"WEATHER_DELAY", "DELAY_WEATHER"}
    WEATHER_RESUME_CODES = {"GAME_RESUMPTION", "WEATHER_RESUMPTION", "RESUME"}
    WEATHER_EMERGENCY_CODES = {"WEATHER_EMERGENCY", "SEVERE_WEATHER"}
    TEAM_STAT_LABELS = {
        "first_downs": "first downs",
        "rushing_yards": "rushing yards",
        "passing_yards": "passing yards",
        "total_yards": "total yards",
        "turnovers": "turnovers",
        "penalties": "penalties",
        "penalty_yards": "penalty yards",
    }
    DEFAULT_STATE: dict[str, Any] = {
        "schema": SCHEMA,
        "recaps": [],
        "audit": [],
        "updated_at": 0,
    }

    def __init__(
        self,
        *,
        state_file: Path,
        load_broadcast_state: LoadMapping,
        create_social_draft: SocialDraftCallback | None = None,
        clock: Clock = time.time,
    ) -> None:
        self.state_file = Path(state_file)
        self._load_broadcast_state = load_broadcast_state
        self._create_social_draft = create_social_draft
        self._clock = clock
        self._lock = Lock()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return copy.deepcopy(default)

    def _load(self) -> dict[str, Any]:
        payload = self._read(self.state_file, self.DEFAULT_STATE)
        if not isinstance(payload, dict):
            payload = {}
        state = copy.deepcopy(self.DEFAULT_STATE)
        state["recaps"] = payload.get("recaps", []) if isinstance(payload.get("recaps"), list) else []
        state["audit"] = payload.get("audit", []) if isinstance(payload.get("audit"), list) else []
        state["updated_at"] = int(payload.get("updated_at", 0) or 0)
        return state

    def _write(self, state: Mapping[str, Any]) -> None:
        payload = copy.deepcopy(dict(state))
        payload["schema"] = self.SCHEMA
        payload["updated_at"] = int(self._clock())
        temporary = self.state_file.with_name(f".{self.state_file.name}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.state_file)

    def _audit(self, state: dict[str, Any], action: str, **details: Any) -> None:
        rows = list(state.get("audit") or [])
        rows.append(
            {
                "id": f"RCA-{int(self._clock() * 1000)}-{len(rows) % 1000:03d}",
                "action": action,
                "created_at": int(self._clock()),
                **copy.deepcopy(details),
            }
        )
        state["audit"] = rows[-self.MAX_AUDIT :]

    @staticmethod
    def _canonical_hash(value: Mapping[str, Any]) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _event_code(event: Mapping[str, Any]) -> str:
        return str(event.get("event") or event.get("kind") or event.get("type") or "").strip().upper()

    @staticmethod
    def _event_description(event: Mapping[str, Any]) -> str:
        return str(event.get("description") or event.get("result") or event.get("message") or "").strip()

    @staticmethod
    def _score_pair(source: Any) -> tuple[int, int] | None:
        if not isinstance(source, Mapping):
            return None
        home_value = source.get("home_score", source.get("home"))
        visitor_value = source.get("visitor_score", source.get("visitor"))
        if home_value is None or visitor_value is None:
            return None
        try:
            return int(home_value), int(visitor_value)
        except (TypeError, ValueError):
            return None

    def _event_after_score(self, event: Mapping[str, Any]) -> tuple[int, int] | None:
        return self._score_pair(event.get("after")) or self._score_pair(event)

    @staticmethod
    def _clean_rows(rows: Any) -> list[dict[str, Any]]:
        if not isinstance(rows, list):
            return []
        return [copy.deepcopy(dict(row)) for row in rows if isinstance(row, Mapping) and not row.get("undone")]

    def _source_snapshot(self) -> dict[str, Any]:
        raw = copy.deepcopy(dict(self._load_broadcast_state()))
        events = self._clean_rows(raw.get("events"))
        plays = self._clean_rows(raw.get("plays"))
        halftime = raw.get("halftime_score") if isinstance(raw.get("halftime_score"), Mapping) else {}
        statistics = raw.get("statistics") if isinstance(raw.get("statistics"), Mapping) else {}
        snapshot = {
            "broadcast_id": str(raw.get("broadcast_id", "")).strip(),
            "home_team": str(raw.get("home_team", "")).strip(),
            "visitor_team": str(raw.get("visitor_team", "")).strip(),
            "home_score": raw.get("home_score"),
            "visitor_score": raw.get("visitor_score"),
            "date": str(raw.get("date", "")).strip(),
            "venue": str(raw.get("venue", "")).strip(),
            "status": str(raw.get("status", "")).strip(),
            "broadcast_phase": str(raw.get("broadcast_phase", "")).strip(),
            "halftime_score": copy.deepcopy(dict(halftime)),
            "events": events,
            "plays": plays,
            "statistician_enabled": bool(raw.get("statistician_enabled")),
            "statistics": copy.deepcopy(dict(statistics)),
            "team_stats": copy.deepcopy(raw.get("team_stats")) if isinstance(raw.get("team_stats"), Mapping) else {},
            "player_stats": copy.deepcopy(raw.get("player_stats")) if isinstance(raw.get("player_stats"), Mapping) else {},
            "player_of_game": copy.deepcopy(raw.get("player_of_game")) if isinstance(raw.get("player_of_game"), Mapping) else {},
        }
        return snapshot

    @staticmethod
    def _leader(home_score: int, visitor_score: int) -> str:
        if home_score > visitor_score:
            return "home"
        if visitor_score > home_score:
            return "visitor"
        return "tie"

    def _scoring_sequence(self, snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for event in snapshot.get("events", []):
            code = self._event_code(event)
            if code not in self.SCORING_CODES:
                continue
            description = self._event_description(event)
            score = self._event_after_score(event)
            row = {
                "event_id": str(event.get("id", "")),
                "code": code,
                "quarter": str(event.get("quarter", "")),
                "clock": str(event.get("clock", "")),
                "description": description,
                "score": {"home": score[0], "visitor": score[1]} if score else {},
            }
            rows.append(row)
        return rows

    def _lead_changes(self, scoring: list[dict[str, Any]]) -> int:
        last_non_tie = ""
        changes = 0
        for row in scoring:
            score = row.get("score", {})
            pair = self._score_pair(score)
            if not pair:
                continue
            leader = self._leader(*pair)
            if leader == "tie":
                continue
            if last_non_tie and leader != last_non_tie:
                changes += 1
            last_non_tie = leader
        return changes

    def _event_group(self, snapshot: Mapping[str, Any], codes: set[str]) -> list[dict[str, Any]]:
        return [
            copy.deepcopy(event)
            for event in snapshot.get("events", [])
            if self._event_code(event) in codes
        ]

    @staticmethod
    def _format_event(row: Mapping[str, Any]) -> str:
        pieces: list[str] = []
        quarter = str(row.get("quarter", "")).strip()
        clock = str(row.get("clock", "")).strip()
        if quarter:
            pieces.append(f"Q{quarter}" if quarter.isdigit() else quarter)
        if clock:
            pieces.append(clock)
        description = str(row.get("description", "")).strip()
        if description:
            pieces.append(description)
        score = row.get("score", {})
        pair = GroundedGameRecapService._score_pair(score)
        if pair:
            pieces.append(f"score {pair[0]}-{pair[1]}")
        return " — ".join(pieces) if pieces else "Recorded scoring event"

    @staticmethod
    def _stat_phrase(value: Any, label: str) -> str:
        try:
            singular = float(value) == 1
        except (TypeError, ValueError):
            singular = False
        human = label[:-1] if singular and label.endswith("s") else label
        return f"{value} {human}"

    def _team_statistics(self, snapshot: Mapping[str, Any]) -> tuple[list[str], list[str]]:
        if not snapshot.get("statistician_enabled"):
            return [], []
        candidates: list[Mapping[str, Any]] = []
        for value in (snapshot.get("team_stats"), snapshot.get("statistics")):
            if isinstance(value, Mapping):
                candidates.append(value)
        team_payload: Mapping[str, Any] = {}
        for candidate in candidates:
            possible = candidate.get("teams") or candidate.get("team") or candidate.get("team_stats") or candidate
            if isinstance(possible, Mapping) and any(key in possible for key in ("home", "visitor")):
                team_payload = possible
                break
        if not team_payload:
            return [], []
        paragraphs: list[str] = []
        paths: list[str] = []
        for side, label in (("home", str(snapshot.get("home_team") or "Home")), ("visitor", str(snapshot.get("visitor_team") or "Visitor"))):
            values = team_payload.get(side)
            if not isinstance(values, Mapping):
                continue
            parts: list[str] = []
            for key, human in self.TEAM_STAT_LABELS.items():
                value = values.get(key)
                if value is None or isinstance(value, (dict, list)):
                    continue
                parts.append(self._stat_phrase(value, human))
                paths.append(f"team_stats.{side}.{key}")
            if parts:
                paragraphs.append(f"{label} recorded " + ", ".join(parts) + ".")
        return paragraphs, paths

    def _player_leaders(self, snapshot: Mapping[str, Any]) -> tuple[list[str], list[str]]:
        if not snapshot.get("statistician_enabled"):
            return [], []
        payload = snapshot.get("player_stats")
        if not isinstance(payload, Mapping) or not payload:
            statistics = snapshot.get("statistics")
            if isinstance(statistics, Mapping) and isinstance(statistics.get("players"), Mapping):
                payload = statistics["players"]
        if not isinstance(payload, Mapping):
            return [], []
        paragraphs: list[str] = []
        paths: list[str] = []
        for category in ("passing", "rushing", "receiving", "defense"):
            leader = payload.get(category)
            if not isinstance(leader, Mapping):
                continue
            name = str(leader.get("name") or leader.get("player_name") or "").strip()
            if not name:
                continue
            facts: list[str] = []
            for key, value in leader.items():
                if key in {"name", "player_name", "id", "player_id", "team"} or isinstance(value, (dict, list)) or value in (None, ""):
                    continue
                human = str(key).replace("_", " ")
                facts.append(self._stat_phrase(value, human))
                paths.append(f"player_stats.{category}.{key}")
            if facts:
                paragraphs.append(f"Recorded {category} leader {name}: " + ", ".join(facts) + ".")
        return paragraphs, paths

    def _build_generated(self, snapshot: Mapping[str, Any], article_style: str = "local_sports") -> dict[str, Any]:
        broadcast_id = str(snapshot.get("broadcast_id", "")).strip()
        home = str(snapshot.get("home_team", "")).strip()
        visitor = str(snapshot.get("visitor_team", "")).strip()
        if not broadcast_id or not home or not visitor:
            raise ValueError("BROADCAST_NOT_READY")
        final_pair = self._score_pair(snapshot)
        if not final_pair:
            raise ValueError("FINAL_SCORE_UNAVAILABLE")
        home_score, visitor_score = final_pair
        winner = home if home_score > visitor_score else visitor if visitor_score > home_score else ""
        loser = visitor if winner == home else home if winner == visitor else ""
        if winner:
            headline = f"{winner} tops {loser} {max(home_score, visitor_score)}-{min(home_score, visitor_score)}"
            lead = f"{winner} defeated {loser} {max(home_score, visitor_score)}-{min(home_score, visitor_score)}."
        else:
            headline = f"{home} and {visitor} finish tied {home_score}-{visitor_score}"
            lead = f"{home} and {visitor} finished tied {home_score}-{visitor_score}."

        scoring = self._scoring_sequence(snapshot)
        turnovers = self._event_group(snapshot, self.TURNOVER_CODES)
        delays = self._event_group(snapshot, self.WEATHER_DELAY_CODES)
        resumptions = self._event_group(snapshot, self.WEATHER_RESUME_CODES)
        emergencies = self._event_group(snapshot, self.WEATHER_EMERGENCY_CODES)
        lead_changes = self._lead_changes(scoring)
        halftime_pair = self._score_pair(snapshot.get("halftime_score"))

        sections: list[dict[str, Any]] = []
        event_ids: list[str] = []
        play_ids = [str(play.get("play_id") or play.get("id") or "") for play in snapshot.get("plays", []) if str(play.get("play_id") or play.get("id") or "")]
        omitted: list[str] = []

        if halftime_pair:
            sections.append(
                {
                    "key": "halftime",
                    "heading": "Halftime",
                    "paragraphs": [
                        f"At halftime, {home} led {visitor} {halftime_pair[0]}-{halftime_pair[1]}."
                        if halftime_pair[0] > halftime_pair[1]
                        else f"At halftime, {visitor} led {home} {halftime_pair[1]}-{halftime_pair[0]}."
                        if halftime_pair[1] > halftime_pair[0]
                        else f"The game was tied {halftime_pair[0]}-{halftime_pair[1]} at halftime."
                    ],
                    "source_refs": ["halftime_score"],
                }
            )
        else:
            omitted.append("halftime score")

        if scoring:
            paragraphs = [self._format_event(row) + "." for row in scoring]
            event_ids.extend(str(row.get("event_id", "")) for row in scoring if str(row.get("event_id", "")))
            sections.append(
                {
                    "key": "scoring_sequence",
                    "heading": "Scoring sequence",
                    "paragraphs": paragraphs,
                    "source_refs": [str(row.get("event_id", "")) for row in scoring if str(row.get("event_id", ""))],
                }
            )
        else:
            omitted.append("scoring sequence")

        if lead_changes:
            sections.append(
                {
                    "key": "lead_changes",
                    "heading": "Lead changes",
                    "paragraphs": [f"The recorded scoring sequence produced {lead_changes} lead change{'s' if lead_changes != 1 else ''}."],
                    "source_refs": [str(row.get("event_id", "")) for row in scoring if str(row.get("event_id", ""))],
                }
            )
        else:
            omitted.append("lead changes")

        if turnovers:
            paragraphs = [self._event_description(row) for row in turnovers if self._event_description(row)]
            if not paragraphs:
                paragraphs = [f"The event log contains {len(turnovers)} recorded turnover{'s' if len(turnovers) != 1 else ''}."]
            ids = [str(row.get("id", "")) for row in turnovers if str(row.get("id", ""))]
            event_ids.extend(ids)
            sections.append({"key": "turnovers", "heading": "Turnovers", "paragraphs": paragraphs, "source_refs": ids})
        else:
            omitted.append("turnovers")

        weather_rows = delays + resumptions + emergencies
        if weather_rows:
            paragraphs = [self._event_description(row) for row in weather_rows if self._event_description(row)]
            if paragraphs:
                ids = [str(row.get("id", "")) for row in weather_rows if str(row.get("id", ""))]
                event_ids.extend(ids)
                sections.append({"key": "weather", "heading": "Weather and delays", "paragraphs": paragraphs, "source_refs": ids})
        else:
            omitted.append("weather delays or resumptions")

        team_paragraphs, team_paths = self._team_statistics(snapshot)
        player_paragraphs, player_paths = self._player_leaders(snapshot)
        stat_paths = team_paths + player_paths
        if team_paragraphs:
            sections.append({"key": "team_statistics", "heading": "Team statistics", "paragraphs": team_paragraphs, "source_refs": team_paths})
        if player_paragraphs:
            sections.append({"key": "player_leaders", "heading": "Recorded leaders", "paragraphs": player_paragraphs, "source_refs": player_paths})
        if not snapshot.get("statistician_enabled"):
            omitted.append("statistician-only team and player statistics")
        elif not team_paragraphs and not player_paragraphs:
            omitted.append("unavailable team and player statistic fields")

        # Build a readable article from the same grounded facts. Sentence choice is
        # deterministic for a broadcast so regeneration is stable while different
        # games receive some natural variation.
        article_style = article_style if article_style in {"straight_news", "local_sports", "feature_recap", "brief_report"} else "local_sports"
        variant = int(hashlib.sha256((broadcast_id + article_style).encode("utf-8")).hexdigest()[:2], 16) % 4
        if winner:
            lead_variants = [
                f"{winner} came away with a {max(home_score, visitor_score)}-{min(home_score, visitor_score)} victory over {loser}.",
                f"{winner} closed the night with a {max(home_score, visitor_score)}-{min(home_score, visitor_score)} win against {loser}.",
                f"A complete-game effort carried {winner} past {loser}, {max(home_score, visitor_score)}-{min(home_score, visitor_score)}.",
                f"{winner} secured a {max(home_score, visitor_score)}-{min(home_score, visitor_score)} decision over {loser}."
            ]
            lead = lead_variants[variant]
        else:
            lead = f"{home} and {visitor} played to a {home_score}-{visitor_score} tie."

        article_paragraphs: list[str] = [lead]
        if halftime_pair:
            if halftime_pair[0] > halftime_pair[1]:
                article_paragraphs.append(f"{home} carried a {halftime_pair[0]}-{halftime_pair[1]} lead into halftime.")
            elif halftime_pair[1] > halftime_pair[0]:
                article_paragraphs.append(f"{visitor} led {halftime_pair[1]}-{halftime_pair[0]} at the break.")
            else:
                article_paragraphs.append(f"The teams went to halftime tied at {halftime_pair[0]}.")

        if scoring:
            flow_sentences = []
            for row in scoring[:8]:
                description = str(row.get("description") or "").strip()
                if not description:
                    continue
                when = " ".join(part for part in [str(row.get("quarter") or "").strip(), str(row.get("clock") or "").strip()] if part)
                flow_sentences.append(f"{description}{f' ({when})' if when else ''}.")
            if flow_sentences:
                article_paragraphs.append(" ".join(flow_sentences))

        if turnovers:
            article_paragraphs.append(f"The recorded game log included {len(turnovers)} turnover{'s' if len(turnovers) != 1 else ''}, an important part of the game flow.")

        if team_paragraphs:
            article_paragraphs.append(" ".join(team_paragraphs))
        if player_paragraphs:
            article_paragraphs.append(" ".join(player_paragraphs))

        pog = snapshot.get("player_of_game") if isinstance(snapshot.get("player_of_game"), Mapping) else {}
        pog_name = str(pog.get("name") or pog.get("player_name") or "").strip()
        if not pog_name:
            for event in snapshot.get("events", []):
                if self._event_code(event) == "PLAYER_OF_GAME":
                    pog_name = str(event.get("player_name") or event.get("player") or self._event_description(event)).strip()
                    if pog_name:
                        event_ids.append(str(event.get("id") or ""))
                        break
        if pog_name:
            article_paragraphs.append(f"{pog_name} was selected as the Player of the Game.")

        closing_variants = [
            f"The result moves {winner or home} forward as attention turns to the next game.",
            f"With the final recorded, both teams now turn their attention to the next week.",
            f"The game concluded with {home} at {home_score} and {visitor} at {visitor_score}.",
            "The recap is based entirely on events and statistics recorded during the broadcast."
        ]
        closing = closing_variants[variant]
        body = "\n\n".join(article_paragraphs[1:])
        social_summary = f"FINAL: {home} {home_score}, {visitor} {visitor_score}."
        if pog_name:
            social_summary += f" Player of the Game: {pog_name}."
        social_summary = social_summary[:500]

        source_payload = {
            "broadcast_id": broadcast_id,
            "home_team": home,
            "visitor_team": visitor,
            "home_score": home_score,
            "visitor_score": visitor_score,
            "halftime_score": copy.deepcopy(snapshot.get("halftime_score", {})),
            "events": snapshot.get("events", []),
            "plays": snapshot.get("plays", []),
            "statistician_enabled": bool(snapshot.get("statistician_enabled")),
            "statistics": snapshot.get("statistics", {}),
            "team_stats": snapshot.get("team_stats", {}),
            "player_stats": snapshot.get("player_stats", {}),
            "player_of_game": snapshot.get("player_of_game", {}),
        }
        return {
            "broadcast_id": broadcast_id,
            "headline": headline,
            "lead": lead,
            "body": body,
            "closing": closing,
            "social_summary": social_summary,
            "sections": sections,
            "facts": {
                "home_team": home,
                "visitor_team": visitor,
                "home_score": home_score,
                "visitor_score": visitor_score,
                "winner": winner,
                "halftime_score": {"home": halftime_pair[0], "visitor": halftime_pair[1]} if halftime_pair else {},
                "scoring_events": len(scoring),
                "lead_changes": lead_changes,
                "turnovers": len(turnovers),
                "weather_events": len(weather_rows),
            },
            "grounding": {
                "policy": "Use only recorded game events and available statistics; omit missing data.",
                "source_hash": self._canonical_hash(source_payload),
                "event_ids": sorted(set(filter(None, event_ids))),
                "play_ids": sorted(set(filter(None, play_ids))),
                "stat_paths": sorted(set(stat_paths)),
                "omitted": sorted(set(omitted)),
                "operator_edited_fields": [],
                "generated_at": int(self._clock()),
            },
        }

    @staticmethod
    def _recap_index(state: Mapping[str, Any], recap_id: str) -> int:
        for index, recap in enumerate(state.get("recaps", [])):
            if str(recap.get("id", "")) == recap_id:
                return index
        return -1

    @staticmethod
    def _safe_id(broadcast_id: str) -> str:
        value = re.sub(r"[^A-Za-z0-9_.-]+", "-", broadcast_id).strip("-")
        return (value or "GAME")[:80]

    def _current_hash(self, broadcast_id: str) -> str:
        snapshot = self._source_snapshot()
        if str(snapshot.get("broadcast_id", "")) != broadcast_id:
            return ""
        try:
            return str(self._build_generated(snapshot)["grounding"]["source_hash"])
        except ValueError:
            return ""

    def _public_recap(self, recap: Mapping[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(dict(recap))
        current_hash = self._current_hash(str(result.get("broadcast_id", "")))
        stored_hash = str(result.get("grounding", {}).get("source_hash", ""))
        result["stale"] = bool(current_hash and stored_hash and current_hash != stored_hash)
        return result

    def status(self) -> RecapResult:
        with self._lock:
            state = self._load()
            recaps = [self._public_recap(item) for item in state["recaps"][-100:]]
        return RecapResult(
            "OK",
            {
                "recaps": recaps,
                "audit": copy.deepcopy(state["audit"][-200:]),
                "policy": {
                    "recorded_events_only": True,
                    "available_statistics_only": True,
                    "missing_data_omitted": True,
                    "operator_review_required": True,
                },
            },
        )

    def generate(self, *, regenerate: bool = False, article_style: str = "local_sports") -> RecapResult:
        snapshot = self._source_snapshot()
        try:
            generated = self._build_generated(snapshot, article_style)
        except ValueError as exc:
            return RecapResult(str(exc))
        broadcast_id = generated["broadcast_id"]
        recap_id = f"RECAP-{self._safe_id(broadcast_id)}"
        now = int(self._clock())
        with self._lock:
            state = self._load()
            index = self._recap_index(state, recap_id)
            if index >= 0 and not regenerate:
                return RecapResult("RECAP_ALREADY_EXISTS", {"recap": self._public_recap(state["recaps"][index])})
            prior_revision = int(state["recaps"][index].get("revision", 0) or 0) if index >= 0 else 0
            recap = {
                "id": recap_id,
                "broadcast_id": broadcast_id,
                "status": "DRAFT",
                "revision": prior_revision + 1,
                "headline": generated["headline"],
                "lead": generated["lead"],
                "body": generated["body"],
                "closing": generated["closing"],
                "social_summary": generated["social_summary"],
                "article_style": article_style if article_style in {"straight_news", "local_sports", "feature_recap", "brief_report"} else "local_sports",
                "sponsor_id": "",
                "sponsor_name": "",
                "sections": generated["sections"],
                "facts": generated["facts"],
                "grounding": generated["grounding"],
                "created_at": int(state["recaps"][index].get("created_at", now) or now) if index >= 0 else now,
                "updated_at": now,
                "approved_at": 0,
                "approved_by": "",
                "social_draft_id": "",
            }
            if index >= 0:
                state["recaps"][index] = recap
            else:
                state["recaps"] = (state["recaps"] + [recap])[-self.MAX_RECAPS :]
            self._audit(state, "RECAP_REGENERATED" if index >= 0 else "RECAP_GENERATED", recap_id=recap_id, broadcast_id=broadcast_id)
            self._write(state)
        return RecapResult("RECAP_GENERATED", {"recap": self._public_recap(recap)})

    def read(self, recap_id: Any) -> RecapResult:
        recap_id = str(recap_id or "").strip()
        with self._lock:
            state = self._load()
            index = self._recap_index(state, recap_id)
            if index < 0:
                return RecapResult("RECAP_NOT_FOUND")
            return RecapResult("OK", {"recap": self._public_recap(state["recaps"][index])})

    def update(self, recap_id: Any, incoming: Mapping[str, Any] | None) -> RecapResult:
        recap_id = str(recap_id or "").strip()
        data = dict(incoming or {})
        unknown = sorted(set(data) - self.EDITABLE_FIELDS)
        if unknown:
            return RecapResult("RECAP_UPDATE_INVALID", {"unknown": unknown})
        with self._lock:
            state = self._load()
            index = self._recap_index(state, recap_id)
            if index < 0:
                return RecapResult("RECAP_NOT_FOUND")
            recap = state["recaps"][index]
            if recap.get("status") == "DELETED":
                return RecapResult("RECAP_IMMUTABLE")
            edited = set(recap.get("grounding", {}).get("operator_edited_fields", []))
            for key in self.EDITABLE_FIELDS:
                if key in data:
                    limit = 20000 if key == "body" else 1000
                    recap[key] = str(data[key] or "").strip()[:limit]
                    edited.add(key)
            recap.setdefault("grounding", {})["operator_edited_fields"] = sorted(edited)
            recap["status"] = "DRAFT"
            recap["approved_at"] = 0
            recap["approved_by"] = ""
            recap["updated_at"] = int(self._clock())
            self._audit(state, "RECAP_UPDATED", recap_id=recap_id, fields=sorted(set(data)))
            self._write(state)
        return RecapResult("RECAP_UPDATED", {"recap": self._public_recap(recap)})

    def approve(self, recap_id: Any, *, operator: Any, confirmation: Any) -> RecapResult:
        recap_id = str(recap_id or "").strip()
        if str(confirmation or "") != self.APPROVAL_PHRASE:
            return RecapResult("RECAP_APPROVAL_CONFIRMATION_REQUIRED")
        operator = str(operator or "operator").strip()[:120]
        with self._lock:
            state = self._load()
            index = self._recap_index(state, recap_id)
            if index < 0:
                return RecapResult("RECAP_NOT_FOUND")
            recap = state["recaps"][index]
            if recap.get("status") not in {"DRAFT", "APPROVED"}:
                return RecapResult("RECAP_NOT_APPROVABLE")
            public = self._public_recap(recap)
            if public.get("stale"):
                return RecapResult("RECAP_STALE")
            recap["status"] = "APPROVED"
            recap["approved_at"] = int(self._clock())
            recap["approved_by"] = operator
            recap["updated_at"] = int(self._clock())
            self._audit(state, "RECAP_APPROVED", recap_id=recap_id, operator=operator)
            self._write(state)
        return RecapResult("RECAP_APPROVED", {"recap": self._public_recap(recap)})

    def grounding_report(self, recap_id: Any) -> RecapResult:
        result = self.read(recap_id)
        if not result.ok:
            return result
        recap = result.data["recap"]
        return RecapResult(
            "OK",
            {
                "grounding": copy.deepcopy(recap.get("grounding", {})),
                "facts": copy.deepcopy(recap.get("facts", {})),
                "sections": copy.deepcopy(recap.get("sections", [])),
                "stale": bool(recap.get("stale")),
            },
        )

    def export_text(self, recap_id: Any) -> RecapResult:
        result = self.read(recap_id)
        if not result.ok:
            return result
        recap = result.data["recap"]
        sponsor = str(recap.get("sponsor_name") or "").strip()
        parts = [f"Presented by {sponsor}" if sponsor else "", recap.get("headline", ""), recap.get("lead", ""), recap.get("body", ""), recap.get("closing", "")]
        text = "\n\n".join(str(part).strip() for part in parts if str(part).strip()) + "\n"
        return RecapResult("OK", {"text": text, "filename": f"{recap['id']}.txt"})

    def create_social_final_draft(self, recap_id: Any) -> RecapResult:
        recap_id = str(recap_id or "").strip()
        if self._create_social_draft is None:
            return RecapResult("SOCIAL_HANDOFF_UNAVAILABLE")
        with self._lock:
            state = self._load()
            index = self._recap_index(state, recap_id)
            if index < 0:
                return RecapResult("RECAP_NOT_FOUND")
            recap = copy.deepcopy(state["recaps"][index])
            if recap.get("status") != "APPROVED":
                return RecapResult("RECAP_NOT_APPROVED")
        result = self._create_social_draft(recap)
        code = str(getattr(result, "code", ""))
        data = copy.deepcopy(getattr(result, "data", {}) or {})
        if not getattr(result, "ok", False):
            return RecapResult("SOCIAL_DRAFT_FAILED", {"social_code": code, **data})
        draft = data.get("draft", {}) if isinstance(data, Mapping) else {}
        draft_id = str(draft.get("id", "")) if isinstance(draft, Mapping) else ""
        with self._lock:
            state = self._load()
            index = self._recap_index(state, recap_id)
            if index < 0:
                return RecapResult("RECAP_NOT_FOUND")
            state["recaps"][index]["social_draft_id"] = draft_id
            state["recaps"][index]["updated_at"] = int(self._clock())
            self._audit(state, "RECAP_SOCIAL_DRAFT_CREATED", recap_id=recap_id, social_draft_id=draft_id)
            self._write(state)
            recap = copy.deepcopy(state["recaps"][index])
        return RecapResult("SOCIAL_DRAFT_CREATED", {"recap": self._public_recap(recap), "social_draft": draft})

    def delete(self, recap_id: Any, confirmation: Any) -> RecapResult:
        recap_id = str(recap_id or "").strip()
        if str(confirmation or "") != self.DELETE_PHRASE:
            return RecapResult("RECAP_DELETE_CONFIRMATION_REQUIRED")
        with self._lock:
            state = self._load()
            index = self._recap_index(state, recap_id)
            if index < 0:
                return RecapResult("RECAP_NOT_FOUND")
            state["recaps"][index]["status"] = "DELETED"
            state["recaps"][index]["updated_at"] = int(self._clock())
            self._audit(state, "RECAP_DELETED", recap_id=recap_id)
            self._write(state)
        return RecapResult("RECAP_DELETED", {"recap_id": recap_id})
