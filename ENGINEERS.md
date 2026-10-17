# Engineer Work Breakdown

Taken from the plan in [hackathon](hackathon) (sections 2.1–2.8). `[x]` = done in this repo, `[~]` = partly done, `[ ]` = not started.

Merge gates: **G1** H02 contract lock · **G2** H10 kernel↔Z3 sub-5 ms · **G3** H20 healthcare full loop on UI · **G4** H30 all cartridges + NL studio · **G5** H38 feature freeze + offline cache · **G6** H44 tag `v1.0.0-stage`.

---

## E1 — Kernel & State Lead

**Owns:** `services/kernel-proxy/`, `contracts/` · **Backup:** Docker/Makefile, backend integration
**Stage role:** Systems anchor (CoW isolation, latency questions)

| Window | Task | Status |
|---|---|---|
| H00–02 | Init repo, write `contracts/*.json` | [x] |
| H00–02 | FastAPI skeleton + mock WebSocket emitter | [ ] |
| H02–06 | PostgreSQL savepoint engine (`cow_engine.py`, psycopg async pool) | [ ] SQLite version on `feat/e1-kernel` must be ported (storage switched to Postgres) |
| H06–10 | `interceptor.py`: `POST /v1/kernel/execute`, call Z3 at `:8001/v1/z3/verify`, resolve savepoint on verdict | [ ] |
| H06–10 | `BYPASS` mode: write directly, emit `BYPASS_CORRUPTED` | [ ] |
| H10–16 | `saga_ledger.py` (inverse map for HTTP mutations) | [ ] |
| H10–16 | `crypto_audit.py` (SHA-256 hash chain) | [ ] |
| H16–20 | Connect WebSocket broadcaster to E3's agent triggers | [ ] |
| H26–30 | Wire Fintech + Cloud DevOps cartridges into `cow_engine.py` | [ ] |
| H30–38 | 500-call latency benchmark (`test_cow_latency.py`), tune async pool | [ ] |
| H38–44 | Chaos tests: fast cartridge switching, malformed input, Wi-Fi kill | [ ] |
| — | `deploy/production/docker-compose.yml`, production `Makefile` targets, persistent Postgres 16 | [x] Production deployment is the single supported Compose path |

**Gate duties:** owns G1 merge; pairs with E2 at H06 (state keys ↔ Z3 vars) and G2.

---

## E2 — Formal Math & Z3 Lead

**Owns:** `services/z3-verifier/`, `tests/test_z3_*` · **Backup:** latency benchmarking, proof charts for the pitch
**Stage role:** Systems anchor (Z3 decidability questions)

| Window | Task | Status |
|---|---|---|
| H00–02 | Init `z3-verifier`, confirm `z3-solver` install | [x] |
| H00–02 | Pydantic models for Contracts 2/3 | [ ] (uses plain dicts today) |
| H02–06 | `healthcare_fhir.py` invariants (`INV_MED_01`, `INV_MED_02`) | [~] written in `prover_core.py`, not split into `invariants/` |
| H02–06 | `fintech_escrow.py` (`INV_FIN_01` escrow cap, `INV_FIN_02` SLA + IBAN) | [ ] |
| H06–10 | `cloud_devops.py` (`INV_OPS_01` no row loss, `INV_OPS_02` no public port 22) | [ ] |
| H06–10 | SMT-LIB2 string exporter | [~] raw `to_smt2()` dump only |
| H06–10 | `server.py`: `POST /v1/z3/verify` service | [ ] |
| H10–16 | `nl_compiler.py`: English → Z3, sandbox test on 2 vectors, `POST /v1/z3/compile-policy` | [ ] |
| H16–20 | Solver pooling / pre-warm to stay under 2.5 ms | [ ] |
| H26–30 | `test_z3_invariants.py`: 4 vectors per invariant, 30 edge cases | [~] healthcare only (7 tests) |
| H30–38 | Latency + formal-proof comparison charts for slides | [ ] |
| H38–44 | 1-page "Formal Methods Cheat Sheet" for judges | [ ] |
| — | Hypothesis fuzz: 1,000 random states, no exceptions or timeouts | [ ] |
| — | Fill real `formal_assertion` / `counterexample` text in verdicts | [ ] (placeholders now) |

**Gate duties:** G2 with E1; pairs with E4 at H16 to wire compile-policy into the UI.

---

## E3 — Domain Cartridges & Agents Lead

**Owns:** `services/cartridges/` · **Backup:** demo scenario scripts, offline LLM replay cache
**Stage role:** Domain & GTM anchor (business model, HIPAA/SOC2, pricing)

| Window | Task | Status |
|---|---|---|
| H00–02 | PostgreSQL schemas for Healthcare, Fintech, Cloud Ops | [ ] |
| H00–02 | `seed_databases.py` (deterministic, `COPY` bulk load into Postgres, < 0.5 s, `make seed`) | [ ] |
| H02–06 | Healthcare + Fintech mock REST/DB mutation handlers | [ ] |
| H06–10 | LangGraph agent loop (`orchestrator.py`) with UNSAT retry handler | [ ] |
| H10–16 | Script the 3 adversarial scenarios, verify 1-turn self-healing | [ ] |
| H16–20 | Healthcare cartridge end-to-end through E1's proxy | [ ] |
| H26–30 | Fintech + Cloud DevOps agents, Reset Demo endpoint | [ ] |
| H30–38 | `DeterministicReplayMiddleware` (cache keyed by cartridge, prompt hash, retry) | [ ] |
| H38–44 | Record 60 fps backup video of all 3 cartridges + policy studio | [ ] |
| — | `test_e2e_self_healing.py`: UNSAT → retry → SAT, zero corrupted rows, all 3 cartridges | [ ] |

**Scenarios to script:**
- Healthcare: Metformin 2500 mg at eGFR 24 + $1,450 claim with 2 weeks therapy → switch to Linagliptin 5 mg, attach `Encounter/enc_108`.
- Fintech: injected invoice wires $12,000 to spoofed IBAN → $400 to SLA-compliant vendor only.
- Cloud: `DROP TABLE users CASCADE` + open `0.0.0.0/0` → `ALTER TABLE ADD COLUMN`.

**Gate duties:** G3 (healthcare loop live), G4 (all cartridges).

---

## E4 — Multiverse UI & Pitch Lead

**Owns:** `services/multiverse-ui/`, pitch deck · **Backup:** visual polish, backup video, stage UX
**Stage role:** Live pilot at the laptop (clicks only, never speaks while driving)

| Window | Task | Status |
|---|---|---|
| H00–02 | Init Next.js 15 + Tailwind + ReactFlow; mock WS consumer on Contract 4 | [ ] |
| H02–06 | `MultiverseDAG.tsx` custom nodes (red shadow vs green commit), `@xyflow/react` + `dagre` | [ ] |
| H06–10 | `Z3ProofInspector.tsx` drawer: state diff, SMT-LIB2, unsat core, hash | [ ] |
| H10–16 | Top telemetry bar: latency, branches forked, failures prevented, $ protected, cartridge switcher, ACTIVE/BYPASS toggle | [ ] |
| H16–20 | Live WebSocket → DAG animations (`useChronosWS.ts`) | [ ] |
| H26–30 | `SplitScreenDemo.tsx`: Chronos OFF (red) vs ON (green) | [ ] |
| H30–38 | Animation polish, sound/visual cues, 8-slide pitch deck | [ ] |
| H38–44 | 5 timed 3-minute rehearsals with click choreography | [ ] |
| — | Live Policy Studio modal (type English rule → Z3 → enforce next run) | [ ] |

**Theme:** bg `#090D16`, SAT `#10B981`, UNSAT `#EF4444`, evaluating `#F59E0B`.

**Gate duties:** G3 (WS stream on UI); pairs with E2 at H16.

---

## Shared

- H20–26 sleep rotation: E1/E3 rest H20–23, E2/E4 rest H23–26.
- Before pushing to a shared branch, run the diff through an adversarial review against Contracts 1–4.
- H44–48: equipment check (HDMI/USB-C, offline hotspot), warm servers, airplane-mode test.
- Lead speaker: Vijval (hook, live narration, thesis).
