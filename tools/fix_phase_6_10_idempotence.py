from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools" / "apply_phase_6_10.py"


def apply() -> None:
    source = PATH.read_text(encoding="utf-8")
    old = '''def replace_once(text: str, old: str, new: str, label: str) -> str:\n    if new in text:\n        return text\n    if old not in text:\n        raise RuntimeError(f"Phase 6.10 integration anchor missing: {label}")\n    return text.replace(old, new, 1)\n'''
    new = '''def replace_once(text: str, old: str, new: str, label: str) -> str:\n    if new in text:\n        return text\n    if label == "commercial UX roadmap insertion" and "### 6.10 Commercial UX, Navigation, and Account Onboarding" in text:\n        return text\n    if old not in text:\n        raise RuntimeError(f"Phase 6.10 integration anchor missing: {label}")\n    return text.replace(old, new, 1)\n'''
    if new in source:
        return
    if old not in source:
        raise RuntimeError("Phase 6.10 replace_once anchor missing")
    PATH.write_text(source.replace(old, new, 1), encoding="utf-8")


if __name__ == "__main__":
    apply()
