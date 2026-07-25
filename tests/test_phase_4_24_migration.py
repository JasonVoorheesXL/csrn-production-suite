from __future__ import annotations

from pathlib import Path

import pytest

from tools.apply_phase_4_24 import apply


LEGACY_APP = '''from __future__ import annotations

import copy
import io
import socket
import qrcode
import qrcode.image.svg

# Phase 3.5: BroadcastRespository integrated

# Phase 3.4: VenueRepository integrated

# Phase 3.3: SponsorRepository integrated

# Phase 3.2: RosterRepository integrated

# Phase 3.1: SchoolRepository integrated

from security_service import SecurityService
'''


def test_phase_4_24_cleanup_removes_obsolete_imports_and_comments(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "import io" not in migrated
    assert "import socket" not in migrated
    assert "import qrcode" not in migrated
    assert "BroadcastRespository" not in migrated
    assert "Phase 3 repository boundaries remain integrated below." in migrated
    assert apply(target) is False


def test_phase_4_24_cleanup_refuses_to_remove_a_used_import(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text(
        "import socket\n\ndef resolve():\n    return socket.gethostname()\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="still used"):
        apply(target)
