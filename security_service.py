from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any, Callable

from werkzeug.security import check_password_hash, generate_password_hash

from core_repositories import SecurityRepository


@dataclass(frozen=True)
class SecurityResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class SecurityService:
    """Authentication business logic independent of Flask routes."""

    def __init__(
        self,
        repository: SecurityRepository,
        *,
        max_attempts: int = 3,
        lockout_seconds: int = 60,
        clock: Callable[[], float] = time,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if lockout_seconds < 1:
            raise ValueError("lockout_seconds must be at least 1.")

        self.repository = repository
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self.clock = clock

    def ensure_secret_key(
        self,
        secret_factory: Callable[[], str],
    ) -> dict[str, Any]:
        security = self.repository.load()
        if not security.get("secret_key"):
            security = self.repository.update_credentials(
                secret_key=secret_factory()
            )
        return security

    def pin_is_configured(self) -> bool:
        return bool(self.repository.load().get("pin_hash"))

    def setup_pin(self, pin: str, confirm: str) -> SecurityResult:
        if self.pin_is_configured():
            return SecurityResult("PIN_ALREADY_CONFIGURED")

        if not (pin.isdigit() and len(pin) == 6):
            return SecurityResult("PIN_MUST_BE_6_DIGITS")

        if pin != confirm:
            return SecurityResult("PIN_MISMATCH")

        self.repository.update_credentials(
            pin_hash=generate_password_hash(pin, method="scrypt")
        )
        self.repository.clear_failed_attempts()
        return SecurityResult("OK")

    def authenticate(self, pin: str) -> SecurityResult:
        security = self.repository.load()
        now = self.clock()
        locked_until = float(security.get("locked_until", 0))

        if now < locked_until:
            return SecurityResult(
                "LOCKED",
                {"locked_seconds": int(locked_until - now)},
            )

        if check_password_hash(
            security.get("pin_hash", ""),
            pin,
        ):
            self.repository.clear_failed_attempts()
            return SecurityResult("OK")

        failed = self.repository.record_failed_attempt(
            max_attempts=self.max_attempts,
            locked_until=int(now + self.lockout_seconds),
        )
        attempts = int(failed.get("failed_attempts", 0))
        new_locked_until = float(failed.get("locked_until", 0))

        if attempts == 0 and new_locked_until > now:
            return SecurityResult(
                "LOCKED",
                {"locked_seconds": self.lockout_seconds},
            )

        return SecurityResult(
            "INVALID_PIN",
            {"attempts_remaining": self.max_attempts - attempts},
        )
