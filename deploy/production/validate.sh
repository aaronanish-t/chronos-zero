#!/usr/bin/env bash
set -Eeuo pipefail

# Validate the production bundle without printing secret-expanded Compose output.
# This is intentionally a preflight check; it does not start, stop, migrate, or
# seed any service.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy/production"
ENV_FILE_INPUT="${1:-$DEPLOY_DIR/.env}"
if [[ "$ENV_FILE_INPUT" = /* ]]; then
  ENV_FILE="$ENV_FILE_INPUT"
else
  ENV_FILE="$PWD/$ENV_FILE_INPUT"
fi
ENV_FILE="$(cd "$(dirname "$ENV_FILE")" && pwd)/$(basename "$ENV_FILE")"

die() {
  printf 'production preflight: %s\n' "$1" >&2
  exit 1
}

[[ -f "$ENV_FILE" ]] || die "missing env file: $ENV_FILE"
command -v docker >/dev/null 2>&1 || die "Docker CLI is required"
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required"

if [[ "$(stat -c '%a' "$ENV_FILE" 2>/dev/null || stat -f '%Lp' "$ENV_FILE")" != "600" ]]; then
  die "$ENV_FILE must have mode 600"
fi

# Parse the dotenv file without sourcing it. A deployment secret file is input,
# not shell code; command substitutions, redirects, and arbitrary assignments
# must never execute during preflight.
declare -A seen_keys=()
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  [[ -z "$line" || "$line" == \#* ]] && continue
  [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || die "invalid dotenv line"
  key="${BASH_REMATCH[1]}"
  value="${BASH_REMATCH[2]}"
  case "$key" in
    POSTGRES_ADMIN_USER|POSTGRES_ADMIN_PASSWORD|POSTGRES_APP_PASSWORD|CHRONOS_API_TOKEN|PUBLIC_HOSTNAME|PUBLIC_ORIGIN|CHRONOS_UI_USER|CHRONOS_UI_PASSWORD_HASH) ;;
    *) die "unsupported dotenv key: $key" ;;
  esac
  [[ -z "${seen_keys[$key]+x}" ]] || die "duplicate dotenv key: $key"
  seen_keys[$key]=1
  printf -v "$key" '%s' "$value"
done < "$ENV_FILE"

for name in POSTGRES_ADMIN_USER POSTGRES_ADMIN_PASSWORD POSTGRES_APP_PASSWORD CHRONOS_API_TOKEN PUBLIC_HOSTNAME PUBLIC_ORIGIN CHRONOS_UI_USER CHRONOS_UI_PASSWORD_HASH; do
  [[ -n "${!name:-}" ]] || die "$name is required"
done

[[ "$POSTGRES_ADMIN_PASSWORD" != *replace-with* ]] || die "POSTGRES_ADMIN_PASSWORD still contains a placeholder"
[[ "$POSTGRES_APP_PASSWORD" != *replace-with* ]] || die "POSTGRES_APP_PASSWORD still contains a placeholder"
[[ "$CHRONOS_API_TOKEN" != *replace-with* ]] || die "CHRONOS_API_TOKEN still contains a placeholder"
(( ${#POSTGRES_ADMIN_PASSWORD} >= 24 )) || die "POSTGRES_ADMIN_PASSWORD must be at least 24 characters"
(( ${#POSTGRES_APP_PASSWORD} >= 24 )) || die "POSTGRES_APP_PASSWORD must be at least 24 characters"
[[ "$POSTGRES_APP_PASSWORD" =~ ^[A-Za-z0-9._~-]+$ ]] || die "POSTGRES_APP_PASSWORD contains characters unsafe in a PostgreSQL DSN"
(( ${#CHRONOS_API_TOKEN} >= 32 )) || die "CHRONOS_API_TOKEN must be at least 32 characters"
[[ "$PUBLIC_ORIGIN" == https://* ]] || die "PUBLIC_ORIGIN must use HTTPS"
[[ "$PUBLIC_HOSTNAME" != chronos.example.com ]] || die "PUBLIC_HOSTNAME still contains the example hostname"
[[ "$CHRONOS_UI_USER" =~ ^[A-Za-z0-9._-]+$ ]] || die "CHRONOS_UI_USER may only contain letters, digits, '.', '_' and '-'"
# Single quotes keep Compose from expanding the $ signs inside the bcrypt hash.
[[ "$CHRONOS_UI_PASSWORD_HASH" =~ ^\'\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}\'$ ]] \
  || die "CHRONOS_UI_PASSWORD_HASH must be a single-quoted bcrypt hash from 'caddy hash-password'"

cd "$DEPLOY_DIR"
docker compose --env-file "$ENV_FILE" config --quiet

services="$(docker compose --env-file "$ENV_FILE" config --services)"
for service in postgres audit-db kernel z3 agent ui gateway; do
  grep -qx "$service" <<<"$services" || die "Compose service missing: $service"
done

printf 'production preflight: PASS (%s)\n' "$ENV_FILE"
