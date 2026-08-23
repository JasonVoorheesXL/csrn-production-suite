from __future__ import annotations

from live_command_service import (
    attach_metadata,
    command_metadata,
    duplicate_result,
    remember_command,
)


def test_recent_command_ledger_stores_compact_result_and_replays_current_state() -> None:
    state = {
        "broadcast_id": "game-1",
        "state_revision": 42,
        "home_score": 7,
        "visitor_score": 3,
        "history": [{"large": "x" * 1000}],
        "recent_commands": {},
    }
    metadata = command_metadata(
        {"command_id": "cmd-1", "client_id": "phone"},
        action="rules_play:run",
        state_revision=42,
    )
    result = attach_metadata(
        {
            "state": dict(state),
            "play": {"play_id": "game-1-0001"},
        },
        metadata,
    )

    remember_command(state, "cmd-1", metadata=metadata, result=result)

    record = state["recent_commands"]["cmd-1"]
    assert "state" not in record["result"]
    replay = duplicate_result(state, "cmd-1")
    assert replay["command_id"] == "cmd-1"
    assert replay["state"]["state_revision"] == 42
    assert replay["play"]["play_id"] == "game-1-0001"
