"""Runtime configuration and production safety checks.

Development and test profiles may use local defaults. A deployable installation
must opt into ``CHRONOS_ENV=production`` and provide explicit, non-demo
connection strings and browser origins. This module keeps that boundary in one
place so a service cannot silently boot with unsafe defaults in production.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit


DEMO_PG_USER = "chronos_kernel"
DEMO_PG_PASSWORD = "chronos_kernel"
DEMO_AUDIT_DB = "chronos_audit"


class ConfigurationError(RuntimeError):
    """Raised when a deployment is unsafe or incomplete."""


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    return value.strip() if value else value


def _required(name: str) -> str:
    value = _env(name)
    if not value:
        raise ConfigurationError(f"{name} is required when CHRONOS_ENV=production")
    return value


def _validate_dsn(name: str, value: str, *, audit: bool = False) -> None:
    parsed = urlsplit(value)
    if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname:
        raise ConfigurationError(f"{name} must be a PostgreSQL DSN with a hostname")
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        raise ConfigurationError(f"{name} cannot target loopback in production")
    if parsed.username == DEMO_PG_USER and unquote(parsed.password or "") == DEMO_PG_PASSWORD:
        raise ConfigurationError(f"{name} uses the development demo credential")
    if audit and parsed.path.rstrip("/") != f"/{DEMO_AUDIT_DB}":
        raise ConfigurationError(f"{name} must point to the chronos_audit database")


@dataclass(frozen=True)
class RuntimeConfig:
    environment: str
    bind_host: str
    kernel_port: int
    z3_port: int
    agent_port: int
    pg_dsn: str
    audit_dsn: str
    cors_origins: tuple[str, ...]
    z3_url: str
    kernel_url: str
    api_token: str | None

    @property
    def production(self) -> bool:
        return self.environment == "production"


def load_config() -> RuntimeConfig:
    environment = (_env("CHRONOS_ENV", "development") or "development").lower()
    if environment not in {"development", "test", "production"}:
        raise ConfigurationError("CHRONOS_ENV must be development, test, or production")

    production = environment == "production"
    pg_dsn = _required("CHRONOS_PG_DSN") if production else _env(
        "CHRONOS_PG_DSN", "postgresql://chronos_kernel:chronos_kernel@127.0.0.1:5432"
    )
    audit_dsn = _required("CHRONOS_AUDIT_DSN") if production else _env(
        "CHRONOS_AUDIT_DSN", "postgresql://chronos_kernel:chronos_kernel@127.0.0.1:5433/chronos_audit"
    )
    assert pg_dsn is not None and audit_dsn is not None

    origins = tuple(filter(None, (_env("CHRONOS_CORS_ORIGINS", "") or "").split(",")))
    if production:
        _validate_dsn("CHRONOS_PG_DSN", pg_dsn)
        _validate_dsn("CHRONOS_AUDIT_DSN", audit_dsn, audit=True)
        if not origins or "*" in origins:
            raise ConfigurationError("CHRONOS_CORS_ORIGINS must contain explicit origins in production")

    return RuntimeConfig(
        environment=environment,
        bind_host=_env("CHRONOS_BIND_HOST", "0.0.0.0" if production else "127.0.0.1") or "127.0.0.1",
        kernel_port=int(_env("CHRONOS_KERNEL_PORT", "8000") or "8000"),
        z3_port=int(_env("CHRONOS_Z3_PORT", "8001") or "8001"),
        agent_port=int(_env("CHRONOS_AGENT_PORT", "8002") or "8002"),
        pg_dsn=pg_dsn,
        audit_dsn=audit_dsn,
        cors_origins=origins,
        z3_url=_env("CHRONOS_Z3_URL", "http://127.0.0.1:8001/v1/z3/verify") or "",
        kernel_url=_env("CHRONOS_KERNEL_URL", "http://127.0.0.1:8000") or "",
        api_token=_env("CHRONOS_API_TOKEN"),
    )


def validate_production_config() -> RuntimeConfig:
    """Load config and fail closed when production requirements are missing."""
    config = load_config()
    if config.production and len(config.api_token or "") < 32:
        raise ConfigurationError("CHRONOS_API_TOKEN must be at least 32 characters in production")
    return config
