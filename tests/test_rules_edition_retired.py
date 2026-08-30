"""Round 7 Task B step 6: the dead rules_edition: "NFHS" config stub is
retired. ruleset_service is the real rule-variance mechanism now.
"""

from __future__ import annotations

from pathlib import Path

import app

ROOT = Path(__file__).resolve().parents[1]


def test_rules_edition_is_gone_from_default_config() -> None:
    assert "rules_edition" not in app.DEFAULT_CONFIG["application"]


def test_runtime_foundation_no_longer_force_injects_it() -> None:
    src = (ROOT / "core_repository_runtime.py").read_text(encoding="utf-8")
    assert "rules_edition" not in src


def test_nothing_live_reads_rules_edition() -> None:
    for rel in ("app.py", "core_repository_runtime.py"):
        assert "rules_edition" not in _stripped_comments((ROOT / rel).read_text(encoding="utf-8"))


def _stripped_comments(text: str) -> str:
    out = []
    for line in text.splitlines():
        code = line.split("#", 1)[0]
        out.append(code)
    return "\n".join(out)
