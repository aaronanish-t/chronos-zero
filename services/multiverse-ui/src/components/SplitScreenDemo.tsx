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
} from "lucide-react";

interface SplitScreenDemoProps {
  isOpen: boolean;
  onClose: () => void;
}

type DemoStep = "IDLE" | "TOOL_INIT" | "UNPROTECTED_FAULT" | "CHRONOS_INTERCEPT" | "CHRONOS_REWIND_HEAL" | "COMPLETED";

export const SplitScreenDemo: React.FC<SplitScreenDemoProps> = ({
  isOpen,
  onClose,
}) => {
  const [currentStep, setCurrentStep] = useState<DemoStep>("COMPLETED");
  const [isPlaying, setIsPlaying] = useState(false);
  const [activeScenario, setActiveScenario] = useState<"ALL" | "DEVOPS" | "FINTECH" | "HEALTH">("ALL");

  // Simulated metrics state for live animation
  const [unprotectedRows, setUnprotectedRows] = useState(0);
  const [unprotectedWireLost, setUnprotectedWireLost] = useState(12000);
  const [unprotectedClinicalHazard, setUnprotectedClinicalHazard] = useState(true);

  const [chronosRows, setChronosRows] = useState(15420);
  const [chronosWireProtected, setChronosWireProtected] = useState(12000);
  const [chronosClinicalSafe, setChronosClinicalSafe] = useState(true);

  // Play animation through timeline
  const runSimulation = () => {
    setIsPlaying(true);
    setCurrentStep("TOOL_INIT");
    setUnprotectedRows(15420);
    setUnprotectedWireLost(0);
    setUnprotectedClinicalHazard(false);

    // Timeline sequence
    setTimeout(() => {
      setCurrentStep("UNPROTECTED_FAULT");
      // Animate database rows dropping
      let rows = 15420;
      const interval = setInterval(() => {
        rows = Math.max(0, rows - 1542);
        setUnprotectedRows(rows);
        if (rows <= 0) {
          clearInterval(interval);
          setUnprotectedWireLost(12000);
          setUnprotectedClinicalHazard(true);
        }
      }, 70);
    }, 1000);

    setTimeout(() => {
      setCurrentStep("CHRONOS_INTERCEPT");
    }, 2200);

    setTimeout(() => {
      setCurrentStep("CHRONOS_REWIND_HEAL");
    }, 3400);

    setTimeout(() => {
      setCurrentStep("COMPLETED");
      setIsPlaying(false);
    }, 4500);
  };

  const resetSimulation = () => {
    setIsPlaying(false);
    setCurrentStep("COMPLETED");
    setUnprotectedRows(0);
    setUnprotectedWireLost(12000);
    setUnprotectedClinicalHazard(true);
    setChronosRows(15420);
    setChronosWireProtected(12000);
    setChronosClinicalSafe(true);
  };

  if (!isOpen) return null;

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
                50 / 50 Dual Reality View
              </span>
              <span className="hidden xl:inline-flex text-[10px] px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800/80 font-mono">
                Phase: {currentStep}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Direct Side-by-Side: Unprotected Production Failure vs. Chronos-Zero Formal CoW Shield
            </p>
          </div>
        </div>

        {/* Central Controls: Scenario Switcher & Play Simulation */}
        <div className="flex items-center gap-3">
          <div className="hidden md:flex items-center rounded-lg bg-[#0F172A] p-0.5 border border-[#1E293B] text-xs">
            <button
              onClick={() => setActiveScenario("ALL")}
              className={`px-2.5 py-1 rounded transition-colors ${
                activeScenario === "ALL"
                  ? "bg-cyan-950 text-cyan-300 font-semibold border border-cyan-700/60"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              All 3 Incidents
            </button>
            <button
              onClick={() => setActiveScenario("DEVOPS")}
              className={`px-2.5 py-1 rounded transition-colors ${
                activeScenario === "DEVOPS"
                  ? "bg-cyan-950 text-cyan-300 font-semibold border border-cyan-700/60"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              DevOps Drop
            </button>
            <button
              onClick={() => setActiveScenario("FINTECH")}
              className={`px-2.5 py-1 rounded transition-colors ${
                activeScenario === "FINTECH"
                  ? "bg-cyan-950 text-cyan-300 font-semibold border border-cyan-700/60"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              FinTech $12k
            </button>
            <button
              onClick={() => setActiveScenario("HEALTH")}
              className={`px-2.5 py-1 rounded transition-colors ${
                activeScenario === "HEALTH"
                  ? "bg-cyan-950 text-cyan-300 font-semibold border border-cyan-700/60"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Healthcare eGFR
            </button>
          </div>

          <button
            onClick={runSimulation}
            disabled={isPlaying}
            className="flex items-center gap-2 px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-950 font-bold text-xs transition-colors shadow-sm"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>{isPlaying ? "Simulating Timeline..." : "Run Split Benchmark"}</span>
          </button>

          <button
            onClick={resetSimulation}
            disabled={isPlaying}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-slate-900 hover:bg-slate-800 border border-[#1E293B] text-slate-300 text-xs transition-colors"
            title="Reset to default comparison state"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Reset</span>
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

      {/* 50/50 Split Screen Body */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-[#1E293B] min-h-0 overflow-y-auto">
        {/* ========================================================
            LEFT SIDE: Standard AI Agent — Without Chronos (Bypass)
            ======================================================== */}
        <section className="flex flex-col bg-gradient-to-b from-[#150709] via-[#0E0406] to-[#0A0304] p-6 space-y-5 overflow-y-auto">
          {/* Header Banner */}
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
                  <span className="text-[10px] px-2 py-0.5 rounded bg-red-950 border border-red-700 text-red-300 animate-pulse font-bold">
                    RAW BYPASS
                  </span>
                </div>
                <p className="text-[11px] text-red-400/80">
                  Tool calls directly committed to production disk without formal verification
                </p>
              </div>
            </div>

            <div className="text-right">
              <span className="text-[10px] uppercase font-bold text-red-400">Status</span>
              <p className="text-xs text-red-300 font-bold tracking-wider">
                CATASTROPHIC FAILURE
              </p>
            </div>
          </div>

          {/* 3 Live Catastrophe Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* 1. Database Rows Dropping 15,420 -> 0 */}
            <div className="bg-[#1C080B] p-3.5 rounded-lg border border-red-800/60 relative overflow-hidden">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-semibold text-red-400 flex items-center gap-1.5 uppercase">
                  <Database className="w-3.5 h-3.5 text-red-400" />
                  DevOps DB State
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-950 border border-red-800 text-red-300 font-bold">
                  DROP TABLE
                </span>
              </div>
              <div className="flex items-baseline gap-1 text-2xl font-bold text-red-400 numeral-mono">
                <span>{unprotectedRows.toLocaleString()}</span>
                <span className="text-xs text-red-500 font-normal">/ 15,420 rows</span>
              </div>
              <div className="mt-2 flex items-center gap-1 text-[10px] text-red-300/80">
                <TrendingDown className="w-3 h-3 text-red-400" />
                <span>15,420 rows dropped to 0 (Permanent Loss)</span>
              </div>
            </div>

            {/* 2. $12,000 Wire Lost */}
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
                <span>-${unprotectedWireLost.toLocaleString()}</span>
                <span className="text-xs text-red-500 font-normal">USD</span>
              </div>
              <div className="mt-2 flex items-center gap-1 text-[10px] text-red-300/80">
                <AlertOctagon className="w-3 h-3 text-red-400" />
                <span>$12,000 wire lost to unverified offshore IBAN</span>
              </div>
            </div>

            {/* 3. Contraindicated Prescription Committed */}
            <div className="bg-[#1C080B] p-3.5 rounded-lg border border-red-800/60 relative overflow-hidden">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-semibold text-red-400 flex items-center gap-1.5 uppercase">
                  <HeartPulse className="w-3.5 h-3.5 text-red-400" />
                  Healthcare FHIR
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-950 border border-red-800 text-red-300 font-bold">
                  {unprotectedClinicalHazard ? "TOXIC EVENT" : "PENDING ORDER"}
                </span>
              </div>
              <div className="text-sm font-bold text-red-300 leading-tight">
                {unprotectedClinicalHazard ? "Contraindicated Rx Committed" : "Medication Order Pending"}
              </div>
              <div className="mt-2 flex items-center gap-1 text-[10px] text-red-400">
                <span>{unprotectedClinicalHazard ? "Ketorolac 30mg IV committed to eGFR 18 patient" : "Checking patient medical record..."}</span>
              </div>
            </div>
          </div>

          {/* Red Terminal Logs */}
          <div className="flex-1 bg-[#100305] rounded-lg border border-red-900/60 p-4 space-y-2 flex flex-col min-h-[220px]">
            <div className="flex items-center justify-between pb-2 border-b border-red-950 text-xs">
              <span className="flex items-center gap-1.5 font-bold text-red-400">
                <Terminal className="w-3.5 h-3.5 text-red-400" />
                Production Terminal Output [Raw Disk Execution]
              </span>
              <span className="text-[10px] text-red-500 font-mono">Rollback: NONE</span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-1.5 text-[11px] font-mono leading-relaxed text-red-300/90 select-text">
              <div className="text-slate-500">[00:00:00.100] Autonomous agent initiated multi-step workflow...</div>
              <div className="text-amber-400">
                [00:00:00.450] TOOL CALL: execute_migration(&quot;DROP TABLE users CASCADE;&quot;)
              </div>
              <div className="text-red-500 font-bold">
                [00:00:00.452] EXECUTING DIRECT SQLITE DISK WRITE (NO SHADOW CoW)
              </div>
              <div className="text-red-400">
                [00:00:00.455] SQLITE SUCCESS: 15,420 user records dropped. WAL checkpoint flushed.
              </div>
              <div className="text-amber-400">
                [00:00:00.680] TOOL CALL: wire_transfer(recipient=&quot;GB99UNVERIFIED&quot;, amount=12000.00)
              </div>
              <div className="text-red-500 font-bold">
                [00:00:00.683] BANK GATEWAY: $12,000 wire dispatched. Funds left escrow account.
              </div>
              <div className="text-amber-400">
                [00:00:00.910] TOOL CALL: create_medication_order(drug=&quot;Ketorolac&quot;, dose=30, egfr=18)
              </div>
              <div className="text-red-400">
                [00:00:00.914] FHIR SERVER: MedicationOrder/MO-9912 saved to Patient/P-401. Status: ACTIVE.
              </div>
              <div className="p-2 rounded bg-red-950/80 border border-red-800 text-red-200 mt-2 font-bold text-xs">
                FATAL ALERT: 3 Critical Invariants Violated. Irreversible production corruption committed. Rollback impossible.
              </div>
            </div>
          </div>

          {/* Left Summary Box */}
          <div className="p-3 bg-red-950/40 rounded-lg border border-red-900/40 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="text-red-400 font-semibold">Total Damage:</span>
              <span className="text-red-200">15,420 records destroyed | $12k wire lost | Patient in ICU</span>
            </div>
            <div className="text-red-400 font-bold numeral-mono text-[11px]">
              Recovery Time: ~48 hours
            </div>
          </div>
        </section>

        {/* ========================================================
            RIGHT SIDE: Chronos-Zero Protected (CoW + Z3 Proof)
            ======================================================== */}
        <section className="flex flex-col bg-gradient-to-b from-[#061812] via-[#04100C] to-[#030A08] p-6 space-y-5 overflow-y-auto">
          {/* Header Banner */}
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
                  Speculative fork on RAM disk -&gt; Verified via Z3 -&gt; Rewound in 0ms -&gt; Self-healed
                </p>
              </div>
            </div>

            <div className="text-right">
              <span className="text-[10px] uppercase font-bold text-emerald-400">Verdict</span>
              <p className="text-xs text-emerald-300 font-bold tracking-wider">
                100% PROVEN SAFE (SAT)
              </p>
            </div>
          </div>

          {/* 3 Resilience Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* 1. Database Rows Preserved */}
            <div className="bg-[#061F17] p-3.5 rounded-lg border border-emerald-800/60 relative overflow-hidden">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-semibold text-emerald-400 flex items-center gap-1.5 uppercase">
                  <Database className="w-3.5 h-3.5 text-emerald-400" />
                  DevOps DB State
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 font-bold">
                  0 DROPPED
                </span>
              </div>
              <div className="flex items-baseline gap-1 text-2xl font-bold text-emerald-300 numeral-mono">
                <span>{chronosRows.toLocaleString()}</span>
                <span className="text-xs text-emerald-500 font-normal">/ 15,420 rows</span>
              </div>
              <div className="mt-2 flex items-center gap-1 text-[10px] text-emerald-300/80">
                <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                <span>100% Preserved. DROP blocked in shadow branch.</span>
              </div>
            </div>

            {/* 2. $12,000 Wire Protected */}
            <div className="bg-[#061F17] p-3.5 rounded-lg border border-emerald-800/60 relative overflow-hidden">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-semibold text-emerald-400 flex items-center gap-1.5 uppercase">
                  <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
                  FinTech Escrow
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 font-bold">
                  SECURED
                </span>
              </div>
              <div className="flex items-baseline gap-1 text-2xl font-bold text-emerald-300 numeral-mono">
                <span>+${chronosWireProtected.toLocaleString()}</span>
                <span className="text-xs text-emerald-500 font-normal">SAVED</span>
              </div>
              <div className="mt-2 flex items-center gap-1 text-[10px] text-emerald-300/80">
                <ShieldCheck className="w-3 h-3 text-emerald-400" />
                <span>Rogue wire aborted. Escrow funds untouched.</span>
              </div>
            </div>

            {/* 3. Clinical Hazard Defused */}
            <div className="bg-[#061F17] p-3.5 rounded-lg border border-emerald-800/60 relative overflow-hidden">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-semibold text-emerald-400 flex items-center gap-1.5 uppercase">
                  <HeartPulse className="w-3.5 h-3.5 text-emerald-400" />
                  Healthcare FHIR
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 font-bold">
                  {chronosClinicalSafe ? "HEALED" : "INTERCEPTING"}
                </span>
              </div>
              <div className="text-sm font-bold text-emerald-300 leading-tight">
                {chronosClinicalSafe ? "Nephrotoxic Hazard Defused" : "Z3 Invariant Checking"}
              </div>
              <div className="mt-2 flex items-center gap-1 text-[10px] text-emerald-400">
                <span>{chronosClinicalSafe ? "Auto-switched to Acetaminophen 650mg (SAT proven)" : "Verifying contraindication with Z3 Prover..."}</span>
              </div>
            </div>
          </div>

          {/* Green Terminal Logs */}
          <div className="flex-1 bg-[#02100A] rounded-lg border border-emerald-900/60 p-4 space-y-2 flex flex-col min-h-[220px]">
            <div className="flex items-center justify-between pb-2 border-b border-emerald-950 text-xs">
              <span className="flex items-center gap-1.5 font-bold text-emerald-400">
                <Terminal className="w-3.5 h-3.5 text-emerald-400" />
                Chronos Kernel Proxy Interception Log
              </span>
              <span className="text-[10px] text-emerald-400 font-mono">Rewind Latency: 0.00ms</span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-1.5 text-[11px] font-mono leading-relaxed text-emerald-300/90 select-text">
              <div className="text-slate-500">[00:00:00.100] Intercepted tool call &apos;execute_migration&apos; in 0.38ms</div>
              <div className="text-cyan-400">
                [00:00:00.101] CoW RAM Disk Fork: SAVEPOINT cow_branch_7f82 pinned on /dev/shm (1.18ms)
              </div>
              <div className="text-cyan-300">
                [00:00:00.102] Applied mutation to isolated shadow branch. Extracted state diff.
              </div>
              <div className="text-amber-300">
                [00:00:00.103] Z3 Theorem Prover evaluated invariants in 1.64ms -&gt; Status: UNSAT!
              </div>
              <div className="text-red-400 font-semibold">
                [00:00:00.103] FAULT CAUGHT IN 3.2ms TOTAL: Violated &apos;INV_OPS_01_DESTRUCTIVE_DDL&apos;
              </div>
              <div className="text-emerald-400 font-bold">
                [00:00:00.103] CO-W REWIND EXECUTED: ROLLBACK TO cow_branch_7f82 in 0.00ms (0 bytes prod damage)
              </div>
              <div className="text-purple-300">
                [00:00:00.104] 1-Turn Self-Healing: Injected UnsatCore remediation hint into agent message history
              </div>
              <div className="text-cyan-400">
                [00:00:00.105] Agent corrective retry: archive_table_soft(&apos;users_archived_2026&apos;)
              </div>
              <div className="text-emerald-300 font-bold">
                [00:00:00.106] Shadow re-evaluation: Z3 PROVEN SAT! Committed to prod with Merkle receipt.
              </div>
              <div className="p-2 rounded bg-emerald-950/80 border border-emerald-800 text-emerald-200 mt-2 font-bold text-xs flex items-center justify-between">
                <span>CHRONOS RECEIPT: SHA-256 e8b29c0177... bound into tamper-evident Merkle log</span>
                <span className="text-[10px] text-emerald-400 font-mono">P50: 3.2ms</span>
              </div>
            </div>
          </div>

          {/* Right Summary Box */}
          <div className="p-3 bg-emerald-950/40 rounded-lg border border-emerald-900/40 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="text-emerald-400 font-semibold">Production Damage:</span>
              <span className="text-emerald-200 font-bold">0 BYTES (100% Formal Determinism)</span>
            </div>
            <div className="text-emerald-400 font-bold numeral-mono text-[11px]">
              Speedup vs LLM Guardrails: 453x Faster
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
