#!/usr/bin/env bash
set -Eeuo pipefail

# CHRONOS-ZERO stage launcher.
# Cartridge state is PostgreSQL 16 per AGENTS.md; the database container uses
# tmpfs for RAM-backed demo state. replay_cache.sqlite remains only the offline
# LLM trajectory cache, never production cartridge state.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
UI_URL="http://127.0.0.1:3000"
LOG_DIR="${TMPDIR:-/tmp}/chronos-zero-stage-${$}"
PIDS=()

cleanup() {
  trap - EXIT INT TERM
  for pid in "${PIDS[@]:-}"; do
    kill -INT "$pid" 2>/dev/null || true
  done
  for pid in "${PIDS[@]:-}"; do
    wait "$pid" 2>/dev/null || true
  done
  rm -rf "$LOG_DIR"
}
trap cleanup EXIT INT TERM

kill_port() {
  local port="$1"
  if command -v fuser >/dev/null 2>&1; then
    fuser -k -TERM "${port}/tcp" >/dev/null 2>&1 || true
  fi
}

wait_http() {
  local name="$1"
  local url="$2"
  for _ in $(seq 1 90); do
    if curl --silent --show-error --fail --max-time 1 "$url" >/dev/null 2>&1; then
      printf '  %-8s ready: %s\n' "$name" "$url"
      return 0
    fi
    sleep 0.5
  done
  printf 'service did not become ready: %s (%s)\n' "$name" "$url" >&2
  return 1
}

start_service() {
  local name="$1"
  local cwd="$2"
  shift 2
  printf 'starting %-8s\n' "$name"
  (cd "$cwd" && env \
    OFFLINE_MODE=1 \
    PYTHONUNBUFFERED=1 \
    CHRONOS_KERNEL_PORT=8000 \
    CHRONOS_Z3_PORT=8001 \
    CHRONOS_AGENT_PORT=8002 \
    CHRONOS_Z3_URL=http://127.0.0.1:8001/v1/z3/verify \
    CHRONOS_KERNEL_URL=http://127.0.0.1:8000 \
    CHRONOS_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000 \
    CHRONOS_KERNEL_HTTP=http://127.0.0.1:8000 \
    CHRONOS_KERNEL_POLICY_EVENT_URL=http://127.0.0.1:8000/v1/kernel/telemetry/policy-compiled \
    CHRONOS_Z3_HTTP=http://127.0.0.1:8001 \
    CHRONOS_AGENT_HTTP=http://127.0.0.1:8002 \
    NEXT_PUBLIC_CHRONOS_WS_URL=ws://127.0.0.1:8000/ws/telemetry \
    "$@" >"$LOG_DIR/${name}.log" 2>&1) &
  PIDS+=("$!")
}

mkdir -p "$LOG_DIR"
for port in 8000 8001 8002 3000; do
  kill_port "$port"
done

if [[ "${SKIP_DB:-0}" != "1" ]]; then
  command -v docker >/dev/null 2>&1 || {
    printf 'Docker is required for the PostgreSQL stage database. Set SKIP_DB=1 only when it is already running.\n' >&2
    exit 1
  }
  docker compose -f "$ROOT_DIR/docker-compose.yml" up -d --wait postgres audit-db
fi

printf 'seeding PostgreSQL cartridge databases\n'
(cd "$ROOT_DIR" && "$PYTHON_BIN" services/cartridges/seed_databases.py)

start_service kernel "$ROOT_DIR/services/kernel-proxy" "$PYTHON_BIN" main.py
start_service z3 "$ROOT_DIR/services/z3-verifier" "$PYTHON_BIN" server.py
start_service agent "$ROOT_DIR/services/cartridges" "$PYTHON_BIN" orchestrator.py

printf 'starting ui\n'
(
  cd "$ROOT_DIR/services/multiverse-ui"
  env NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_CHRONOS_WS_URL=ws://127.0.0.1:8000/ws/telemetry npm run dev
) >"$LOG_DIR/ui.log" 2>&1 &
PIDS+=("$!")

wait_http kernel http://127.0.0.1:8000/health
wait_http z3 http://127.0.0.1:8001/health
wait_http agent http://127.0.0.1:8002/docs
wait_http ui "$UI_URL"

printf '\nCHRONOS-ZERO stage is ready (offline replay enabled).\n'
printf 'Open %s\n' "$UI_URL"
printf 'Pilot keys: 1/2/3 cartridge | Space run | B bypass | R reset | S split comparison\n'
printf 'Logs: %s\n' "$LOG_DIR"

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$UI_URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "$UI_URL" >/dev/null 2>&1 || true
fi

while true; do
  for pid in "${PIDS[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      printf 'a stage service exited; inspect %s\n' "$LOG_DIR" >&2
      exit 1
    fi
  done
  sleep 1
done
