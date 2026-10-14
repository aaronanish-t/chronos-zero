PY ?= python

.PHONY: test test-z3 test-cow bench db-up db-down db-reset db-psql seed

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
