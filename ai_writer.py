"""AI writer for the postgame and pregame stories (Social Publishing, 2026-11-01).

Sends the app's fact sheet to Claude and gets back a story in a sportswriter's
voice. The pregame story (and, more lightly, the postgame one) may search the
web for what the app doesn't store: records, district standings, head-to-head
history (ahsfhs.org first for Mississippi and Alabama schools). The station's
own numbers always win over anything found online.

The station's Anthropic API key is kept in a Windows DPAPI vault, never in
config, logs or route responses. Every failure comes back as a code so the
caller can fall back to the built-in writer.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

MODEL = "claude-opus-5-5"
KEY_NAME = "ANTHROPIC_API_KEY"
# Set once the saved key has worked (a Test or a story); cleared when the key changes.
VERIFIED_NAME = "ANTHROPIC_API_KEY_VERIFIED"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_SEARCHES = {"pregame": 8, "postgame": 6}
NOTES_MARKER = "NOTES FOR THE STATION"
MAX_CONTINUATIONS = 4
# USD per million tokens, and per web search, for the cost note shown after each story.
PRICES = {"claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_read": 0.20, "cache_write": 5.0}}
WEB_SEARCH_PRICE = 0.01

SYSTEM_PROMPT = """You write high school football stories for {station}, a local broadcast station that posts them on its Facebook Page.

Write like a good local sports reporter: specific, warm toward both teams, never cheesy. Use AP style (numerals for scores and yards, spell out one through nine otherwise, "p.m.", abbreviated months).

Accuracy rules, in order:
1. The fact sheet from the station is correct. Every number you use from it must match exactly. Never change a score, a yardage, a name or who scored.
2. You may add context you find with web search (season records, district or region standings, past meetings between the schools, notable results). Only use what a source clearly states, and leave out anything you cannot confirm. If a source disagrees with the fact sheet, the fact sheet wins.
3. Never invent quotes, injuries, crowd details, weather or anything else not in the fact sheet or a source.

Format: the headline on the first line, then a blank line, then the story in short paragraphs. Plain text only: no markdown, no links or web addresses, no hashtags, no sponsor line, no "Player of the Game" line (the app adds those itself).

If there is anything the station should check or answer (a fact you could not confirm, something you left out and why, a question about the data), put it after the story under a line that reads exactly NOTES FOR THE STATION, one note per line starting with "- ". The notes are shown to the station, never posted. Leave the section out when you have nothing to say."""

REVISE_TASK = """Here are the station's answers and corrections to your story and notes:

{instructions}

Rewrite the whole story with these applied. The station's answers are correct; keep everything else accurate to the fact sheet. Use the same format, and list under NOTES FOR THE STATION only what is still open. If this is a pregame preview, also repeat the GRAPHIC DATA block with any corrections."""

POSTGAME_TASK = """Write the postgame story for this game, about 350 to 450 words. Tell the game in order: every score belongs in the story, with the quarter, and the drives and turning points that matter. Close with each team's standout players and one sentence of team statistics.

You may search the web for each team's season record and district or region standing after this game, to add a sentence of context. Prefer ahsfhs.org for Mississippi and Alabama schools, then MaxPreps or the local paper.

FACT SHEET
{facts}"""

PREGAME_TASK = """Write a pregame preview of this game, about 300 to 400 words: who, when and where; both teams' records and recent form; what is at stake in the district or region; the history between the two schools; players to watch.

Search the web for what the fact sheet doesn't have, especially for {opponent}: their season results and record, their district or region standing, and the head-to-head history between {home} and {visitor}. Try ahsfhs.org first for Mississippi and Alabama schools (it keeps season results and series history), then MaxPreps or the local paper.

FACT SHEET
{facts}

After the story and any notes, add a line that reads exactly GRAPHIC DATA, then one JSON object with what your sources clearly state, for the graphic that goes with the post. The station reviews it before anything is used.
{{"home": {{"record": "6-3", "region_record": "3-1", "points_per_game": "28.4", "points_allowed": "14.2", "results": ["W 27-8 vs. Columbus"], "players": [{{"name": "First Last", "line": "595 rush yds, 8 TD"}}]}}, "visitor": {{same fields}}, "last_meeting": "New Hope won 28-14 in 2025"}}
Rules for it: use an empty string or empty list for anything a source does not clearly state, and never estimate or calculate a number. Up to four most recent results (W, L or T first) and three players per team. Report what the source says even when it differs from the record on the fact sheet, and say so in your notes. Values only: no links."""


@dataclass(frozen=True)
class AiResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


def _default_client_factory(api_key: str) -> Any:
    import anthropic  # imported lazily: the app runs without it when AI is never used

    return anthropic.Anthropic(api_key=api_key, timeout=240.0, max_retries=2)


_URL = re.compile(r"(https?://\S+|www\.\S+)", re.I)


_NOTES_SPLIT = re.compile(r"\n[ \t]*(?:-{3,}|\*{3,}|_{3,})?[ \t]*\n*[ \t]*(?:#+\s*)?\**\s*(?:NOTES FOR THE STATION|Notes)\s*:?\**[ \t]*\n", re.I)


def split_notes(text: str) -> tuple[str, list[str]]:
    """(story text, notes): the notes never belong in the post."""
    text = str(text or "").replace("\r\n", "\n")
    match = _NOTES_SPLIT.search("\n" + text)
    if not match:
        return re.sub(r"\n[ \t]*-{3,}[ \t]*$", "", text.rstrip()), []
    start = match.start() - 1 if match.start() > 0 else 0
    body, tail = text[:max(start, 0)], text[match.end() - 1:]
    notes, current = [], ""
    for line in tail.split("\n"):
        stripped = line.strip()
        if re.match(r"^[-*\u2022]\s+", stripped):
            if current:
                notes.append(current)
            current = re.sub(r"^[-*\u2022]\s+", "", stripped)
        elif stripped and current:
            current += " " + stripped
        elif stripped:
            current = stripped
    if current:
        notes.append(current)
    notes = [re.sub(r"\*\*(.+?)\*\*", r"\1", n).strip() for n in notes if n.strip()]
    return re.sub(r"\n[ \t]*-{3,}[ \t]*$", "", body.rstrip()), notes


_GRAPHIC_LINE = re.compile(r"^[ \t]*[#*]*[ \t]*GRAPHIC DATA[ \t]*[*:]*[ \t]*$", re.I | re.M)


def split_graphic_data(text: str) -> tuple[str, dict[str, Any] | None]:
    """(everything else, the GRAPHIC DATA object): the numbers never belong in the post."""
    text = str(text or "")
    match = _GRAPHIC_LINE.search(text)
    if not match:
        return text, None
    start, end = text.find("{", match.end()), text.rfind("}")
    data = None
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
            data = parsed if isinstance(parsed, dict) else None
        except ValueError:
            data = None
    rest = "" if start == -1 or end <= start else text[end + 1:]
    rest = re.sub(r"^\s*```\s*", "", rest)
    return (text[:match.start()].rstrip() + ("\n\n" + rest.strip() if rest.strip() else "")), data


def clean_story(text: str) -> tuple[str, str]:
    """Split the model's answer into (headline, story): strip markdown and
    any web address that slipped through (a link costs reach on the Page)."""
    text, _ = split_notes(text)
    lines = [line.rstrip() for line in str(text or "").replace("\r\n", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return "", ""
    head = re.sub(r"^[#*\s]+|[*\s]+$", "", lines[0]).strip()
    head = re.sub(r"^headline:\s*", "", head, flags=re.I)
    body = "\n".join(lines[1:]).strip()
    body = re.sub(r"\*\*(.+?)\*\*", r"\1", body)
    body = _URL.sub("", body)
    body = re.sub(r"[ \t]+([.,;:])", r"\1", body)
    body = re.sub(r"\(\s*\)", "", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return head, body.strip()


class AiWriter:
    def __init__(
        self,
        *,
        vault: Any,
        client_factory: Callable[[str], Any] | None = None,
        model: str = MODEL,
    ) -> None:
        self._vault = vault
        self._client_factory = client_factory or _default_client_factory
        self.model = model

    # -- the key ---------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        key = self._vault.get(KEY_NAME)
        return {"configured": bool(key), "verified": bool(key) and self._vault.get(VERIFIED_NAME) == "1",
                "key_hint": f"…{key[-4:]}" if len(key) >= 8 else "", "model": self.model}

    def set_key(self, api_key: str) -> AiResult:
        key = str(api_key or "").strip()
        if not re.fullmatch(r"sk-ant-[A-Za-z0-9_\-]{20,}", key):
            return AiResult("AI_KEY_FORMAT")
        self._vault.set(KEY_NAME, key)
        self._vault.set(VERIFIED_NAME, "")
        return AiResult("OK", self.status())

    def remove_key(self) -> AiResult:
        self._vault.set(KEY_NAME, "")
        self._vault.set(VERIFIED_NAME, "")
        return AiResult("OK", self.status())

    def _mark(self, verified: bool) -> None:
        try:
            self._vault.set(VERIFIED_NAME, "1" if verified else "")
        except Exception:  # noqa: BLE001 -- the flag is a convenience, never a failure
            pass

    def test(self) -> AiResult:
        key = self._vault.get(KEY_NAME)
        if not key:
            return AiResult("AI_NOT_CONFIGURED")
        try:
            self._client_factory(key).models.retrieve(self.model)
        except Exception as exc:  # noqa: BLE001 -- mapped to a code below
            code = self._error_code(exc)
            if code == "AI_KEY_INVALID":
                self._mark(False)
            return AiResult(code, {"message": self._error_message(exc)})
        self._mark(True)
        return AiResult("OK", self.status())

    # -- writing ---------------------------------------------------------------

    def _first_turn(self, kind: str, fact_sheet: str, home: str, visitor: str, opponent: str) -> str:
        return (PREGAME_TASK if kind == "pregame" else POSTGAME_TASK).format(
            facts=fact_sheet, home=home, visitor=visitor, opponent=opponent or visitor)

    def write(self, kind: str, fact_sheet: str, *, station: str, home: str = "", visitor: str = "",
              opponent: str = "") -> AiResult:
        task = self._first_turn(kind, fact_sheet, home, visitor, opponent)
        return self._run(kind, [{"role": "user", "content": task}], station)

    def revise(self, kind: str, fact_sheet: str, *, previous: str, notes: list[str] | None = None,
               instructions: str, station: str, home: str = "", visitor: str = "", opponent: str = "") -> AiResult:
        """Rewrite with the station's answers: the conversation is replayed (the
        fact sheet, the story as the station has it now, its notes) and the
        answers go in as the next turn."""
        if not str(instructions or "").strip():
            return AiResult("AI_NOTHING_TO_REVISE")
        task = self._first_turn(kind, fact_sheet, home, visitor, opponent)
        answer = str(previous or "").strip()
        if notes:
            answer += f"\n\n{NOTES_MARKER}\n" + "\n".join(f"- {note}" for note in notes)
        messages = [{"role": "user", "content": task},
                    {"role": "assistant", "content": answer},
                    {"role": "user", "content": REVISE_TASK.format(instructions=str(instructions).strip())}]
        return self._run(kind, messages, station)

    def _run(self, kind: str, messages: list[dict[str, Any]], station: str) -> AiResult:
        key = self._vault.get(KEY_NAME)
        if not key:
            return AiResult("AI_NOT_CONFIGURED")
        system = SYSTEM_PROMPT.format(station=station or "the station")
        tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_SEARCHES.get(kind, 4)}]
        responses: list[Any] = []
        try:
            client = self._client_factory(key)
            response = None
            for _ in range(MAX_CONTINUATIONS + 1):
                response = client.beta.messages.create(
                    model=self.model,
                    max_tokens=16000,
                    system=system,
                    messages=messages,
                    tools=tools,
                    output_config={"effort": "medium"},
                    betas=[FALLBACK_BETA],
                    extra_body={"fallbacks": "default"},
                )
                responses.append(response)
                if response.stop_reason != "pause_turn":
                    break
                # A long web search paused the turn: hand it back to continue.
                messages = [*messages, {"role": "assistant", "content": response.content}]
        except Exception as exc:  # noqa: BLE001 -- mapped to a code below
            code = self._error_code(exc)
            if code == "AI_KEY_INVALID":
                self._mark(False)
            return AiResult(code, {"message": self._error_message(exc)})
        self._mark(True)
        if response is None or response.stop_reason == "refusal":
            return AiResult("AI_REFUSED")
        text = "".join(getattr(block, "text", "") for block in response.content if getattr(block, "type", "") == "text")
        text, graphic = split_graphic_data(text)
        _, notes = split_notes(text)
        headline, story = clean_story(text)
        if not story:
            return AiResult("AI_EMPTY")
        return AiResult("OK", {"headline": headline, "story": story, "notes": notes, "cost_usd": self._cost(responses),
                               "sources": self._sources(responses), "search": self._search_report(responses),
                               "model": getattr(response, "model", self.model), "writer": "ai", "graphic": graphic})

    def _cost(self, responses: list[Any]) -> float | None:
        """What this run cost, from the token counts Anthropic returns (the
        account's balance itself is only shown on console.anthropic.com)."""
        prices = PRICES.get(self.model)
        if not prices:
            return None
        total = 0.0
        for response in responses:
            usage = getattr(response, "usage", None)
            if usage is None:
                continue
            total += (getattr(usage, "input_tokens", 0) or 0) * prices["input"] / 1e6
            total += (getattr(usage, "output_tokens", 0) or 0) * prices["output"] / 1e6
            total += (getattr(usage, "cache_read_input_tokens", 0) or 0) * prices["cache_read"] / 1e6
            total += (getattr(usage, "cache_creation_input_tokens", 0) or 0) * prices["cache_write"] / 1e6
            server = getattr(usage, "server_tool_use", None)
            total += (getattr(server, "web_search_requests", 0) or 0) * WEB_SEARCH_PRICE
        return round(total, 4)

    @staticmethod
    def _search_report(responses: list[Any]) -> dict[str, Any]:
        """How the web searches went, so an empty search can be explained
        (the tool reports errors inside a 200 response, not as exceptions)."""
        searches = results = 0
        errors: list[str] = []
        for response in responses:
            for block in getattr(response, "content", []) or []:
                kind = getattr(block, "type", "")
                if kind == "server_tool_use" and getattr(block, "name", "") == "web_search":
                    searches += 1
                elif kind == "web_search_tool_result":
                    content = getattr(block, "content", None)
                    if isinstance(content, list):
                        results += len(content)
                    else:
                        code = content.get("error_code") if isinstance(content, dict) else getattr(content, "error_code", None)
                        errors.append(str(code or "unknown"))
        return {"searches": searches, "results": results, "errors": errors}

    @staticmethod
    def _sources(responses: list[Any]) -> list[dict[str, str]]:
        """Pages the writer cited, else every page its searches returned --
        shown to the operator for checking, never put in the post."""
        cited: dict[str, str] = {}
        found: dict[str, str] = {}
        for block in [b for r in responses for b in (getattr(r, "content", []) or [])]:
            kind = getattr(block, "type", "")
            if kind == "text":
                for citation in getattr(block, "citations", None) or []:
                    url = getattr(citation, "url", "") or ""
                    if url:
                        cited.setdefault(url, getattr(citation, "title", "") or url)
            elif kind == "web_search_tool_result":
                content = getattr(block, "content", None)
                if isinstance(content, list):
                    for item in content:
                        url = getattr(item, "url", "") or ""
                        if url:
                            found.setdefault(url, getattr(item, "title", "") or url)
        chosen = cited or found
        return [{"url": url, "title": title} for url, title in list(chosen.items())[:12]]

    @staticmethod
    def _error_code(exc: Exception) -> str:
        name = type(exc).__name__
        # Anthropic answers an empty balance with a 400 whose message says so.
        if "credit balance" in str(getattr(exc, "message", "") or exc).lower():
            return "AI_NO_CREDIT"
        return {
            "AuthenticationError": "AI_KEY_INVALID",
            "PermissionDeniedError": "AI_KEY_INVALID",
            "RateLimitError": "AI_BUSY",
            "APIConnectionError": "AI_UNREACHABLE",
            "APITimeoutError": "AI_UNREACHABLE",
            "ModuleNotFoundError": "AI_UNAVAILABLE",
            "ImportError": "AI_UNAVAILABLE",
        }.get(name, "AI_FAILED")

    @staticmethod
    def _error_message(exc: Exception) -> str:
        # Never echo anything that could carry the key.
        return re.sub(r"sk-ant-[A-Za-z0-9_\-]+", "[key]", str(getattr(exc, "message", "") or exc))[:300]
