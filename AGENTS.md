# AGENTS.md — Chronos-Zero

Instructions for AI coding agents (Claude Code, Codex, Cursor, etc.) working in this repo.

## What this project is

Chronos-Zero is a transparent interception kernel that sits between an autonomous AI agent and stateful systems (SQL, REST, FHIR, payment ledgers). Every mutating tool call is:

1. Intercepted at the gateway (`services/kernel-proxy/interceptor.py`).
2. Applied speculatively inside a SQLite SAVEPOINT (a shadow branch).
3. Diffed into `state_pre` / `state_post_shadow`.
4. Checked by a Z3 SMT prover against domain invariants.
5. Either committed (`RELEASE SAVEPOINT`, status `SAT`) or rolled back (`ROLLBACK TO SAVEPOINT`, status `UNSAT`), with the unsat core returned to the agent as a remediation hint.

Three domain cartridges ship with it: `HEALTHCARE_FHIR`, `FINTECH_ESCROW`, `CLOUD_DEVOPS`.

## Repo layout

```
chronos-zero/
├── contracts/            # JSON Schemas — the source of truth for all payloads
├── services/
│   ├── kernel-proxy/     # FastAPI interceptor, CoW engine, saga ledger, audit chain
│   ├── z3-verifier/      # Z3 prover service, NL-to-Z3 compiler, invariants/
│   ├── cartridges/       # Mock servers, seed script, LangGraph orchestrator
│   └── multiverse-ui/    # Next.js 15 + ReactFlow control plane
└── tests/                # pytest: latency, invariants, end-to-end self-healing
```

Ports: kernel-proxy `:8000`, z3-verifier `:8001`.

## Hard rules

1. **Contracts are frozen.** The four files in `contracts/` (`intercept_payload`, `state_diff`, `z3_verdict`, `ws_telemetry`) define the wire format. Do not rename, remove, or retype a field without updating every service and the schema together, and flag it to the user. Adding optional fields is allowed.
2. **Never write to production state before the verdict.** In `ACTIVE` mode, all mutations run inside a savepoint first. Only `resolve_branch(commit=True)` may release it.
3. **`BYPASS` mode is deliberately unsafe.** It skips savepoints and Z3 and emits `BYPASS_CORRUPTED`. Do not "fix" it into a safe path. It exists so the demo can show the damage without Chronos.
4. **Use tracked assertions for every invariant.** Use `solver.assert_and_track(expr, RULE_ID)` so `solver.unsat_core()` can name the violated rules. A bare `s.add()` for an invariant is a bug.
5. **Every invariant needs four tests:** `true_positive` (SAT), `true_negative` (UNSAT), `boundary_exact` (e.g. `eGFR == 30.0`), and `malformed_state_handling`.
6. **Solver timeout is 50 ms hard cap.** `s.set("timeout", 50)` must stay on every solver. Treat a timeout as a failure, never as SAT.
7. **No runtime internet dependency.** The stack must run offline on one laptop. Any LLM call must go through the deterministic replay cache (`DeterministicReplayMiddleware`) when offline.
8. **Latency targets:** Z3 + fork in the low single-digit ms. Benchmark P50 < 3.5 ms and P99 < 8.0 ms (`tests/test_cow_latency.py`). Do not add per-call I/O (logging to disk, network) on the hot path.

## Platform notes

- The original spec assumes Linux `/dev/shm` for RAM-backed SQLite. This repo may be developed on Windows. Put the DB directory in an env var (e.g. `CHRONOS_DB_DIR`) with a default per platform: `/dev/shm` on Linux, a temp dir on Windows. Do not hard-code `/dev/shm`.
- Use `time.perf_counter_ns()` for latency measurement, not `time.time()`.

## Ownership (from the 4-engineer plan)

| Area | Owner |
|---|---|
| `services/kernel-proxy/`, `contracts/`, Docker/Makefile | E1 |
| `services/z3-verifier/`, `tests/test_z3_*` | E2 |
| `services/cartridges/` | E3 |
| `services/multiverse-ui/`, pitch assets | E4 |

Changes outside your area: open a note or ask first, don't silently edit.

## Commands

Expected `Makefile` targets (create them if missing):

- `make up` — start all services locally
- `make seed` — reset the three SQLite DBs to deterministic initial state (< 0.5 s)
- `make test` — run pytest
- `make bench` — 500-call latency benchmark

## Before you finish a change

- Run `make test` (or the relevant subset) and report the actual output.
- If you touched a contract, confirm all consumers still validate against the schema.
- If you touched an invariant, confirm its four test vectors still exist and pass.
- Don't claim latency numbers you didn't measure.

## Workflow

- Read `SKILL.md` in `skills/chronos-zero/` before adding an invariant, a cartridge, or a contract change.
- Keep changes small and in the owning directory. Prefer adding a file over editing a shared one.
