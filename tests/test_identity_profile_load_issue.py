"""An unusable identity_profile.json must stay survivable but stop being silent.

Before: an unparseable file made load_identity_profile() quietly return the
built-in seed (for an existing install that is Caledonia's own identity) and
nothing anywhere said so. Now the same fallback is logged, the bad file is kept
aside, and the problem is surfaced through identity_service.load_issue() into
/api/diagnostics and /api/readiness. These tests run the real loader against
real files in tmp_path.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

import identity_service
from diagnostics_service import DiagnosticsService

GOOD = {"organization": {"name": "Riverside Radio"}}


def _write(tmp_path: Path, content: str | bytes, name: str = "identity_profile.json") -> Path:
    path = tmp_path / name
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def _load(path: Path, *, existing: bool = True):
    return identity_service.load_identity_profile(path, existing_install=existing)


# --- the fallback still never crashes -------------------------------------------

BAD_FILES = {
    "truncated": ('{"organization": {"name": "Riverside', "invalid_json"),
    "garbage": ("<<<< not json >>>>", "invalid_json"),
    "empty": ("", "invalid_json"),
    "top-level list": ("[1, 2, 3]", "not_an_object"),
    "top-level string": ('"just a string"', "not_an_object"),
    "not utf-8": (b"\xff\xfe\x00{\x80", "invalid_json"),
}


@pytest.mark.parametrize("label", sorted(BAD_FILES))
def test_an_unusable_file_still_falls_back_to_the_seed_without_raising(tmp_path, label) -> None:
    content, kind = BAD_FILES[label]
    path = _write(tmp_path, content)
    profile = _load(path)
    assert profile == identity_service._template(True)  # exactly the same fallback as before
    assert identity_service.load_issue(path)["kind"] == kind


def test_the_bad_file_itself_is_left_exactly_as_it_was(tmp_path) -> None:
    path = _write(tmp_path, '{"organization": {"name": "Riverside')
    _load(path)
    assert path.read_text(encoding="utf-8") == '{"organization": {"name": "Riverside'


# --- it is loud: logged, kept aside, described ------------------------------------


def test_the_failure_is_logged_with_path_reason_position_and_fallback(tmp_path, caplog) -> None:
    path = _write(tmp_path, '{\n  "organization": {\n    "name": "Riverside\n')
    with caplog.at_level(logging.ERROR, logger="csrn.identity"):
        _load(path)
    [record] = [r for r in caplog.records if r.name == "csrn.identity"]
    assert record.levelno == logging.ERROR
    text = record.getMessage()
    assert str(path) in text
    assert "invalid_json" in text and "line " in text and "column " in text
    assert "Caledonia" in text  # says which identity is actually on the air
    assert "copy of the bad file was kept" in text


def test_the_issue_describes_the_problem_precisely(tmp_path) -> None:
    path = _write(tmp_path, '{"organization": {"name": "Riverside",}}')
    _load(path)
    issue = identity_service.load_issue(path)
    assert issue["path"] == str(path)
    assert issue["kind"] == "invalid_json"
    assert issue["line"] == 1 and issue["column"] and issue["error"]
    assert issue["size_bytes"] == len(path.read_bytes())
    assert issue["detected_at"].endswith("Z") and "T" in issue["detected_at"]
    assert issue["fallback"].startswith("existing-install seed")
    json.dumps(issue)  # it is served as JSON


def test_a_new_install_reports_the_blank_seed_as_its_fallback(tmp_path) -> None:
    path = _write(tmp_path, "{oops")
    assert _load(path, existing=False) == identity_service._template(False)
    assert "blank" in identity_service.load_issue(path)["fallback"]


def test_a_copy_of_the_bad_file_is_kept_because_a_later_save_would_overwrite_it(tmp_path) -> None:
    content = '{"organization": {"name": "Riverside", "oops'
    path = _write(tmp_path, content)
    _load(path)
    backup = Path(identity_service.load_issue(path)["backup"])
    assert backup.parent == tmp_path and backup.name.startswith("identity_profile.json.corrupt-")
    assert backup.read_text(encoding="utf-8") == content
    # the overwrite it protects against: saving over the file is exactly what
    # a Configuration Manager save does after a fallback load
    identity_service.save_identity_profile(path, _load(path), existing_install=True)
    assert json.loads(path.read_text(encoding="utf-8"))  # file is valid again...
    assert backup.read_text(encoding="utf-8") == content  # ...and the original is still on disk


def test_repeated_loads_of_the_same_problem_log_once_and_keep_the_first_timestamp(tmp_path, caplog) -> None:
    path = _write(tmp_path, "{broken")
    with caplog.at_level(logging.ERROR, logger="csrn.identity"):
        _load(path)
        first = identity_service.load_issue(path)
        for _ in range(4):
            _load(path)
    assert len([r for r in caplog.records if r.levelno == logging.ERROR]) == 1
    assert identity_service.load_issue(path)["detected_at"] == first["detected_at"]
    assert len(list(tmp_path.glob("identity_profile.json.corrupt-*"))) == 1  # not one copy per load


def test_a_different_problem_is_a_new_event(tmp_path, caplog) -> None:
    path = _write(tmp_path, "{broken")
    with caplog.at_level(logging.ERROR, logger="csrn.identity"):
        _load(path)
        path.write_text("[1]", encoding="utf-8")
        _load(path)
    assert len([r for r in caplog.records if r.levelno == logging.ERROR]) == 2
    assert identity_service.load_issue(path)["kind"] == "not_an_object"


# --- it heals -----------------------------------------------------------------------


def test_the_issue_clears_when_the_file_is_fixed_and_says_so(tmp_path, caplog) -> None:
    path = _write(tmp_path, "{broken")
    _load(path)
    assert identity_service.load_issue(path)
    path.write_text(json.dumps(GOOD), encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="csrn.identity"):
        profile = _load(path)
    assert identity_service.load_issue(path) is None
    assert profile["organization"]["name"] == "Riverside Radio"
    assert any("resolved" in r.getMessage() for r in caplog.records)


def test_saving_a_valid_profile_clears_the_issue(tmp_path) -> None:
    path = _write(tmp_path, "{broken")
    fallback = _load(path)
    assert identity_service.load_issue(path)
    identity_service.save_identity_profile(path, fallback, existing_install=True)
    assert identity_service.load_issue(path) is None


# --- no false alarms ----------------------------------------------------------------


def test_a_healthy_file_reports_nothing_and_logs_nothing(tmp_path, caplog) -> None:
    path = _write(tmp_path, json.dumps(GOOD))
    with caplog.at_level(logging.DEBUG, logger="csrn.identity"):
        profile = _load(path)
    assert profile["organization"]["name"] == "Riverside Radio"
    assert identity_service.load_issue(path) is None
    assert not caplog.records
    assert not list(tmp_path.glob("*.corrupt-*"))


def test_a_missing_file_is_a_first_run_seed_not_a_problem(tmp_path) -> None:
    path = tmp_path / "identity_profile.json"
    _load(path)
    assert path.exists() and identity_service.load_issue(path) is None


def test_a_utf8_byte_order_mark_is_not_corruption(tmp_path) -> None:
    """Windows editors add a BOM to otherwise valid JSON; json.loads rejects it,
    which used to trigger the silent fallback for a perfectly good file."""
    path = _write(tmp_path, b"\xef\xbb\xbf" + json.dumps(GOOD).encode("utf-8"))
    profile = _load(path)
    assert profile["organization"]["name"] == "Riverside Radio"
    assert identity_service.load_issue(path) is None


def test_an_unreadable_file_is_reported_and_still_does_not_crash(tmp_path, monkeypatch, caplog) -> None:
    path = _write(tmp_path, json.dumps(GOOD))
    real = Path.read_bytes

    def locked(self):
        if self == path:
            raise PermissionError(13, "Access is denied")
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", locked)
    with caplog.at_level(logging.ERROR, logger="csrn.identity"):
        profile = _load(path)
    assert profile == identity_service._template(True)
    issue = identity_service.load_issue(path)
    assert issue["kind"] == "unreadable" and "PermissionError" in issue["error"]
    assert issue["backup"] is None  # nothing readable to keep
    assert caplog.records


def test_the_p0_layouts_fallback_is_unchanged(tmp_path) -> None:
    """A file that parses but has a malformed `layouts` section keeps the P0
    behaviour (default layouts) and is not treated as an unparseable profile."""
    path = _write(tmp_path, json.dumps({"layouts": "not-a-document"}))
    profile = _load(path)
    assert profile["layouts"] == identity_service.layout_builder_service.default_layouts_document()
    assert identity_service.load_issue(path) is None


# --- surfaced where the operator looks: diagnostics + readiness ------------------------


def _service(issue) -> DiagnosticsService:
    class _Stub:
        exists = staticmethod(lambda: True)

    def path(name: str) -> Path:
        return Path("nonexistent") / name

    return DiagnosticsService(
        base_dir=Path("."), data_dir=Path("data"),
        config_file=path("config.json"), schools_file=path("s"), broadcasters_file=path("b"),
        rosters_file=path("r"), venues_file=path("v"), logos_file=path("l"), packages_file=path("p"),
        assets_file=path("a"), sponsors_file=path("sp"),
        load_config=lambda: {}, load_state=lambda: {}, public_state=lambda s: {},
        load_obs_status=lambda: {}, authenticated=lambda: True, migrate_venues=lambda: None,
        identity_status=(lambda: issue) if not callable(issue) else issue,
        identity_file=Path("identity_profile.json"),
    )


ISSUE = {"path": "identity_profile.json", "kind": "invalid_json", "error": "Expecting ',' delimiter",
         "line": 4, "column": 9, "backup": "identity_profile.json.corrupt-1a2b3c4d", "detected_at": "2026-09-20T01:02:03Z"}


def test_diagnostics_reports_the_problem_and_a_healthy_profile() -> None:
    bad = _service(ISSUE).diagnostics().data["diagnostics"]["identity_profile"]
    assert bad["ok"] is False and bad["issue"]["line"] == 4 and bad["path"] == "identity_profile.json"
    good = _service(None).diagnostics().data["diagnostics"]["identity_profile"]
    assert good == {"ok": True, "path": "identity_profile.json", "issue": None}


def test_readiness_gets_a_failing_identity_check_only_when_there_is_a_problem() -> None:
    bad = _service(ISSUE).readiness().data["readiness"]
    check = next(c for c in bad["checks"] if c["key"] == "identity_profile")
    assert check["ok"] is False and bad["ready"] is False
    assert "Expecting ',' delimiter" in check["action"] and "corrupt-1a2b3c4d" in check["action"]
    assert "restart" in check["action"].lower()

    good = _service(None).readiness().data["readiness"]
    assert "identity_profile" not in {c["key"] for c in good["checks"]}  # healthy payload unchanged


def test_a_failing_status_probe_cannot_break_diagnostics() -> None:
    def boom():
        raise RuntimeError("probe failed")

    service = _service(boom)
    assert service.diagnostics().data["diagnostics"]["identity_profile"]["ok"] is True
    assert "identity_profile" not in {c["key"] for c in service.readiness().data["readiness"]["checks"]}


def test_the_real_app_reports_its_own_corrupt_profile_through_diagnostics(tmp_path, monkeypatch) -> None:
    import app as app_module

    path = _write(tmp_path, '{"organization": ')
    monkeypatch.setattr(app_module, "IDENTITY_FILE", path)
    _load(path)  # what a startup / save does
    with app_module.app.test_request_context():  # diagnostics() reads the session
        diagnostics = app_module.diagnostic_status()
        assert diagnostics["identity_profile"]["ok"] is False
        assert diagnostics["identity_profile"]["issue"]["kind"] == "invalid_json"
        assert diagnostics["identity_profile"]["path"] != ""
        path.write_text(json.dumps(GOOD), encoding="utf-8")
        _load(path)
        assert app_module.diagnostic_status()["identity_profile"]["ok"] is True


def test_command_center_shows_the_identity_row_in_the_diagnostics_panel() -> None:
    html = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")
    assert "d.identity_profile" in html and "Identity profile" in html
    assert "running on built-in defaults" in html
    assert "idp.issue" in html and "escapeHtml(" in html  # the path/error come from disk: escaped
