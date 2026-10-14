# CHRONOS-ZERO

Speculative-execution and Z3 verification kernel for autonomous AI agents. Tool calls are applied to a shadow savepoint, checked against domain invariants, then committed or rolled back. See [hackathon](hackathon) for the full plan, [AGENTS.md](AGENTS.md) for the team rules, and [ENGINEERS.md](ENGINEERS.md) for the per-engineer breakdown.

## Storage

Cartridge state lives in **PostgreSQL 16** (one database per cartridge), run locally in Docker with its data in RAM. Shadow branches are Postgres transactions with a named `SAVEPOINT`, committed on `SAT` and rolled back on `UNSAT`. See AGENTS.md §4.1.

## Status

Stage-ready local stack:

- `contracts/` — JSON Schemas for the four wire contracts
- `services/z3-verifier/` — all three cartridge invariant registries, tracked assertions, 50 ms solver cap, fail-closed Contract 3 receipts, and AST-sandboxed policy compilation
- `services/kernel-proxy/` — pool-pinned PostgreSQL CoW branches, audit-chain gating, interceptor HTTP API, and telemetry WebSocket
- `services/cartridges/` — PostgreSQL seeding, deterministic offline replay, and one-turn self-healing orchestration
- `services/multiverse-ui/` — live Multiverse DAG, proof inspector, split comparison, and policy studio
- `docker-compose.yml`, `infra/postgres/` — RAM-backed PostgreSQL 16 with the three cartridge databases
- `run_stage_demo.sh` — one-command offline stage launcher with port cleanup and health polling
- `tests/` — contract, invariant, CoW, latency, self-healing, and offline live-stack gates

The tracked stage gate is `P50 < 3.5ms` and `P99 < 8.0ms` for 500 sequential CoW + Z3 cycles.

## Run

```bash
cp .env.example .env
make db-up
make seed
make test
make bench

# Or, after PostgreSQL is running and seeded:
./run_stage_demo.sh
```

Requires Docker for PostgreSQL. `make` is optional: `docker compose up -d --wait postgres` and `python -m pytest tests -q` work directly.
