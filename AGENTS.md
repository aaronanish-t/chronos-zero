# CHRONOS-ZERO System Constitution & Agent Operating Manual

## 1. System Identity & Core Mission
You are operating inside **CHRONOS-ZERO**: *The Speculative Execution & Formal Verification Kernel for High-Stakes Autonomous AI*.
* **Core Mechanism**: Intercept agent tool calls (`< 1.5ms`) -> Fork a PostgreSQL transaction-scoped Copy-on-Write (CoW) shadow branch (`SAVEPOINT`, `< 1.5ms`) -> Verify post-mutation state delta via Microsoft Z3 SMT Theorem Prover (`< 2.5ms`) -> Commit (`SAT`) or Rewind + Self-Heal (`UNSAT`).
* **Golden Rule**: Never substitute deterministic Z3 mathematical proofs or real PostgreSQL `SAVEPOINT`/transaction rollbacks with probabilistic LLM prompts or simulated delays. Every verification must produce a real SMT-LIB2 dump, a tracked `UnsatCore`, and a SHA-256 receipt.
* **Storage Engine**: PostgreSQL 16 replaces SQLite for all cartridge state. Where the original plan (`hackathon`) mentions SQLite, `/dev/shm`, `PRAGMA` or WAL, this file takes precedence.

---

## 2. Worktree Ownership & Directory Write-Locks
This repository is developed in parallel by 4 engineers across 4 isolated Git branches. **NEVER modify files outside your active branch's owned directory** unless explicitly executing a Merge Gate sync.

| Branch / Worktree | Agent Persona | Owned Paths (READ/WRITE) | Read-Only Paths |
| :--- | :--- | :--- | :--- |
| `feat/e1-kernel` | `@kernel-agent` | `services/kernel-proxy/`, `contracts/`, `Makefile`, `deploy/production/` | `services/z3-verifier/`, `services/cartridges/`, `services/multiverse-ui/` |
| `feat/e2-z3-prover` | `@z3-formal-agent` | `services/z3-verifier/`, `tests/test_z3_*` | `contracts/`, `services/kernel-proxy/` |
| `feat/e3-cartridges` | `@cartridge-agent` | `services/cartridges/`, `tests/test_e2e_*` | `contracts/`, `services/kernel-proxy/`, `services/z3-verifier/`, `infra/postgres/` |
| `feat/e4-multiverse-ui` | `@multiverse-ui-agent` | `services/multiverse-ui/` | `contracts/` |

---

## 3. Immutable Data Contracts (Strict Schema Lock)
All inter-service communication MUST validate against Pydantic v2 (Python) and Zod/TypeScript interfaces derived from `/contracts/`. **Field renaming is strictly forbidden.** The move to PostgreSQL does not change any contract.

1. **Contract 1 (`POST http://localhost:8000/v1/kernel/execute`)**:
   * Required root keys: `trace_id` (`str`), `timestamp_ns` (`int`), `cartridge_id` (`Literal["HEALTHCARE_FHIR", "FINTECH_ESCROW", "CLOUD_DEVOPS"]`), `chronos_mode` (`Literal["ACTIVE", "BYPASS"]`), `agent_id` (`str`), `tool_call` (`dict` with `tool_name`, `target_resource`, `arguments`).
2. **Contract 2 (`POST http://localhost:8001/v1/z3/verify`)**:
   * Required root keys: `trace_id` (`str`), `shadow_branch_id` (`str`), `cartridge_id` (`str`), `cow_fork_latency_ms` (`float`), `state_pre` (`dict`), `state_post_shadow` (`dict`).
3. **Contract 3 (Z3 Response & Kernel Return)**:
   * Required root keys: `trace_id` (`str`), `shadow_branch_id` (`str`), `status` (`Literal["SAT", "UNSAT"]`), `proof_latency_ms` (`float`), `violated_invariants` (`list[ViolatedInvariant]`), `smt2_dump` (`str`), `sha256_proof_hash` (`str`).
4. **Contract 4 (`WS ws://localhost:8000/ws/telemetry`)**:
   * Required root keys: `event_type` (`Literal["BRANCH_EVALUATED", "BYPASS_CORRUPTED", "POLICY_COMPILED", "DEMO_RESET"]`), `trace_id` (`str`), `cartridge_id` (`str`), `node` (`dict` with `id`, `parent_id`, `branch_type`, `action_label`, `total_latency_ms`, `z3_verdict`, `violated_rules`, `financial_loss_prevented_usd`, `clinical_hazard_prevented`).

---

## 4. Non-Negotiable Engineering Invariants

### 4.1 Kernel & CoW Engine (`services/kernel-proxy/`)
* **Storage**: All cartridge state lives in PostgreSQL 16, one database per cartridge: `chronos_healthcare_fhir`, `chronos_fintech_escrow`, `chronos_cloud_devops` (i.e. `chronos_{cartridge_id.lower()}`). Every service reads the server address from `CHRONOS_PG_DSN` (default `postgresql://chronos_kernel:chronos_kernel@127.0.0.1:5432`) and appends the database name. Use `127.0.0.1`, not `localhost`, to avoid IPv6 fallback delays.
* **Production Deployment**: `make up` runs `deploy/production/docker-compose.yml` with persistent PostgreSQL volumes, normal durability, private service networking, non-root application containers, and Caddy as the only public gateway. Never use disposable database settings against a real deployment.
* **Audit Chain Storage**: The SHA-256 audit chain is the one durable store. It lives in a separate volume-backed Postgres (`audit-db`, `CHRONOS_AUDIT_DSN`, default `postgresql://chronos_kernel:chronos_kernel@127.0.0.1:5433/chronos_audit`) with normal fsync, in an append-only `audit_chain` table (UPDATE/DELETE/TRUNCATE blocked by trigger). Each entry hashes the Contract 1 `timestamp_ns`. A branch may commit only after its audit entry is written.
* **Driver**: `psycopg` 3 (async) with one `psycopg_pool.AsyncConnectionPool` per cartridge database. No synchronous database calls inside async FastAPI routes.
* **Connection Pinning**: PostgreSQL transactions and `SAVEPOINT`s are connection-scoped. A shadow branch MUST take a dedicated connection from the pool, run inside one `REPEATABLE READ` transaction, issue `SAVEPOINT cow_branch_X`, and pin that connection in `self._pinned[shadow_branch_id]` until resolved:
  * `SAT` → `RELEASE SAVEPOINT cow_branch_X` then `COMMIT`.
  * `UNSAT`, verifier error, or timeout → `ROLLBACK` (the transaction contains only this branch).
  * The connection goes back to the pool **only after** `COMMIT`/`ROLLBACK` completes. Never return a connection to the pool mid-transaction.
* **Bounded Locking**: Every pooled kernel connection runs with `lock_timeout = '2s'` and `statement_timeout = '2s'` (set once in the pool's `configure` callback, not per branch, to save round trips) so a stuck branch cannot stall others. A serialization failure (`SQLSTATE 40001`) or lock timeout on commit is treated as a rejected branch: roll back and report it, never retry silently.
* **Least Privilege**: Services connect as role `chronos_kernel` (owner of the cartridge databases, not a superuser). Agent-supplied SQL (e.g. `CLOUD_DEVOPS` migrations) MUST be rejected if it contains transaction or session control (`BEGIN`, `START TRANSACTION`, `COMMIT`, `END`, `ROLLBACK`, `SAVEPOINT`, `RELEASE`, `PREPARE TRANSACTION`, `SET`/`RESET` other than `SET LOCAL`, `DISCARD`), or server-level statements (`COPY`, `DO`, `CREATE/DROP DATABASE`, `ALTER SYSTEM`, `VACUUM`, `LISTEN`/`NOTIFY`). These would escape or end the shadow branch.
* **Timing Precision**: Use `time.perf_counter_ns()` divided by `1_000_000.0` for all latency telemetry. Never use `time.time()` for sub-millisecond measurement.

### 4.2 Z3 Formal Verifier (`services/z3-verifier/`)
* **Tracked Assertions Only**: Never use bare `solver.add()` for business/safety invariants. Always use `solver.assert_and_track(boolean_expr, "INV_ID_NAME")` so `solver.unsat_core()` deterministically extracts every violated rule ID on `UNSAT`.
* **Hard Solver Timeout**: Every `Solver()` instance MUST set `s.set("timeout", 50)` (50 milliseconds) to prevent undecidable non-linear arithmetic from hanging the kernel.
* **Explicit Type Casting**: Cast all incoming JSON floats to `z3.RealVal(val)` and ints to `z3.IntVal(val)` to avoid Python float-precision solver mismatches.

### 4.3 Domain Cartridges & Orchestrator (`services/cartridges/`)
* **Seeding**: `seed_databases.py` connects via `CHRONOS_PG_DSN`, rebuilds each cartridge database's tables, and bulk-loads data with `COPY` (not row-by-row `INSERT`) so all three reset in `< 0.5s`. Mock "production" SQL is real PostgreSQL, so demo statements such as `DROP TABLE users CASCADE` run natively.
* **1-Turn Self-Healing**: When `chronos_mode == "ACTIVE"` and the kernel returns `status == "UNSAT"`, the agent orchestrator MUST automatically append the `violated_invariants` and `remediation_hint` into the agent message history and trigger a corrective tool call without human intervention.
* **Offline Determinism**: Wrap all external LLM calls (Opus 5.5 / GPT 6 Astra) with `DeterministicReplayMiddleware` backed by `/services/cartridges/replay_cache.sqlite`. If `OFFLINE_MODE=1` or network latency exceeds `1500ms`, serve the cached tool-call trajectory immediately. (The replay cache is a local file of recorded LLM responses, not cartridge state, so it stays SQLite.)

### 4.4 Multiverse UI (`services/multiverse-ui/`)
* **Zero Polling**: All DAG updates and telemetry counters must update reactively via the single WebSocket stream (`ws://localhost:8000/ws/telemetry`).
* **Visual Semantics**:
  * `SHADOW_REJECTED` (`UNSAT`): Crimson (`#EF4444`), dashed animated edge, branches downward-right (`+120px Y`), displays `UnsatCore` badge.
  * `COMMITTED_SAFE` (`SAT`): Emerald (`#10B981`), solid edge, continues on primary horizontal axis (`0px Y`), displays SHA-256 receipt badge.
  * `BYPASS_CORRUPTED`: Flashing crimson banner with live capital/data loss counter.

---

## 5. Standard Commands & Verification Gates
Run these commands from the repository root before opening any PR or calling a Merge Gate:

```bash
# 0. Validate and start the persistent production deployment
make deploy-config
make up

# 1. Seed all 3 cartridge databases (< 0.5s)
make seed

# 2. Validate JSON Schema parity across Python Pydantic & TypeScript interfaces
make test-contracts

# 3. Run Z3 formal invariant unit tests (SAT, UNSAT, Boundary, Fuzz)
pytest tests/test_z3_invariants.py -v

# 4. Run 500-iteration CoW + Z3 latency benchmark (Gate: P50 < 3.5ms, P99 < 8.0ms)
pytest tests/test_cow_latency.py -s

# 5. Run End-to-End 3-Cartridge Self-Healing Test
pytest tests/test_e2e_self_healing.py -v
```

Tests that need PostgreSQL may `pytest.skip` only when `CHRONOS_PG_DSN` is unreachable. Merge Gate runs MUST have the database up, so nothing is skipped.

---

## 6. Dual-Model Prompting Protocol (Opus 5.5 + GPT 6 Astra)
* **Builder Step (Claude Opus 5.5)**: Use for implementation. Always include `@AGENTS.md` and the relevant skill from `@SKILLS.md` in context.
* **Auditor Step (GPT 6 Astra)**: Before committing on any branch, run:
  > *"Act as `@redteam-auditor`. Inspect `git diff` against `@AGENTS.md` Section 3 (Contracts) and Section 4 (Invariants). Flag any blocking I/O, untracked Z3 assertions, PostgreSQL connections returned to the pool mid-transaction, unbounded lock waits, agent SQL that can escape the shadow branch, or schema key mismatches."*
