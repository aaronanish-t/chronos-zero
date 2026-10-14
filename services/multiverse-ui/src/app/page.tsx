"use client";

import React, { useState, useEffect } from "react";
import { useChronosWS } from "../hooks/useChronosWS";
import { TopTelemetryBar } from "../components/TopTelemetryBar";
import { MultiverseDAG } from "../components/MultiverseDAG";
import { Z3ProofInspector } from "../components/Z3ProofInspector";
import { LivePolicyStudio } from "../components/LivePolicyStudio";
import { SplitScreenDemo } from "../components/SplitScreenDemo";

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
    isSimulating,
    bypassActiveAlert,
    dismissBypassAlert,
    resetDAG,
    simulateMockTelemetry,
    simulateBypassCorruption,
  } = useChronosWS();

  const [isInspectorOpen, setIsInspectorOpen] = useState(true);
  const [isSplitDemoOpen, setIsSplitDemoOpen] = useState(false);

  // Stage Pilot Keyboard Shortcuts:
  // Key 1: Switch to HEALTHCARE_FHIR
  // Key 2: Switch to FINTECH_ESCROW
  // Key 3: Switch to CLOUD_DEVOPS
  // Spacebar: Trigger active scenario run
  // Key R: Instant <200ms demo reset (POST /v1/kernel/reset)
  // Key S: Toggle Split-Screen (BYPASS vs ACTIVE) mode
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
        if (!isSimulating) {
          simulateMockTelemetry(activeCartridge);
        }
      } else if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        resetDAG();
      } else if (e.key === "s" || e.key === "S") {
        e.preventDefault();
        setIsSplitDemoOpen((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    activeCartridge,
    isSimulating,
    resetDAG,
    setActiveCartridge,
    simulateMockTelemetry,
  ]);

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
        isSimulating={isSimulating}
        onSimulate={simulateMockTelemetry}
        onSimulateBypass={simulateBypassCorruption}
        onReset={resetDAG}
        onOpenSplitDemo={() => setIsSplitDemoOpen(true)}
      />

      {/* Center Layout: ReactFlow Canvas (Panel 2) + Right Z3 Proof Drawer (Panel 3) */}
      <div className="flex flex-1 min-h-0 relative overflow-hidden">
        {/* Panel 2: Center ReactFlow Canvas (MultiverseDAG) */}
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

        {/* Panel 3: Right Z3 Proof Inspector Drawer */}
        {isInspectorOpen && (
          <Z3ProofInspector
            node={selectedNode}
            onClose={() => setIsInspectorOpen(false)}
          />
        )}
      </div>

      {/* Panel 4: Bottom Live Policy Studio Bar */}
      <LivePolicyStudio activeCartridge={activeCartridge} />

      {/* 50/50 Comparative Multiverse Split Screen Modal */}
      <SplitScreenDemo
        isOpen={isSplitDemoOpen}
        onClose={() => setIsSplitDemoOpen(false)}
      />
    </main>
  );
}
