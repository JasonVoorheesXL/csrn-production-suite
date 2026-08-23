from __future__ import annotations

import copy
import time
from typing import Any, Mapping


LEDGER_FIELD = "recent_commands"
LEDGER_LIMIT = 200


def command_id_from(payload: Mapping[str, Any] | None) -> str:
    return str((payload or {}).get("command_id", "") or "").strip()


def command_scope(state: Mapping[str, Any]) -> str:
    return str(state.get("broadcast_id", "") or "unscheduled").strip() or "unscheduled"


def current_revision(state: Mapping[str, Any]) -> int:
    try:
        return max(0, int(state.get("state_revision", 0) or 0))
    except (TypeError, ValueError):
        return 0


def next_revision(state: Mapping[str, Any]) -> int:
    return current_revision(state) + 1


def assign_next_revision(state: dict[str, Any]) -> int:
    revision = next_revision(state)
    state["state_revision"] = revision
    return revision


def duplicate_result(
    state: Mapping[str, Any],
    command_id: str,
) -> dict[str, Any] | None:
    if not command_id:
        return None
    ledger = state.get(LEDGER_FIELD)
    if not isinstance(ledger, Mapping):
        return None
    record = ledger.get(command_id)
    if not isinstance(record, Mapping):
        return None
    if str(record.get("broadcast_id", "") or "") != command_scope(state):
        return None
    result = record.get("result")
    if not isinstance(result, Mapping):
        return None
    duplicate = copy.deepcopy(dict(result))
    if not isinstance(duplicate.get("state"), Mapping):
        metadata = {
            "command_id": record.get("command_id", command_id),
            "command_status": record.get("status", "committed"),
            "client_id": record.get("client_id", ""),
            "issued_at": record.get("issued_at", ""),
            "expected_revision": record.get("expected_revision", None),
            "action": record.get("action", ""),
            "state_revision": record.get("resulting_revision", current_revision(state)),
            "committed_at": record.get("committed_at", 0),
        }
        duplicate["state"] = command_result_state(state)
        duplicate = attach_metadata(duplicate, metadata)
    return duplicate


def command_metadata(
    payload: Mapping[str, Any] | None,
    *,
    action: str,
    state_revision: int,
    committed_at: int | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    incoming = payload or {}
    command_id = command_id_from(incoming)
    timestamp = int(committed_at if committed_at is not None else time.time())
    return {
        "command_id": command_id,
        "command_status": status or ("committed" if command_id else "legacy_committed"),
        "client_id": str(incoming.get("client_id", "") or ""),
        "issued_at": incoming.get("issued_at", ""),
        "expected_revision": incoming.get("expected_revision", None),
        "action": action,
        "state_revision": state_revision,
        "committed_at": timestamp,
    }


def attach_metadata(
    result: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    outgoing = copy.deepcopy(dict(result))
    outgoing.update(copy.deepcopy(dict(metadata)))
    state = outgoing.get("state")
    if isinstance(state, Mapping):
        state_copy = copy.deepcopy(dict(state))
        state_copy["state_revision"] = metadata.get("state_revision", state_copy.get("state_revision", 0))
        state_copy["command_id"] = metadata.get("command_id", "")
        state_copy["command_status"] = metadata.get("command_status", "")
        state_copy["committed_at"] = metadata.get("committed_at", 0)
        outgoing["state"] = state_copy
    return outgoing


def command_result_state(state: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(state))
    for key in (
        LEDGER_FIELD,
        "history",
        "redo_stack",
        "events",
        "plays",
        "correction_log",
        "graphics_queue",
    ):
        result.pop(key, None)
    return result


def remember_command(
    state: dict[str, Any],
    command_id: str,
    *,
    metadata: Mapping[str, Any],
    result: Mapping[str, Any],
    limit: int = LEDGER_LIMIT,
) -> None:
    if not command_id:
        return
    ledger = state.get(LEDGER_FIELD)
    if not isinstance(ledger, dict):
        ledger = {}
    ledger[command_id] = {
        "command_id": command_id,
        "broadcast_id": command_scope(state),
        "action": str(metadata.get("action", "") or ""),
        "status": str(metadata.get("command_status", "committed") or "committed"),
        "client_id": str(metadata.get("client_id", "") or ""),
        "issued_at": metadata.get("issued_at", ""),
        "expected_revision": metadata.get("expected_revision", None),
        "resulting_revision": int(metadata.get("state_revision", 0) or 0),
        "committed_at": int(metadata.get("committed_at", 0) or 0),
        "result": compact_command_result(result),
    }
    if len(ledger) > limit:
        ordered = sorted(
            ledger.items(),
            key=lambda item: int(
                item[1].get("committed_at", 0)
                if isinstance(item[1], Mapping)
                else 0
            ),
        )
        for key, _ in ordered[: len(ledger) - limit]:
            ledger.pop(key, None)
    state[LEDGER_FIELD] = ledger


def compact_command_result(result: Mapping[str, Any]) -> dict[str, Any]:
    compact = copy.deepcopy(dict(result))
    compact.pop("state", None)
    return compact


def compact_recent_commands(state: dict[str, Any], *, limit: int = LEDGER_LIMIT) -> None:
    ledger = state.get(LEDGER_FIELD)
    if not isinstance(ledger, dict):
        state[LEDGER_FIELD] = {}
        return
    for record in ledger.values():
        if not isinstance(record, dict):
            continue
        result = record.get("result")
        if isinstance(result, Mapping):
            record["result"] = compact_command_result(result)
    if len(ledger) > limit:
        ordered = sorted(
            ledger.items(),
            key=lambda item: int(
                item[1].get("committed_at", 0)
                if isinstance(item[1], Mapping)
                else 0
            ),
        )
        for key, _ in ordered[: len(ledger) - limit]:
            ledger.pop(key, None)
    state[LEDGER_FIELD] = ledger
