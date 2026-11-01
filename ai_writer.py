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

import re
from dataclasses import dataclass, field
from typing import Any, Callable

MODEL = "claude-opus-5-5"
KEY_NAME = "ANTHROPIC_API_KEY"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_SEARCHES = {"pregame": 8, "postgame": 4}
MAX_CONTINUATIONS = 4

SYSTEM_PROMPT = """You write high school football stories for {station}, a local broadcast station that posts them on its Facebook Page.

Write like a good local sports reporter: specific, warm toward both teams, never cheesy. Use AP style (numerals for scores and yards, spell out one through nine otherwise, "p.m.", abbreviated months).

Accuracy rules, in order:
1. The fact sheet from the station is correct. Every number you use from it must match exactly. Never change a score, a yardage, a name or who scored.
2. You may add context you find with web search (season records, district or region standings, past meetings between the schools, notable results). Only use what a source clearly states, and leave out anything you cannot confirm. If a source disagrees with the fact sheet, the fact sheet wins.
3. Never invent quotes, injuries, crowd details, weather or anything else not in the fact sheet or a source.

Format: the headline on the first line, then a blank line, then the story in short paragraphs. Plain text only: no markdown, no links or web addresses, no hashtags, no sponsor line, no "Player of the Game" line (the app adds those itself)."""

POSTGAME_TASK = """Write the postgame story for this game, about 350 to 450 words. Tell the game in order: every score belongs in the story, with the quarter, and the drives and turning points that matter. Close with each team's standout players and one sentence of team statistics.

You may search the web for each team's season record and district or region standing after this game, to add a sentence of context. Prefer ahsfhs.org for Mississippi and Alabama schools, then MaxPreps or the local paper.

FACT SHEET
{facts}"""

PREGAME_TASK = """Write a pregame preview of this game, about 300 to 400 words: who, when and where; both teams' records and recent form; what is at stake in the district or region; the history between the two schools; players to watch.

Search the web for what the fact sheet doesn't have, especially for {opponent}: their season results and record, their district or region standing, and the head-to-head history between {home} and {visitor}. Try ahsfhs.org first for Mississippi and Alabama schools (it keeps season results and series history), then MaxPreps or the local paper.

FACT SHEET
{facts}"""


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


def clean_story(text: str) -> tuple[str, str]:
    """Split the model's answer into (headline, story): strip markdown and
    any web address that slipped through (a link costs reach on the Page)."""
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
        return {"configured": bool(key), "key_hint": f"…{key[-4:]}" if len(key) >= 8 else "", "model": self.model}

    def set_key(self, api_key: str) -> AiResult:
        key = str(api_key or "").strip()
        if not re.fullmatch(r"sk-ant-[A-Za-z0-9_\-]{20,}", key):
            return AiResult("AI_KEY_FORMAT")
        self._vault.set(KEY_NAME, key)
        return AiResult("OK", self.status())

    def remove_key(self) -> AiResult:
        self._vault.set(KEY_NAME, "")
        return AiResult("OK", self.status())

    def test(self) -> AiResult:
        key = self._vault.get(KEY_NAME)
        if not key:
            return AiResult("AI_NOT_CONFIGURED")
        try:
            self._client_factory(key).models.retrieve(self.model)
        except Exception as exc:  # noqa: BLE001 -- mapped to a code below
            return AiResult(self._error_code(exc), {"message": self._error_message(exc)})
        return AiResult("OK", self.status())

    # -- writing ---------------------------------------------------------------

    def write(self, kind: str, fact_sheet: str, *, station: str, home: str = "", visitor: str = "",
              opponent: str = "") -> AiResult:
        key = self._vault.get(KEY_NAME)
        if not key:
            return AiResult("AI_NOT_CONFIGURED")
        task = (PREGAME_TASK if kind == "pregame" else POSTGAME_TASK).format(
            facts=fact_sheet, home=home, visitor=visitor, opponent=opponent or visitor)
        system = SYSTEM_PROMPT.format(station=station or "the station")
        tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_SEARCHES.get(kind, 4)}]
        messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
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
                if response.stop_reason != "pause_turn":
                    break
                # A long web search paused the turn: hand it back to continue.
                messages = [messages[0], {"role": "assistant", "content": response.content}]
        except Exception as exc:  # noqa: BLE001 -- mapped to a code below
            return AiResult(self._error_code(exc), {"message": self._error_message(exc)})
        if response is None or response.stop_reason == "refusal":
            return AiResult("AI_REFUSED")
        text = "".join(getattr(block, "text", "") for block in response.content if getattr(block, "type", "") == "text")
        headline, story = clean_story(text)
        if not story:
            return AiResult("AI_EMPTY")
        return AiResult("OK", {"headline": headline, "story": story, "sources": self._sources(response),
                               "model": getattr(response, "model", self.model), "writer": "ai"})

    @staticmethod
    def _sources(response: Any) -> list[dict[str, str]]:
        """Pages the writer cited, else every page its searches returned --
        shown to the operator for checking, never put in the post."""
        cited: dict[str, str] = {}
        found: dict[str, str] = {}
        for block in response.content:
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
