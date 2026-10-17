#!/usr/bin/env bash
set -Eeuo pipefail

: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD is required}"

psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=app_password="$POSTGRES_APP_PASSWORD" <<'SQL'
CREATE ROLE chronos_app LOGIN PASSWORD :'app_password';
CREATE DATABASE chronos_healthcare_fhir OWNER chronos_app;
CREATE DATABASE chronos_fintech_escrow OWNER chronos_app;
CREATE DATABASE chronos_cloud_devops OWNER chronos_app;
SQL
