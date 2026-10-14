PY ?= python

.PHONY: test test-z3 test-cow test-contracts bench db-up db-down db-reset db-psql seed \n	stage kernel z3 agent ui ui-install record-replay demo-verify

# The latency benchmark has its own target (it is slower and hardware-dependent).
test:
	$(PY) -m pytest tests -q --ignore=tests/test_cow_latency.py

# 500 sequential + 50 concurrent CoW + Z3 cycles; gate P50 < 3.5ms, P99 < 8.0ms;
# writes contracts/benchmark_report.json for the UI header.
bench:
	$(PY) -m pytest tests/test_cow_latency.py -s -q

test-z3:
	$(PY) -m pytest tests/test_z3_invariants.py -q

test-cow:
	$(PY) -m pytest tests/test_cow_engine.py -q

# RAM-backed PostgreSQL 16 for all cartridge databases (see docker-compose.yml).
db-up:
	docker compose up -d --wait postgres audit-db

db-down:
	docker compose down

# tmpfs storage: recreating the container wipes every cartridge database.
# The audit chain lives on the chronos-audit-data volume and is kept.
db-reset: db-down db-up

db-psql:
	docker compose exec postgres psql -U chronos_kernel -d chronos_cloud_devops

# Rebuild all 3 cartridge databases (E3's seeder; reads CHRONOS_PG_DSN).
seed:
	$(PY) services/cartridges/seed_databases.py

# Contract parity: JSON Schema == Pydantic == TypeScript, and live verdicts validate (AGENTS.md section 5).
test-contracts:
	$(PY) -m pytest tests/test_contract_parity.py -q

# --- Stage -----------------------------------------------------------------------------------
# Everything binds 127.0.0.1 and runs with OFFLINE_MODE=1 (no LLM calls, replay cache available).
# Order on the demo laptop: make db-up && make seed && make stage

# All four services in one terminal; Ctrl+C stops them.
stage:
	$(PY) infra/stage.py

# Or one per terminal / tmux pane:
kernel:
	cd services/kernel-proxy && OFFLINE_MODE=1 $(PY) main.py

z3:
	cd services/z3-verifier && OFFLINE_MODE=1 $(PY) server.py

agent:
	cd services/cartridges && OFFLINE_MODE=1 $(PY) orchestrator.py

ui:
	cd services/multiverse-ui && NEXT_TELEMETRY_DISABLED=1 npm run dev

# Needs network once (before the venue); afterwards the UI runs offline.
ui-install:
	cd services/multiverse-ui && npm ci

# Re-record services/cartridges/replay_cache.sqlite after changing a scenario (needs a seeded DB).
record-replay: seed
	RECORD_REPLAY=1 $(PY) services/cartridges/replay_middleware.py

# Airplane-mode gate (@skill:lock-offline-replay): real kernel + Z3 + agent + Postgres in-process,
# all 3 cartridges, judge policies, BYPASS + reset, split comparison, offline replay; fails on any
# non-loopback connection. Run with Wi-Fi off before the pitch.
demo-verify:
	OFFLINE_MODE=1 $(PY) -m pytest tests/test_e2e_live_stack.py tests/test_contract_parity.py -v
