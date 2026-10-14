# CHRONOS-ZERO

Speculative-execution and Z3 verification kernel for autonomous AI agents. Tool calls are applied to a shadow savepoint, checked against domain invariants, then committed or rolled back. See [AGENTS.md](AGENTS.md) and [hackathon](hackathon) for the full plan.

## Status

Early scaffold (hours 0–2 of the plan):

- `contracts/` — JSON Schemas for the four wire contracts
- `services/z3-verifier/prover_core.py` — healthcare invariants with tracked assertions, 50 ms solver cap, fail-closed on malformed state
- `services/kernel-proxy/cow_engine.py` — SQLite SAVEPOINT shadow branches (fork / resolve)
- `tests/` — invariant and CoW tests

Not yet built: HTTP interceptor, WebSocket telemetry, cartridges, NL-to-Z3 compiler, UI.

## Run tests

```bash
pip install z3-solver pytest
make test
```

(`make` is optional; `python -m pytest tests -q` works directly.)
