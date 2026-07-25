from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


STALE_IMPORT_LINES: tuple[str, ...] = (
    "import io\n",
    "import socket\n",
    "import qrcode\n",
    "import qrcode.image.svg\n",
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

    candidate = text
    for import_line in STALE_IMPORT_LINES:
        candidate = candidate.replace(import_line, "", 1)

    for root in ("io", "socket", "qrcode"):
        if re.search(rf"\b{re.escape(root)}\.", candidate):
            raise RuntimeError(
                f"Cannot remove obsolete {root!r} import; "
                f"{root!r} is still used in app.py."
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
