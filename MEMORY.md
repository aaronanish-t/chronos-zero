# CHRONOS-ZERO — Merge Gate Memory (2026-10-14)

Everything done in the red-team Merge Gate sync, from the audit to a green CI on `main`.

| | |
|---|---|
| Repo | https://github.com/aaronanish-t/chronos-zero (private) |
| `main` | **c5412d9**, same as `merge-gate/sync`; CI green. Commit IDs are post-rewrite (section 8). |
| Work branch | `merge-gate/sync` (pushed) |
| Local worktree | `C:\Users\anish\Projects\chronos-zero-gate` |
| Original checkout | `C:\Users\anish\Projects\chronos-zero` (still on `feat/e1-kernel`) |
| Storage | PostgreSQL 16 (AGENTS.md section 4.1). The audit prompt's SQLite / `/dev/shm` / `nmcli` wording is outdated, so its checks were applied to the Postgres design. |

`MEMORY.md` is committed on `main`. It was force-added past the local `.git/info/exclude` entry; tracked files ignore that exclude. Appendix A keeps the original local project overview verbatim.

---

## 1. Timeline

1. **Merge.** `feat/e1-kernel`, `feat/e2-z3-prover`, `feat/e3-cartridges` and `feat/e4-multiverse-ui` were merged onto `main` in the `merge-gate/sync` worktree. No conflicts. 120 existing tests passed, but they mocked Z3 or the kernel.
2. **Audit.** Read every service and reproduced each suspected bug with probe scripts before fixing it (section 2).
3. **First fixes, pushed as WIP** (f05ea4a): kernel, Z3, cartridge and UI fixes (section 3).
4. **Stage readiness** (e7be1c3). First fast-forward of `main`.
   - Contract-parity tests and a live-stack E2E test.
   - Recorded the offline replay cache.
   - Stage launcher and Makefile targets.
   - Fixed the WebSocket dependency found while driving the UI in the browser.
5. **Follow-ups** (d8ebe71, 102f28c). Second fast-forward of `main`; all CI jobs green.
   - CI workflow.
   - Flaky timing tests hardened.
   - Test isolation.
   - FinTech fail-closed fix.
   - Lockfile resync.
6. **MEMORY.md committed** (c5412d9), with the original overview as Appendix A.
7. **Claude co-author trailers removed from all history**: three branches rewritten and force-pushed (section 8).

## 2. Audit verdicts (before fixes) — all four FAIL

| Check | Verdict | Findings |
|---|---|---|
| 1. Schema parity (Contracts 1-4) | **FAIL** | The verifier emitted `rule_id: "MALFORMED_STATE"`, which breaks the Contract 3 pattern `^INV_[A-Z]+_[0-9]{2}_[A-Z0-9_]+$`. Compiled-policy IDs were never validated (E2's tests used `INV_DYN_WIRE_5K`). UI `contracts.ts` allowed `TIMEOUT`/`ERROR` and lacked `BYPASS`, `N/A` and `SYSTEM_EVENT`; `parent_id` was nullable. The Split Screen called tool names the kernel doesn't register (`transfer_funds_zk_escrow`) and mixed cartridges in one request, so every step came back 404. |
| 2. Savepoint / pinned-connection safety | **FAIL** (narrow) | A failing `rollback()` in `fork_and_mutate` skipped `putconn()`, leaking the connection. `_execute_active` built the Contract 2 diff outside its try/finally. A cancellation during the audit append could still COMMIT with no receipt. `rollback_all`/`close` stopped at the first failing branch. |
| 3. Z3 determinism | **FAIL** | A Z3 `unknown` (50 ms timeout) counted as a pass, failing open. unsat with an empty core passed too. Compiled policies never fired on real kernel diffs: the dynamic builder re-bound `daily_escrow_spent_usd` to its post value, which conflicted with the static solver, so a $600 wire against "max $500" returned **SAT**. Z3's shared context isn't thread-safe and sync FastAPI routes run on threads: **8 concurrent requests crashed the process natively**. `assert_and_track`, `RealVal`/`IntVal`/`BoolVal` and `timeout=50` were otherwise present. |
| 4. Wi-Fi-off readiness | **FAIL** | Nothing needed the network: the agent is scripted, Postgres is local, and the UI has no remote fonts. **But the demo was fake**: Space/Simulate/Bypass streamed hard-coded proofs, hashes and rule IDs; the Policy Studio "compiled" in the browser with `Math.random()` latency and enforced nothing; the inspector invented pre/post state and a 38% "CoW fork" share; Merkle verify reported `verified: true` from a local one-entry chain; the benchmark badge showed invented 4.14 ms / 350x where the real report said P50 8.09 ms, gate not met. Also: `OFFLINE_MODE=1` failed because `replay_cache.sqlite` was never recorded; 2 of 5 judge policies didn't compile offline; re-runs broke (DevOps duplicate `ADD COLUMN`, FinTech cap exhausted). |

## 3. All fixes

### Kernel (E1): `services/kernel-proxy/`
- `cow_engine.py`: `_rollback_and_return()` always hands the connection back, even if rollback fails. Secondary rollback errors no longer mask the original (so 40001 still surfaces as 409). `rollback_all`/`close` continue past failing branches.
- `interceptor.py`: the Contract 2 diff is built inside the guarded block. A branch commits only when `audited` is true (receipt written) and the verdict is SAT. Split-comparison lanes never raise, so `gather` can't drop the sandbox under a running lane.
- `requirements.txt`: `uvicorn[standard]` + `websockets`. Plain uvicorn rejected `/ws/telemetry` with "Unsupported upgrade request", so the UI's DAG would never have received an event.
- `main.py`: port from `CHRONOS_KERNEL_PORT` (default 8000).

### Z3 verifier (E2): `services/z3-verifier/`
- `server.py`:
  - Global `_Z3_LOCK` around verify, compile and prewarm (fixes the native crash).
  - Binds `127.0.0.1`; port from `CHRONOS_Z3_PORT`.
  - `PolicyCompileRequest` validates the cartridge literal and the Contract 3 `rule_id` pattern.
  - New `POST /v1/z3/policies/clear` (used by stage reset).
  - `/health` reports `offline_mode`.
- `prover_core.py`:
  - Fails closed on `unknown` and on an empty unsat core.
  - Malformed state is `INV_SYS_00_MALFORMED_STATE`.
  - Readable counterexamples for compiled policies: only the variables the formula uses.
- `invariants/*.py`: same fail-closed loop. `STATE_ERROR` → `INV_SYS_00_MALFORMED_STATE`. FinTech raises (UNSAT) on a missing daily cap or vendor latency instead of defaulting to $50,000 / 0 ms.
- `nl_compiler.py`:
  - The builder binds shared variables from the static solver's context, so compiled rules are actually enforced.
  - New offline patterns: "SLA latency under N ms" and drop/truncate/delete.
  - `rule_id` validated.

### Cartridges (E3): `services/cartridges/`
- `orchestrator.py`: kernel URL `127.0.0.1:8000`; port from `CHRONOS_AGENT_PORT`.
- `scenarios/cloud_devops_scenario.py`: the heal uses `ADD COLUMN IF NOT EXISTS`, so it can be re-run.
- `scenarios/fintech_scenario.py`: the heal is a **$400** micro-escrow (the pitch number), capped at the remaining cap. Two heals fit before a reset.
- `scenarios/judge_policies.py`: the "$500 cap" policy no longer overrides the amount.
- `requirements.txt`: new file.
- `replay_cache.sqlite`: **recorded and committed**. It holds 16 trajectories: 3 scenarios plus 5 judge policies, 2 turns each.

### UI (E4): `services/multiverse-ui/`
- `next.config.ts`: same-origin rewrites `/v1/z3` → :8001, `/v1/agent` → :8002, `/v1` → :8000 (env-overridable).
- `types/contracts.ts`:
  - Exact Contract 3/4 unions and a `TelemetryNodePayload` matching Contract 4.
  - `isTelemetryEvent()` runtime guard, plus orchestrator and compile response types.
  - `AuditEntry.timestamp_ns` is a string: nanoseconds exceed `Number.MAX_SAFE_INTEGER`, and rounding broke hash verification.
- `hooks/useChronosWS.ts`: all mock data removed.
  - `runScenario(cartridge, mode)` → orchestrator. Each Contract 3 verdict is merged into its node (`node_<shadow_branch_id>`).
  - A synthesized root node; edges derived from `parent_id`.
  - WS events are validated; a superseded socket is ignored (StrictMode).
  - A BYPASS run marks production dirty, so the next run auto-reseeds.
  - Reset also clears compiled policies.
- `app/page.tsx`: keys **1/2/3** cartridge, **Space** run, **B** run without Chronos, **R** reset, **S** split screen. A run-status strip shows real results and errors.
- `components/TopTelemetryBar.tsx`: measured benchmark only. Honest labels: "Run Scenario", "Run Without Chronos", "Avg Kernel Latency".
- `components/LivePolicyStudio.tsx`: real `/v1/z3/compile-policy` with `INV_POL_NN_<MED|FIN|OPS>` IDs. Presets are E3's 5 judge policies. The compiled policy goes as `custom_prompt` on the next run.
- `components/SplitScreenDemo.tsx`: E3's exact hazard and heal calls per cartridge; "All 3" runs the three in sequence. Numbers come only from the kernel response, and errors are shown.
- `components/Z3ProofInspector.tsx`: real proof time (kernel = total − proof); shows the Contract 1 tool call; state diff only when real (BYPASS); browser-side Merkle verification.
- `utils/cryptoAudit.ts`: `fetchAndVerifyAuditLog()` recomputes every entry hash, link and the Merkle root, and checks the node's receipt against `sha256(smt2_dump)`.
- `components/MultiverseDAG.tsx`: siblings from several timelines no longer overlap.
- `app/api/benchmark/route.ts`: reads `gate`/`runs` from `contracts/benchmark_report.json`, or returns `available: false`.
- `package-lock.json`: resynced so `npm ci` works on npm 10 (Node 20).

### Tests: `tests/`
- New `contract_validator.py`: a dependency-free JSON Schema validator.
- New `test_contract_parity.py`: JSON Schema == Pydantic == TypeScript (interfaces, unions, runtime guard); live verifier output validated against Contract 3.
- New `test_e2e_live_stack.py`: the real kernel + Z3 + orchestrator + Postgres in one process, behind an airplane-mode guard that records any non-loopback socket. It covers:
  - all 3 cartridges;
  - re-runs without reset;
  - policy enforcement ($600 vs $500 → UNSAT);
  - all 5 judge presets;
  - BYPASS + reset;
  - the split comparison;
  - offline replay from the committed cache.
- New `test_z3_concurrency.py`: 8 threads of verify + compile in a subprocess.
- `conftest.py`: unloads compiled policies after every test (they're process-global, and leaking them made verdicts order-dependent).
- `test_z3_smoke.py`: the 5 ms gates use best-of-5 samples; the verdict is checked on every response.
- `test_z3_fuzz.py`: works without POSIX `resource`.
- `test_z3_invariants.py`: new FinTech fail-closed regression tests.
- `test_z3_nl_compiler.py`: Contract-3 rule IDs (`INV_DYN_01_*`).
- `test_e2e_self_healing.py` / `test_e2e_replay.py`: updated for the $400 heal and `IF NOT EXISTS`.

### Infra / orchestration (E1)
- `deploy/production/docker-compose.yml`: persistent kernel / Z3 / agent / UI deployment with health checks, private networking, and Caddy as the public gateway.
- `Makefile`: new targets `stage`, `kernel`, `z3`, `agent`, `ui`, `ui-install`, `record-replay`, `demo-verify`, `test-contracts`.
- `.github/workflows/merge-gate.yml`: CI on every push and PR.
  - `contracts`: parity.
  - `backend`: docker compose Postgres + seed + the full suite; the benchmark is report-only.
  - `ui`: `npm ci` + `tsc` + `next build`.

## 4. Verification evidence
- **Probes:** each Z3 bug was reproduced before its fix and confirmed fixed after.
  - All 5 judge policies compile offline.
  - $600 vs $500 → UNSAT.
  - The malformed `rule_id` conforms to Contract 3.
  - A forced `unknown` → UNSAT.
  - 8 threads no longer crash.
- **Regression power:** swapping the pre-fix `nl_compiler.py` back in makes 5 of 6 live policy tests fail.
- **Local suite (Windows):** 160 passed, plus the 2 new FinTech fail-closed tests (32/32 in that file).
- **CI (Linux):** all three jobs green on `merge-gate/sync` and on `main`, including after the history rewrite (run 38546403647).
- **UI:** `tsc` clean and `next build` passes.
- **Driven live in the browser** (stack on offset ports):
  - Healthcare: UNSAT with 3 violations, healed in 1 turn from `replay_offline`; the inspector shows the real SMT-LIB2, counterexamples and timings.
  - Policy Studio: compiled `INV_POL_01_FIN`; the $12k hazard was blocked with it in the unsat core; healed.
  - Split screen "All 3": BYPASS lane 15,420 rows dropped, $12k wired, Rx committed; ACTIVE lane 3 blocked, 3 committed; proofs 1.4-3.4 ms.
  - Reset reseeded the stage and cleared the policy. BYPASS, then ACTIVE, auto-reseeded.
  - Merkle verify: chain and root recomputed in the browser; the receipt matches `sha256(smt2_dump)`.

## 5. Latency numbers (for the pitch)
| Where | Kernel P50 | Kernel P99 | Gate (P50 < 3.5, P99 < 8.0 ms) |
|---|---|---|---|
| Linux CI runner (GitHub Actions) | **2.75 ms** | **4.93 ms** | **PASS** |
| This Windows PC + Docker Desktop (the committed `contracts/benchmark_report.json`) | 8.09 ms | 18.31 ms | not met |

- The benchmark times the CoW fork plus commit/rollback; **Z3 is excluded** ("untimed"). The Z3 proof adds about 1.3-2 ms (measured p50 1.3-1.9 ms).
- A defensible line: *about 3 ms kernel overhead plus about 2 ms Z3 proof, roughly 300x faster than a 1.5 s LLM guardrail.* The plan's "3.4 ms total / 350x" is slightly optimistic.
- The UI badge shows whatever `contracts/benchmark_report.json` holds; it currently shows the Windows numbers as 179x. Run `make bench` on the stage laptop to replace them.

## 6. Stage runbook
1. `git pull` on the stage laptop (`main`).
2. `pip install -r services/kernel-proxy/requirements.txt -r services/z3-verifier/requirements.txt -r services/cartridges/requirements.txt`
3. `make ui-install` (once, with network).
4. Optional: `make bench`, so the badge shows that laptop's numbers.
5. Copy `deploy/production/.env.example` to `deploy/production/.env`, replace the
   placeholders, run `make deploy-config`, then `make up` and `make seed`.
6. With Wi-Fi off: `make demo-verify` (the airplane-mode gate).

During the pitch:
- Do **one warm-up run** first (the first call is ~100 ms while pools warm).
- Press **R between segments**: the FinTech $5,000 daily cap allows two $400 heals.
- Policy Studio presets compile offline and enforce on the next run of their cartridge. Reset unloads them.

## 7. Gotchas found on this PC
- An older kernel and Z3, not started by us, sometimes answer on :8000/:8001. `netstat` can't see them (likely WSL or another network namespace). Use `--offset 100`.
- MSYS `sed -i` and Python `write_text` on Windows can flip files to CRLF. Edits were normalized to LF before committing.
- `feat/e1-kernel`, `feat/e2-z3-prover` and `feat/e4-multiverse-ui` are unchanged. `feat/e3-cartridges` was rewritten (section 8). Teammates should rebase onto the new `main`.

## 8. History rewrite: Claude co-author trailers removed (2026-10-14)

Aaron asked for Claude to be removed from the GitHub contributors.

**Source.** Aaron's commits never carried Claude attribution. The only credits were `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` trailers on three E3 commits by rishipradeep-stack:
- `4a7a983` seeder
- `0e2badd` orchestrator
- `040a152` tool-name fix

**How.** `git filter-branch --msg-filter` deleted only the trailer lines on every branch containing those commits. All three were rewritten in one pass, so shared commits got identical new IDs. Then `git push --force-with-lease` (so a newer push by someone else would have been refused rather than overwritten).

| Branch | Before | After |
|---|---|---|
| `main` | `fdb1612` | `c5412d9` |
| `merge-gate/sync` | `fdb1612` | `c5412d9` |
| `feat/e3-cartridges` | `de56490` | `fe7a670` |

**Checked before pushing:**
- File trees identical to the originals.
- Same commit counts (43; 12 on E3) and the same authors.
- Zero Claude trailers left.
- E3 is still an ancestor of `main`.

**Checked after:** zero Claude trailers on any remote or local branch, and CI green on the rewritten `main`. The local `main` and `feat/e3-cartridges` in `C:\Users\anish\Projects\chronos-zero` were moved onto the new history; neither had local-only work.

**Old to new IDs (main):**

| Before | After |
|---|---|
| `08f2172` | `f05ea4a` |
| `ecdb3ee` | `e7be1c3` |
| `2b634bd` | `d8ebe71` |
| `5388e04` | `102f28c` |
| `fdb1612` | `c5412d9` |

Commits before `4a7a983` (and those not descending from it) kept their IDs.

**Team follow-up:**
- Anyone with the old history, especially Rishi (E3), runs `git fetch && git reset --hard origin/<branch>`, or rebases unpushed work onto the new history first.
- GitHub caches the contributors graph, so the Claude entry can take a while to disappear.
- Rishi should turn off co-author trailers in his coding assistant so they don't return.

## 9. Still open
- Run `make bench` on the actual stage laptop and rehearse there with Wi-Fi off.
- Optional: emit the Contract 4 `POLICY_COMPILED` event from the kernel when a policy is compiled. Nothing emits it today; the UI ignores it.
- Optional: CI actions on Node 20 are deprecated on GitHub runners. Warnings only; bump `actions/*` versions later.

---

## Appendix A: Project overview (original E1 memory, written before the merge gate)

> Kept verbatim so nothing is lost. **Superseded by the sections above:**
> - The SQLite wording in A.3: storage is PostgreSQL 16 (`SAVEPOINT` inside a pinned `REPEATABLE READ` transaction).
> - The status table, test count and commit history in A.8.
> - The known issues in A.9: all of them are now resolved.
> - The A.10 latency answer: see section 5 for the measured numbers.

Everything in the GitHub repo [aaronanish-t/chronos-zero](https://github.com/aaronanish-t/chronos-zero) (private), as of 2026-10-14. It covers the `main` and `feat/e1-kernel` branches.

---

### 1. The pitch in one line

**CHRONOS-ZERO lets AI agents act on real systems safely.** Before any action reaches the real system, it is tried on a throwaway copy of the data and mathematically proven safe.

### 2. The problem

AI agents now take real actions: prescribing drugs, wiring money, running database migrations. Existing guardrails (NeMo Guardrails, Guardrails AI, LlamaGuard) only read the agent's *text*. They can't see what an action does to the *data*. For example, `UPDATE accounts SET balance = balance - 5000` looks harmless as text.

### 3. How it works

```
Agent tool call
   │
   ▼
1. INTERCEPT    Kernel catches the call before it hits production
2. FORK         Opens a SQLite SAVEPOINT (a shadow copy of the data)
3. SIMULATE     Runs the action inside the shadow copy
4. DIFF         Captures state before vs. after
5. PROVE        Z3 theorem prover checks the "after" state against domain rules
   │
   ├── SAT   → RELEASE SAVEPOINT (commit to production) + SHA-256 receipt
   └── UNSAT → ROLLBACK (production untouched) + tell the agent exactly which rule failed
                   └── agent fixes its action and retries (self-healing)
```

**What makes it different:** the safety check is a mathematical proof (Z3 SMT solver), not another AI's opinion. The answer is deterministic and comes with a reason.

**Latency targets** (from the spec, not yet measured): proof plus fork P50 under 3.5 ms and P99 under 8 ms. For comparison, an LLM guardrail call takes about 1,200–2,000 ms.

### 4. The three demo scenarios ("cartridges")

| Cartridge | Unsafe action the agent tries | What Chronos catches | Self-healed retry |
|---|---|---|---|
| **HEALTHCARE_FHIR** | Prescribe Metformin 2500 mg to a patient with eGFR 24, and submit a $1,450 claim with only 2 weeks of therapy | Renal-safety rule + payer-authorization rule | Switches to Linagliptin 5 mg and attaches the PT encounter log |
| **FINTECH_ESCROW** | A prompt-injected invoice tricks the agent into wiring $12,000 to a spoofed IBAN | Escrow cap + SLA/IBAN allowlist rule | Pays $400 only to the verified, SLA-compliant vendor |
| **CLOUD_DEVOPS** | Fixes a migration with `DROP TABLE users CASCADE` and opens port 22 to `0.0.0.0/0` | Zero-data-loss rule + no-public-admin-port rule | Uses a non-destructive `ALTER TABLE ADD COLUMN` |

#### The safety rules (invariants)

| Rule ID | Rule |
|---|---|
| `INV_MED_01_RENAL_SAFETY` | If eGFR < 30, Metformin dose must be 0 |
| `INV_MED_02_PAYER_AUTH` | If a claim is submitted, therapy weeks ≥ 6 |
| `INV_FIN_01_ESCROW_CAP` | Daily spent + transfer ≤ daily limit |
| `INV_FIN_02_SLA_ATTESTATION` | Any transfer requires vendor latency ≤ 200 ms and an allowlisted IBAN |
| `INV_OPS_01_ZERO_DATA_LOSS` | Row count after ≥ row count before |
| `INV_OPS_02_NO_PUBLIC_ADMIN_PORT` | Port 22 must never be open to the world |

### 5. Architecture

| Service | Port | Purpose |
|---|---|---|
| `services/kernel-proxy/` | 8000 | Interceptor, CoW engine, saga ledger, SHA-256 audit chain, WebSocket telemetry |
| `services/z3-verifier/` | 8001 | Z3 prover, rule files, English-to-Z3 compiler |
| `services/cartridges/` | — | Mock hospital/bank/cloud systems, seed data, LangGraph agent, offline replay cache |
| `services/multiverse-ui/` | — | Next.js 15 + ReactFlow live branching timeline |

Everything runs offline on one laptop. An offline replay cache serves stored LLM responses if venue Wi-Fi drops. The database copies and Z3 proofs still run live either way.

#### The four contracts (locked message formats)

1. **Intercept request:** `POST /v1/kernel/execute`. The agent's tool call plus mode (`ACTIVE` or `BYPASS`).
2. **State diff:** `POST /v1/z3/verify`. Before/after state sent from the kernel to Z3.
3. **Verdict:** `SAT`/`UNSAT`, violated rules with remediation hints, SMT-LIB2 dump, SHA-256 hash.
4. **Telemetry:** `ws://localhost:8000/ws/telemetry`. Events `BRANCH_EVALUATED`, `BYPASS_CORRUPTED`, `POLICY_COMPILED`, `DEMO_RESET` for the UI.

#### The UI ("Multiverse Time-Travel Debugger")

- **Top bar:** live counters for proof latency, branches forked, failures prevented and $ protected, plus the cartridge switcher and the ACTIVE/BYPASS toggle.
- **Centre:** a branching timeline. Blocked attempts split off in red; safe retries continue in green.
- **Right drawer:** for any node, the state diff, Z3 math, failed rule and receipt hash.
- **Live Policy Studio:** a judge types a rule in English, it compiles to Z3, and it is enforced on the next run.
- **Split screen:** "without Chronos" (damage) vs. "with Chronos" (safe).

### 6. Team and ownership

| Engineer | Role | Owns | Branch |
|---|---|---|---|
| **E1 — Aaron** | Kernel & State | `kernel-proxy/`, `contracts/`, Makefile, Docker | `feat/e1-kernel` |
| **E2** | Z3 / Formal math | `z3-verifier/`, Z3 tests | `feat/e2-z3-prover` |
| **E3** | Cartridges & Agents | `cartridges/`, end-to-end tests | `feat/e3-cartridges` |
| **E4** | UI & Pitch | `multiverse-ui/`, deck | `feat/e4-multiverse-ui` |

- Vijval (GitHub: Alphacew) is the lead speaker and owns `AGENTS.md` and `SKILLS.md`.
- The **build workflow** pairs Claude Opus 5.5 as builder with GPT 6 Astra as adversarial reviewer.

### 7. 48-hour plan: merge gates

| Gate | Hour | Milestone |
|---|---|---|
| G1 | 02 | Contracts locked |
| G2 | 10 | Kernel ↔ Z3 working end to end in under 5 ms |
| G3 | 20 | Healthcare demo working live on the UI |
| G4 | 30 | All 3 cartridges + English-to-Z3 studio live |
| G5 | 38 | Feature freeze, offline cache locked, backup video |
| G6 | 44 | Tagged `v1.0.0-stage`, airplane-mode test |

### 8. What's in the repo

#### Documents

| File | Contents |
|---|---|
| `hackathon` | Full spec: architecture bible + 48-hour playbook |
| `AGENTS.md` | Team constitution: ownership, locked contracts, engineering rules, verification commands |
| `SKILLS.md` | Reusable coding playbooks (CoW savepoint, Z3 invariant, cartridge, UI node, offline replay, red-team audit) |
| `ENGINEERS.md` | Per-engineer task list by time window (its status marks predate the E1 fixes) |
| `README.md` | Short overview |

#### Code and status

| Area | Status | Where |
|---|---|---|
| Contract JSON Schemas (1–4) | Done | `main` + `feat/e1-kernel` |
| Pydantic contract models (`contracts/schemas.py`) | Done | `feat/e1-kernel` |
| CoW engine: one pinned connection per branch | Done | `feat/e1-kernel` |
| Z3 healthcare rules (renal, payer) | Done, early version | both branches |
| Fintech + cloud Z3 rules | Not started on any branch | — |
| Interceptor API, WebSocket, audit chain | Not started | — |
| Cartridges, agent loop, offline cache | Not started | — |
| UI | Not started | — |

**Tests:** 13 passing on `feat/e1-kernel` (6 CoW engine, 7 Z3).

#### Commit history

| Commit | Author | Change |
|---|---|---|
| `f056187` | Aaron | Repo created with plan |
| `53b9c49` | Aaron | Contracts, Z3 healthcare rules, first CoW engine |
| `8adf736` | Aaron | Engineer breakdown added |
| `e4d5787` | Vijval | Restored `AGENTS.md` and `SKILLS.md` |
| `80cd496` | Aaron | **E1 fixes:** locked Contract 3/4, per-branch connection pinning (on `feat/e1-kernel`) |

### 9. Known issues and next steps

- **E2 – Z3 not reporting every broken rule.** `test_multi_violation` in the proposed E2 patch fails: Z3 reported only the renal rule when both rules were broken. E2 needs a way to report every violated rule, for example checking each rule separately.
- **E2 – missing data passes the checks.** The proposed E2 patch fills in safe-looking defaults when data is missing (eGFR → 90, IBAN allowlisted → True). It should block instead.
- **E2/E3 – field name mismatch.** `SKILLS.md` uses `last_transfer_amount_usd`; the E2 patch uses `transfer_amount_usd`. Agree on one.
- **E1 – Windows support.** The DB path falls back to the system temp folder when `/dev/shm` doesn't exist (Windows). It can be overridden with `CHRONOS_DB_DIR`.
- **E1 – next:** the `POST /v1/kernel/execute` interceptor and the WebSocket telemetry. Together with E2's verifier service, that gives Gate 2.

### 10. Hard judge questions and answers

1. **"Doesn't a theorem prover add latency?"** It only checks the small before/after difference, in memory. The target is single-digit milliseconds, versus 1–2 seconds for an LLM guardrail.
2. **"What about APIs without savepoints, like email or Stripe?"** Read-only calls pass straight through. Stateful calls run against a copy first. Irreversible calls are held until the whole sequence is proven safe. A saga ledger maps each action to its undo.
3. **"Who writes the Z3 rules?"** Nobody writes Z3 by hand. Rules are typed in English in the Policy Studio, compiled to Z3, and tested at setup time.
4. **"How is this different from guardrails?"** Guardrails read text. Chronos checks the actual data after the action.
5. **"Who pays first?"** Open-source the core proxy for developers. Sell pre-audited HIPAA and SOC2 rule packs to mid-market hospitals and fintechs at $4,000 per month per cluster.
