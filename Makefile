PY ?= python
DEPLOY_FILE ?= deploy/production/docker-compose.yml
DEPLOY_ENV ?= deploy/production/.env

.PHONY: test test-z3 test-cow test-contracts bench up down deploy-config db-psql seed ui-install record-replay demo-verify \n	demo-up demo-down demo-reset demo-seed stage

test:
	$(PY) -m pytest tests -q --ignore=tests/test_cow_latency.py

bench:
	$(PY) -m pytest tests/test_cow_latency.py -s -q

test-z3:
	$(PY) -m pytest tests/test_z3_invariants.py -q

test-cow:
	$(PY) -m pytest tests/test_cow_engine.py -q

test-contracts:
	$(PY) -m pytest tests/test_contract_parity.py -q

# The persistent production deployment is the only supported deployment. The offline demo
# profile below is for the stage laptop only and never touches production state.
up:
	./deploy/production/validate.sh "$(DEPLOY_ENV)"
	docker compose --env-file "$(DEPLOY_ENV)" -f "$(DEPLOY_FILE)" up -d --build

down:
	docker compose --env-file "$(DEPLOY_ENV)" -f "$(DEPLOY_FILE)" down

deploy-config:
	./deploy/production/validate.sh "$(DEPLOY_ENV)"

db-psql:
	docker compose --env-file "$(DEPLOY_ENV)" -f "$(DEPLOY_FILE)" exec postgres psql -U chronos_app -d chronos_cloud_devops

# Rebuild all three cartridge databases as an explicit operational action.
seed:
	docker compose --env-file "$(DEPLOY_ENV)" -f "$(DEPLOY_FILE)" run --rm agent python services/cartridges/seed_databases.py

ui-install:
	cd services/multiverse-ui && npm ci

record-replay: seed
	RECORD_REPLAY=1 $(PY) services/cartridges/replay_middleware.py

demo-verify:
	OFFLINE_MODE=1 $(PY) -m pytest tests/test_e2e_live_stack.py tests/test_contract_parity.py -v

# --- Offline demo profile (stage laptop, Wi-Fi off) -------------------------------------------
# RAM-backed Postgres on 127.0.0.1, development credentials, OFFLINE_MODE=1. Not a deployment.
# Stage order: make demo-up && make demo-seed && make stage
DEMO_FILE ?= deploy/demo/docker-compose.yml

demo-up:
	docker compose -f "$(DEMO_FILE)" up -d --wait postgres audit-db

demo-down:
	docker compose -f "$(DEMO_FILE)" down

# tmpfs storage: recreating the container wipes every demo cartridge database.
demo-reset: demo-down demo-up

demo-seed:
	CHRONOS_ENV=development $(PY) services/cartridges/seed_databases.py

# Kernel :8000, Z3 :8001, agent :8002, UI :3000 in one terminal; Ctrl+C stops them.
# `python deploy/demo/stage.py --offset 100` if those ports are taken.
stage:
	$(PY) deploy/demo/stage.py
