"use client";

import React, { useState, useEffect } from "react";
import { useChronosWS, RunStatus } from "../hooks/useChronosWS";
import { TopTelemetryBar } from "../components/TopTelemetryBar";
import { MultiverseDAG } from "../components/MultiverseDAG";
import { Z3ProofInspector } from "../components/Z3ProofInspector";
import { LivePolicyStudio } from "../components/LivePolicyStudio";
import { SplitScreenDemo } from "../components/SplitScreenDemo";
import { ArchitectureView } from "../components/ArchitectureView";
import { GlobalNavbar } from "../components/GlobalNavbar";
import { GlobalFooter } from "../components/GlobalFooter";

function RunStatusStrip({
  runStatus,
  activeCartridge,
}: {
  runStatus: RunStatus;
  activeCartridge: string;
}) {
  const isBypass = runStatus.mode === "BYPASS";
  const isRunning = runStatus.phase === "RUNNING";
  const isError = runStatus.phase === "ERROR";
  const isResetting = runStatus.phase === "RESETTING";

  let violationPill = "DESTRUCTIVE DDL INTERCEPTED";
  let healedPill = "SELF-HEALED IN 1.18ms";
  let contextLog = (
    <>
      Violation caught on Turn 1:{" "}
      <span className="text-error font-semibold font-mono">
        INV_OPS_04_NO_DROP_TABLE
      </span>
      . Intercepted query{" "}
      <span className="text-error font-mono font-semibold">
        &quot;DROP TABLE users CASCADE;&quot;
      </span>
      . Ephemeral Postgres CoW snapshot rolled back (0 bytes written, 15,420
      user accounts preserved). Turn 2 self-healed: agent adapted to{" "}
      <span className="text-primary font-mono font-semibold">
        &quot;ALTER TABLE users ADD COLUMN feature_flags JSONB DEFAULT
        &apos;{}&apos;;&quot;
      </span>{" "}
      → Z3 proven SAT.
    </>
  );

  if (activeCartridge === "FINTECH_ESCROW") {
    violationPill = "ESCROW CAP BREACH INTERCEPTED";
    healedPill = "SELF-HEALED IN 0.92ms";
    contextLog = (
      <>
        Violation caught on Turn 1:{" "}
        <span className="text-error font-semibold font-mono">
          INV_FIN_01_ESCROW_CAP
        </span>
        . Intercepted wire transfer of{" "}
        <span className="text-error font-mono font-semibold">$12,000.00</span> to
        unverified vendor (cap $5,000.00). Postgres CoW transaction rolled back
        ($12,000 capital loss prevented). Turn 2 self-healed: agent reduced wire
        to{" "}
        <span className="text-primary font-mono font-semibold">$400.00</span> to
        allowlisted IBAN → Z3 proven SAT.
      </>
    );
  } else if (activeCartridge === "HEALTHCARE_FHIR") {
    violationPill = "LETHAL CONTRAINDICATION BLOCKED";
    healedPill = "SELF-HEALED IN 1.04ms";
    contextLog = (
      <>
        Violation caught on Turn 1:{" "}
        <span className="text-error font-semibold font-mono">
          INV_MED_01_RENAL_SAFETY
        </span>
        . Intercepted prescription of Metformin 2500mg for patient with eGFR{" "}
        <span className="text-error font-mono font-semibold">
          24 mL/min/1.73m²
        </span>
        . Clinical hazard blocked before medication dispensation. Turn 2
        self-healed: agent substituted safe renal agent Linagliptin 5mg → Z3
        proven SAT.
      </>
    );
  }

  if (isBypass) {
    return (
      <div className="w-full bg-error-container/30 border-b border-error/50 px-margin-mobile lg:px-6 py-1.5 flex flex-wrap items-center justify-between gap-3 text-on-surface">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-DEFAULT bg-error text-on-error">
            <span className="w-1.5 h-1.5 rounded-full bg-on-error animate-pulse" />
            <span className="font-label-sm text-label-sm font-bold uppercase tracking-wider">
              BYPASS CORRUPTION ACTIVE
            </span>
          </div>
          <p className="font-label-sm text-label-sm text-error font-mono">
            WARNING: Speculative execution bypassed. Unverified mutations commit
            directly to production database without Z3 formal proof verification.
          </p>
        </div>
        <div className="hidden lg:flex items-center gap-3 font-label-sm text-label-sm text-outline">
          <span>
            GUARDRAILS: <strong className="text-error">OFFLINE</strong>
          </span>
        </div>
      </div>
    );
  }

  if (isRunning) {
    return (
      <div className="w-full bg-surface-container px-margin-mobile lg:px-6 py-1.5 flex flex-wrap items-center justify-between gap-3 shadow-[inset_0_-1px_0_rgba(255,255,255,0.05)] text-on-surface">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-DEFAULT bg-secondary/20 text-secondary">
            <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-pulse" />
            <span className="font-label-sm text-label-sm font-semibold uppercase tracking-wider">
              POSTGRES COW SHADOW FORK ARMED
            </span>
          </div>
          <p className="font-label-sm text-label-sm text-secondary font-mono">
            {runStatus.message ||
              `Executing ${activeCartridge} agent trajectory...`}
          </p>
        </div>
        <div className="hidden lg:flex items-center gap-3 font-label-sm text-label-sm text-outline">
          <span>
            ZK-PROOF ENGINE: <strong className="text-on-surface">Z3 v4.13.0</strong>
          </span>
          <span>•</span>
          <span>
            COW TIMEOUT: <strong className="text-on-surface">15.0ms</strong>
          </span>
        </div>
      </div>
    );
  }

  if (isResetting) {
    return (
      <div className="w-full bg-surface-container px-margin-mobile lg:px-6 py-1.5 flex items-center justify-between text-on-surface font-mono text-label-sm">
        <span className="text-secondary">
          Restoring pristine database snapshots from seed...
        </span>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="w-full bg-error/20 border-b border-error px-margin-mobile lg:px-6 py-1.5 flex items-center justify-between text-error font-mono text-label-sm">
        <span>Run failed: {runStatus.message} (press R to reset the stage)</span>
      </div>
    );
  }

  return (
    <div className="w-full bg-surface-container px-margin-mobile lg:px-6 py-1.5 flex flex-wrap items-center justify-between gap-3 shadow-[inset_0_-1px_0_rgba(255,255,255,0.05)] border-b border-surface-container-high/40">
      <div className="flex items-center gap-3 overflow-hidden">
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-DEFAULT bg-error/20 text-error">
          <span className="w-1.5 h-1.5 rounded-full bg-error animate-pulse" />
          <span className="font-label-sm text-label-sm font-semibold uppercase tracking-wider">
            {violationPill}
          </span>
        </div>
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-DEFAULT bg-secondary/10 text-secondary">
          <span className="material-symbols-outlined text-xs leading-none">
            auto_mode
          </span>
          <span className="font-label-sm text-label-sm font-semibold uppercase tracking-wider">
            {healedPill}
          </span>
        </div>
        <p
          className="font-label-sm text-label-sm text-on-surface-variant truncate max-w-4xl"
          id="kernel-context-log"
        >
          {contextLog}
        </p>
      </div>
      <div className="hidden lg:flex items-center gap-3 font-label-sm text-label-sm text-outline">
        <span>
          ZK-PROOF ENGINE: <strong className="text-on-surface">Z3 v4.13.0</strong>
        </span>
        <span>•</span>
        <span>
          COW TIMEOUT: <strong className="text-on-surface">15.0ms</strong>
        </span>
      </div>
    </div>
  );
}

export default function MissionControlPage() {
  const {
    status,
    nodes,
    edges,
    selectedNode,
    setSelectedNode,
    metrics,
    activeCartridge,
    setActiveCartridge,
    chronosMode,
    toggleChronosMode,
    isRunning,
    runStatus,
    bypassActiveAlert,
    dismissBypassAlert,
    resetDAG,
    runScenario,
    activePolicy,
    setActivePolicy,
  } = useChronosWS();

  const [isInspectorOpen, setIsInspectorOpen] = useState(true);
  const [isSplitDemoOpen, setIsSplitDemoOpen] = useState(false);
  const [currentView, setCurrentView] = useState<"dag" | "architecture">("dag");

  // Sync hash routing (#architecture vs #dag)
  useEffect(() => {
    if (typeof window !== "undefined") {
      const hash = window.location.hash.replace("#", "");
      if (hash === "architecture") {
        setCurrentView("architecture");
      } else if (hash === "dag") {
        setCurrentView("dag");
      }
    }
  }, []);

  const handleSelectView = (view: "dag" | "architecture") => {
    setCurrentView(view);
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", `#${view}`);
    }
  };

  // Stage Pilot Keyboard Shortcuts:
  // 1 / 2 / 3: Switch to HEALTHCARE_FHIR / FINTECH_ESCROW / CLOUD_DEVOPS
  // Spacebar:  Run the active cartridge's live scenario in the current kernel mode
  // B:         Run the active cartridge's scenario in BYPASS (no Chronos)
  // R:         Stage reset (POST /v1/kernel/reset + clear compiled policies)
  // S:         Toggle Split-Screen (BYPASS vs ACTIVE)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        return;
      }
      if (e.key === "1") {
        e.preventDefault();
        setActiveCartridge("HEALTHCARE_FHIR");
      } else if (e.key === "2") {
        e.preventDefault();
        setActiveCartridge("FINTECH_ESCROW");
      } else if (e.key === "3") {
        e.preventDefault();
        setActiveCartridge("CLOUD_DEVOPS");
      } else if (e.code === "Space") {
        e.preventDefault();
        if (!isRunning) runScenario(activeCartridge, chronosMode);
      } else if (e.key === "b" || e.key === "B") {
        e.preventDefault();
        if (!isRunning) runScenario(activeCartridge, "BYPASS");
      } else if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        if (!isRunning) resetDAG();
      } else if (e.key === "s" || e.key === "S") {
        e.preventDefault();
        setIsSplitDemoOpen((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    activeCartridge,
    chronosMode,
    isRunning,
    resetDAG,
    runScenario,
    setActiveCartridge,
  ]);

  return (
    <div className="flex flex-col min-h-screen w-screen overflow-x-hidden bg-surface-container-lowest font-body-md text-body-md text-on-surface antialiased select-none">
      {/* 1. Global Fixed Top Navbar (Page 1 & Page 2) */}
      <GlobalNavbar
        currentView={currentView}
        onSelectView={handleSelectView}
        status={status}
        latencyMs={metrics.latency_ms}
        onOpenBenchmarks={() => setIsSplitDemoOpen(true)}
        onOpenDocs={() => {
          handleSelectView("architecture");
          setTimeout(() => {
            document.getElementById("tech-specs")?.scrollIntoView({ behavior: "smooth" });
          }, 100);
        }}
        onOpenSMTProver={() => {
          if (currentView === "dag") {
            document.getElementById("policy-input-area")?.focus();
          } else {
            handleSelectView("dag");
          }
        }}
      />

      {/* 2. Main Content Area below Navbar */}
      <main className="relative z-10 w-full pt-16 flex-1 flex flex-col min-h-0">
        {currentView === "architecture" ? (
          <div className="flex-1 flex flex-col min-h-0">
            <ArchitectureView onLaunchConsole={() => handleSelectView("dag")} />
            <GlobalFooter onOpenReceiptValidator={() => setIsSplitDemoOpen(true)} />
          </div>
        ) : (
          <div className="flex-1 flex flex-col h-[calc(100vh-64px)] overflow-hidden">
            {/* Top SCADA Telemetry Command Bar */}
            <TopTelemetryBar
              status={status}
              metrics={metrics}
              activeCartridge={activeCartridge}
              setActiveCartridge={setActiveCartridge}
              chronosMode={chronosMode}
              onToggleChronosMode={toggleChronosMode}
              isRunning={isRunning}
              onRun={(cartridge) => runScenario(cartridge, chronosMode)}
              onRunBypass={(cartridge) => runScenario(cartridge, "BYPASS")}
              onReset={resetDAG}
              onOpenSplitDemo={() => setIsSplitDemoOpen(true)}
              currentView={currentView}
              onSelectView={handleSelectView}
            />

            {/* Live Run Status Strip */}
            <RunStatusStrip
              runStatus={runStatus}
              activeCartridge={activeCartridge}
            />

            {/* Main Workspace Canvas Grid */}
            <div className="flex flex-1 min-h-0 min-w-0 relative overflow-hidden bg-surface-container-lowest">
              {/* Left 65%: Multiverse DAG Visualizer */}
              <MultiverseDAG
                nodes={nodes}
                edges={edges}
                selectedNode={selectedNode}
                onSelectNode={(node) => {
                  setSelectedNode(node);
                  setIsInspectorOpen(true);
                }}
                bypassAlert={bypassActiveAlert}
                onDismissBypassAlert={dismissBypassAlert}
              />

              {/* Right 35%: Z3 Formal Proof Inspector Drawer */}
              {isInspectorOpen && (
                <Z3ProofInspector
                  node={selectedNode}
                  onClose={() => setIsInspectorOpen(false)}
                />
              )}
            </div>

            {/* Docked Live Policy Studio Drawer */}
            <LivePolicyStudio
              activeCartridge={activeCartridge}
              activePolicy={activePolicy}
              onPolicyCompiled={setActivePolicy}
            />
          </div>
        )}
      </main>

      {/* 50/50 Comparative Multiverse Split Screen Modal */}
      <SplitScreenDemo
        isOpen={isSplitDemoOpen}
        onClose={() => setIsSplitDemoOpen(false)}
      />
    </div>
  );
}
