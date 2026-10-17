PY ?= python
DEPLOY_FILE ?= deploy/production/docker-compose.yml
DEPLOY_ENV ?= deploy/production/.env

.PHONY: test test-z3 test-cow test-contracts bench up down deploy-config db-psql seed ui-install record-replay demo-verify

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

# The persistent production deployment is the only supported Compose entry point.
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
