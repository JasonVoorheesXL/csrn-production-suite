from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


STALE_IMPORTS: tuple[tuple[str, str], ...] = (
    ("import io\n", "io."),
    ("import socket\n", "socket."),
    ("import qrcode\n", "qrcode."),
    ("import qrcode.image.svg\n", "qrcode."),
)

LEGACY_REPOSITORY_COMMENTS = '''# Phase 3.5: BroadcastRespository integrated

# Phase 3.4: VenueRepository integrated

# Phase 3.3: SponsorRepository integrated

# Phase 3.2: RosterRepository integrated

# Phase 3.1: SchoolRepository integrated
'''

CONSOLIDATED_REPOSITORY_COMMENT = (
    "# Phase 3 repository boundaries remain integrated below.\n"
)


def apply(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    for import_line, usage_marker in STALE_IMPORTS:
        if import_line not in text:
            continue
        candidate = text.replace(import_line, "", 1)
        if usage_marker in candidate:
            raise RuntimeError(
                f"Cannot remove {import_line.strip()!r}; "
                f"{usage_marker!r} is still used in app.py."
            )
        text = candidate

    if LEGACY_REPOSITORY_COMMENTS in text:
        text = text.replace(
            LEGACY_REPOSITORY_COMMENTS,
            CONSOLIDATED_REPOSITORY_COMMENT,
            1,
        )

    if text == original:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 4.24 consolidation cleanup applied.")
    else:
        print("Phase 4.24 consolidation cleanup was already present.")


if __name__ == "__main__":
    main()
