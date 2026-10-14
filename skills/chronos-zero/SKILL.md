---
name: chronos-zero
description: Work on the Chronos-Zero speculative-execution kernel — SQLite savepoint shadow branches, Z3 SMT invariant checks, the healthcare/fintech/cloud-devops cartridges, the JSON contracts, and the Multiverse UI telemetry. Use when adding or changing an invariant, a cartridge scenario, a contract field, the /v1/kernel/execute or /v1/z3/verify flow, or the WebSocket telemetry events.
---

# Chronos-Zero domain skill

## Core flow (keep this order)

1. Agent request hits `POST /v1/kernel/execute` (Contract 1).
2. `cow_engine.fork_and_simulate` reads `state_pre`, opens `SAVEPOINT cow_branch_{uuid}`, applies the mutation, reads `state_post_shadow`. The savepoint stays open.
3. `POST /v1/z3/verify` with Contract 2 (`state_pre`, `state_post_shadow`, cartridge id).
4. Z3 returns Contract 3: `SAT` or `UNSAT` with `violated_invariants`, `smt2_dump`, `sha256_proof_hash`.
5. `SAT` → `RELEASE SAVEPOINT` (commit). `UNSAT` → `ROLLBACK TO SAVEPOINT`. Never the reverse.
6. Append a hash-chain entry (`crypto_audit.py`) and broadcast Contract 4 on `/ws/telemetry`.
7. On `UNSAT`, return the `remediation_hint`s to the agent as a `CHRONOS_KERNEL_BLOCK:` observation so it retries once.

## Adding an invariant

1. Pick the cartridge file in `services/z3-verifier/invariants/` (`healthcare_fhir.py`, `fintech_escrow.py`, `cloud_devops.py`).
2. Name it `INV_<DOMAIN>_<NN>_<SHORT_NAME>` (e.g. `INV_MED_01_RENAL_SAFETY`). The ID is user-visible and appears in the UI.
3. Express it as `Implies(precondition, requirement)` over Z3 `Real`/`Int`/`Bool` vars bound from `state_post`.
4. Add with `s.assert_and_track(expr, RULE_ID)` — never plain `s.add`.
5. Give it a `remediation_hint` a clinician, FinOps, or SRE would understand. No jargon-only text.
6. Write the four vectors in `tests/test_z3_invariants.py`: `true_positive`, `true_negative`, `boundary_exact`, `malformed_state_handling`.
7. Run the Hypothesis fuzz test (1,000 random state dicts; no unhandled exceptions; no timeouts).

Reference invariants:

| ID | Formal rule |
|---|---|
| `INV_MED_01_RENAL_SAFETY` | `Implies(egfr < 30, metformin_dose == 0)` |
| `INV_MED_02_PAYER_AUTH` | `Implies(claim_submitted, therapy_weeks >= 6)` |
| `INV_FIN_01_ESCROW_CAP` | `daily_spent + transfer_amount <= daily_limit` |
| `INV_FIN_02_SLA_ATTESTATION` | `Implies(transfer_amount > 0, And(sla_latency_ms <= 200, iban_allowlisted))` |
| `INV_OPS_01_ZERO_DATA_LOSS` | `row_count_post >= row_count_pre` |
| `INV_OPS_02_NO_PUBLIC_ADMIN_PORT` | `Not(And(cidr_open_world, port == 22))` |

## Adding a cartridge scenario

1. Seed data goes in `services/cartridges/seed_databases.py` — deterministic, so `make seed` restores the exact demo state.
2. The adversarial prompt lives in `services/cartridges/attack_scenarios/`. It must trigger a real `UNSAT` in `ACTIVE` mode and be fixable in one retry turn.
3. The agent's retry must reach `SAT` with zero corrupted rows. Assert that in `tests/test_e2e_self_healing.py`.
4. Run the same scenario in `BYPASS` to confirm the damage is visible (`BYPASS_CORRUPTED`).

## Contract changes

- Contracts in `contracts/*.schema.json` are frozen after Merge Gate 1. Changing a field name or type needs all four engineers informed and every consumer updated in the same change.
- Additive, optional fields are fine. Document them in the schema.
- Validate payloads against the schema in tests; don't hand-check shapes.

## Telemetry events (Contract 4)

- `BRANCH_EVALUATED` with `branch_type`: `SHADOW_REJECTED` (red, `UNSAT`), `COMMITTED_SAFE` (green, `SAT`).
- `BYPASS_CORRUPTED` for `BYPASS` mode.
- Include `financial_loss_prevented_usd` and `clinical_hazard_prevented` when they apply.

## Gotchas

- Z3 `unsat_core()` returns the tracked Bool names as strings. Map them to remediation hints; don't show raw SMT to the agent.
- Keep the savepoint open across the Z3 call, and always resolve it, including on exceptions and timeouts (treat timeout as `UNSAT`/fail-closed, and roll back).
- Wrap every Z3 call with the 50 ms timeout; a timeout must never commit.
- The `timestamp_ns` example in Contract 1 is in nanoseconds — make sure producers use real ns values, not seconds or µs.
- Each Z3 context is pre-warmed; don't rebuild `Solver()` objects per request in a way that adds init cost on the hot path.
- SQLite RAM-disk path differs by OS (see `AGENTS.md`); never hard-code `/dev/shm`.

## Definition of done for a change in this domain

- [ ] Contract(s) validated against schema
- [ ] Invariant(s) tracked, named, with four test vectors passing
- [ ] `ACTIVE` path: UNSAT rolls back, SAT commits — both tested
- [ ] `BYPASS` path still produces `BYPASS_CORRUPTED` for the scenario
- [ ] Latency measured with `perf_counter_ns`, not claimed
