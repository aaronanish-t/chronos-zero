# CHRONOS-ZERO

Speculative-execution and Z3 verification kernel for autonomous AI agents. Tool calls are applied to a shadow savepoint, checked against domain invariants, then committed or rolled back. See [hackathon](hackathon) for the full plan, [AGENTS.md](AGENTS.md) for the team rules, and [ENGINEERS.md](ENGINEERS.md) for the per-engineer breakdown.

## Storage

Cartridge state lives in **PostgreSQL 16** (one database per cartridge), run locally in Docker with its data in RAM. Shadow branches are Postgres transactions with a named `SAVEPOINT`, committed on `SAT` and rolled back on `UNSAT`. See AGENTS.md §4.1.

## Status

Early scaffold (hours 0–2 of the plan):

- `contracts/` — JSON Schemas for the four wire contracts
- `services/z3-verifier/prover_core.py` — healthcare invariants with tracked assertions, 50 ms solver cap, fail-closed on malformed state
- `services/kernel-proxy/cow_engine.py` — first CoW engine (still SQLite; being ported to PostgreSQL on `feat/e1-kernel`)
- `docker-compose.yml`, `infra/postgres/` — RAM-backed PostgreSQL 16 with the three cartridge databases
- `tests/` — invariant and CoW tests

Not yet built: HTTP interceptor, WebSocket telemetry, cartridges, NL-to-Z3 compiler, UI.

## Run

```bash
cp .env.example .env
make db-up
make test
```

Requires Docker for PostgreSQL. `make` is optional: `docker compose up -d --wait postgres` and `python -m pytest tests -q` work directly.
