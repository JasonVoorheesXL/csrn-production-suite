from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path
from tkinter import Tk, filedialog, simpledialog, messagebox

def load_rosters(path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw, "list"
    if isinstance(raw, dict) and isinstance(raw.get("rosters"), list):
        return raw["rosters"], "dict"
    raise RuntimeError("Unsupported rosters.json shape.")

def save_rosters(path: Path, rosters, shape: str):
    payload = {"rosters": rosters} if shape == "dict" else rosters
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

def main():
    project = Path.cwd()
    roster_file = project / "Data" / "Rosters" / "rosters.json"
    if not roster_file.is_file():
        print("ERROR: Data\\Rosters\\rosters.json was not found.")
        return 2

    root = Tk()
    root.withdraw()

    player_id = simpledialog.askstring(
        "CSRN Player Headshot Manager",
        "Enter the player ID exactly as stored in the roster:"
    )
    if not player_id:
        return 0

    rosters, shape = load_rosters(roster_file)
    player = None
    for roster in rosters:
        for candidate in roster.get("players", []):
            if str(candidate.get("id", "")).strip() == player_id.strip():
                player = candidate
                break
        if player:
            break

    if not player:
        messagebox.showerror("Player not found", f"No roster player uses ID: {player_id}")
        return 3

    source = filedialog.askopenfilename(
        title="Select player headshot",
        filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.webp")]
    )
    if not source:
        return 0

    source_path = Path(source)
    safe_name = f"{player_id}{source_path.suffix.lower()}"
    target_dir = project / "Data" / "Rosters" / "Headshots" / "managed"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe_name
    shutil.copy2(source_path, target)

    player["headshot"] = f"/roster-headshots/managed/{safe_name}"
    save_rosters(roster_file, rosters, shape)
    messagebox.showinfo(
        "Headshot assigned",
        f"Assigned {safe_name} to {player.get('first_name','')} {player.get('last_name','')}."
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
