"use client";

import React, { useState, useEffect } from "react";
import { useChronosWS, RunStatus } from "../hooks/useChronosWS";
import { TopTelemetryBar } from "../components/TopTelemetryBar";
import { MultiverseDAG } from "../components/MultiverseDAG";
import { Z3ProofInspector } from "../components/Z3ProofInspector";
import { LivePolicyStudio } from "../components/LivePolicyStudio";
import { SplitScreenDemo } from "../components/SplitScreenDemo";

function RunStatusStrip({ runStatus }: { runStatus: RunStatus }) {
  if (runStatus.phase === "IDLE" && !runStatus.message) return null;
  const tone =
    runStatus.phase === "ERROR"
      ? "bg-red-950/80 border-red-800 text-red-200"
      : runStatus.phase === "RUNNING" || runStatus.phase === "RESETTING"
      ? "bg-amber-950/60 border-amber-800/70 text-amber-200 animate-pulse"
      : runStatus.mode === "BYPASS"
      ? "bg-red-950/60 border-red-900 text-red-200"
      : "bg-emerald-950/60 border-emerald-800/70 text-emerald-200";
  const label =
    runStatus.phase === "RUNNING"
      ? `Running ${runStatus.cartridge} scenario in ${runStatus.mode} mode...`
      : runStatus.phase === "RESETTING"
      ? runStatus.message ?? "Resetting stage..."
      : runStatus.phase === "ERROR"
      ? `Run failed: ${runStatus.message} (press R to reset the stage)`
      : runStatus.message;
  return (
    <div className={`px-4 py-1.5 border-b text-[11px] font-mono flex items-center justify-between ${tone}`}>
      <span className="font-semibold">{label}</span>
      {runStatus.agentSource && runStatus.phase === "DONE" && (
        <span className="text-[10px] opacity-80">agent tool calls: {runStatus.agentSource}</span>
      )}
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

  // Stage Pilot Keyboard Shortcuts:
  // 1 / 2 / 3: Switch to HEALTHCARE_FHIR / FINTECH_ESCROW / CLOUD_DEVOPS
  // Spacebar:  Run the active cartridge's live scenario in the current kernel mode
  // B:         Run the active cartridge's scenario in BYPASS (no Chronos)
  // R:         Stage reset (POST /v1/kernel/reset + clear compiled policies)
  // S:         Toggle Split-Screen (BYPASS vs ACTIVE)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
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
  }, [activeCartridge, chronosMode, isRunning, resetDAG, runScenario, setActiveCartridge]);

  return (
    <main className="flex flex-col h-screen w-screen overflow-hidden bg-[#090D16]">
      {/* Panel 1: Top Telemetry Bar */}
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
      />
      <RunStatusStrip runStatus={runStatus} />

      {/* Center Layout: ReactFlow Canvas (Panel 2) + Right Z3 Proof Drawer (Panel 3) */}
      <div className="flex flex-1 min-h-0 relative overflow-hidden">
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

        {isInspectorOpen && (
          <Z3ProofInspector node={selectedNode} onClose={() => setIsInspectorOpen(false)} />
        )}
      </div>

      {/* Panel 4: Bottom Live Policy Studio Bar */}
      <LivePolicyStudio
        activeCartridge={activeCartridge}
        activePolicy={activePolicy}
        onPolicyCompiled={setActivePolicy}
      />

      {/* 50/50 Comparative Multiverse Split Screen Modal */}
      <SplitScreenDemo isOpen={isSplitDemoOpen} onClose={() => setIsSplitDemoOpen(false)} />
    </main>
  );
}
