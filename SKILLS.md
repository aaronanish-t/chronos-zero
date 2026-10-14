# CHRONOS-ZERO Reusable Agent Playbooks

Invoke these skills explicitly by name (e.g., `Execute @skill:compile-z3-invariant for FINTECH_ESCROW`) so coding agents generate standardized, drop-in compliant code across all four worktrees.

## Skill Registry Overview

| Skill ID | Owner | Trigger Use Case | Output Artifact | Verification Gate |
| :--- | :--- | :--- | :--- | :--- |
| `@skill:scaffold-cow-savepoint` | E1 | Adding/updating stateful CoW mutation handlers in `kernel-proxy` | Thread-pinned SQLite WAL Savepoint context manager | `P99 < 2.0ms` fork/rollback |
| `@skill:compile-z3-invariant` | E2 | Writing new formal rules or building the NL-to-Z3 compiler | Tracked Z3 solver function + 4-vector `pytest` suite | 100% pass on `SAT`/`UNSAT`/Boundary |
| `@skill:build-domain-cartridge` | E3 | Creating a vertical scenario (seed DB + attack + self-healing retry) | Seed SQL + adversarial prompt + self-healing handler | E2E self-healing in 1 retry turn |
| `@skill:wire-multiverse-node` | E4 | Adding custom ReactFlow nodes, drawers, or telemetry animations | TypeScript ReactFlow component + WebSocket reducer | 60fps render with 0 hydration errors |
| `@skill:lock-offline-replay` | E3/E1 | Recording live LLM agent trajectories for zero-Wi-Fi stage mode | Populated `replay_cache.sqlite` + Airplane Mode test | 100% pass with network disabled |
| `@skill:redteam-merge-audit` | All | Pre-merge verification at Merge Gates 1 through 6 | Schema & race-condition audit report | 0 contract violations |

---

## `@skill:scaffold-cow-savepoint`
**Objective**: Implement a zero-copy, sub-2ms transactional shadow branch using `/dev/shm` SQLite WAL savepoints.

### Execution Pattern
1. Open a dedicated SQLite connection to `/dev/shm/chronos_{cartridge_id}.db` with `check_same_thread=False`.
2. Snapshot `state_pre` using a fast read query.
3. Issue `SAVEPOINT {shadow_branch_id};`.
4. Execute the parameterized SQL mutation representing `tool_call`.
5. Snapshot `state_post_shadow` inside the uncommitted savepoint.
6. Store the live connection in `self._pinned_branches[shadow_branch_id]` until E2's Z3 service responds.
7. Execute `RELEASE SAVEPOINT {shadow_branch_id};` on `SAT` or `ROLLBACK TO SAVEPOINT {shadow_branch_id}; RELEASE SAVEPOINT {shadow_branch_id};` on `UNSAT`.

### Reference Template
```python
import sqlite3
import time
import uuid
from typing import Any

class CoWBranchEngine:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._pinned: dict[str, sqlite3.Connection] = {}

    def fork_and_mutate(self, state_reader_fn, mutation_fn, tool_args: dict[str, Any]) -> tuple[str, dict, dict, float]:
        t0 = time.perf_counter_ns()
        branch_id = f"cow_branch_{uuid.uuid4().hex[:8]}"
        conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")

        state_pre = state_reader_fn(conn)
        conn.execute(f"SAVEPOINT {branch_id};")
        try:
            mutation_fn(conn, tool_args)
            state_post = state_reader_fn(conn)
        except Exception:
            conn.execute(f"ROLLBACK TO SAVEPOINT {branch_id};")
            conn.execute(f"RELEASE SAVEPOINT {branch_id};")
            conn.close()
            raise

        self._pinned[branch_id] = conn
        latency_ms = round((time.perf_counter_ns() - t0) / 1_000_000.0, 3)
        return branch_id, state_pre, state_post, latency_ms

    def resolve(self, branch_id: str, commit: bool) -> float:
        t0 = time.perf_counter_ns()
        conn = self._pinned.pop(branch_id)
        try:
            if commit:
                conn.execute(f"RELEASE SAVEPOINT {branch_id};")
            else:
                conn.execute(f"ROLLBACK TO SAVEPOINT {branch_id};")
                conn.execute(f"RELEASE SAVEPOINT {branch_id};")
        finally:
            conn.close()
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
1. **Seed Function (`seed_{cartridge}.py`)**: Create clean SQLite tables in `/dev/shm/chronos_{cartridge_id}.db` and insert both the "Trap/Hazard Record" (e.g., spoofed IBAN, low-eGFR patient, production user table) and the "Safe Recovery Record" (e.g., verified backup vendor, historical physical therapy encounter `enc_108`, safe migration column).
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
4. Confirm that while the agent's text/tool emission comes from the local cache on timeout, **100% of the SQLite CoW savepoint branching, Z3 mathematical proving, and WebSocket DAG streaming execute live on the CPU**.

---

## `@skill:redteam-merge-audit`
**Objective**: Pre-merge verification prompt for GPT 6 Astra at Merge Gates 1–6.

### Audit Prompt Template
```text
You are @redteam-auditor for CHRONOS-ZERO.
Inspect the following git diff against AGENTS.md and Contracts 1-4:
1. Are all JSON keys in requests/responses 100% identical to Contracts 1-4?
2. Does any SQLite connection close or return to the pool before its SAVEPOINT is explicitly RELEASED or ROLLED BACK?
3. Are all Z3 assertions registered with assert_and_track() and bounded by s.set("timeout", 50)?
4. Is there any synchronous blocking network/disk call inside an async FastAPI route?
Output PASS or a numbered list of exact file:line fixes required.
```