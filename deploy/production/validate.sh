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

# Read only the names needed for local validation. The values never go to stdout.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

for name in POSTGRES_ADMIN_USER POSTGRES_ADMIN_PASSWORD POSTGRES_APP_PASSWORD CHRONOS_API_TOKEN PUBLIC_HOSTNAME PUBLIC_ORIGIN; do
  [[ -n "${!name:-}" ]] || die "$name is required"
done

[[ "$POSTGRES_ADMIN_PASSWORD" != *replace-with* ]] || die "POSTGRES_ADMIN_PASSWORD still contains a placeholder"
[[ "$POSTGRES_APP_PASSWORD" != *replace-with* ]] || die "POSTGRES_APP_PASSWORD still contains a placeholder"
[[ "$CHRONOS_API_TOKEN" != *replace-with* ]] || die "CHRONOS_API_TOKEN still contains a placeholder"
(( ${#CHRONOS_API_TOKEN} >= 32 )) || die "CHRONOS_API_TOKEN must be at least 32 characters"
[[ "$PUBLIC_ORIGIN" == https://* ]] || die "PUBLIC_ORIGIN must use HTTPS"
[[ "$PUBLIC_HOSTNAME" != chronos.example.com ]] || die "PUBLIC_HOSTNAME still contains the example hostname"

cd "$DEPLOY_DIR"
docker compose --env-file "$ENV_FILE" config --quiet

services="$(docker compose --env-file "$ENV_FILE" config --services)"
for service in postgres audit-db kernel z3 agent ui gateway; do
  grep -qx "$service" <<<"$services" || die "Compose service missing: $service"
done

printf 'production preflight: PASS (%s)\n' "$ENV_FILE"
