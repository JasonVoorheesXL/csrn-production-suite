from __future__ import annotations

import copy
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Callable


Clock = Callable[[], float]


@dataclass(frozen=True)
class CaptionServiceResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class CaptionService:
    """Persistent channel-based caption state and transcript boundary."""

    DEFAULT_PROFILE: dict[str, Any] = {
        "enabled": False,
        "overlay_visible": False,
        "minimum_confidence": 0.72,
        "display_delay_ms": 1200,
        "display_duration_ms": 6500,
        "max_lines": 2,
        "max_characters": 96,
        "profanity_policy": "mask",
        "profanity_words": [],
        "theme": "standard",
        "channels": [
            {"channel": 1, "speaker": "Announcer 1", "enabled": True},
            {"channel": 2, "speaker": "Announcer 2", "enabled": True},
            {"channel": 3, "speaker": "Announcer 3", "enabled": False},
            {"channel": 4, "speaker": "Announcer 4", "enabled": False},
        ],
    }

    DEFAULT_STATE: dict[str, Any] = {
        "visible": False,
        "current": [],
        "last_segment_id": "",
        "updated_at": 0,
        "cleared_at": 0,
    }

    def __init__(
        self,
        *,
        profile_file: Path,
        state_file: Path,
        transcripts_dir: Path,
        clock: Clock = time.time,
    ) -> None:
        self.profile_file = profile_file
        self.state_file = state_file
        self.transcripts_dir = transcripts_dir
        self._clock = clock
        self._lock = Lock()
        self.profile_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)

    def status(self) -> CaptionServiceResult:
        with self._lock:
            return CaptionServiceResult(
                "OK",
                {
                    "profile": self._load_profile(),
                    "state": self._load_state(),
                },
            )

    def public_state(self) -> CaptionServiceResult:
        with self._lock:
            profile = self._load_profile()
            state = self._load_state()
            now_ms = int(self._clock() * 1000)
            delay_ms = int(profile["display_delay_ms"])
            duration_ms = int(profile["display_duration_ms"])
            current = []
            for segment in state.get("current", []):
                available_at = int(segment.get("created_at_ms", 0)) + delay_ms
                expires_at = available_at + duration_ms
                if available_at <= now_ms <= expires_at:
                    current.append(copy.deepcopy(segment))
            visible = bool(profile.get("enabled") and profile.get("overlay_visible"))
            return CaptionServiceResult(
                "OK",
                {
                    "visible": visible,
                    "segments": current[-int(profile["max_lines"]):] if visible else [],
                    "theme": profile.get("theme", "standard"),
                    "updated_at": state.get("updated_at", 0),
                },
            )

    def update_profile(self, payload: Any) -> CaptionServiceResult:
        if not isinstance(payload, dict):
            return CaptionServiceResult("PROFILE_REQUIRED")
        with self._lock:
            current = self._load_profile()
            merged = copy.deepcopy(current)
            for key in (
                "enabled",
                "overlay_visible",
                "minimum_confidence",
                "display_delay_ms",
                "display_duration_ms",
                "max_lines",
                "max_characters",
                "profanity_policy",
                "profanity_words",
                "theme",
                "channels",
            ):
                if key in payload:
                    merged[key] = copy.deepcopy(payload[key])
            error = self._validate_profile(merged)
            if error:
                return CaptionServiceResult("INVALID_PROFILE", {"message": error})
            normalized = self._normalize_profile(merged)
            self._write_json(self.profile_file, normalized)
            state = self._load_state()
            state["visible"] = bool(
                normalized.get("enabled") and normalized.get("overlay_visible")
            )
            state["updated_at"] = int(self._clock())
            self._write_json(self.state_file, state)
            return CaptionServiceResult("OK", {"profile": normalized, "state": state})

    def ingest_segment(self, payload: Any) -> CaptionServiceResult:
        if not isinstance(payload, dict):
            return CaptionServiceResult("SEGMENT_REQUIRED")
        try:
            channel = int(payload.get("channel"))
        except (TypeError, ValueError):
            return CaptionServiceResult("CHANNEL_INVALID")
        text = self._normalize_text(payload.get("text", ""))
        if not text:
            return CaptionServiceResult("TEXT_REQUIRED")
        try:
            confidence = float(payload.get("confidence", 1.0))
        except (TypeError, ValueError):
            return CaptionServiceResult("CONFIDENCE_INVALID")
        if confidence < 0 or confidence > 1:
            return CaptionServiceResult("CONFIDENCE_INVALID")

        with self._lock:
            profile = self._load_profile()
            channel_profile = next(
                (
                    item
                    for item in profile["channels"]
                    if int(item.get("channel", 0)) == channel
                ),
                None,
            )
            if channel_profile is None:
                return CaptionServiceResult("CHANNEL_NOT_CONFIGURED")
            if not channel_profile.get("enabled", False):
                return CaptionServiceResult("CHANNEL_DISABLED")
            if confidence < float(profile["minimum_confidence"]):
                return CaptionServiceResult(
                    "LOW_CONFIDENCE",
                    {"minimum_confidence": profile["minimum_confidence"]},
                )

            raw_text = text
            text = self._apply_profanity_policy(text, profile)
            max_characters = int(profile["max_characters"])
            if len(text) > max_characters:
                text = text[: max_characters - 1].rstrip() + "…"

            created_at_ms = int(self._clock() * 1000)
            start_ms = self._coerce_nonnegative_int(payload.get("start_ms"), created_at_ms)
            end_ms = self._coerce_nonnegative_int(payload.get("end_ms"), created_at_ms)
            if end_ms < start_ms:
                end_ms = start_ms
            broadcast_id = self._safe_identifier(payload.get("broadcast_id", "unscheduled"))
            segment = {
                "id": str(payload.get("id") or uuid.uuid4()),
                "broadcast_id": broadcast_id,
                "channel": channel,
                "speaker": str(channel_profile.get("speaker", f"Channel {channel}")).strip(),
                "text": text,
                "raw_text": raw_text,
                "confidence": round(confidence, 4),
                "start_ms": start_ms,
                "end_ms": end_ms,
                "created_at_ms": created_at_ms,
                "corrected": False,
            }
            transcript = self._load_transcript(broadcast_id)
            transcript.append(segment)
            transcript.sort(key=lambda item: (int(item.get("start_ms", 0)), item.get("id", "")))
            self._write_json(self._transcript_path(broadcast_id), transcript)

            state = self._load_state()
            current = list(state.get("current", []))
            current.append(segment)
            current = current[-max(8, int(profile["max_lines"]) * 4):]
            state.update(
                {
                    "visible": bool(
                        profile.get("enabled") and profile.get("overlay_visible")
                    ),
                    "current": current,
                    "last_segment_id": segment["id"],
                    "updated_at": int(self._clock()),
                }
            )
            self._write_json(self.state_file, state)
            return CaptionServiceResult("OK", {"segment": copy.deepcopy(segment), "state": state})

    def set_visibility(self, visible: Any) -> CaptionServiceResult:
        if not isinstance(visible, bool):
            return CaptionServiceResult("VISIBLE_MUST_BE_BOOLEAN")
        with self._lock:
            profile = self._load_profile()
            profile["overlay_visible"] = visible
            self._write_json(self.profile_file, profile)
            state = self._load_state()
            state["visible"] = bool(profile.get("enabled") and visible)
            state["updated_at"] = int(self._clock())
            self._write_json(self.state_file, state)
            return CaptionServiceResult("OK", {"profile": profile, "state": state})

    def clear(self) -> CaptionServiceResult:
        with self._lock:
            state = self._load_state()
            state["current"] = []
            state["last_segment_id"] = ""
            state["cleared_at"] = int(self._clock())
            state["updated_at"] = int(self._clock())
            self._write_json(self.state_file, state)
            return CaptionServiceResult("OK", {"state": state})

    def correct_segment(self, segment_id: str, text: Any) -> CaptionServiceResult:
        normalized = self._normalize_text(text)
        if not normalized:
            return CaptionServiceResult("TEXT_REQUIRED")
        with self._lock:
            match: tuple[Path, list[dict[str, Any]], int] | None = None
            for path in sorted(self.transcripts_dir.glob("*.json")):
                transcript = self._read_json(path, [])
                if not isinstance(transcript, list):
                    continue
                for index, segment in enumerate(transcript):
                    if str(segment.get("id", "")) == segment_id:
                        match = (path, transcript, index)
                        break
                if match is not None:
                    break
            if match is None:
                return CaptionServiceResult("SEGMENT_NOT_FOUND")
            path, transcript, index = match
            transcript[index]["text"] = normalized
            transcript[index]["corrected"] = True
            transcript[index]["corrected_at"] = int(self._clock())
            self._write_json(path, transcript)

            state = self._load_state()
            for segment in state.get("current", []):
                if str(segment.get("id", "")) == segment_id:
                    segment["text"] = normalized
                    segment["corrected"] = True
                    segment["corrected_at"] = int(self._clock())
            state["updated_at"] = int(self._clock())
            self._write_json(self.state_file, state)
            return CaptionServiceResult("OK", {"segment": copy.deepcopy(transcript[index])})

    def transcript(self, broadcast_id: str) -> CaptionServiceResult:
        safe_id = self._safe_identifier(broadcast_id)
        with self._lock:
            return CaptionServiceResult(
                "OK",
                {"broadcast_id": safe_id, "segments": self._load_transcript(safe_id)},
            )

    def export_srt(self, broadcast_id: str) -> CaptionServiceResult:
        transcript = self.transcript(broadcast_id).data["segments"]
        lines: list[str] = []
        for index, segment in enumerate(transcript, start=1):
            lines.extend(
                [
                    str(index),
                    f"{self._srt_time(segment.get('start_ms', 0))} --> {self._srt_time(segment.get('end_ms', 0))}",
                    f"{segment.get('speaker', '')}: {segment.get('text', '')}".strip(),
                    "",
                ]
            )
        return CaptionServiceResult("OK", {"content": "\n".join(lines), "mimetype": "application/x-subrip"})

    def export_vtt(self, broadcast_id: str) -> CaptionServiceResult:
        transcript = self.transcript(broadcast_id).data["segments"]
        lines = ["WEBVTT", ""]
        for segment in transcript:
            lines.extend(
                [
                    f"{self._vtt_time(segment.get('start_ms', 0))} --> {self._vtt_time(segment.get('end_ms', 0))}",
                    f"<v {segment.get('speaker', '')}>{segment.get('text', '')}",
                    "",
                ]
            )
        return CaptionServiceResult("OK", {"content": "\n".join(lines), "mimetype": "text/vtt"})

    def _load_profile(self) -> dict[str, Any]:
        data = self._read_json(self.profile_file, self.DEFAULT_PROFILE)
        if not isinstance(data, dict) or self._validate_profile(data):
            data = copy.deepcopy(self.DEFAULT_PROFILE)
        normalized = self._normalize_profile(data)
        if not self.profile_file.exists() or normalized != data:
            self._write_json(self.profile_file, normalized)
        return normalized

    def _load_state(self) -> dict[str, Any]:
        data = self._read_json(self.state_file, self.DEFAULT_STATE)
        if not isinstance(data, dict):
            data = copy.deepcopy(self.DEFAULT_STATE)
        normalized = copy.deepcopy(self.DEFAULT_STATE)
        normalized.update(data)
        if not isinstance(normalized.get("current"), list):
            normalized["current"] = []
        if not self.state_file.exists() or normalized != data:
            self._write_json(self.state_file, normalized)
        return normalized

    def _load_transcript(self, broadcast_id: str) -> list[dict[str, Any]]:
        data = self._read_json(self._transcript_path(broadcast_id), [])
        return copy.deepcopy(data) if isinstance(data, list) else []

    def _transcript_path(self, broadcast_id: str) -> Path:
        return self.transcripts_dir / f"{self._safe_identifier(broadcast_id)}.json"

    @classmethod
    def _validate_profile(cls, profile: dict[str, Any]) -> str:
        if not isinstance(profile.get("enabled"), bool):
            return "enabled must be boolean"
        if not isinstance(profile.get("overlay_visible"), bool):
            return "overlay_visible must be boolean"
        try:
            minimum_confidence = float(profile.get("minimum_confidence"))
            delay = int(profile.get("display_delay_ms"))
            duration = int(profile.get("display_duration_ms"))
            max_lines = int(profile.get("max_lines"))
            max_characters = int(profile.get("max_characters"))
        except (TypeError, ValueError):
            return "numeric caption settings are invalid"
        if not 0 <= minimum_confidence <= 1:
            return "minimum_confidence must be between 0 and 1"
        if not 0 <= delay <= 15000:
            return "display_delay_ms must be between 0 and 15000"
        if not 1000 <= duration <= 30000:
            return "display_duration_ms must be between 1000 and 30000"
        if not 1 <= max_lines <= 4:
            return "max_lines must be between 1 and 4"
        if not 24 <= max_characters <= 240:
            return "max_characters must be between 24 and 240"
        if str(profile.get("profanity_policy", "")) not in {"allow", "mask", "drop"}:
            return "profanity_policy must be allow, mask, or drop"
        channels = profile.get("channels")
        if not isinstance(channels, list) or not channels:
            return "at least one channel is required"
        seen: set[int] = set()
        for item in channels:
            if not isinstance(item, dict):
                return "channel entries must be objects"
            try:
                channel = int(item.get("channel"))
            except (TypeError, ValueError):
                return "channel number is invalid"
            if channel < 1 or channel > 12 or channel in seen:
                return "channel numbers must be unique and between 1 and 12"
            seen.add(channel)
            if not str(item.get("speaker", "")).strip():
                return "every channel requires a speaker name"
            if not isinstance(item.get("enabled"), bool):
                return "channel enabled must be boolean"
        return ""

    @classmethod
    def _normalize_profile(cls, profile: dict[str, Any]) -> dict[str, Any]:
        normalized = copy.deepcopy(cls.DEFAULT_PROFILE)
        normalized.update(copy.deepcopy(profile))
        normalized["minimum_confidence"] = round(float(normalized["minimum_confidence"]), 3)
        normalized["display_delay_ms"] = int(normalized["display_delay_ms"])
        normalized["display_duration_ms"] = int(normalized["display_duration_ms"])
        normalized["max_lines"] = int(normalized["max_lines"])
        normalized["max_characters"] = int(normalized["max_characters"])
        normalized["theme"] = str(normalized.get("theme", "standard")).strip() or "standard"
        normalized["profanity_words"] = sorted(
            {
                cls._normalize_text(word).lower()
                for word in normalized.get("profanity_words", [])
                if cls._normalize_text(word)
            }
        )
        normalized["channels"] = sorted(
            [
                {
                    "channel": int(item["channel"]),
                    "speaker": str(item["speaker"]).strip(),
                    "enabled": bool(item["enabled"]),
                }
                for item in normalized["channels"]
            ],
            key=lambda item: item["channel"],
        )
        return normalized

    @staticmethod
    def _apply_profanity_policy(text: str, profile: dict[str, Any]) -> str:
        words = profile.get("profanity_words", [])
        if not words or profile.get("profanity_policy") == "allow":
            return text
        pattern = re.compile(r"\b(" + "|".join(re.escape(word) for word in words) + r")\b", re.IGNORECASE)
        if profile.get("profanity_policy") == "drop" and pattern.search(text):
            return "[caption withheld]"
        return pattern.sub(lambda match: "*" * len(match.group(0)), text)

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return " ".join(str(value or "").replace("\x00", " ").split())

    @staticmethod
    def _safe_identifier(value: Any) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip()).strip("-.")
        return cleaned[:96] or "unscheduled"

    @staticmethod
    def _coerce_nonnegative_int(value: Any, default: int) -> int:
        try:
            result = int(value)
        except (TypeError, ValueError):
            result = int(default)
        return max(0, result)

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return copy.deepcopy(default)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return copy.deepcopy(default)

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _srt_time(value: Any) -> str:
        total = max(0, int(value))
        hours, remainder = divmod(total, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, milliseconds = divmod(remainder, 1_000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    @staticmethod
    def _vtt_time(value: Any) -> str:
        return CaptionService._srt_time(value).replace(",", ".")
