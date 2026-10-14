"use client";

import React, { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  Node,
  Edge,
  NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { MultiverseNode } from "./MultiverseNode";
import { DAGNode, DAGEdge } from "../hooks/useChronosWS";
import { TelemetryNode } from "../types/contracts";
import { AlertTriangle, X } from "lucide-react";

interface MultiverseCanvasProps {
  nodes: DAGNode[];
  edges: DAGEdge[];
  selectedNode: TelemetryNode | null;
  onSelectNode: (node: TelemetryNode) => void;
  bypassAlert: string | null;
  onDismissBypassAlert: () => void;
}

export const MultiverseCanvas: React.FC<MultiverseCanvasProps> = ({
  nodes,
  edges,
  selectedNode,
  onSelectNode,
  bypassAlert,
  onDismissBypassAlert,
}) => {
  // Register custom node type
  const nodeTypes = useMemo(
    () => ({
      multiverseNode: MultiverseNode,
    }),
    []
  );

  // Map DAG nodes to ReactFlow nodes with selected flag
  const flowNodes: Node<TelemetryNode>[] = useMemo(() => {
    return nodes.map((n) => ({
      id: n.id,
      type: "multiverseNode",
      position: n.position,
      data: n.data,
      selected: selectedNode?.id === n.id,
    }));
  }, [nodes, selectedNode]);

  // Map DAG edges to ReactFlow edges
  const flowEdges: Edge[] = useMemo(() => {
    return edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      animated: e.animated,
      style: e.style,
      type: "smoothstep",
    }));
  }, [edges]);

  const handleNodeClick: NodeMouseHandler = (_, node) => {
    onSelectNode(node.data as unknown as TelemetryNode);
  };

  return (
    <div className="relative flex-1 h-full w-full bg-[#090D16] overflow-hidden">
      {/* Bypass Corruption Warning Banner (Section 4.4 AGENTS.md) */}
      {bypassAlert && (
        <div className="absolute top-4 left-6 right-6 z-20 flex items-center justify-between p-3 rounded-lg bg-red-950/90 border-2 border-chronos-crimson shadow-[0_0_25px_rgba(239,68,68,0.5)] animate-pulse">
          <div className="flex items-center gap-2 text-red-200 text-xs font-mono">
            <AlertTriangle className="w-5 h-5 text-chronos-crimson shrink-0" />
            <span className="font-bold uppercase tracking-wider text-chronos-crimson">
              CRITICAL UNVERIFIED BYPASS:
            </span>
            <span>{bypassAlert}</span>
          </div>
          <button
            onClick={onDismissBypassAlert}
            className="p-1 rounded hover:bg-red-900/50 text-red-300 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Empty State Banner if no nodes */}
      {nodes.length === 0 && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center pointer-events-none text-slate-500 font-mono text-center px-4">
          <div className="w-12 h-12 rounded-full border border-slate-800 bg-[#0F172A] flex items-center justify-center mb-3">
            <span className="w-3 h-3 rounded-full bg-cyan-400 animate-ping"></span>
          </div>
          <p className="text-sm font-semibold text-slate-300 mb-1">
            Multiverse DAG Ready
          </p>
          <p className="text-xs text-slate-500 max-w-sm">
            Waiting for live telemetry stream from ws://localhost:8000/ws/telemetry. Click &quot;Simulate Mock Telemetry&quot; in the top bar to run a 60fps speculative branching demo.
          </p>
        </div>
      )}

      {/* ReactFlow Canvas */}
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.3, maxZoom: 1.2 }}
        minZoom={0.2}
        maxZoom={2.0}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1.5}
          color="#1E293B"
        />
        <Controls
          showInteractive={false}
          className="!bottom-4 !left-4"
        />
        <MiniMap
          nodeColor={(n) => {
            const nodeData = n.data as unknown as TelemetryNode;
            if (nodeData?.branch_type === "SHADOW_REJECTED") return "#EF4444";
            if (nodeData?.branch_type === "COMMITTED_SAFE") return "#10B981";
            if (nodeData?.branch_type === "BYPASS_CORRUPTED") return "#F59E0B";
            return "#64748B";
          }}
          maskColor="rgba(9, 13, 22, 0.75)"
          className="!bottom-4 !right-4 !bg-[#0F172A] !border !border-[#1E293B] !rounded-lg overflow-hidden"
          zoomable
          pannable
        />
      </ReactFlow>
    </div>
  );
};
