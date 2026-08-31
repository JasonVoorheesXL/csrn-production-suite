from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


PRODUCT_VENDOR = "PossumFrog"
PRODUCT_NAME = "CSRN Production Suite"
PRODUCT_ID = "possumfrog.csrn-production-suite"


@dataclass(frozen=True)
class ProductPaths:
    base_dir: Path
    runtime_root: Path
    data_dir: Path
    state_file: Path
    security_file: Path
    identity_file: Path
    logs_dir: Path
    exports_dir: Path
    updates_dir: Path
    support_dir: Path
    license_file: Path
    installation_file: Path
    installed_mode: bool

    def ensure(self) -> None:
        for directory in (
            self.runtime_root,
            self.data_dir,
            self.logs_dir,
            self.exports_dir,
            self.updates_dir,
            self.support_dir,
            self.license_file.parent,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _default_runtime_root(env: Mapping[str, str]) -> Path:
    local_app_data = str(env.get("LOCALAPPDATA", "")).strip()
    if local_app_data:
        return Path(local_app_data) / PRODUCT_VENDOR / PRODUCT_NAME
    return Path.home() / ".possumfrog" / "csrn-production-suite"


def resolve_product_paths(
    base_dir: Path,
    *,
    env: Mapping[str, str] | None = None,
    frozen: bool | None = None,
) -> ProductPaths:
    """Resolve development or installed data locations without moving data implicitly."""

    source = dict(os.environ if env is None else env)
    base = Path(base_dir).resolve()
    explicit_root = str(source.get("CSRN_RUNTIME_ROOT", "")).strip()
    explicit_data = str(source.get("CSRN_DATA_ROOT", "")).strip()
    installed = _truthy(source.get("CSRN_INSTALLED")) or bool(frozen)
    if explicit_root or explicit_data:
        installed = True

    runtime_root = (
        Path(explicit_root).expanduser().resolve()
        if explicit_root
        else (_default_runtime_root(source).expanduser().resolve() if installed else base)
    )
    data_dir = (
        Path(explicit_data).expanduser().resolve()
        if explicit_data
        else (runtime_root / "Data" if installed else base / "Data")
    )

    return ProductPaths(
        base_dir=base,
        runtime_root=runtime_root,
        data_dir=data_dir,
        state_file=runtime_root / "state.json" if installed else base / "state.json",
        security_file=runtime_root / "security.json" if installed else base / "security.json",
        identity_file=(
            runtime_root / "identity_profile.json"
            if installed
            else base / "identity_profile.json"
        ),
        logs_dir=runtime_root / "Logs" if installed else data_dir / "Logs",
        exports_dir=runtime_root / "Exports" if installed else base / "Exports",
        updates_dir=runtime_root / "Updates",
        support_dir=runtime_root / "Support",
        license_file=runtime_root / "Licensing" / "license.json",
        installation_file=runtime_root / "Licensing" / "installation.json",
        installed_mode=installed,
    )


def migrate_legacy_runtime(
    paths: ProductPaths,
    *,
    confirmation: str,
) -> dict[str, object]:
    """Copy legacy colocated runtime data into an external runtime root once."""

    if confirmation != "MIGRATE LEGACY CSRN DATA":
        return {"status": "CONFIRMATION_REQUIRED", "copied": 0}
    if not paths.installed_mode:
        return {"status": "NOT_INSTALLED_MODE", "copied": 0}

    marker = paths.runtime_root / ".legacy-runtime-migrated"
    if marker.exists():
        return {"status": "ALREADY_MIGRATED", "copied": 0}

    legacy_data = paths.base_dir / "Data"
    copied = 0
    paths.ensure()
    if legacy_data.exists() and legacy_data.resolve() != paths.data_dir.resolve():
        for source in legacy_data.rglob("*"):
            if not source.is_file() or "Backups" in source.relative_to(legacy_data).parts:
                continue
            relative = source.relative_to(legacy_data)
            destination = paths.data_dir / relative
            if destination.exists():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied += 1

    for source, destination in (
        (paths.base_dir / "state.json", paths.state_file),
        (paths.base_dir / "security.json", paths.security_file),
    ):
        if source.exists() and source.resolve() != destination.resolve() and not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied += 1

    marker.write_text("completed\n", encoding="utf-8")
    return {"status": "MIGRATED", "copied": copied, "runtime_root": str(paths.runtime_root)}
