from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"


def replace_block(text: str, start: str, end: str, replacement: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise RuntimeError(f"Missing migration start marker: {start!r}")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise RuntimeError(f"Missing migration end marker: {end!r}")
    return text[:start_index] + replacement.rstrip() + "\n\n" + text[end_index:]


def apply(path: Path = APP_PATH) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    import_line = "from state_service import StateService\n"
    if import_line not in text:
        anchor = "from configuration_service import ConfigurationService\n"
        if anchor not in text:
            raise RuntimeError("ConfigurationService import anchor not found.")
        text = text.replace(anchor, anchor + import_line, 1)

    normalize_replacement = '''def normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    return get_state_service().normalize(state)
'''
    if "return get_state_service().normalize(state)" not in text:
        text = replace_block(
            text,
            "def normalize_state(state: dict[str, Any]) -> dict[str, Any]:",
            "def load_json(",
            normalize_replacement,
        )

    state_replacement = '''STATE_SERVICE: StateService | None = None


def persist_linked_state_snapshot(normalized: dict[str, Any]) -> None:
    broadcast_id = str(normalized.get("broadcast_id", "")).strip()
    if not broadcast_id:
        return
    items = load_broadcasts()
    item = next(
        (row for row in items if row.get("broadcast_id") == broadcast_id),
        None,
    )
    if not item:
        return
    snapshot = copy.deepcopy(normalized)
    snapshot["history"] = []
    item["live_state"] = snapshot
    item["status"] = normalized.get(
        "status",
        item.get("status", "planned"),
    )
    item["updated_at"] = int(time.time())
    save_broadcasts(items)
    detail = DATA_DIR / "Broadcasts" / f"{broadcast_id}.json"
    detail.write_text(json.dumps(item, indent=2), encoding="utf-8")


def get_state_service() -> StateService:
    global STATE_SERVICE
    if STATE_SERVICE is None:
        STATE_SERVICE = StateService(
            load_raw=STATE_REPOSITORY.load,
            replace_raw=STATE_REPOSITORY.replace,
            default_state=lambda: copy.deepcopy(DEFAULT_STATE),
            persist_linked_snapshot=persist_linked_state_snapshot,
            resolve_player=resolve_game_roster_player,
            canonical_team_key=canonical_team_key,
            canonical_team_name=canonical_team_name,
        )
    return STATE_SERVICE


def load_state() -> dict[str, Any]:
    return get_state_service().load().data["state"]


def save_state(state: dict[str, Any]) -> None:
    get_state_service().save(state)


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    return get_state_service().public(state).data["state"]
'''
    if "STATE_SERVICE: StateService | None = None" not in text:
        text = replace_block(
            text,
            "def load_state() -> dict[str, Any]:",
            "def load_security() -> dict[str, Any]:",
            state_replacement,
        )

    history_replacement = '''def push_history(state: dict[str, Any]) -> None:
    StateService.push_history(state)


def apply_change(
    changes: dict[str, Any],
    save_undo: bool = True,
) -> dict[str, Any]:
    with lock:
        return get_state_service().apply_change(
            changes,
            save_undo=save_undo,
        ).data["state"]
'''
    if "return get_state_service().apply_change(" not in text:
        text = replace_block(
            text,
            "def push_history(state: dict[str, Any]) -> None:",
            "def load_obs_status() -> dict[str, Any]:",
            history_replacement,
        )

    if text == original:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 4.15 StateService integration applied.")
    else:
        print("Phase 4.15 StateService integration already present.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
