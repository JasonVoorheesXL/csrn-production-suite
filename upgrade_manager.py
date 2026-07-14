from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

BUILD_PREFIX = "CSRN_Production_Suite_1.0_Alpha_Build_"
SUITE_PREFIX = "CSRN_Production_Suite"
MIGRATION_STATE_FILE = ".migration-complete.json"


def deep_merge(defaults: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(defaults))
    for key, value in existing.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def build_number(path: Path) -> int:
    if not path.name.startswith(BUILD_PREFIX):
        return -1
    suffix = path.name.replace(BUILD_PREFIX, "", 1).split("_")[0]
    return int(suffix) if suffix.isdigit() else -1


def release_rank(path: Path) -> tuple[int, int, int, int]:
    """Return a sortable release rank for versioned and legacy CSRN folders."""
    import re

    name = path.name
    version = re.search(r"Version[_ ](\d+)\.(\d+)", name, flags=re.IGNORECASE)
    if version:
        hotfix = re.search(r"Hotfix[_ ](\d+)", name, flags=re.IGNORECASE)
        return (2, int(version.group(1)), int(version.group(2)), int(hotfix.group(1)) if hotfix else 0)

    number = build_number(path)
    if number >= 0:
        return (1, 0, number, 0)
    return (0, 0, 0, 0)


def find_previous_builds(current_dir: Path) -> list[Path]:
    """Find prior CSRN installations beside the current folder.

    Version 1.0 introduced semantic release folder names, so migration can no
    longer rely only on the legacy Build_#### prefix.
    """
    builds: list[Path] = []
    parent = current_dir.parent
    current_rank = release_rank(current_dir)
    if not parent.exists():
        return builds

    for child in parent.iterdir():
        if not child.is_dir() or child.resolve() == current_dir.resolve():
            continue
        if not child.name.startswith(SUITE_PREFIX):
            continue
        if not (child / "Data").exists():
            continue

        rank = release_rank(child)
        # Do not migrate from a release newer than the current installation.
        if current_rank[0] and rank[0] and rank > current_rank:
            continue
        builds.append(child)

    def candidate_rank(path: Path) -> tuple[tuple[int, int, int, int], int, float]:
        data = path / "Data"
        record_count = (
            count_json_records(data / "Schools" / "schools.json")
            + count_json_records(data / "Settings" / "broadcasters.json")
            + count_json_records(data / "Venues" / "venues.json")
            + count_json_records(data / "Logos" / "logos.json")
            + (len(list((data / "Broadcasts").glob("*.json"))) if (data / "Broadcasts").exists() else 0)
        )
        newest_data_change = data.stat().st_mtime if data.exists() else 0.0
        if data.exists():
            for item in data.rglob("*"):
                try:
                    newest_data_change = max(newest_data_change, item.stat().st_mtime)
                except OSError:
                    pass
        security = path / "security.json"
        if security.exists():
            newest_data_change = max(newest_data_change, security.stat().st_mtime)
        return release_rank(path), record_count, newest_data_change

    return sorted(builds, key=candidate_rank, reverse=True)


def count_json_records(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            for key in ("schools", "items", "records"):
                if isinstance(data.get(key), list):
                    return len(data[key])
            return 1
    except Exception:
        return 0
    return 0


def inspect_candidate(current_dir: Path) -> dict[str, Any]:
    previous = find_previous_builds(current_dir)
    if not previous:
        return {
            "available": False,
            "source_build": "",
            "source_path": "",
            "summary": {},
            "message": "No previous build was found beside this installation.",
        }

    source = previous[0]
    marker_path = current_dir / MIGRATION_STATE_FILE
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8")) if marker_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        marker = {}
    if marker.get("source_path") == str(source.resolve()) and marker.get("status") == "MIGRATED":
        return {
            "available": False,
            "migration_complete": True,
            "source_build": source.name,
            "source_path": str(source),
            "summary": marker.get("summary", {}),
            "message": f"Migration from {source.name} is already complete.",
        }
    data = source / "Data"
    summary = {
        "configuration": (data / "Settings" / "config.json").exists(),
        "schools": count_json_records(data / "Schools" / "schools.json"),
        "staff": count_json_records(data / "Settings" / "broadcasters.json"),
        "broadcasts": len(list((data / "Broadcasts").glob("*.json"))) if (data / "Broadcasts").exists() else 0,
        "statistics_files": len(list((data / "Statistics").rglob("*"))) if (data / "Statistics").exists() else 0,
        "logs_files": len(list((data / "Logs").rglob("*"))) if (data / "Logs").exists() else 0,
        "security_file": (source / "security.json").exists(),
    }
    return {
        "available": data.exists(),
        "migration_complete": False,
        "source_build": source.name,
        "source_path": str(source),
        "summary": summary,
        "message": "Previous build data is available for migration." if data.exists()
                   else "The previous build was found, but it has no Data folder.",
    }


def create_backup(current_dir: Path) -> Path:
    current_data = current_dir / "Data"
    backup_root = current_data / "Backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_path = backup_root / time.strftime("pre-upgrade-%Y%m%d-%H%M%S")
    shutil.copytree(
        current_data,
        backup_path,
        ignore=shutil.ignore_patterns("Backups"),
    )
    return backup_path


def migrate(current_dir: Path, defaults: dict[str, Any], include_security: bool = True) -> dict[str, Any]:
    candidate = inspect_candidate(current_dir)
    report: dict[str, Any] = {
        "status": "NOT_RUN",
        "source_build": candidate.get("source_build", ""),
        "source_path": candidate.get("source_path", ""),
        "backup_path": "",
        "copied_files": 0,
        "merged_config": False,
        "security_migrated": False,
        "errors": [],
    }
    if not candidate.get("available"):
        report["status"] = "NO_PREVIOUS_DATA"
        return report

    source = Path(candidate["source_path"])
    source_data = source / "Data"
    current_data = current_dir / "Data"

    try:
        report["backup_path"] = str(create_backup(current_dir))

        for src_file in source_data.rglob("*"):
            if not src_file.is_file():
                continue
            relative = src_file.relative_to(source_data)
            if relative.as_posix() == "Settings/config.json":
                continue
            if relative.parts and relative.parts[0] == "Backups":
                continue
            destination = current_data / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, destination)
            report["copied_files"] += 1

        old_config_path = source_data / "Settings" / "config.json"
        existing_config: dict[str, Any] = {}
        if old_config_path.exists():
            existing_config = json.loads(old_config_path.read_text(encoding="utf-8"))

        merged_config = deep_merge(defaults, existing_config)
        merged_config.setdefault("application", {})
        merged_config["application"]["version"] = defaults["application"]["version"]
        merged_config["application"]["build"] = defaults["application"]["build"]
        merged_config["application"]["upgrade_manager_enabled"] = True
        merged_config["application"]["last_migration_status"] = "MIGRATED"

        new_config_path = current_data / "Settings" / "config.json"
        new_config_path.parent.mkdir(parents=True, exist_ok=True)
        new_config_path.write_text(json.dumps(merged_config, indent=2), encoding="utf-8")
        report["merged_config"] = True

        if include_security and (source / "security.json").exists():
            shutil.copy2(source / "security.json", current_dir / "security.json")
            report["security_migrated"] = True

        report["status"] = "MIGRATED"
        marker = {
            "status": "MIGRATED",
            "source_build": source.name,
            "source_path": str(source.resolve()),
            "completed_at": int(time.time()),
            "security_migrated": report["security_migrated"],
            "summary": candidate.get("summary", {}),
        }
        (current_dir / MIGRATION_STATE_FILE).write_text(
            json.dumps(marker, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        report["status"] = "FAILED"
        report["errors"].append(str(exc))

    return report
