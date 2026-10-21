"""Subprocess coverage for the production deployment preflight."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "deploy" / "production" / "validate.sh"
CADDYFILE = SCRIPT.parent / "Caddyfile"
UI_PASSWORD_HASH = "'$2a$14$Zkx19XLiW6VYouLHR5NmfOFU0z2GTNmpkT/5qqR7hx4IjWJPDhjvG'"


def _env_file(
    path: Path, *, app_password: str, api_token: str, ui_password_hash: str = UI_PASSWORD_HASH
) -> None:
    path.write_text(
        "\n".join(
            [
                "POSTGRES_ADMIN_USER=chronos_admin",
                "POSTGRES_ADMIN_PASSWORD=" + "a" * 32,
                "POSTGRES_APP_PASSWORD=" + app_password,
                "CHRONOS_API_TOKEN=" + api_token,
                "PUBLIC_HOSTNAME=chronos.test.example",
                "PUBLIC_ORIGIN=https://chronos.test.example",
                "CHRONOS_UI_USER=operator",
                "CHRONOS_UI_PASSWORD_HASH=" + ui_password_hash,
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


def test_preflight_rejects_unquoted_ui_password_hash(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    _env_file(
        env_file,
        app_password="safe-app-password-0123456789",
        api_token="x" * 40,
        ui_password_hash=UI_PASSWORD_HASH.strip("'"),
    )

    result = _run(env_file)

    assert result.returncode != 0
    assert "single-quoted bcrypt hash" in result.stderr


def test_gateway_attaches_the_api_token_only_after_operator_sign_in() -> None:
    caddyfile = CADDYFILE.read_text(encoding="utf-8")

    assert "@protected not path /readyz" in caddyfile
    assert re.search(
        r"basic_auth @protected \{\s*\{\$CHRONOS_UI_USER\} \{\$CHRONOS_UI_PASSWORD_HASH\}\s*\}", caddyfile
    )
    # The sign-in is ambient in browsers, so API calls started by another site are refused.
    assert "respond @cross_site 403" in caddyfile
    assert "not header Origin {$PUBLIC_ORIGIN}" in caddyfile
    # /readyz is the one anonymous route, so it must not carry the token.
    readiness = re.search(r"reverse_proxy @readiness[^\n]*", caddyfile)
    assert readiness and "{" not in readiness.group(0)
