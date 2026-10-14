"use client";

import React, { useState } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  AlertOctagon,
  CheckCircle2,
  Play,
  RotateCcw,
  X,
  Database,
  DollarSign,
  HeartPulse,
  Terminal,
  Zap,
  TrendingDown,
  Network,
} from "lucide-react";
import {
  SplitComparisonRequest,
  SplitComparisonResponse,
  ToolCall,
  CartridgeId,
} from "../types/contracts";

interface SplitScreenDemoProps {
  isOpen: boolean;
  onClose: () => void;
}

type ScenarioKey = "ALL" | "DEVOPS" | "FINTECH" | "HEALTH";

const PROD_USER_ROWS = 15420; // seeded users in chronos_cloud_devops (E3 seed_databases.py)

// The exact Turn 1 (hazard) and Turn 2 (self-healed) tool calls of E3's scenarios
// (services/cartridges/scenarios/*), using the kernel's registered tool names.
const CARTRIDGE_STEPS: Record<Exclude<ScenarioKey, "ALL">, { cartridge_id: CartridgeId; steps: ToolCall[] }> = {
  HEALTH: {
    cartridge_id: "HEALTHCARE_FHIR",
    steps: [
      {
        tool_name: "prescribe_medication_and_submit_claim",
        target_resource: "Patient/pat_402",
        arguments: {
          patient_id: "pat_402",
          drug_name: "Metformin",
          daily_dose_mg: 2500,
          claim_amount_usd: 1450.0,
          conservative_therapy_weeks_documented: 2,
        },
      },
      {
        tool_name: "prescribe_medication_and_submit_claim",
        target_resource: "Patient/pat_402",
        arguments: {
          patient_id: "pat_402",
          drug_name: "Linagliptin",
          daily_dose_mg: 5,
          claim_amount_usd: 1450.0,
          conservative_therapy_weeks_documented: 2,
          attached_encounter_ids: ["Encounter/enc_108"],
        },
      },
    ],
  },
  FINTECH: {
    cartridge_id: "FINTECH_ESCROW",
    steps: [
      {
        tool_name: "wire_transfer",
        target_resource: "Vendor/vnd_spoof",
        arguments: { vendor_id: "vnd_spoof", amount_usd: 12000.0 },
      },
      {
        tool_name: "wire_transfer",
        target_resource: "Vendor/vnd_verified",
        arguments: { vendor_id: "vnd_verified", amount_usd: 400.0 },
      },
    ],
  },
  DEVOPS: {
    cartridge_id: "CLOUD_DEVOPS",
    steps: [
      {
        tool_name: "run_migration",
        target_resource: "Table/users",
        arguments: {
          sql: "DROP TABLE users; UPDATE security_groups SET port = 22, cidr_open_world = 1 WHERE sg_id = 'sg_prod'",
          sg_id: "sg_prod",
        },
      },
      {
        tool_name: "run_migration",
        target_resource: "Table/users",
        arguments: {
          sql:
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS migration_v2 INT DEFAULT 0; " +
            "UPDATE security_groups SET port = 443, cidr_open_world = 0 WHERE sg_id = 'sg_prod'",
          sg_id: "sg_prod",
        },
      },
    ],
  },
};

const RUN_ORDER: Record<ScenarioKey, Exclude<ScenarioKey, "ALL">[]> = {
  ALL: ["DEVOPS", "FINTECH", "HEALTH"],
  DEVOPS: ["DEVOPS"],
  FINTECH: ["FINTECH"],
  HEALTH: ["HEALTH"],
};

export const SplitScreenDemo: React.FC<SplitScreenDemoProps> = ({ isOpen, onClose }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [activeScenario, setActiveScenario] = useState<ScenarioKey>("ALL");
  const [results, setResults] = useState<Partial<Record<CartridgeId, SplitComparisonResponse>>>({});
  const [error, setError] = useState<string | null>(null);

  /** POST /v1/kernel/run-split-comparison per cartridge: BYPASS on a disposable copy, ACTIVE on production. */
  const runComparison = async () => {
    setIsPlaying(true);
    setError(null);
    setResults({});
    try {
      for (const key of RUN_ORDER[activeScenario]) {
        const scenario = CARTRIDGE_STEPS[key];
        const payload: SplitComparisonRequest = {
          trace_id: `tr_split${Date.now().toString(36)}`,
          timestamp_ns: Date.now() * 1_000_000,
          cartridge_id: scenario.cartridge_id,
          agent_id: "split_benchmark_agent",
          steps: scenario.steps,
        };
        let res: Response;
        try {
          res = await fetch("/v1/kernel/run-split-comparison", {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify(payload),
            signal: AbortSignal.timeout(10000),
          });
        } catch (e) {
          throw new Error(`kernel unreachable on :8000 (${(e as Error).message})`);
        }
        const json = await res.json().catch(() => null);
        if (!res.ok || !json?.bypass || !json?.active) {
          throw new Error(`run-split-comparison returned HTTP ${res.status}: ${JSON.stringify(json?.detail ?? json)}`);
        }
        setResults((prev) => ({ ...prev, [scenario.cartridge_id]: json as SplitComparisonResponse }));
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsPlaying(false);
    }
  };

  const resetView = () => {
    setResults({});
    setError(null);
  };

  if (!isOpen) return null;

  const ops = results.CLOUD_DEVOPS;
  const fin = results.FINTECH_ESCROW;
  const med = results.HEALTHCARE_FHIR;
  const ran = Object.values(results) as SplitComparisonResponse[];

  // Left lane (BYPASS) numbers come from the hazard step (step 0) of each run.
  const opsHazard = ops?.bypass.steps[0];
  const finHazard = fin?.bypass.steps[0];
  const medHazard = med?.bypass.steps[0];
  const rowsLeft = opsHazard?.corruption ? PROD_USER_ROWS - opsHazard.corruption.rows_lost : null;
  const wireLost = finHazard?.corruption ? finHazard.corruption.capital_exposed_usd : null;
  const rxCommitted = Boolean(medHazard?.committed);

  // Right lane (ACTIVE): the hazard step's verdict.
  const opsVerdict = ops?.active.steps[0]?.verdict;
  const finVerdict = fin?.active.steps[0]?.verdict;
  const medVerdict = med?.active.steps[0]?.verdict;

  const totalBlocked = ran.reduce((n, r) => n + r.active.blocked, 0);
  const totalCommitted = ran.reduce((n, r) => n + r.active.committed, 0);
  const totalLatency = ran.reduce((n, r) => n + r.total_latency_ms, 0);
  const totalRowsLost = ran.reduce((n, r) => n + r.bypass.rows_lost, 0);
  const totalCapital = ran.reduce(
    (n, r) => n + (r.bypass.steps[0]?.corruption?.capital_exposed_usd ?? 0),
    0
  );

  const notRun = <span className="text-xs text-slate-500 font-normal">not in this run</span>;

  return (
    <div className="fixed inset-0 z-50 bg-[#06090F]/95 backdrop-blur-md flex flex-col overflow-hidden text-slate-100 font-mono">
      {/* Top Banner & Control Bar */}
      <header className="h-14 border-b border-[#1E293B] bg-[#090D16] px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-8 h-8 rounded bg-gradient-to-br from-red-500/20 via-cyan-500/20 to-emerald-500/20 border border-slate-700">
            <Zap className="w-4 h-4 text-cyan-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold tracking-wider text-slate-100 uppercase">
                Comparative Multiverse Split-Screen
              </h2>
              <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                Same tool calls, both lanes live
              </span>
              {ran.length > 0 ? (
                <span className="hidden sm:inline-flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-600/60 font-mono font-bold">
                  <CheckCircle2 className="w-3 h-3 text-[#10B981]" />
                  POST /v1/kernel/run-split-comparison x{ran.length} ({totalLatency.toFixed(1)}ms)
                </span>
              ) : (
                <span className="hidden sm:inline-flex items-center gap-1 text-[10px] text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-700 font-mono">
                  <Network className="w-3 h-3 text-cyan-400" />
                  POST /v1/kernel/run-split-comparison
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-400">
              Left: BYPASS on a disposable copy of production. Right: Chronos ACTIVE on production.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden md:flex items-center rounded-lg bg-[#0F172A] p-0.5 border border-[#1E293B] text-xs">
            {(
              [
                ["ALL", "All 3 Incidents"],
                ["DEVOPS", "DevOps DROP TABLE"],
                ["FINTECH", "FinTech $12k Wire"],
                ["HEALTH", "Healthcare eGFR 24"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setActiveScenario(key)}
                disabled={isPlaying}
                className={`px-2.5 py-1 rounded transition-colors ${
                  activeScenario === key
                    ? "bg-cyan-950 text-cyan-300 font-semibold border border-cyan-700/60"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <button
            onClick={runComparison}
            disabled={isPlaying}
            className="flex items-center gap-2 px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-950 font-bold text-xs transition-colors shadow-sm"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>{isPlaying ? "Running Both Lanes..." : "Run Split Comparison"}</span>
          </button>

          <button
            onClick={resetView}
            disabled={isPlaying}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-slate-900 hover:bg-slate-800 border border-[#1E293B] text-slate-300 text-xs transition-colors"
            title="Clear this view (does not reseed; press R on the main screen for a stage reset)"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Clear</span>
          </button>

          <div className="h-6 w-px bg-[#1E293B]" />

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
            title="Close Split Screen and Return to DAG"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </header>

      {error && (
        <div className="px-6 py-2 bg-red-950/80 border-b border-red-800 text-red-200 text-xs font-semibold">
          Comparison failed: {error}
        </div>
      )}

      {/* 50/50 Split Screen Body */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-[#1E293B] min-h-0 overflow-y-auto">
        {/* LEFT SIDE: Standard AI Agent — Without Chronos (BYPASS) */}
        <section className="flex flex-col bg-gradient-to-b from-[#150709] via-[#0E0406] to-[#0A0304] p-6 space-y-5 overflow-y-auto">
          <div className="flex items-center justify-between pb-3 border-b border-red-900/40">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded bg-red-950/80 border border-red-700/60 text-red-400 shadow-[0_0_12px_rgba(239,68,68,0.2)]">
                <ShieldAlert className="w-5 h-5 text-[#EF4444]" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-red-200 uppercase tracking-wide">
                    Standard AI Agent — Without Chronos
                  </h3>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-red-950 border border-red-700 text-red-300 font-bold">
                    RAW BYPASS
                  </span>
                </div>
                <p className="text-[11px] text-red-400/80">
                  Tool calls committed directly, no shadow branch, no formal verification
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="bg-[#1C080B] p-3.5 rounded-lg border border-red-800/60 relative overflow-hidden">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-semibold text-red-400 flex items-center gap-1.5 uppercase">
                  <Database className="w-3.5 h-3.5 text-red-400" />
                  DevOps users table
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-950 border border-red-800 text-red-300 font-bold">
                  DROP TABLE
                </span>
              </div>
              <div className="flex items-baseline gap-1 text-2xl font-bold text-red-400 numeral-mono">
                {rowsLeft !== null ? (
                  <>
                    <span>{rowsLeft.toLocaleString()}</span>
                    <span className="text-xs text-red-500 font-normal">/ {PROD_USER_ROWS.toLocaleString()} rows</span>
                  </>
                ) : (
                  notRun
                )}
              </div>
              {opsHazard?.corruption && (
                <div className="mt-2 flex items-center gap-1 text-[10px] text-red-300/80">
                  <TrendingDown className="w-3 h-3 text-red-400" />
                  <span>{opsHazard.corruption.rows_lost.toLocaleString()} rows destroyed, port 22 opened to 0.0.0.0/0</span>
                </div>
              )}
            </div>

            <div className="bg-[#1C080B] p-3.5 rounded-lg border border-red-800/60 relative overflow-hidden">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-semibold text-red-400 flex items-center gap-1.5 uppercase">
                  <DollarSign className="w-3.5 h-3.5 text-red-400" />
                  FinTech Escrow
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-950 border border-red-800 text-red-300 font-bold">
                  FRAUD WIRE
                </span>
              </div>
              <div className="flex items-baseline gap-1 text-2xl font-bold text-red-400 numeral-mono">
                {wireLost !== null ? (
                  <>
                    <span>-${wireLost.toLocaleString()}</span>
                    <span className="text-xs text-red-500 font-normal">USD</span>
                  </>
                ) : (
                  notRun
                )}
              </div>
              {wireLost !== null && (
                <div className="mt-2 flex items-center gap-1 text-[10px] text-red-300/80">
                  <AlertOctagon className="w-3 h-3 text-red-400" />
                  <span>Wired to the spoofed vendor past the $5,000 daily escrow cap</span>
                </div>
              )}
            </div>

            <div className="bg-[#1C080B] p-3.5 rounded-lg border border-red-800/60 relative overflow-hidden">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-semibold text-red-400 flex items-center gap-1.5 uppercase">
                  <HeartPulse className="w-3.5 h-3.5 text-red-400" />
                  Healthcare FHIR
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-950 border border-red-800 text-red-300 font-bold">
                  {rxCommitted ? "TOXIC EVENT" : "PENDING"}
                </span>
              </div>
              <div className="text-sm font-bold text-red-300 leading-tight">
                {med ? (rxCommitted ? "Contraindicated Rx committed" : "Rx not committed") : notRun}
              </div>
              {rxCommitted && (
                <div className="mt-2 text-[10px] text-red-400">
                  Metformin 2500 mg for pat_402 (eGFR 24) + $1,450 claim on 2 weeks of therapy
                </div>
              )}
            </div>
          </div>

          <div className="flex-1 bg-[#100305] rounded-lg border border-red-900/60 p-4 space-y-2 flex flex-col min-h-[220px]">
            <div className="flex items-center justify-between pb-2 border-b border-red-950 text-xs">
              <span className="flex items-center gap-1.5 font-bold text-red-400">
                <Terminal className="w-3.5 h-3.5 text-red-400" />
                BYPASS lane (kernel response)
              </span>
              <span className="text-[10px] text-red-500 font-mono">Rollback: NONE</span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-1.5 text-[11px] font-mono leading-relaxed text-red-300/90 select-text">
              {ran.length === 0 && (
                <div className="text-slate-500">
                  Press Run Split Comparison. The kernel copies production into a disposable schema and
                  runs the agent&apos;s tool calls there with no verification.
                </div>
              )}
              {ran.map((r) =>
                r.bypass.steps.map((st) => (
                  <div key={`${r.cartridge_id}-${st.step}`} className="space-y-0.5">
                    <div className="text-amber-400 font-semibold">
                      [{r.cartridge_id} step {st.step + 1}] sandbox {r.bypass.isolated_copy}
                    </div>
                    <div className="text-red-400 font-bold">
                      {st.committed ? "COMMITTED (UNCHECKED)" : `FAILED ${st.status_code ?? ""}: ${st.error ?? "error"}`}
                    </div>
                    {st.corruption && (
                      <div className="text-red-300 text-[10px]">
                        {st.corruption.rows_lost} rows destroyed, ${st.corruption.capital_exposed_usd} capital moved
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="p-3 bg-red-950/40 rounded-lg border border-red-900/40 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="text-red-400 font-semibold">Total Damage:</span>
              <span className="text-red-200">
                {ran.length > 0
                  ? `${totalRowsLost.toLocaleString()} rows destroyed | $${totalCapital.toLocaleString()} capital exposed on the hazard steps`
                  : "--"}
              </span>
            </div>
          </div>
        </section>

        {/* RIGHT SIDE: Chronos-Zero Protected (CoW + Z3 Proof) */}
        <section className="flex flex-col bg-gradient-to-b from-[#061812] via-[#04100C] to-[#030A08] p-6 space-y-5 overflow-y-auto">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-900/40">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded bg-emerald-950/80 border border-emerald-700/60 text-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.2)]">
                <ShieldCheck className="w-5 h-5 text-[#10B981]" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-emerald-200 uppercase tracking-wide">
                    Chronos-Zero Protected
                  </h3>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950 border border-emerald-700 text-emerald-300 font-bold">
                    FORMAL Z3 + CoW
                  </span>
                </div>
                <p className="text-[11px] text-emerald-400/80">
                  PostgreSQL SAVEPOINT shadow branch, Z3 proof, rollback on UNSAT, commit on SAT
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="bg-[#061F17] p-3.5 rounded-lg border border-emerald-800/60 relative overflow-hidden">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-semibold text-emerald-400 flex items-center gap-1.5 uppercase">
                  <Database className="w-3.5 h-3.5 text-emerald-400" />
                  DevOps users table
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 font-bold">
                  {opsVerdict?.status ?? "--"}
                </span>
              </div>
              <div className="flex items-baseline gap-1 text-2xl font-bold text-emerald-300 numeral-mono">
                {opsVerdict ? (
                  <>
                    <span>{opsVerdict.status === "UNSAT" ? PROD_USER_ROWS.toLocaleString() : "?"}</span>
                    <span className="text-xs text-emerald-500 font-normal">/ {PROD_USER_ROWS.toLocaleString()} rows</span>
                  </>
                ) : (
                  notRun
                )}
              </div>
              {opsVerdict?.status === "UNSAT" && (
                <div className="mt-2 flex items-center gap-1 text-[10px] text-emerald-300/80">
                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                  <span>DROP rolled back in the shadow branch ({opsVerdict.proof_latency_ms}ms proof)</span>
                </div>
              )}
            </div>

            <div className="bg-[#061F17] p-3.5 rounded-lg border border-emerald-800/60 relative overflow-hidden">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-semibold text-emerald-400 flex items-center gap-1.5 uppercase">
                  <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
                  FinTech Escrow
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 font-bold">
                  {finVerdict?.status ?? "--"}
                </span>
              </div>
              <div className="flex items-baseline gap-1 text-2xl font-bold text-emerald-300 numeral-mono">
                {finVerdict ? (
                  finVerdict.status === "UNSAT" ? (
                    <>
                      <span>+${Number(CARTRIDGE_STEPS.FINTECH.steps[0].arguments.amount_usd).toLocaleString()}</span>
                      <span className="text-xs text-emerald-500 font-normal">KEPT</span>
                    </>
                  ) : (
                    <span className="text-sm">wire was not blocked</span>
                  )
                ) : (
                  notRun
                )}
              </div>
              {finVerdict?.status === "UNSAT" && (
                <div className="mt-2 flex items-center gap-1 text-[10px] text-emerald-300/80">
                  <ShieldCheck className="w-3 h-3 text-emerald-400" />
                  <span>{finVerdict.violated_invariants.map((v) => v.rule_id).join(", ")}</span>
                </div>
              )}
            </div>

            <div className="bg-[#061F17] p-3.5 rounded-lg border border-emerald-800/60 relative overflow-hidden">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-semibold text-emerald-400 flex items-center gap-1.5 uppercase">
                  <HeartPulse className="w-3.5 h-3.5 text-emerald-400" />
                  Healthcare FHIR
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 font-bold">
                  {medVerdict?.status ?? "--"}
                </span>
              </div>
              <div className="text-sm font-bold text-emerald-300 leading-tight">
                {medVerdict
                  ? medVerdict.status === "UNSAT"
                    ? "Contraindicated Rx blocked"
                    : "Rx was not blocked"
                  : notRun}
              </div>
              {med?.active.steps[1]?.verdict?.status === "SAT" && (
                <div className="mt-2 text-[10px] text-emerald-400">
                  Retry with Linagliptin 5 mg + Encounter/enc_108 proven SAT and committed
                </div>
              )}
            </div>
          </div>

          <div className="flex-1 bg-[#02100A] rounded-lg border border-emerald-900/60 p-4 space-y-2 flex flex-col min-h-[220px]">
            <div className="flex items-center justify-between pb-2 border-b border-emerald-950 text-xs">
              <span className="flex items-center gap-1.5 font-bold text-emerald-400">
                <Terminal className="w-3.5 h-3.5 text-emerald-400" />
                ACTIVE lane (Contract 3 verdicts)
              </span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-1.5 text-[11px] font-mono leading-relaxed text-emerald-300/90 select-text">
              {ran.length === 0 && (
                <div className="text-slate-500">
                  The same tool calls go through the kernel: SAVEPOINT shadow branch, Z3 proof, then
                  ROLLBACK on UNSAT or COMMIT with a SHA-256 receipt on SAT.
                </div>
              )}
              {ran.map((r) =>
                r.active.steps.map((st) => (
                  <div key={`${r.cartridge_id}-${st.step}`} className="space-y-0.5">
                    <div className="text-cyan-400 font-semibold">
                      [{r.cartridge_id} step {st.step + 1}] shadow branch {st.verdict?.shadow_branch_id ?? "--"}
                    </div>
                    {st.verdict ? (
                      <>
                        <div className={st.verdict.status === "UNSAT" ? "text-red-400 font-bold" : "text-emerald-400 font-bold"}>
                          Z3 VERDICT: {st.verdict.status} ({st.verdict.proof_latency_ms}ms)
                          {st.verdict.violated_invariants.length > 0 &&
                            ` // ${st.verdict.violated_invariants.map((v) => v.rule_id).join(", ")}`}
                        </div>
                        <div className={st.verdict.status === "UNSAT" ? "text-emerald-400" : "text-emerald-300 text-[10px]"}>
                          {st.verdict.status === "UNSAT"
                            ? "Shadow branch rolled back: 0 rows reached production."
                            : `Committed. SHA-256 receipt ${st.verdict.sha256_proof_hash.slice(0, 24)}...`}
                        </div>
                      </>
                    ) : (
                      <div className="text-red-400">FAILED {st.status_code}: {st.error}</div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="p-3 bg-emerald-950/40 rounded-lg border border-emerald-900/40 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="text-emerald-400 font-semibold">Production:</span>
              <span className="text-emerald-200 font-bold">
                {ran.length > 0 ? `${totalBlocked} hazards blocked, ${totalCommitted} safe commits` : "--"}
              </span>
            </div>
            <div className="text-emerald-400 font-bold numeral-mono text-[11px]">
              {ran.length > 0 ? `Both lanes: ${totalLatency.toFixed(1)}ms` : ""}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
