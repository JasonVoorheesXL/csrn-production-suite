from __future__ import annotations

import copy
import json
import re
import time

import pronouncing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


Roster = dict[str, Any]
School = dict[str, Any]
Player = dict[str, Any]
RosterLoader = Callable[[], list[Roster]]
RosterSaver = Callable[[list[Roster]], None]
SchoolLoader = Callable[[], list[School]]
Clock = Callable[[], float]


@dataclass(frozen=True)
class RosterResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class RosterService:
    """Roster-domain behavior independent of Flask routes."""

    _PRONUNCIATION_VOWELS = {
        "AA": "ah",
        "AE": "a",
        "AH": "uh",
        "AO": "aw",
        "AW": "ow",
        "AY": "eye",
        "EH": "eh",
        "ER": "er",
        "EY": "ay",
        "IH": "ih",
        "IY": "ee",
        "OW": "oh",
        "OY": "oy",
        "UH": "oo",
        "UW": "oo",
    }

    _PRONUNCIATION_CONSONANTS = {
        "B": "b",
        "CH": "ch",
        "D": "d",
        "DH": "th",
        "F": "f",
        "G": "g",
        "HH": "h",
        "JH": "j",
        "K": "k",
        "L": "l",
        "M": "m",
        "N": "n",
        "NG": "ng",
        "P": "p",
        "R": "r",
        "S": "s",
        "SH": "sh",
        "T": "t",
        "TH": "th",
        "V": "v",
        "W": "w",
        "Y": "y",
        "Z": "z",
        "ZH": "zh",
    }

    @classmethod
    def pronunciation_for_word(cls, word: str) -> str:
        clean = str(word or "").strip()
        lookup = re.sub(r"[^A-Za-z'-]", "", clean).lower()
        if not lookup:
            return ""

        phones = pronouncing.phones_for_word(lookup)
        if not phones:
            return ""

        parsed = []
        for token in phones[0].split():
            match = re.fullmatch(r"([A-Z]+)([012]?)", token)
            if match:
                parsed.append(match.groups())

        if not parsed:
            return ""

        vowel_positions = [
            i for i, (sound, _) in enumerate(parsed)
            if sound in cls._PRONUNCIATION_VOWELS
        ]
        if not vowel_positions:
            return ""

        valid_single_onsets = {
            "B","CH","D","DH","F","G","HH","JH","K","L","M","N",
            "P","R","S","SH","T","TH","V","W","Y","Z","ZH"
        }

        valid_onset_clusters = {
            ("P","L"),("P","R"),
            ("B","L"),("B","R"),
            ("T","R"),("D","R"),
            ("K","L"),("K","R"),("K","W"),
            ("G","L"),("G","R"),("G","W"),
            ("F","L"),("F","R"),
            ("TH","R"),("SH","R"),
            ("S","L"),("S","M"),("S","N"),
            ("S","P"),("S","T"),("S","K"),("S","W"),
            ("S","P","L"),("S","P","R"),
            ("S","T","R"),
            ("S","K","L"),("S","K","R"),("S","K","W"),
        }

        def consonant_text(sound: str) -> str:
            return cls._PRONUNCIATION_CONSONANTS.get(
                sound,
                sound.lower(),
            )

        def vowel_text(sound: str) -> str:
            return cls._PRONUNCIATION_VOWELS.get(
                sound,
                sound.lower(),
            )

        def onset_split(cluster: list[tuple[str, str]]) -> int:
            if not cluster:
                return 0

            sounds = [sound for sound, _ in cluster]

            for length in range(min(3, len(sounds)), 1, -1):
                suffix = tuple(sounds[-length:])
                if suffix in valid_onset_clusters:
                    return len(sounds) - length

            if sounds[-1] in valid_single_onsets:
                return len(sounds) - 1

            return len(sounds)

        syllables = []
        first_vowel = vowel_positions[0]

        pending_onset = parsed[:first_vowel]

        for vowel_number, vowel_index in enumerate(vowel_positions):
            sound, stress = parsed[vowel_index]

            next_vowel = (
                vowel_positions[vowel_number + 1]
                if vowel_number + 1 < len(vowel_positions)
                else None
            )

            if next_vowel is None:
                between = parsed[vowel_index + 1:]
                split_at = len(between)
            else:
                between = parsed[vowel_index + 1:next_vowel]
                split_at = onset_split(between)

            coda = between[:split_at]
            next_onset = between[split_at:]

            pieces = []

            for consonant, _ in pending_onset:
                pieces.append(consonant_text(consonant))

            pieces.append(vowel_text(sound))

            for consonant, _ in coda:
                pieces.append(consonant_text(consonant))

            syllable = "".join(pieces)

            if stress == "1":
                syllable = syllable.upper()
            else:
                syllable = syllable.lower()

            if syllable:
                syllables.append(syllable)

            pending_onset = next_onset

        result = "-".join(syllables)

        # Convert technically faithful CMUdict rendering into a more
        # broadcaster-friendly pronunciation guide. These are phonetic
        # cleanup rules, not player-specific exceptions.
        replacements = (
            ("wehl", "well"),
            ("WEHL", "WELL"),
            ("rihng", "ring"),
            ("RIHNG", "RING"),
            ("ihng", "ing"),
            ("IHNG", "ING"),
            ("tuhn", "tuhn"),
            ("TUHN", "TUHN"),
            ("chuhnt", "chunt"),
            ("CHUHNT", "CHUNT"),
            ("duhn", "duhn"),
            ("DUHN", "DUHN"),
        )

        for source, target in replacements:
            result = result.replace(source, target)

        return result


    @classmethod
    def fallback_pronunciation_for_word(cls, word: str) -> str:
        """
        Best-effort broadcaster-friendly fallback for names absent from CMUdict.
        This is intentionally conservative: produce something readable rather
        than pretending an uncertain pronunciation is authoritative.
        """
        clean = str(word or "").strip()
        if not clean:
            return ""

        # Ignore common suffixes/titles rather than trying to pronounce them
        # as part of the player's actual name.
        normalized = re.sub(r"[^A-Za-z']", "", clean).lower()
        if normalized in {
            "jr", "sr", "ii", "iii", "iv",
        }:
            return ""

        # Preserve apostrophe-separated name components.
        parts = [part for part in re.split(r"['?]+", clean) if part]
        if len(parts) > 1:
            rendered = [
                cls.fallback_pronunciation_for_word(part)
                for part in parts
            ]
            return "-".join(part for part in rendered if part)

        lookup = re.sub(r"[^A-Za-z]", "", clean).lower()
        if not lookup:
            return ""

        # Common name-oriented spelling patterns.
        value = lookup
        substitutions = (
            (r"^mc", "mick"),
            (r"^mac", "mack"),
            (r"ph", "f"),
            (r"qu", "kw"),
            (r"tion$", "shun"),
            (r"tious$", "shus"),
            (r"ious$", "eeus"),
            (r"eigh", "ay"),
            (r"ough", "oh"),
            (r"ee", "ee"),
            (r"oo", "oo"),
        )
        for pattern, replacement in substitutions:
            value = re.sub(pattern, replacement, value)

        # Split by vowel nuclei. This is not linguistic syllabification;
        # it is only a readable fallback for broadcaster notes.
        chunks = re.findall(
            r"[^aeiouy]*[aeiouy]+(?:[^aeiouy](?=[^aeiouy]*[aeiouy]|$))?",
            value,
        )

        if not chunks:
            return clean.upper()

        if len(chunks) == 1:
            return chunks[0].upper()

        # Favor first-syllable stress for unknown names. Broadcasters can
        # correct and verify anything unusual afterward.
        return "-".join(
            chunk.upper() if index == 0 else chunk.lower()
            for index, chunk in enumerate(chunks)
        )

    @classmethod
    def pronunciation_for_name(
        cls,
        first_name: str = "",
        last_name: str = "",
    ) -> str:
        """
        Build a complete broadcaster pronunciation guide.

        CMUdict is preferred for every individual word. Unknown words fall
        back to the conservative spelling-based renderer so that one unknown
        first name does not cause the entire first name to disappear.
        """
        raw_parts = []

        for field in (first_name, last_name):
            field = str(field or "").strip()
            if not field:
                continue

            # Names can contain spaces, hyphens, suffixes, or parenthetical
            # nicknames from imported roster data.
            field = re.sub(r"\([^)]*\)", "", field).strip()

            for token in re.split(r"\s+", field):
                token = token.strip(" ,.")
                if not token:
                    continue

                # Hyphenated names should retain each component.
                hyphen_parts = [
                    part for part in token.split("-") if part
                ]

                rendered_parts = []
                for part in hyphen_parts:
                    pronunciation = cls.pronunciation_for_word(part)
                    if not pronunciation:
                        pronunciation = cls.fallback_pronunciation_for_word(
                            part
                        )
                    if pronunciation:
                        rendered_parts.append(pronunciation)

                if rendered_parts:
                    raw_parts.append("-".join(rendered_parts))

        return " ".join(raw_parts).strip()



    @staticmethod
    def _pronunciation_dictionary_key(value: str) -> str:
        text = str(value or "").strip().casefold()
        text = text.replace("?", "'").replace("`", "'")
        text = re.sub(r"[^a-z0-9' -]+", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _load_pronunciation_dictionary(self) -> dict[str, str]:
        path = self._pronunciation_dictionary_path
        if path is None or not path.exists():
            return {}

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}

        if isinstance(payload, dict) and isinstance(payload.get("entries"), dict):
            payload = payload["entries"]

        if not isinstance(payload, dict):
            return {}

        entries: dict[str, str] = {}

        for raw_key, raw_value in payload.items():
            key = self._pronunciation_dictionary_key(raw_key)
            value = str(raw_value or "").strip()

            if key and value:
                entries[key] = value

        return entries

    def _save_pronunciation_dictionary(
        self,
        entries: dict[str, str],
    ) -> bool:
        path = self._pronunciation_dictionary_path
        if path is None:
            return False

        cleaned: dict[str, str] = {}

        for raw_key, raw_value in entries.items():
            key = self._pronunciation_dictionary_key(raw_key)
            value = str(raw_value or "").strip()

            if key and value:
                cleaned[key] = value

        payload = {
            "version": 1,
            "entries": dict(sorted(cleaned.items())),
        }

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.tmp")
            temporary.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError:
            return False

        return True


    def pronunciation_for_player_name(
        self,
        first_name: str = "",
        last_name: str = "",
    ) -> str:
        """
        Resolve a broadcaster-friendly pronunciation for a player's full name.

        Resolution order:
        1. Learned pronunciation dictionary
        2. CMUdict + conservative fallback engine
        """
        full_name = " ".join(
            part
            for part in (
                str(first_name or "").strip(),
                str(last_name or "").strip(),
            )
            if part
        ).strip()

        if not full_name:
            return ""

        dictionary = self._load_pronunciation_dictionary()
        key = self._pronunciation_dictionary_key(full_name)

        learned = str(dictionary.get(key, "")).strip()
        if learned:
            return learned

        return self.pronunciation_for_name(
            first_name,
            last_name,
        )


    def remember_player_pronunciation(
        self,
        first_name: str,
        last_name: str,
        pronunciation: str,
    ) -> bool:
        """
        Save a confirmed player pronunciation for reuse on future rosters.
        """
        full_name = " ".join(
            part
            for part in (
                str(first_name or "").strip(),
                str(last_name or "").strip(),
            )
            if part
        ).strip()

        value = str(pronunciation or "").strip()

        if not full_name or not value:
            return False

        key = self._pronunciation_dictionary_key(full_name)
        if not key:
            return False

        dictionary = self._load_pronunciation_dictionary()
        dictionary[key] = value

        return self._save_pronunciation_dictionary(dictionary)



    UPDATE_FIELDS = (
        "school_id",
        "sport",
        "season",
        "level",
        "division",
    )
    PLAYER_STRING_FIELDS = (
        "number",
        "first_name",
        "last_name",
        "preferred_name",
        "position",
        "secondary_position",
        "grade",
        "height",
        "weight",
        "pronunciation",
        "headshot",
    )
    PLAYER_BOOLEAN_FIELDS = (
        "captain",
        "starter",
        "pronunciation_verified",
    )

    def __init__(
        self,
        *,
        load_rosters: RosterLoader,
        save_rosters: RosterSaver,
        load_schools: SchoolLoader,
        clock: Clock | None = None,
        pronunciation_dictionary_path: Path | str | None = None,
    ) -> None:
        self._load_rosters = load_rosters
        self._save_rosters = save_rosters
        self._load_schools = load_schools
        self._clock = clock or time.time
        self._pronunciation_dictionary_path = (
            Path(pronunciation_dictionary_path)
            if pronunciation_dictionary_path
            else None
        )

    @staticmethod
    def normalize_roster_id(value: str) -> str:
        cleaned = "".join(
            character.lower() if character.isalnum() else "-"
            for character in str(value or "").strip()
        )
        while "--" in cleaned:
            cleaned = cleaned.replace("--", "-")
        return cleaned.strip("-") or "roster"

    @classmethod
    def normalize_player_id(cls, value: str) -> str:
        return cls.normalize_roster_id(value)

    @staticmethod
    def summary(
        roster: Roster,
        schools: list[School] | None = None,
    ) -> Roster:
        school_list = schools or []
        school = next(
            (
                item
                for item in school_list
                if str(item.get("id", ""))
                == str(roster.get("school_id", ""))
            ),
            {},
        )
        players = (
            roster.get("players", [])
            if isinstance(roster.get("players"), list)
            else []
        )
        payload = copy.deepcopy(roster)
        payload.update(
            {
                "school_name": (
                    school.get("broadcast_name")
                    or school.get("official_name")
                    or roster.get("school_id", "Unknown School")
                ),
                "active_count": sum(
                    1
                    for player in players
                    if str(player.get("status", "active")).lower()
                    == "active"
                ),
                "inactive_count": sum(
                    1
                    for player in players
                    if str(player.get("status", "active")).lower()
                    == "inactive"
                ),
                "player_count": len(players),
            }
        )
        return payload

    def list_rosters(self) -> list[Roster]:
        schools = self._load_schools()
        return [
            self.summary(roster, schools)
            for roster in self._load_rosters()
        ]

    def read(self, roster_id: str) -> RosterResult:
        roster = self._find(self._load_rosters(), roster_id)
        if roster is None:
            return RosterResult("ROSTER_NOT_FOUND")
        return RosterResult(
            "OK",
            {"roster": self.summary(roster, self._load_schools())},
        )

    def create(self, incoming: Roster) -> RosterResult:
        incoming = copy.deepcopy(incoming)
        school_id = str(incoming.get("school_id", "")).strip()
        sport = str(incoming.get("sport", "Football")).strip() or "Football"
        season = str(incoming.get("season", "")).strip()
        level = str(incoming.get("level", "Varsity")).strip() or "Varsity"
        division = str(incoming.get("division", "Boys")).strip() or "Boys"

        if not school_id or not season:
            return RosterResult("SCHOOL_AND_SEASON_REQUIRED")

        rosters = self._load_rosters()
        schools = self._load_schools()
        duplicate = next(
            (
                roster
                for roster in rosters
                if str(roster.get("school_id", "")) == school_id
                and str(roster.get("sport", "")).lower() == sport.lower()
                and str(roster.get("season", "")) == season
                and str(roster.get("level", "")).lower() == level.lower()
                and str(roster.get("division", "")).lower()
                == division.lower()
            ),
            None,
        )
        if duplicate is not None:
            return RosterResult(
                "ROSTER_ALREADY_EXISTS",
                {"roster": self.summary(duplicate, schools)},
            )

        roster_id = self.normalize_roster_id(
            f"{school_id}-{sport}-{season}-{level}-{division}"
        )
        base_id = roster_id
        suffix = 2
        while any(roster.get("id") == roster_id for roster in rosters):
            roster_id = f"{base_id}-{suffix}"
            suffix += 1

        now = int(self._clock())
        record: Roster = {
            "id": roster_id,
            "school_id": school_id,
            "sport": sport,
            "season": season,
            "level": level,
            "division": division,
            "players": [],
            "created_at": now,
            "updated_at": now,
        }
        rosters.append(record)
        self._save_rosters(rosters)
        return RosterResult(
            "OK",
            {"roster": self.summary(record, schools)},
        )

    def update(self, roster_id: str, incoming: Roster) -> RosterResult:
        rosters = self._load_rosters()
        roster = self._find(rosters, roster_id)
        if roster is None:
            return RosterResult("ROSTER_NOT_FOUND")

        for field_name in self.UPDATE_FIELDS:
            if field_name in incoming:
                roster[field_name] = str(incoming[field_name]).strip()
        roster["updated_at"] = int(self._clock())
        self._save_rosters(rosters)
        return RosterResult(
            "OK",
            {"roster": self.summary(roster, self._load_schools())},
        )

    def delete(self, roster_id: str) -> RosterResult:
        rosters = self._load_rosters()
        if self._find(rosters, roster_id) is None:
            return RosterResult("ROSTER_NOT_FOUND")
        self._save_rosters(
            [
                roster
                for roster in rosters
                if str(roster.get("id", "")) != str(roster_id)
            ]
        )
        return RosterResult("OK", {"ok": True})

    def create_player(
        self,
        roster_id: str,
        incoming: Player,
    ) -> RosterResult:
        rosters = self._load_rosters()
        roster = self._find(rosters, roster_id)
        if roster is None:
            return RosterResult("ROSTER_NOT_FOUND")

        first_name = str(incoming.get("first_name", "")).strip()
        last_name = str(incoming.get("last_name", "")).strip()
        number = str(incoming.get("number", "")).strip()
        if not first_name and not last_name:
            return RosterResult("PLAYER_NAME_REQUIRED")

        players = roster.setdefault("players", [])
        player_id = self._unique_player_id(
            players,
            incoming.get("id") or f"{number}-{first_name}-{last_name}",
        )
        duplicate_number = self._duplicate_number(players, number)
        player = self._player_record(
            incoming,
            player_id=player_id,
            first_name=first_name,
            last_name=last_name,
            number=number,
        )
        players.append(player)
        roster["updated_at"] = int(self._clock())
        self._save_rosters(rosters)
        return RosterResult(
            "OK",
            {
                "player": copy.deepcopy(player),
                "warning": (
                    "DUPLICATE_JERSEY_NUMBER" if duplicate_number else ""
                ),
            },
        )

    def update_player(
        self,
        roster_id: str,
        player_id: str,
        incoming: Player,
    ) -> RosterResult:
        rosters = self._load_rosters()
        roster = self._find(rosters, roster_id)
        if roster is None:
            return RosterResult("ROSTER_NOT_FOUND")

        players = roster.get("players", [])
        player = self._find_player(players, player_id)
        if player is None:
            return RosterResult("PLAYER_NOT_FOUND")

        number = str(incoming.get("number", player.get("number", ""))).strip()
        duplicate_number = self._duplicate_number(
            players,
            number,
            exclude_id=player_id,
        )

        for field_name in self.PLAYER_STRING_FIELDS:
            if field_name in incoming:
                player[field_name] = str(incoming[field_name]).strip()
        for field_name in self.PLAYER_BOOLEAN_FIELDS:
            if field_name in incoming:
                player[field_name] = bool(incoming[field_name])
        if "status" in incoming:
            player["status"] = (
                "inactive"
                if str(incoming["status"]).lower() == "inactive"
                else "active"
            )

        if (
            bool(player.get("pronunciation_verified"))
            and str(player.get("pronunciation", "")).strip()
        ):
            self.remember_player_pronunciation(
                str(player.get("first_name", "")).strip(),
                str(player.get("last_name", "")).strip(),
                str(player.get("pronunciation", "")).strip(),
            )

        roster["updated_at"] = int(self._clock())
        self._save_rosters(rosters)
        return RosterResult(
            "OK",
            {
                "player": copy.deepcopy(player),
                "warning": (
                    "DUPLICATE_JERSEY_NUMBER" if duplicate_number else ""
                ),
            },
        )

    def delete_player(self, roster_id: str, player_id: str) -> RosterResult:
        rosters = self._load_rosters()
        roster = self._find(rosters, roster_id)
        if roster is None:
            return RosterResult("ROSTER_NOT_FOUND")

        players = roster.get("players", [])
        if self._find_player(players, player_id) is None:
            return RosterResult("PLAYER_NOT_FOUND")
        roster["players"] = [
            player
            for player in players
            if str(player.get("id", "")) != str(player_id)
        ]
        roster["updated_at"] = int(self._clock())
        self._save_rosters(rosters)
        return RosterResult("OK", {"ok": True})

    def import_players(
        self,
        roster_id: str,
        rows: Any,
    ) -> RosterResult:
        if not isinstance(rows, list):
            return RosterResult("INVALID_PLAYER_LIST")

        rosters = self._load_rosters()
        roster = self._find(rosters, roster_id)
        if roster is None:
            return RosterResult("ROSTER_NOT_FOUND")

        players = roster.setdefault("players", [])
        added = 0
        warnings: list[str] = []

        for row in rows:
            if not isinstance(row, dict):
                continue
            first_name = str(row.get("first_name", "")).strip()
            last_name = str(row.get("last_name", "")).strip()
            if not first_name and not last_name:
                continue

            number = str(row.get("number", "")).strip()
            if self._duplicate_number(players, number):
                warnings.append(f"Duplicate jersey number {number}")
            player_id = self._unique_player_id(
                players,
                f"{number}-{first_name}-{last_name}",
            )
            player = self._player_record(
                row,
                player_id=player_id,
                first_name=first_name,
                last_name=last_name,
                number=number,
                imported=True,
            )
            players.append(player)
            added += 1

        roster["updated_at"] = int(self._clock())
        self._save_rosters(rosters)
        return RosterResult(
            "OK",
            {
                "added": added,
                "warnings": warnings,
                "roster": self.summary(roster, self._load_schools()),
            },
        )

    @classmethod
    def _player_record(
        cls,
        incoming: Player,
        *,
        player_id: str,
        first_name: str,
        last_name: str,
        number: str,
        imported: bool = False,
    ) -> Player:
        def flag(name: str) -> bool:
            value = incoming.get(name, False)
            if imported:
                return str(value).lower() in ("1", "true", "yes", "y")
            return bool(value)

        return {
            "id": player_id,
            "number": number,
            "first_name": first_name,
            "last_name": last_name,
            "preferred_name": str(incoming.get("preferred_name", "")).strip(),
            "position": str(incoming.get("position", "")).strip(),
            "secondary_position": str(
                incoming.get("secondary_position", "")
            ).strip(),
            "grade": str(incoming.get("grade", "")).strip(),
            "height": str(incoming.get("height", "")).strip(),
            "weight": str(incoming.get("weight", "")).strip(),
            "captain": flag("captain"),
            "starter": flag("starter"),
            "status": (
                "inactive"
                if str(incoming.get("status", "active")).lower() == "inactive"
                else "active"
            ),
            "pronunciation": str(incoming.get("pronunciation", "")).strip(),
            "pronunciation_verified": flag("pronunciation_verified"),
            "headshot": str(incoming.get("headshot", "")).strip(),
        }

    @classmethod
    def _unique_player_id(
        cls,
        players: list[Player],
        value: Any,
    ) -> str:
        player_id = cls.normalize_player_id(str(value or ""))
        base_id = player_id
        suffix = 2
        while any(player.get("id") == player_id for player in players):
            player_id = f"{base_id}-{suffix}"
            suffix += 1
        return player_id

    @staticmethod
    def _duplicate_number(
        players: list[Player],
        number: str,
        *,
        exclude_id: str = "",
    ) -> bool:
        if not number:
            return False
        return any(
            str(player.get("id", "")) != str(exclude_id)
            and str(player.get("number", "")).strip() == number
            for player in players
        )

    @staticmethod
    def _find_player(
        players: list[Player],
        player_id: str,
    ) -> Player | None:
        target = str(player_id or "")
        return next(
            (
                player
                for player in players
                if str(player.get("id", "")) == target
            ),
            None,
        )

    @staticmethod
    def _find(rosters: list[Roster], roster_id: str) -> Roster | None:
        target = str(roster_id or "")
        return next(
            (
                roster
                for roster in rosters
                if str(roster.get("id", "")) == target
            ),
            None,
        )
