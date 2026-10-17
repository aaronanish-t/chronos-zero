"""Production configuration fail-closed tests."""

from __future__ import annotations

import importlib

import pytest


def _config(monkeypatch, **values):
    names = (
        "CHRONOS_ENV",
        "CHRONOS_PG_DSN",
        "CHRONOS_AUDIT_DSN",
        "CHRONOS_CORS_ORIGINS",
        "CHRONOS_API_TOKEN",
    )
    for name in names:
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    import services.runtime_config as runtime_config

    return importlib.reload(runtime_config)


def test_production_requires_explicit_secrets(monkeypatch):
    runtime_config = _config(monkeypatch, CHRONOS_ENV="production")
    with pytest.raises(runtime_config.ConfigurationError, match="CHRONOS_PG_DSN"):
        runtime_config.validate_production_config()


def test_production_rejects_demo_database_credentials(monkeypatch):
    runtime_config = _config(
        monkeypatch,
        CHRONOS_ENV="production",
        CHRONOS_PG_DSN="postgresql://chronos_kernel:chronos_kernel@postgres:5432",
        CHRONOS_AUDIT_DSN="postgresql://chronos_kernel:chronos_kernel@audit-db:5432/chronos_audit",
        CHRONOS_CORS_ORIGINS="https://chronos.example.com",
        CHRONOS_API_TOKEN="x" * 32,
    )
    with pytest.raises(runtime_config.ConfigurationError, match="development demo credential"):
        runtime_config.validate_production_config()


def test_production_accepts_non_demo_private_services(monkeypatch):
    runtime_config = _config(
        monkeypatch,
        CHRONOS_ENV="production",
        CHRONOS_PG_DSN="postgresql://chronos_app:app-secret@postgres:5432",
        CHRONOS_AUDIT_DSN="postgresql://chronos_app:audit-secret@audit-db:5432/chronos_audit",
        CHRONOS_CORS_ORIGINS="https://chronos.example.com",
        CHRONOS_API_TOKEN="x" * 32,
    )
    config = runtime_config.validate_production_config()
    assert config.production is True
    assert config.bind_host == "0.0.0.0"
    assert config.cors_origins == ("https://chronos.example.com",)


def test_development_profile_keeps_local_defaults(monkeypatch):
    runtime_config = _config(monkeypatch, CHRONOS_ENV="development")
    config = runtime_config.validate_production_config()
    assert config.production is False
    assert config.pg_dsn.startswith("postgresql://chronos_kernel")
    assert config.bind_host == "127.0.0.1"
