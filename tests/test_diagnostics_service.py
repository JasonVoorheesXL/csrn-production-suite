from __future__ import annotations

from pathlib import Path
from typing import Any

from diagnostics_service import DiagnosticsService


def build_service(
    tmp_path: Path,
    *,
    config: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    obs: dict[str, Any] | None = None,
    authenticated: bool = True,
):
    base = tmp_path
    data = base / "Data"
    paths = {
        "config": data / "Settings" / "config.json",
        "schools": data / "Schools" / "schools.json",
        "broadcasters": data / "Settings" / "broadcasters.json",
        "rosters": data / "Rosters" / "rosters.json",
        "venues": data / "Venues" / "venues.json",
        "logos": data / "Logos" / "logos.json",
        "packages": data / "Packages" / "broadcast_packages.json",
        "assets": data / "Assets" / "assets.json",
        "sponsors": data / "Sponsors" / "sponsors.json",
    }
    calls: list[str] = []
    config_value = config or {
        "organization": {"logo_path": "static/csrn-logo.png"},
        "application": {"version": "Version X", "build": "BUILD-X"},
        "obs": {
            "required_scene": "Scorebug Scene",
            "browser_source": "Scorebug Browser",
            "program_visual_scene": "Program Visual",
        },
    }
    state_value = state or {"broadcast_id": "B1"}
    obs_value = obs or {
        "reachable": True,
        "authenticated": True,
        "required_scene_exists": True,
        "browser_source_exists": True,
    }

    service = DiagnosticsService(
        base_dir=base,
        data_dir=data,
        config_file=paths["config"],
        schools_file=paths["schools"],
        broadcasters_file=paths["broadcasters"],
        rosters_file=paths["rosters"],
        venues_file=paths["venues"],
        logos_file=paths["logos"],
        packages_file=paths["packages"],
        assets_file=paths["assets"],
        sponsors_file=paths["sponsors"],
        load_config=lambda: config_value,
        load_state=lambda: state_value,
        public_state=lambda value: {**value, "public": True},
        load_obs_status=lambda: obs_value,
        authenticated=lambda: authenticated,
        migrate_venues=lambda: calls.append("migrate"),
    )
    return service, paths, calls, config_value, state_value, obs_value


def test_diagnostics_reports_required_paths(tmp_path: Path) -> None:
    service, paths, _, _, _, _ = build_service(tmp_path)
    result = service.diagnostics()
    checks = result.data["diagnostics"]["checks"]
    assert result.ok
    assert len(checks) == 12
    assert {row["name"] for row in checks} >= {
        "Configuration",
        "School database",
        "Broadcast packages",
    }
    assert next(row for row in checks if row["name"] == "Configuration")[
        "path"
    ] == str(paths["config"])


def test_diagnostics_preserves_identity_auth_and_obs(tmp_path: Path) -> None:
    service, _, _, _, _, obs = build_service(tmp_path, authenticated=False)
    payload = service.diagnostics().data["diagnostics"]
    assert payload["version"] == "Version X"
    assert payload["build"] == "BUILD-X"
    assert payload["authenticated"] is False
    assert payload["obs"] == obs


def test_diagnostics_marks_file_backed_engines_healthy(tmp_path: Path) -> None:
    service, paths, _, _, _, _ = build_service(tmp_path)
    for key in ("rosters", "broadcasters", "packages", "assets", "sponsors"):
        paths[key].parent.mkdir(parents=True, exist_ok=True)
        paths[key].write_text("{}", encoding="utf-8")
    engines = {
        row["name"]: row["status"]
        for row in service.diagnostics().data["diagnostics"]["engines"]
    }
    assert engines["Roster Engine"] == "Healthy"
    assert engines["Personnel Engine"] == "Healthy"
    assert engines["Asset Manager"] == "Healthy"
    assert engines["Sponsor Engine"] == "Healthy"
    assert engines["Broadcast Package Engine"] == "Healthy"


def test_diagnostics_uses_configured_logo_path(tmp_path: Path) -> None:
    config = {
        "organization": {"logo_path": "branding/network.png"},
        "application": {},
        "obs": {},
    }
    service, _, _, _, _, _ = build_service(tmp_path, config=config)
    logo = next(
        row
        for row in service.diagnostics().data["diagnostics"]["checks"]
        if row["name"] == "Logo file"
    )
    assert logo["path"] == str(tmp_path / "branding/network.png")


def test_diagnostics_uses_identity_fallbacks(tmp_path: Path) -> None:
    service, _, _, _, _, _ = build_service(
        tmp_path,
        config={"organization": {}, "application": {}, "obs": {}},
    )
    payload = service.diagnostics().data["diagnostics"]
    assert payload["version"] == "1.0 Alpha"
    assert payload["build"] == "0007"


def test_readiness_runs_venue_migration(tmp_path: Path) -> None:
    service, _, calls, _, _, _ = build_service(tmp_path)
    service.readiness()
    assert calls == ["migrate"]


def test_readiness_is_ready_when_all_checks_pass(tmp_path: Path) -> None:
    service, _, _, _, _, _ = build_service(tmp_path)
    payload = service.readiness().data["readiness"]
    assert payload["ready"] is True
    assert all(row["ok"] for row in payload["checks"])


def test_readiness_fails_when_obs_requirements_are_missing(tmp_path: Path) -> None:
    service, _, _, _, _, _ = build_service(
        tmp_path,
        obs={
            "reachable": False,
            "authenticated": False,
            "required_scene_exists": False,
            "browser_source_exists": False,
        },
    )
    payload = service.readiness().data["readiness"]
    assert payload["ready"] is False
    failed = {row["key"] for row in payload["checks"] if not row["ok"]}
    assert failed == {"obs", "scene", "browser"}


def test_readiness_actions_use_configured_obs_names(tmp_path: Path) -> None:
    service, _, _, _, _, _ = build_service(tmp_path)
    checks = {
        row["key"]: row
        for row in service.readiness().data["readiness"]["checks"]
    }
    assert checks["scene"]["action"].endswith("Scorebug Scene")
    assert "Scorebug Browser" in checks["browser"]["action"]
    assert "http://127.0.0.1:5050/overlay" in checks["browser"]["action"]


def test_readiness_returns_overlay_safe_state_copy(tmp_path: Path) -> None:
    service, _, _, _, state, _ = build_service(tmp_path)
    payload = service.readiness().data["readiness"]
    assert payload["state"] == {"broadcast_id": "B1", "public": True}
    payload["state"]["broadcast_id"] = "changed"
    assert state["broadcast_id"] == "B1"
