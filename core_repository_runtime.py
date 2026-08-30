from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

from core_repositories import ConfigurationRepository, SecurityRepository, StateRepository
from persistence_engine import JsonPersistenceEngine


class CoreRepositoryRuntime:
    """Integrate core repositories without rewriting the existing Flask routes.

    Existing route functions resolve module globals when called. Installing this
    runtime replaces the configuration functions and dispatches state/security
    JSON access through repositories while leaving all other stores unchanged.
    """

    def __init__(self, module: Any) -> None:
        self.module = module
        self.original_load_json: Callable[..., Any] = module.load_json
        self.original_save_json: Callable[..., Any] = module.save_json
        self.engine = JsonPersistenceEngine(
            backup_root=Path(module.DATA_DIR) / "Backups" / "Persistence",
            quarantine_root=Path(module.DATA_DIR) / "Backups" / "Quarantine",
        )
        self.config = ConfigurationRepository(
            self.engine,
            Path(module.CONFIG_FILE),
            module.DEFAULT_CONFIG,
            runtime_identity={
                "version": getattr(module, "RUNTIME_VERSION", ""),
                "build": getattr(module, "RUNTIME_BUILD", ""),
            },
        )
        self.state = StateRepository(
            self.engine,
            Path(module.STATE_FILE),
            module.DEFAULT_STATE,
        )
        self.security = SecurityRepository(
            self.engine,
            Path(module.SECURITY_FILE),
            module.DEFAULT_SECURITY,
        )

    @staticmethod
    def _same_path(left: Path, right: Path) -> bool:
        try:
            return left.resolve() == right.resolve()
        except OSError:
            return Path(left) == Path(right)

    def load_json(self, path: Path, default: Any) -> Any:
        candidate = Path(path)
        if self._same_path(candidate, Path(self.module.CONFIG_FILE)):
            return self.config.load()
        if self._same_path(candidate, Path(self.module.STATE_FILE)):
            return self.state.load()
        if self._same_path(candidate, Path(self.module.SECURITY_FILE)):
            return self.security.load()
        return self.original_load_json(path, default)

    def save_json(self, path: Path, data: Any) -> None:
        candidate = Path(path)
        if self._same_path(candidate, Path(self.module.CONFIG_FILE)):
            self.config.save(data)
            return
        if self._same_path(candidate, Path(self.module.STATE_FILE)):
            self.state.replace(data)
            return
        if self._same_path(candidate, Path(self.module.SECURITY_FILE)):
            self.security.save(data)
            return
        self.original_save_json(path, data)

    def load_config(self) -> dict[str, Any]:
        self.module.ensure_data_architecture()
        config = self.config.load()
        return config

    def save_config(self, config: dict[str, Any]) -> None:
        self.module.ensure_data_architecture()
        self.config.save(config)

    def load_security(self) -> dict[str, Any]:
        security = self.security.load()
        if not security.get("secret_key"):
            import secrets
            security = self.security.update_credentials(
                secret_key=secrets.token_hex(32)
            )
        return security

    def install(self) -> "CoreRepositoryRuntime":
        module = self.module
        module.ensure_data_architecture()
        module.load_json = self.load_json
        module.save_json = self.save_json
        module.load_config = self.load_config
        module.save_config = self.save_config
        module.load_security = self.load_security

        # app.py initializes Flask's key during import, before this runtime is
        # installed. Re-read through the repository and apply the recovered key.
        security = self.load_security()
        module.security = copy.deepcopy(security)
        module.app.secret_key = security["secret_key"]

        module.CORE_REPOSITORY_RUNTIME = self
        return self


def install_core_repository_runtime(module: Any) -> CoreRepositoryRuntime:
    return CoreRepositoryRuntime(module).install()
