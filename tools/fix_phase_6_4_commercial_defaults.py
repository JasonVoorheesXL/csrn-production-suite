from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old in text:
        target.write_text(text.replace(old, new), encoding="utf-8")
        return
    if new not in text:
        raise RuntimeError(f"Expected text was not found in {path}: {old!r}")


def main() -> None:
    replacements = {
        "caption_service.py": [
            ('{"channel": 1, "speaker": "Jason", "enabled": True}', '{"channel": 1, "speaker": "Announcer 1", "enabled": True}'),
            ('{"channel": 2, "speaker": "Jordan", "enabled": True}', '{"channel": 2, "speaker": "Announcer 2", "enabled": True}'),
            ('{"channel": 3, "speaker": "Guest 1", "enabled": False}', '{"channel": 3, "speaker": "Announcer 3", "enabled": False}'),
            ('{"channel": 4, "speaker": "Guest 2", "enabled": False}', '{"channel": 4, "speaker": "Announcer 4", "enabled": False}'),
        ],
        "commissioning_service.py": [
            ('"speaker": "Jason",', '"speaker": "Announcer 1",'),
            ('"speaker": "Jordan",', '"speaker": "Announcer 2",'),
            ('"role": "Color Analyst",', '"role": "Analyst",'),
            ('"microphone": "Audio-Technica BPHS1",', '"microphone": "",'),
        ],
        "tests/test_caption_service.py": [
            ('assert result.data["profile"]["channels"][0]["speaker"] == "Jason"', 'assert result.data["profile"]["channels"][0]["speaker"] == "Announcer 1"'),
            ('{"channel": 1, "speaker": "Jason", "enabled": True},', '{"channel": 1, "speaker": "Alpha", "enabled": True},'),
            ('{"channel": 1, "speaker": "Jordan", "enabled": True},', '{"channel": 1, "speaker": "Beta", "enabled": True},'),
            ('assert result.data["segment"]["speaker"] == "Jordan"', 'assert result.data["segment"]["speaker"] == "Announcer 2"'),
            ('assert "Jason: Touchdown Caledonia" in content', 'assert "Announcer 1: Touchdown Caledonia" in content'),
            ('assert "<v Jason>Touchdown Caledonia" in content', 'assert "<v Announcer 1>Touchdown Caledonia" in content'),
        ],
        "tests/test_commissioning_service.py": [
            ('assert result.data["profile"]["channels"][0]["speaker"] == "Jason"', 'assert result.data["profile"]["channels"][0]["speaker"] == "Announcer 1"'),
            ('{"channel": 1, "enabled": True, "speaker": " Jason "},', '{"channel": 1, "enabled": True, "speaker": " Avery "},'),
            ('assert profile["channels"][0]["speaker"] == "Jason"', 'assert profile["channels"][0]["speaker"] == "Avery"'),
            ('profile["channels"][1]["speaker"] = "Jason"', 'profile["channels"][1]["speaker"] = profile["channels"][0]["speaker"]'),
        ],
        "docs/PHASE_6_3_HARDWARE_OBS_COMMISSIONING.md": [
            ('1. Jason — Play-by-Play\n2. Jordan — Color Analyst\n3. Sideline Reporter — disabled until assigned\n4. Guest — disabled until assigned', '1. Announcer 1 — Play-by-Play placeholder\n2. Announcer 2 — Analyst placeholder\n3. Announcer 3 — disabled until assigned\n4. Announcer 4 — disabled until assigned'),
            ('Channel assignments are persistent and become the speaker-identity source for Phase 6.4 captioning. At least two enabled channels must have unique, non-empty speaker names.', 'These labels are neutral installation placeholders, not fixed identities. Each customer assigns its own broadcasters, roles, microphones, and enabled channels during commissioning. Channel assignments are persistent and become the speaker-identity source for Phase 6.4 captioning. At least two enabled channels must have unique, non-empty speaker names.'),
            ('the graphics theme engine is Phase 6.7, Social Publishing Engine is Phase 6.8, and grounded postgame recaps are Phase 6.9.', 'the graphics theme engine is Phase 6.8, Social Publishing Engine is Phase 6.9, and grounded postgame recaps are Phase 6.10.'),
        ],
        "docs/PHASE_6_4_CHANNEL_BASED_CAPTIONING.md": [
            ('- Channel 1 — Jason\n- Channel 2 — Jordan\n- Channel 3 — Guest 1, disabled until assigned\n- Channel 4 — Guest 2, disabled until assigned', '- Channel 1 — Announcer 1 placeholder\n- Channel 2 — Announcer 2 placeholder\n- Channel 3 — Announcer 3, disabled until assigned\n- Channel 4 — Announcer 4, disabled until assigned'),
            ('The profile supports channels 1–12 so later hardware can add sideline reporters, studio talent, or remote guests without changing the caption data model.', 'The placeholder labels are never treated as customer identities. Each installation assigns its own speaker name, role, microphone, and enabled state through commissioning and caption settings. The profile supports channels 1–12 so later hardware can add sideline reporters, studio talent, or remote guests without changing the caption data model.'),
        ],
    }

    for path, changes in replacements.items():
        for old, new in changes:
            replace(path, old, new)

    caption_tests = ROOT / "tests" / "test_caption_service.py"
    text = caption_tests.read_text(encoding="utf-8")
    marker = "\ndef test_profile_update_enables_overlay(tmp_path: Path) -> None:\n"
    test_block = '''\ndef test_profile_speaker_names_are_user_assignable(tmp_path: Path) -> None:\n    service = make_service(tmp_path)\n    profile = service.status().data["profile"]\n    profile["channels"][0]["speaker"] = "Alex"\n    profile["channels"][1]["speaker"] = "Morgan"\n    assert service.update_profile({"channels": profile["channels"]}).ok\n    enable(service)\n    result = service.ingest_segment(segment(channel=2))\n    assert result.ok\n    assert result.data["segment"]["speaker"] == "Morgan"\n\n'''
    if "def test_profile_speaker_names_are_user_assignable" not in text:
        if marker not in text:
            raise RuntimeError("Caption test insertion point was not found")
        caption_tests.write_text(text.replace(marker, test_block + marker), encoding="utf-8")

    print("Commercial channel defaults applied. Speaker names remain user-assignable.")


if __name__ == "__main__":
    main()
