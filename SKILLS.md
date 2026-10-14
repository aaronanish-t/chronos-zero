# CHRONOS-ZERO Reusable Agent Playbooks

Invoke these skills explicitly by name (e.g., `Execute @skill:compile-z3-invariant for FINTECH_ESCROW`) so coding agents generate standardized, drop-in compliant code across all four worktrees.

## Skill Registry Overview

| Skill ID | Owner | Trigger Use Case | Output Artifact | Verification Gate |
| :--- | :--- | :--- | :--- | :--- |
| `@skill:scaffold-cow-savepoint` | E1 | Adding/updating stateful CoW mutation handlers in `kernel-proxy` | Pool-pinned PostgreSQL transaction + `SAVEPOINT` branch manager | `P99 < 2.0ms` fork/rollback |
| `@skill:compile-z3-invariant` | E2 | Writing new formal rules or building the NL-to-Z3 compiler | Tracked Z3 solver function + 4-vector `pytest` suite | 100% pass on `SAT`/`UNSAT`/Boundary |
| `@skill:build-domain-cartridge` | E3 | Creating a vertical scenario (seed DB + attack + self-healing retry) | Seed SQL + adversarial prompt + self-healing handler | E2E self-healing in 1 retry turn |
| `@skill:wire-multiverse-node` | E4 | Adding custom ReactFlow nodes, drawers, or telemetry animations | TypeScript ReactFlow component + WebSocket reducer | 60fps render with 0 hydration errors |
| `@skill:lock-offline-replay` | E3/E1 | Recording live LLM agent trajectories for zero-Wi-Fi stage mode | Populated `replay_cache.sqlite` + Airplane Mode test | 100% pass with network disabled |
| `@skill:redteam-merge-audit` | All | Pre-merge verification at Merge Gates 1 through 6 | Schema & race-condition audit report | 0 contract violations |

---

## `@skill:scaffold-cow-savepoint`
**Objective**: Implement a sub-2ms transactional shadow branch on PostgreSQL 16 using a pool-pinned connection, one `REPEATABLE READ` transaction, and a named `SAVEPOINT`.

### Execution Pattern
1. At startup, open one `psycopg_pool.AsyncConnectionPool` per cartridge database (`{CHRONOS_PG_DSN}/chronos_{cartridge_id.lower()}`), configured for `REPEATABLE READ` and `dict_row`.
2. Take a dedicated connection with `await pool.getconn()`. The first statement opens the transaction; bound it with `SET LOCAL lock_timeout = '2s'` and `SET LOCAL statement_timeout = '2s'`.
3. Snapshot `state_pre` with a fast read query.
4. Issue `SAVEPOINT {shadow_branch_id}`.
5. Execute the parameterized SQL mutation representing `tool_call`.
6. Snapshot `state_post_shadow` inside the uncommitted transaction.
7. Pin the live connection in `self._pinned[shadow_branch_id]` until E2's Z3 service responds.
8. On `SAT`: `RELEASE SAVEPOINT {shadow_branch_id}` then `COMMIT`. On `UNSAT` (or any verifier failure): `ROLLBACK`. Only then return the connection with `await pool.putconn(conn)`.
9. A `COMMIT` that fails (e.g. `SQLSTATE 40001` serialization failure because a concurrent branch committed first) is a rejected branch: roll back and surface it, never retry silently.

### Reference Template
```python
import time
import uuid
from typing import Any, Awaitable, Callable, Optional

from psycopg import AsyncConnection, IsolationLevel
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

StateReader = Callable[[AsyncConnection, dict[str, Any]], Awaitable[dict[str, Any]]]
Mutation = Callable[[AsyncConnection, dict[str, Any]], Awaitable[Optional[dict[str, Any]]]]


async def _configure(conn: AsyncConnection) -> None:
    await conn.set_isolation_level(IsolationLevel.REPEATABLE_READ)


class CoWBranchEngine:
    def __init__(self, dsn_base: str, cartridge_ids: list[str]):
        self._pools = {
            cid: AsyncConnectionPool(
                f"{dsn_base}/chronos_{cid.lower()}",
                min_size=2,
                max_size=16,
                open=False,
                kwargs={"row_factory": dict_row},
                configure=_configure,
            )
            for cid in cartridge_ids
        }
        self._pinned: dict[str, tuple[str, AsyncConnection]] = {}

    async def open(self) -> None:
        for pool in self._pools.values():
            await pool.open(wait=True)

    async def close(self) -> None:
        for branch_id in list(self._pinned):
            await self.resolve(branch_id, commit=False)
        for pool in self._pools.values():
            await pool.close()

    async def fork_and_mutate(
        self, cartridge_id: str, state_reader_fn: StateReader, mutation_fn: Mutation, tool_call: dict[str, Any]
    ) -> tuple[str, dict, dict, float]:
        t0 = time.perf_counter_ns()
        branch_id = f"cow_branch_{uuid.uuid4().hex[:8]}"
        pool = self._pools[cartridge_id]
        conn = await pool.getconn()
        try:
            # psycopg opens the REPEATABLE READ transaction on the first statement.
            await conn.execute("SET LOCAL lock_timeout = '2s'")
            await conn.execute("SET LOCAL statement_timeout = '2s'")
            state_pre = await state_reader_fn(conn, tool_call)
            await conn.execute(f"SAVEPOINT {branch_id}")
            overlays = await mutation_fn(conn, tool_call)
            state_post = await state_reader_fn(conn, tool_call)
            if overlays:
                state_post.update(overlays)
        except BaseException:
            await conn.rollback()
            await pool.putconn(conn)
            raise

        self._pinned[branch_id] = (cartridge_id, conn)
        latency_ms = round((time.perf_counter_ns() - t0) / 1_000_000.0, 3)
        return branch_id, state_pre, state_post, latency_ms

    async def resolve(self, branch_id: str, commit: bool) -> float:
        t0 = time.perf_counter_ns()
        cartridge_id, conn = self._pinned.pop(branch_id)
        try:
            if commit:
                await conn.execute(f"RELEASE SAVEPOINT {branch_id}")
                await conn.commit()
            else:
                await conn.rollback()
        except BaseException:
            await conn.rollback()  # e.g. 40001 on COMMIT: the branch is rejected
            raise
        finally:
            # Returned only after COMMIT/ROLLBACK, never mid-transaction.
            await self._pools[cartridge_id].putconn(conn)
        return round((time.perf_counter_ns() - t0) / 1_000_000.0, 3)
```

---

## `@skill:compile-z3-invariant`
**Objective**: Create a deterministic Z3 verification module or compile natural-language rules into tracked SMT assertions with human/LLM remediation hints.

### Execution Pattern
1. Define a rule metadata registry mapping `rule_id -> (formal_str, remediation_template)`.
2. Declare typed Z3 variables (`Real`, `Int`, `Bool`) matching the exact keys of `state_pre` and `state_post_shadow`.
3. Bind the observed values using `s.add(var == RealVal(state_post["key"]))`.
4. Add every safety or compliance policy via `s.assert_and_track(expr, rule_id)`.
5. Extract `s.unsat_core()` when `s.check() == unsat`, populate `ViolatedInvariant` objects, and compute `hashlib.sha256(s.to_smt2().encode()).hexdigest()`.
6. **Mandatory Test Generation**: Immediately generate 4 `pytest` cases (`test_sat_valid`, `test_unsat_violation`, `test_exact_boundary`, `test_multi_violation`).

### Reference Template
```python
import hashlib
import time
from z3 import Solver, Real, Int, Bool, RealVal, IntVal, BoolVal, Implies, And, Not, unsat

RULE_REGISTRY = {
    "INV_FIN_01_ESCROW_CAP": {
        "formal": "daily_escrow_spent_usd + transfer_amount_usd <= daily_escrow_limit_usd",
        "remediation": "Requested wire exceeds remaining daily escrow limit. Reduce transfer_amount_usd to <= {remaining_cap} USD or split into milestone tranches."
    },
    "INV_FIN_02_SLA_ATTESTATION": {
        "formal": "Implies(transfer_amount_usd > 0, And(vendor_latency_ms <= 200.0, iban_allowlisted == True))",
        "remediation": "Counterparty failed zkTLS SLA check (latency {vendor_latency_ms}ms > 200ms) or IBAN is not on treasury allowlist. Route payout to verified backup vendor."
    }
}

def evaluate_fintech_invariants(state_pre: dict, state_post: dict) -> dict:
    t0 = time.perf_counter_ns()
    s = Solver()
    s.set("timeout", 50)

    spent = Real("daily_escrow_spent_usd")
    transfer = Real("transfer_amount_usd")
    limit = Real("daily_escrow_limit_usd")
    latency = Real("vendor_latency_ms")
    allowlisted = Bool("iban_allowlisted")

    s.add(spent == RealVal(state_pre["daily_escrow_spent_usd"]))
    s.add(transfer == RealVal(state_post["last_transfer_amount_usd"]))
    s.add(limit == RealVal(state_pre["daily_escrow_limit_usd"]))
    s.add(latency == RealVal(state_post["vendor_latency_ms"]))
    s.add(allowlisted == BoolVal(state_post["iban_allowlisted"]))

    s.assert_and_track(spent + transfer <= limit, "INV_FIN_01_ESCROW_CAP")
    s.assert_and_track(
        Implies(transfer > RealVal(0), And(latency <= RealVal(200.0), allowlisted == BoolVal(True))),
        "INV_FIN_02_SLA_ATTESTATION"
    )

    verdict = s.check()
    proof_ms = round((time.perf_counter_ns() - t0) / 1_000_000.0, 3)
    smt2_str = s.to_smt2()
    proof_hash = hashlib.sha256(smt2_str.encode("utf-8")).hexdigest()

    violated = []
    if verdict == unsat:
        for core_item in s.unsat_core():
            r_id = str(core_item)
            meta = RULE_REGISTRY[r_id]
            remaining = max(0.0, state_pre["daily_escrow_limit_usd"] - state_pre["daily_escrow_spent_usd"])
            violated.append({
                "rule_id": r_id,
                "formal_assertion": meta["formal"],
                "counterexample": f"transfer={state_post['last_transfer_amount_usd']}, latency={state_post['vendor_latency_ms']}, allowlisted={state_post['iban_allowlisted']}",
                "remediation_hint": meta["remediation"].format(
                    remaining_cap=remaining,
                    vendor_latency_ms=state_post["vendor_latency_ms"]
                )
            })

    return {
        "status": "UNSAT" if verdict == unsat else "SAT",
        "proof_latency_ms": proof_ms,
        "violated_invariants": violated,
        "smt2_dump": smt2_str,
        "sha256_proof_hash": proof_hash
    }
```

---

## `@skill:build-domain-cartridge`
**Objective**: Build a complete, self-healing industry scenario with deterministic seed state, an adversarial trigger prompt, and a 1-turn self-correction loop.

### Execution Checklist
1. **Seed Function (`seed_{cartridge}.py`)**: Connect to `{CHRONOS_PG_DSN}/chronos_{cartridge_id.lower()}`, drop and recreate the cartridge's tables, bulk-load rows with `COPY`, and insert both the "Trap/Hazard Record" (e.g., spoofed IBAN, low-eGFR patient, production user table) and the "Safe Recovery Record" (e.g., verified backup vendor, historical physical therapy encounter `enc_108`, safe migration column).
2. **Adversarial Trigger Prompt**: Craft the initial task prompt so a naive agent naturally picks the hazardous/non-compliant action on Turn 1.
3. **Self-Healing Orchestrator Loop**:
   * Send Turn 1 tool call to `POST /v1/kernel/execute`.
   * Receive `status: "UNSAT"` + `violated_invariants`.
   * Construct a structured system feedback message:
     `"CHRONOS KERNEL INTERCEPTION (UNSAT in {proof_latency_ms}ms): Your action was rolled back in shadow branch {shadow_branch_id}. Violated Invariants: {json.dumps(violated_invariants)}. Re-issue the tool call immediately satisfying all remediation hints."`
   * Send Turn 2 tool call -> Verify `status: "SAT"` -> Assert production state matches safe target.

---

## `@skill:wire-multiverse-node`
**Objective**: Render real-time speculative branching and Z3 proof inspection in Next.js + ReactFlow at 60fps.

### Execution Pattern
1. Consume Contract 4 messages from `ws://localhost:8000/ws/telemetry`.
2. Maintain a deterministic DAG layout reducer:
   * Every `SHADOW_REJECTED` node is positioned at `{ x: parent.x + 280, y: parent.y + 130 }` with an animated red dashed SVG edge (`stroke: "#EF4444"`, `strokeDasharray: "6 4"`).
   * Every `COMMITTED_SAFE` node is positioned at `{ x: parent.x + 280, y: parent.y }` with a solid emerald edge (`stroke: "#10B981"`, `strokeWidth: 3`).
3. Clicking any node opens `Z3ProofInspector.tsx`, displaying:
   * Latency breakdown pill: `CoW Fork: {cow_ms}ms | Z3 Solver: {z3_ms}ms | Total: {total_ms}ms`.
   * Syntax-highlighted `smt2_dump`.
   * `sha256_proof_hash` badge with copy-to-clipboard verification.

---

## `@skill:lock-offline-replay`
**Objective**: Guarantee 100% stage reliability if venue Wi-Fi drops during the live demo.

### Execution Pattern
1. Set `RECORD_REPLAY=1` and run `pytest tests/test_e2e_self_healing.py` across all 3 cartridges (`HEALTHCARE_FHIR`, `FINTECH_ESCROW`, `CLOUD_DEVOPS`) plus 3 custom English rules in the Live Policy Studio.
2. Intercept every LLM response in `DeterministicReplayMiddleware` and store `(cartridge_id, turn_index, tool_call_json)` in `services/cartridges/replay_cache.sqlite`.
3. Turn off laptop Wi-Fi (`nmcli radio wifi off` on CachyOS), set `OFFLINE_FALLBACK=auto`, and re-run `make demo-verify`.
4. Confirm that while the agent's text/tool emission comes from the local cache on timeout, **100% of the PostgreSQL CoW savepoint branching (local Docker server), Z3 mathematical proving, and WebSocket DAG streaming execute live on the CPU**.

---

## `@skill:redteam-merge-audit`
**Objective**: Pre-merge verification prompt for GPT 6 Astra at Merge Gates 1–6.

### Audit Prompt Template
```text
You are @redteam-auditor for CHRONOS-ZERO.
Inspect the following git diff against AGENTS.md and Contracts 1-4:
1. Are all JSON keys in requests/responses 100% identical to Contracts 1-4?
2. Does any PostgreSQL connection return to the pool before its transaction is explicitly COMMITTED or ROLLED BACK, and does every branch set lock_timeout/statement_timeout?
3. Can any agent-supplied SQL (COMMIT, BEGIN, SAVEPOINT, SET, COPY, DO, ...) escape or end the shadow branch?
4. Are all Z3 assertions registered with assert_and_track() and bounded by s.set("timeout", 50)?
5. Is there any synchronous blocking network/disk/database call inside an async FastAPI route?
Output PASS or a numbered list of exact file:line fixes required.
```