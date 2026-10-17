"""Subprocess coverage for the production deployment preflight."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "deploy" / "production" / "validate.sh"


def _env_file(path: Path, *, app_password: str, api_token: str) -> None:
    path.write_text(
        "\n".join(
            [
                "POSTGRES_ADMIN_USER=chronos_admin",
                "POSTGRES_ADMIN_PASSWORD=" + "a" * 32,
                "POSTGRES_APP_PASSWORD=" + app_password,
                "CHRONOS_API_TOKEN=" + api_token,
                "PUBLIC_HOSTNAME=chronos.test.example",
                "PUBLIC_ORIGIN=https://chronos.test.example",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)


def _run(env_file: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), str(env_file)],
        cwd=SCRIPT.parents[2],
        text=True,
        capture_output=True,
        check=False,
    )


def test_preflight_does_not_source_dotenv_values(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist"
    env_file = tmp_path / ".env"
    _env_file(
        env_file,
        app_password="safe-app-password-0123456789",
        api_token="$(touch " + str(marker) + ")-" + "x" * 40,
    )

    result = _run(env_file)

    assert not marker.exists()
    assert result.returncode == 0, result.stderr


def test_preflight_rejects_dsn_unsafe_application_password(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    _env_file(env_file, app_password="unsafe@password-0123456789", api_token="x" * 40)

    result = _run(env_file)

    assert result.returncode != 0
    assert "unsafe in a PostgreSQL DSN" in result.stderr
