"use client";

import React, { useState } from "react";

interface ArchitectureViewProps {
  onLaunchConsole?: () => void;
}

export const ArchitectureView: React.FC<ArchitectureViewProps> = ({
  onLaunchConsole,
}) => {
  const [copiedCurl, setCopiedCurl] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<string | null>(null);

  const handleCopyCurl = () => {
    const cmd = `curl -X POST http://localhost:8000/v1/kernel/execute \\
  -H "Content-Type: application/json" \\
  -d '{"trace_id": "tr_demo_01", "cartridge_id": "CLOUD_DEVOPS", "chronos_mode": "ACTIVE", "tool_call": {"tool_name": "run_migration", "target_resource": "Table/users", "arguments": {"sql": "DROP TABLE users;"}}}'`;
    navigator.clipboard.writeText(cmd);
    setCopiedCurl(true);
    setTimeout(() => setCopiedCurl(false), 2000);
  };

  const handleRunVerify = () => {
    setIsVerifying(true);
    setVerifyResult(null);
    setTimeout(() => {
      setIsVerifying(false);
      setVerifyResult("SAT // 0.88ms (Receipt: 0x9c3d41e8...d84b)");
    }, 600);
  };

  return (
    <div className="flex-1 w-full overflow-y-auto bg-surface-container-lowest text-on-surface select-none pb-20">
      <div className="relative w-full max-w-[1240px] mx-auto px-margin-mobile lg:px-margin pt-space-xl">
        {/* Ambient Focal Glow Orbs */}
        <div className="absolute top-12 left-1/2 -translate-x-1/2 w-[720px] h-[340px] bg-primary/10 blur-[130px] rounded-full pointer-events-none -z-10" />
        <div className="absolute top-72 right-10 w-[420px] h-[260px] bg-secondary/10 blur-[110px] rounded-full pointer-events-none -z-10" />

        {/* 1. HERO SECTION */}
        <section className="flex flex-col items-center text-center max-w-[960px] mx-auto pt-6 pb-space-xl">
          {/* Announcement Pill Badge */}
          <div
            onClick={onLaunchConsole}
            className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-surface-container-high/70 backdrop-blur-md shadow-sm mb-space-lg group cursor-pointer hover:bg-surface-container-high transition-all"
          >
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-80" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
            </span>
            <span className="font-label-sm text-label-sm text-on-surface-variant font-medium tracking-wide">
              Formal Verification Meets Sub-Millisecond Database Rollbacks
            </span>
            <span className="material-symbols-outlined text-primary text-[14px] leading-none group-hover:translate-x-0.5 transition-transform">
              arrow_forward
            </span>
          </div>

          {/* Main High-Contrast Headline */}
          <h1 className="font-headline-xl text-headline-xl tracking-tight text-on-surface max-w-[880px] text-balance mb-space-md">
            Deterministic Safety for{" "}
            <span className="bg-gradient-to-r from-on-surface via-primary to-secondary bg-clip-text text-transparent">
              Autonomous AI Tools.
            </span>
          </h1>

          {/* Technical Sub-headline */}
          <p className="font-body-lg text-body-lg text-on-surface-variant max-w-[720px] text-balance mb-space-lg">
            Intervene before state commits. Chronos-Zero evaluates speculative AI
            transactions with sub-5ms Postgres Copy-on-Write shadow sandboxes
            and Microsoft Z3 SMT formal proofs. Zero leaks. Absolute
            mathematical reversibility.
          </p>

          {/* Minimalist Dual CTA */}
          <div className="flex flex-wrap items-center justify-center gap-space-md mb-space-xl">
            <button
              onClick={onLaunchConsole}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-primary text-on-primary font-label-md text-label-md font-semibold tracking-wide hover:bg-primary-fixed transition-all shadow-[0_0_24px_rgba(78,222,163,0.35)] active:scale-[0.99]"
            >
              <span className="material-symbols-outlined text-[18px]">
                play_circle
              </span>
              Launch Mission Control
            </button>
            <a
              href="#proof-ast"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-surface-container-high/80 text-on-surface hover:text-secondary font-label-md text-label-md font-medium tracking-wide backdrop-blur-md hover:bg-surface-container-highest transition-all shadow-sm"
            >
              <span className="material-symbols-outlined text-[18px]">
                terminal
              </span>
              Explore SMT Proof AST
            </a>
          </div>

          {/* Telemetry Strip: 4 Minimal Monospace Counters */}
          <div className="w-full grid grid-cols-2 md:grid-cols-4 gap-3 p-2 rounded-xl bg-surface-container-low/70 backdrop-blur-lg shadow-sm">
            <div className="flex flex-col items-center justify-center py-3.5 px-3 rounded-lg bg-surface-container-lowest/80">
              <div className="flex items-baseline gap-1">
                <span className="font-label-lg text-label-lg text-primary font-bold tabular-nums">
                  1.42
                </span>
                <span className="font-label-sm text-label-sm text-on-surface-variant">
                  ms
                </span>
              </div>
              <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider mt-0.5">
                Median Latency
              </span>
            </div>
            <div className="flex flex-col items-center justify-center py-3.5 px-3 rounded-lg bg-surface-container-lowest/80">
              <div className="flex items-baseline gap-1">
                <span className="font-label-lg text-label-lg text-secondary font-bold tabular-nums">
                  100%
                </span>
              </div>
              <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider mt-0.5">
                SAT Proof Invariants
              </span>
            </div>
            <div className="flex flex-col items-center justify-center py-3.5 px-3 rounded-lg bg-surface-container-lowest/80">
              <div className="flex items-baseline gap-1">
                <span className="font-label-lg text-label-lg text-primary font-bold tabular-nums">
                  0
                </span>
                <span className="font-label-sm text-label-sm text-on-surface-variant">
                  Bytes
                </span>
              </div>
              <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider mt-0.5">
                Prod Damage Allowed
              </span>
            </div>
            <div className="flex flex-col items-center justify-center py-3.5 px-3 rounded-lg bg-surface-container-lowest/80">
              <div className="flex items-baseline gap-1">
                <span className="font-label-lg text-label-lg text-secondary font-bold tabular-nums">
                  ~300x
                </span>
              </div>
              <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider mt-0.5">
                vs LLM Guardrails
              </span>
            </div>
          </div>
        </section>

        {/* 2. HERO 3D PERSPECTIVE MOCKUP PRESENTATION & TECHNICAL ARCHITECTURE */}
        <section className="relative w-full pt-4 pb-20 overflow-visible" id="tech-specs">
          {/* Floating Spatial Badges */}
          <div className="hidden lg:flex items-center gap-2 absolute top-12 left-4 z-20 px-3 py-1.5 rounded-lg bg-surface-container-high/90 backdrop-blur-xl shadow-xl -rotate-3 hover:rotate-0 transition-transform cursor-default">
            <span className="material-symbols-outlined text-secondary text-[16px]">
              database
            </span>
            <span className="font-label-sm text-label-sm text-on-surface font-mono">
              Postgres CoW Savepoint (&lt; 1.5ms)
            </span>
          </div>
          <div className="hidden lg:flex items-center gap-2 absolute top-4 right-12 z-20 px-3 py-1.5 rounded-lg bg-surface-container-high/90 backdrop-blur-xl shadow-xl rotate-3 hover:rotate-0 transition-transform cursor-default">
            <span className="material-symbols-outlined text-primary text-[16px]">
              verified
            </span>
            <span className="font-label-sm text-label-sm text-on-surface font-mono">
              Z3 SMT Formal Invariant (&lt; 2.5ms)
            </span>
          </div>
          <div className="hidden lg:flex items-center gap-2 absolute -bottom-6 left-16 z-20 px-3 py-1.5 rounded-lg bg-surface-container-high/90 backdrop-blur-xl shadow-xl rotate-2 hover:rotate-0 transition-transform cursor-default">
            <span className="material-symbols-outlined text-secondary-fixed text-[16px]">
              account_tree
            </span>
            <span className="font-label-sm text-label-sm text-on-surface font-mono">
              Merkle Leaf SHA-256 Verified
            </span>
          </div>

          {/* 3D Perspective Viewport Rig */}
          <div className="w-full [perspective:1200px] flex justify-center items-center">
            <div className="w-full max-w-[1120px] rounded-xl bg-surface-container-low/95 backdrop-blur-2xl shadow-[0_25px_70px_rgba(0,0,0,0.8),0_0_50px_rgba(78,222,163,0.12)] p-4 sm:p-6 transition-all duration-700 [transform:rotateX(10deg)_rotateY(-4deg)_rotateZ(1deg)] hover:[transform:rotateX(0deg)_rotateY(0deg)_rotateZ(0deg)] group border border-white/5">
              {/* Top Telemetry Command Strip */}
              <div className="flex flex-wrap items-center justify-between gap-3 pb-4 mb-5 border-b border-surface-variant/40">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-lowest">
                    <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
                    <span className="font-label-sm text-label-sm text-primary font-mono font-medium">
                      LIVE WS: CONNECTED
                    </span>
                  </div>
                  <span className="text-outline-variant font-label-sm text-label-sm">
                    |
                  </span>
                  <span className="font-label-sm text-label-sm text-on-surface-variant font-mono">
                    TX_EPOCH #98421.09
                  </span>
                </div>

                <div className="flex items-center gap-1.5 p-1 rounded-lg bg-surface-container-lowest">
                  <span className="px-2.5 py-0.5 rounded bg-surface-container text-primary font-label-sm text-label-sm font-semibold">
                    FHIR Renal
                  </span>
                  <span className="px-2.5 py-0.5 rounded text-on-surface-variant font-label-sm text-label-sm">
                    FinTech Escrow
                  </span>
                  <span className="px-2.5 py-0.5 rounded text-on-surface-variant font-label-sm text-label-sm">
                    Cloud DevOps
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span className="font-label-sm text-label-sm text-on-surface-variant font-mono">
                    GUARD:
                  </span>
                  <div className="flex items-center p-0.5 rounded bg-surface-container-lowest">
                    <span className="px-2 py-0.5 rounded bg-primary text-on-primary font-label-sm text-label-sm font-bold">
                      ACTIVE
                    </span>
                  </div>
                </div>
              </div>

              {/* Main Inside Split */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                {/* Multiverse DAG Canvas (Left 8 Cols) */}
                <div className="lg:col-span-8 flex flex-col p-5 rounded-lg bg-surface-container-lowest/90 relative overflow-hidden border border-white/5">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-secondary text-[18px]">
                        grain
                      </span>
                      <span className="font-label-md text-label-md text-on-surface font-semibold tracking-wide">
                        MULTIVERSE DAG STATE TREE
                      </span>
                    </div>
                    <span className="font-label-sm text-label-sm text-secondary font-mono">
                      CoW Branch: snapshot_0x3F01
                    </span>
                  </div>

                  <div className="relative w-full h-[280px] bg-surface-container-low/40 rounded-lg p-4 overflow-hidden flex flex-col justify-between">
                    <svg className="absolute inset-0 w-full h-full pointer-events-none stroke-current">
                      <path
                        className="text-primary/70"
                        d="M 80 140 C 180 140, 220 70, 340 70 L 460 70"
                        fill="none"
                        strokeDasharray="4 2"
                        strokeWidth="2"
                      />
                      <path
                        className="text-tertiary-container"
                        d="M 80 140 C 180 140, 220 210, 330 210 L 450 210"
                        fill="none"
                        strokeWidth="2"
                      />
                    </svg>

                    {/* Root Origin Node */}
                    <div className="absolute left-4 top-1/2 -translate-y-1/2 z-10 p-2.5 rounded bg-surface-container-high shadow-lg flex items-center gap-2 border border-white/5">
                      <span className="h-2.5 w-2.5 rounded-full bg-secondary shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
                      <div className="flex flex-col text-left">
                        <span className="font-label-sm text-label-sm text-on-surface font-bold">
                          ROOT_ORIGIN
                        </span>
                        <span className="font-label-sm text-[9px] text-on-surface-variant font-mono">
                          block_#84920
                        </span>
                      </div>
                    </div>

                    {/* Green Safe SAT Node */}
                    <div className="absolute left-[54%] top-[24%] -translate-y-1/2 z-10 p-3 rounded-lg bg-surface-container-high/90 shadow-lg max-w-[280px] border border-primary/30">
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="px-1.5 py-0.5 rounded bg-primary-container/20 text-primary font-label-sm text-[9px] font-bold">
                          Z3 PROVEN SAT
                        </span>
                        <span className="font-label-sm text-[10px] text-on-surface-variant font-mono">
                          1.12ms
                        </span>
                      </div>
                      <p className="font-label-sm text-label-sm text-on-surface font-mono truncate">
                        TX_COMMIT // 0x7f8a9...b401
                      </p>
                      <span className="font-label-sm text-[9px] text-primary flex items-center gap-1 mt-1">
                        <span className="material-symbols-outlined text-[11px]">
                          check
                        </span>{" "}
                        Verified Safe State
                      </span>
                    </div>

                    {/* Red UNSAT Branch */}
                    <div className="absolute left-[52%] bottom-[12%] z-10 p-3 rounded-lg bg-surface-container-high/90 shadow-lg max-w-[310px] border border-error/40">
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="px-1.5 py-0.5 rounded bg-error-container text-tertiary font-label-sm text-[9px] font-bold tracking-wider">
                          UNSAT — KILLED IN SHADOW
                        </span>
                        <span className="font-label-sm text-[10px] text-tertiary font-mono">
                          1.82ms
                        </span>
                      </div>
                      <p className="font-label-sm text-label-sm text-error font-mono font-medium truncate">
                        INV_MED_01_RENAL_SAFETY VIOLATION
                      </p>
                      <div className="flex items-center justify-between text-[10px] font-label-sm text-on-surface-variant mt-1.5 pt-1 border-t border-surface-variant/40">
                        <span className="text-tertiary flex items-center gap-1 font-mono">
                          <span className="material-symbols-outlined text-[12px]">
                            undo
                          </span>{" "}
                          0 Bytes Prod Damage
                        </span>
                        <span className="font-mono text-outline">
                          SHADOW ROLLBACK OK
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-3 text-on-surface-variant font-label-sm text-label-sm">
                    <span className="flex items-center gap-1.5 font-mono">
                      <span className="material-symbols-outlined text-primary text-[14px]">
                        bolt
                      </span>
                      Postgres Shadow Spawn: 0.41ms
                    </span>
                    <span className="font-mono text-secondary">
                      Z3 Solver Execution: 0.94ms
                    </span>
                    <span className="font-mono text-on-surface">Total: 1.35ms</span>
                  </div>
                </div>

                {/* Right Docked Z3 Proof Inspector */}
                <div className="lg:col-span-4 flex flex-col p-4 rounded-lg bg-surface-container-high/60 backdrop-blur-md border border-white/5">
                  <div className="flex items-center justify-between mb-3 pb-2 border-b border-surface-variant/40">
                    <div className="flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-primary text-[16px]">
                        fact_check
                      </span>
                      <span className="font-label-sm text-label-sm text-on-surface font-semibold">
                        Z3 PROOF INSPECTOR
                      </span>
                    </div>
                    <span className="px-1.5 py-0.5 rounded bg-surface-container text-primary font-label-sm text-[10px] font-mono">
                      PASS (Q_AXIOM)
                    </span>
                  </div>

                  <div className="mb-3">
                    <div className="flex justify-between font-label-sm text-[10px] text-on-surface-variant mb-1 font-mono">
                      <span>Latency Breakdown</span>
                      <span className="text-primary">1.35ms total</span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-surface-container-lowest overflow-hidden flex">
                      <div className="h-full bg-secondary" style={{ width: "32%" }} />
                      <div className="h-full bg-primary" style={{ width: "58%" }} />
                      <div
                        className="h-full bg-secondary-fixed"
                        style={{ width: "10%" }}
                      />
                    </div>
                    <div className="flex justify-between font-label-sm text-[9px] text-outline-variant mt-1 font-mono">
                      <span>CoW Spawn (32%)</span>
                      <span>SMT Solv (58%)</span>
                      <span>Merkle (10%)</span>
                    </div>
                  </div>

                  <div className="flex-1 p-2.5 rounded bg-surface-container-lowest font-label-sm text-[11px] font-mono text-on-surface-variant leading-relaxed overflow-x-auto space-y-1">
                    <div className="text-outline-variant">
                      ;; Microsoft Z3 Invariant AST
                    </div>
                    <div>
                      (<span className="text-secondary">assert</span>
                    </div>
                    <div className="pl-2">
                      (<span className="text-primary">not</span>
                    </div>
                    <div className="pl-4">
                      (<span className="text-secondary">and</span>
                    </div>
                    <div className="pl-6 text-on-surface">
                      (&lt; patient.egfr 30)
                    </div>
                    <div className="pl-6 text-error">
                      (= drug.class &quot;METFORMIN&quot;)
                    </div>
                    <div className="pl-4">)</div>
                    <div className="pl-2">)</div>
                    <div>)</div>
                    <div className="text-primary pt-1">
                      =&gt; :status UNSAT (Violation)
                    </div>
                    <div className="text-secondary-fixed text-[10px]">
                      =&gt; Triggering atomic CoW abort
                    </div>
                  </div>

                  <div className="mt-3 pt-2 border-t border-surface-variant/40 flex items-center justify-between">
                    <div className="flex items-center gap-1 text-primary font-label-sm text-[10px]">
                      <span className="material-symbols-outlined text-[13px]">
                        verified
                      </span>
                      <span>Merkle Root Certified</span>
                    </div>
                    <span className="font-label-sm text-[10px] text-outline-variant font-mono">
                      0x4b78...f9c2
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 3. THREE VERIFIED CARTRIDGE DOMAINS */}
        <section className="w-full pt-16 pb-20" id="proof-ast">
          <div className="flex flex-col md:flex-row md:items-end justify-between mb-space-lg gap-4">
            <div>
              <div className="inline-flex items-center gap-1.5 text-primary font-label-sm text-label-sm uppercase tracking-wider mb-1">
                <span className="material-symbols-outlined text-[16px]">
                  extension
                </span>
                Verified Domain Modules
              </div>
              <h2 className="font-headline-lg text-headline-lg text-on-surface">
                Zero Invariant Violations Across Industries
              </h2>
            </div>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-[420px]">
              Replace non-deterministic prompts with mathematical state
              assertions compiled straight into SMT solver predicates.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-space-lg">
            {/* Card 1: Healthcare FHIR */}
            <div className="flex flex-col p-6 rounded-xl bg-surface-container-low/70 backdrop-blur-xl shadow-lg hover:bg-surface-container-low transition-all border border-white/5">
              <div className="flex items-center justify-between mb-4">
                <div className="h-10 w-10 rounded-lg bg-surface-container-high flex items-center justify-center text-primary">
                  <span className="material-symbols-outlined">clinical_notes</span>
                </div>
                <span className="px-2 py-0.5 rounded bg-surface-container-high text-primary font-label-sm text-label-sm font-mono">
                  Rule INV_MED_01
                </span>
              </div>
              <h3 className="font-headline-sm text-headline-sm text-on-surface font-semibold mb-2">
                Healthcare FHIR
              </h3>
              <p className="font-body-sm text-body-sm text-on-surface-variant mb-4 flex-1">
                Intercepts clinical dosage orders. Blocks lethal Metformin
                dispensation when patient renal filtration rate drops under eGFR
                30 mL/min.
              </p>
              <div className="p-3 rounded-lg bg-surface-container-lowest font-label-sm text-[11px] font-mono mb-4 text-on-surface-variant leading-relaxed">
                <span className="text-outline-variant">{"// Z3 Renal Guardrail"}</span>
                <br />
                <span className="text-secondary">forall</span> (rx :
                MedicationRequest) :<br />
                &nbsp;&nbsp;rx.code =={" "}
                <span className="text-tertiary">&quot;METFORMIN&quot;</span>{" "}
                &amp;&amp;
                <br />
                &nbsp;&nbsp;patient.eGFR &lt; 30
                <br />
                &nbsp;&nbsp;==&gt;{" "}
                <span className="text-error font-semibold">
                  ABORT_AND_ROLLBACK
                </span>
              </div>
              <div className="flex items-center justify-between pt-3 border-t border-surface-variant/30 font-label-sm text-label-sm">
                <span className="text-on-surface-variant">Formal Proof</span>
                <span className="text-primary font-mono font-medium">
                  0.88ms SAT Check
                </span>
              </div>
            </div>

            {/* Card 2: FinTech Escrow */}
            <div className="flex flex-col p-6 rounded-xl bg-surface-container-low/70 backdrop-blur-xl shadow-lg hover:bg-surface-container-low transition-all border border-white/5">
              <div className="flex items-center justify-between mb-4">
                <div className="h-10 w-10 rounded-lg bg-surface-container-high flex items-center justify-center text-secondary">
                  <span className="material-symbols-outlined">
                    account_balance
                  </span>
                </div>
                <span className="px-2 py-0.5 rounded bg-surface-container-high text-secondary font-label-sm text-label-sm font-mono">
                  Rule INV_FIN_88
                </span>
              </div>
              <h3 className="font-headline-sm text-headline-sm text-on-surface font-semibold mb-2">
                FinTech Escrow
              </h3>
              <p className="font-body-sm text-body-sm text-on-surface-variant mb-4 flex-1">
                Enforces strict balance caps, daily aggregate ceilings, and
                multi-sig authorization constraints prior to ledger write-ahead
                log flush.
              </p>
              <div className="p-3 rounded-lg bg-surface-container-lowest font-label-sm text-[11px] font-mono mb-4 text-on-surface-variant leading-relaxed">
                <span className="text-outline-variant">
                  {"// Vault Outflow Constraint"}
                </span>
                <br />
                <span className="text-secondary">assert</span> (
                <br />
                &nbsp;&nbsp;sum(outflows_24h) + delta &lt;=
                <br />
                &nbsp;&nbsp;account.max_daily_limit &amp;&amp;
                <br />
                &nbsp;&nbsp;escrow.status =={" "}
                <span className="text-secondary-fixed">&quot;SEALED&quot;</span>
                <br />)
              </div>
              <div className="flex items-center justify-between pt-3 border-t border-surface-variant/30 font-label-sm text-label-sm">
                <span className="text-on-surface-variant">Escrow Leakage</span>
                <span className="text-secondary font-mono font-medium">
                  0.00% Zero Leak
                </span>
              </div>
            </div>

            {/* Card 3: Cloud DevOps */}
            <div className="flex flex-col p-6 rounded-xl bg-surface-container-low/70 backdrop-blur-xl shadow-lg hover:bg-surface-container-low transition-all border border-white/5">
              <div className="flex items-center justify-between mb-4">
                <div className="h-10 w-10 rounded-lg bg-surface-container-high flex items-center justify-center text-primary-fixed">
                  <span className="material-symbols-outlined">terminal</span>
                </div>
                <span className="px-2 py-0.5 rounded bg-surface-container-high text-primary-fixed font-label-sm text-label-sm font-mono">
                  INV_OPS_01 / INV_OPS_02
                </span>
              </div>
              <h3 className="font-headline-sm text-headline-sm text-on-surface font-semibold mb-2">
                Cloud DevOps &amp; IAM
              </h3>
              <p className="font-body-sm text-body-sm text-on-surface-variant mb-4 flex-1">
                Real-time proxy for autonomous agent shell sessions. Instantly
                drops destructive DDL (DROP, TRUNCATE) and insecure CIDR
                0.0.0.0/0 binding.
              </p>
              <div className="p-3 rounded-lg bg-surface-container-lowest font-label-sm text-[11px] font-mono mb-4 text-on-surface-variant leading-relaxed">
                <span className="text-outline-variant">
                  {"// SQL Ast Invariant Filter"}
                </span>
                <br />
                <span className="text-secondary">match</span> query.ast.statement{" "}
                {`{`}
                <br />
                &nbsp;&nbsp;DropTable | Truncate =&gt;
                <br />
                &nbsp;&nbsp;&nbsp;&nbsp;
                <span className="text-error font-semibold">
                  SIGKILL_AUTOPRUNE
                </span>
                ,
                <br />
                &nbsp;&nbsp;_ =&gt;{" "}
                <span className="text-primary font-semibold">PROCEED_TO_COW</span>
                <br />
                {`}`}
              </div>
              <div className="flex items-center justify-between pt-3 border-t border-surface-variant/30 font-label-sm text-label-sm">
                <span className="text-on-surface-variant">Interception</span>
                <span className="text-primary font-mono font-medium">
                  &lt; 0.42ms Drop Hook
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* 4. TERMINAL PLAYGROUND EXPERIENCE */}
        <section className="w-full pt-4 pb-12" id="playground">
          <div className="rounded-xl bg-surface-container-low/80 backdrop-blur-xl p-6 sm:p-8 shadow-2xl border border-white/5">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="material-symbols-outlined text-secondary text-[20px]">
                    terminal
                  </span>
                  <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold">
                    Interactive Verification Kernel
                  </h3>
                </div>
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Send an atomic verification envelope directly to the
                  Chronos-Zero cryptographic pipeline.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleCopyCurl}
                  className="px-3 py-1.5 rounded bg-surface-container-high text-on-surface hover:text-primary font-label-sm text-label-sm flex items-center gap-1.5 transition-colors"
                >
                  <span className="material-symbols-outlined text-[14px]">
                    content_copy
                  </span>
                  {copiedCurl ? "Copied!" : "Copy cURL"}
                </button>
                <button
                  onClick={handleRunVerify}
                  disabled={isVerifying}
                  className="px-4 py-1.5 rounded bg-primary text-on-primary font-label-sm text-label-sm font-semibold hover:bg-primary-fixed flex items-center gap-1.5 transition-all shadow-[0_0_12px_rgba(78,222,163,0.3)] disabled:opacity-50"
                >
                  <span className="material-symbols-outlined text-[14px]">
                    play_arrow
                  </span>
                  {isVerifying ? "Evaluating Proof..." : "Run Verification"}
                </button>
              </div>
            </div>

            <div className="rounded-lg bg-surface-container-lowest p-4 sm:p-5 font-mono border border-surface-container-high/40">
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-surface-variant/30">
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-surface-variant" />
                  <span className="h-2.5 w-2.5 rounded-full bg-surface-variant" />
                  <span className="h-2.5 w-2.5 rounded-full bg-surface-variant" />
                  <span className="ml-2 font-label-sm text-[11px] text-outline">
                    chronos-agent-runtime ~ z3-kernel-v2.4
                  </span>
                </div>
                <span className="font-label-sm text-[10px] text-primary">
                  ENDPOINT: /v1/z3/verify
                </span>
              </div>

              <div className="font-label-sm text-label-sm text-on-surface leading-relaxed mb-4">
                <span className="text-secondary font-bold">$</span> curl -X POST
                http://localhost:8001/v1/z3/verify \<br />
                &nbsp;&nbsp;-H{" "}
                <span className="text-primary">
                  &quot;Content-Type: application/json&quot;
                </span>{" "}
                \<br />
                &nbsp;&nbsp;-d{" "}
                <span className="text-on-surface-variant">
                  &apos;{`{"cartridge_id": "CLOUD_DEVOPS", "state_pre": {"row_count": 15420}, "state_post_shadow": {"row_count": 0}}`}&apos;
                </span>
              </div>

              <div className="p-3.5 rounded bg-surface-container-high/30 border-l-2 border-primary font-label-sm text-label-sm text-on-surface-variant space-y-1">
                <div className="text-primary font-semibold flex items-center gap-2">
                  <span className="material-symbols-outlined text-[15px]">
                    done_all
                  </span>
                  HTTP/2 200 OK — Mathematical Proof Complete
                </div>
                <div className="text-on-surface font-mono">{`{`}</div>
                <div className="pl-4 font-mono text-[11px] text-on-surface">
                  <span className="text-secondary">&quot;status&quot;</span>:{" "}
                  <span className="text-error">&quot;UNSAT&quot;</span>,
                </div>
                <div className="pl-4 font-mono text-[11px] text-on-surface">
                  <span className="text-secondary">&quot;proof_latency_ms&quot;</span>
                  : 0.94,
                </div>
                <div className="pl-4 font-mono text-[11px] text-on-surface">
                  <span className="text-secondary">&quot;unsat_core&quot;</span>:
                  [&quot;INV_OPS_01_ZERO_DATA_LOSS&quot;],
                </div>
                <div className="pl-4 font-mono text-[11px] text-on-surface">
                  <span className="text-secondary">
                    &quot;sha256_proof_hash&quot;
                  </span>
                  : &quot;0x9c3d41e8f7a012e84...&quot;
                </div>
                <div className="text-on-surface font-mono">{`}`}</div>
                {verifyResult && (
                  <div className="mt-2 text-primary text-[11px] font-bold">
                    Result: {verifyResult}
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
