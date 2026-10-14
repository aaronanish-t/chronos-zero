"use client";

import React, { useState } from "react";
import { useChronosWS } from "../hooks/useChronosWS";
import { TopTelemetryBar } from "../components/TopTelemetryBar";
import { MultiverseCanvas } from "../components/MultiverseCanvas";
import { Z3ProofInspector } from "../components/Z3ProofInspector";
import { LivePolicyStudio } from "../components/LivePolicyStudio";

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
    isSimulating,
    bypassActiveAlert,
    dismissBypassAlert,
    resetDAG,
    simulateMockTelemetry,
    simulateBypassCorruption,
  } = useChronosWS();

  const [isInspectorOpen, setIsInspectorOpen] = useState(true);

  return (
    <main className="flex flex-col h-screen w-screen overflow-hidden bg-[#090D16]">
      {/* Panel 1: Top Telemetry Bar */}
      <TopTelemetryBar
        status={status}
        metrics={metrics}
        activeCartridge={activeCartridge}
        setActiveCartridge={setActiveCartridge}
        isSimulating={isSimulating}
        onSimulate={simulateMockTelemetry}
        onSimulateBypass={simulateBypassCorruption}
        onReset={resetDAG}
      />

      {/* Center Layout: ReactFlow Canvas (Panel 2) + Right Z3 Proof Drawer (Panel 3) */}
      <div className="flex flex-1 min-h-0 relative overflow-hidden">
        {/* Panel 2: Center ReactFlow Canvas */}
        <MultiverseCanvas
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
    </main>
  );
}
