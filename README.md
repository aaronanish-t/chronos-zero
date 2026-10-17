# CHRONOS-ZERO

Speculative-execution and Z3 verification kernel for autonomous AI agents. Tool calls are applied to a shadow savepoint, checked against domain invariants, then committed or rolled back. See [hackathon](hackathon) for the full plan, [AGENTS.md](AGENTS.md) for the team rules, and [ENGINEERS.md](ENGINEERS.md) for the per-engineer breakdown.

## Storage

Cartridge state lives in **persistent PostgreSQL 16** (one database per cartridge). Shadow branches are Postgres transactions with a named `SAVEPOINT`, committed on `SAT` and rolled back on `UNSAT`. See [production deployment](docs/production.md).

## Status

Production deployment baseline:

- `contracts/` — JSON Schemas for the four wire contracts
- `services/z3-verifier/` — all three cartridge invariant registries, tracked assertions, 50 ms solver cap, fail-closed Contract 3 receipts, and AST-sandboxed policy compilation
- `services/kernel-proxy/` — pool-pinned PostgreSQL CoW branches, audit-chain gating, interceptor HTTP API, and telemetry WebSocket
- `services/cartridges/` — PostgreSQL seeding, deterministic offline replay, and one-turn self-healing orchestration
- `services/multiverse-ui/` — live Multiverse DAG, proof inspector, split comparison, and policy studio
- `deploy/production/` — persistent PostgreSQL 16, private service network, non-root containers, and Caddy TLS gateway
- `tests/` — contract, invariant, CoW, latency, self-healing, and offline live-stack gates

The tracked stage gate is `P50 < 3.5ms` and `P99 < 8.0ms` for 500 sequential CoW + Z3 cycles.

## Deploy

```bash
cp deploy/production/.env.example deploy/production/.env
# Replace every placeholder with real values, then protect the file.
chmod 600 deploy/production/.env
make deploy-config
make up
make seed
make test
make bench
```

`make up` is the primary working deployment path. It validates the protected
production environment, builds the images, and starts the persistent stack.
See [docs/production.md](docs/production.md) for TLS, backups, upgrades, and
operational requirements.
