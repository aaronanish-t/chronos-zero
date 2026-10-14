PY ?= python

.PHONY: test test-z3 test-cow db-up db-down db-reset db-psql seed

test:
	$(PY) -m pytest tests -q

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
