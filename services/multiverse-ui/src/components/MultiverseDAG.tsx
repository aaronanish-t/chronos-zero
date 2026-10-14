"use client";

import React, { useMemo, memo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  Node,
  Edge,
  Handle,
  Position,
  NodeProps,
  NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  ShieldAlert,
  ShieldCheck,
  KeyRound,
  Database,
  GitBranch,
  AlertTriangle,
  X,
  FileCode2,
} from "lucide-react";
import { TelemetryNode } from "../types/contracts";
import { DAGNode, DAGEdge } from "../hooks/useChronosWS";

// =========================================================================
// 1. Custom Node Components
// =========================================================================

/**
 * ShadowRejectedNode:
 * Crimson border (#EF4444), glowing red pulse animation,
 * Header badge: "UNSAT — KILLED IN SHADOW ({latency}ms)",
 * Listing violated rule IDs and "0 Bytes Prod Damage".
 */
export const ShadowRejectedNode = memo(function ShadowRejectedNode({
  data,
  selected,
}: NodeProps<Node<TelemetryNode>>) {
  const nodeData = data as TelemetryNode;
  const latency = (nodeData.total_latency_ms ?? 0).toFixed(2);

  return (
    <div
      className={`relative min-w-[280px] max-w-[340px] rounded-lg p-3 bg-[#0F172A]/95 border-2 border-[#EF4444] text-left select-none cursor-pointer transition-all duration-200
        shadow-[0_0_22px_rgba(239,68,68,0.4)] hover:shadow-[0_0_28px_rgba(239,68,68,0.6)]
        ${selected ? "ring-2 ring-cyan-400 ring-offset-2 ring-offset-[#090D16]" : ""}`}
    >
      {/* Target Handle (Left) */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-2.5 !h-2.5 !bg-red-400 !border-2 !border-[#090D16]"
      />

      {/* Header Badge: UNSAT — KILLED IN SHADOW ({latency}ms) */}
      <div className="flex items-center justify-between gap-1.5 mb-2">
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-red-950/90 border border-red-800/90 text-red-400 font-mono font-bold text-[10px] tracking-wider">
          <ShieldAlert className="w-3.5 h-3.5 text-[#EF4444] animate-pulse" />
          <span>UNSAT — KILLED IN SHADOW ({latency}ms)</span>
        </div>

        {/* 0 Bytes Prod Damage Indicator */}
        <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 font-mono text-[9px] font-semibold whitespace-nowrap">
          <Database className="w-2.5 h-2.5 text-emerald-400" />
          <span>0 Bytes Prod Damage</span>
        </div>
      </div>

      {/* Intercepted Action Label */}
      <div className="text-xs font-mono font-medium text-slate-200 bg-slate-950/80 p-2 rounded border border-slate-800/80 mb-2 break-all line-clamp-2">
        {nodeData.action_label}
      </div>

      {/* Violated Rule IDs list */}
      <div className="space-y-1 pt-1 border-t border-red-900/40">
        <div className="text-[9px] uppercase font-mono tracking-wider text-red-300/80 font-semibold flex items-center justify-between">
          <span>Violated Invariant Rules:</span>
          {nodeData.financial_loss_prevented_usd > 0 && (
            <span className="text-amber-300 font-bold">
              Protected ${nodeData.financial_loss_prevented_usd.toLocaleString()}
            </span>
          )}
          {nodeData.clinical_hazard_prevented && (
            <span className="text-purple-300 font-bold">Hazard Blocked</span>
          )}
        </div>

        <div className="flex flex-wrap gap-1">
          {nodeData.violated_rules && nodeData.violated_rules.length > 0 ? (
            nodeData.violated_rules.map((ruleId) => (
              <span
                key={ruleId}
                className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-red-950 text-red-300 border border-red-800/70"
              >
                {ruleId}
              </span>
            ))
          ) : (
            <span className="text-[10px] text-red-400 font-mono">
              UnsatCore Detected
            </span>
          )}
        </div>
      </div>

      {/* Source Handle (Right) */}
      <Handle
        type="source"
        position={Position.Right}
        className="!w-2.5 !h-2.5 !bg-red-400 !border-2 !border-[#090D16]"
      />
    </div>
  );
});

/**
 * CommittedSafeNode:
 * Emerald border (#10B981), solid green indicator,
 * Header badge: "Z3 PROVEN SAT ({latency}ms)",
 * Displaying action label and truncated SHA-256 receipt hash.
 */
export const CommittedSafeNode = memo(function CommittedSafeNode({
  data,
  selected,
}: NodeProps<Node<TelemetryNode>>) {
  const nodeData = data as TelemetryNode;
  const latency = (nodeData.total_latency_ms ?? 0).toFixed(2);
  const hash = nodeData.sha256_proof_hash
    ? `${nodeData.sha256_proof_hash.slice(0, 10)}...${nodeData.sha256_proof_hash.slice(-6)}`
    : "Verified Deterministic Receipt";

  return (
    <div
      className={`relative min-w-[280px] max-w-[340px] rounded-lg p-3 bg-[#0F172A]/95 border-2 border-[#10B981] text-left select-none cursor-pointer transition-all duration-200
        shadow-[0_0_20px_rgba(16,185,129,0.35)] hover:shadow-[0_0_28px_rgba(16,185,129,0.55)]
        ${selected ? "ring-2 ring-cyan-400 ring-offset-2 ring-offset-[#090D16]" : ""}`}
    >
      {/* Target Handle (Left) */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-2.5 !h-2.5 !bg-emerald-400 !border-2 !border-[#090D16]"
      />

      {/* Header Badge: Z3 PROVEN SAT ({latency}ms) & Solid Green Indicator */}
      <div className="flex items-center justify-between gap-1.5 mb-2">
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-950/90 border border-emerald-800/90 text-emerald-400 font-mono font-bold text-[10px] tracking-wider">
          <ShieldCheck className="w-3.5 h-3.5 text-[#10B981]" />
          <span>Z3 PROVEN SAT ({latency}ms)</span>
        </div>

        {/* Solid green commit indicator */}
        <div className="flex items-center gap-1.5 px-1.5 py-0.5 rounded bg-emerald-950/80 border border-emerald-700/80 text-[9px] font-mono text-emerald-300 font-semibold">
          <span className="w-2 h-2 rounded-full bg-[#10B981] shadow-[0_0_6px_#10B981]" />
          <span>PROD COMMITTED</span>
        </div>
      </div>

      {/* Safe Action Label */}
      <div className="text-xs font-mono font-medium text-slate-100 bg-slate-950/80 p-2 rounded border border-slate-800/80 mb-2 break-all line-clamp-2">
        {nodeData.action_label}
      </div>

      {/* Truncated SHA-256 Receipt Hash */}
      <div className="pt-1 border-t border-emerald-900/40 flex items-center justify-between text-[10px] font-mono">
        <div className="flex items-center gap-1 text-slate-400">
          <KeyRound className="w-3 h-3 text-emerald-400 shrink-0" />
          <span className="text-[9px] uppercase text-slate-500">Receipt:</span>
          <span className="text-emerald-300 font-medium select-all">{hash}</span>
        </div>

        <span className="text-[9px] text-cyan-400 bg-cyan-950/40 px-1 py-0.2 rounded border border-cyan-800/50">
          Self-Healed
        </span>
      </div>

      {/* Source Handle (Right) */}
      <Handle
        type="source"
        position={Position.Right}
        className="!w-2.5 !h-2.5 !bg-emerald-400 !border-2 !border-[#090D16]"
      />
    </div>
  );
});

/**
 * RootOriginNode:
 * Terminal entry point for agent session.
 */
export const RootOriginNode = memo(function RootOriginNode({
  data,
  selected,
}: NodeProps<Node<TelemetryNode>>) {
  const nodeData = data as TelemetryNode;

  return (
    <div
      className={`relative min-w-[240px] max-w-[280px] rounded-lg p-3 bg-[#0F172A]/90 border border-slate-700 text-left select-none cursor-pointer transition-all duration-200
        shadow-[0_0_12px_rgba(30,41,59,0.5)] hover:border-slate-500
        ${selected ? "ring-2 ring-cyan-400 ring-offset-2 ring-offset-[#090D16]" : ""}`}
    >
      <div className="flex items-center gap-1.5 mb-1.5 text-xs font-mono font-bold text-slate-300">
        <GitBranch className="w-3.5 h-3.5 text-cyan-400" />
        <span className="uppercase tracking-wider">ROOT // SESSION ORIGIN</span>
      </div>

      <div className="text-[11px] font-mono text-slate-400 bg-slate-950/80 p-1.5 rounded border border-slate-800 mb-1 break-all">
        {nodeData.action_label}
      </div>

      <div className="text-[9px] text-slate-500 font-mono flex items-center gap-1">
        <FileCode2 className="w-2.5 h-2.5" />
        <span>Chronos In-Memory RAM CoW Initialized</span>
      </div>

      {/* Source Handle (Right) */}
      <Handle
        type="source"
        position={Position.Right}
        className="!w-2.5 !h-2.5 !bg-slate-400 !border-2 !border-[#090D16]"
      />
    </div>
  );
});

// =========================================================================
// 2. MultiverseDAG Main Component
// =========================================================================

interface MultiverseDAGProps {
  nodes: DAGNode[];
  edges: DAGEdge[];
  selectedNode: TelemetryNode | null;
  onSelectNode: (node: TelemetryNode) => void;
  bypassAlert?: string | null;
  onDismissBypassAlert?: () => void;
}

export const MultiverseDAG: React.FC<MultiverseDAGProps> = ({
  nodes,
  edges,
  selectedNode,
  onSelectNode,
  bypassAlert,
  onDismissBypassAlert,
}) => {
  // Register custom node types with ReactFlow
  const nodeTypes = useMemo(
    () => ({
      shadowRejectedNode: ShadowRejectedNode,
      committedSafeNode: CommittedSafeNode,
      rootOriginNode: RootOriginNode,
      multiverseNode: CommittedSafeNode, // fallback
    }),
    []
  );

  /**
   * Deterministic Multiverse Layout Reducer:
   * - Root node at (80, 220).
   * - SHADOW_REJECTED branches downward-right to (parent.x + 320, parent.y + 150).
   * - COMMITTED_SAFE branches horizontally to (parent.x + 320, parent.y).
   */
  const flowNodes: Node<TelemetryNode>[] = useMemo(() => {
    // Map of computed positions by node id
    const posMap = new Map<string, { x: number; y: number }>();
    // Several timelines (agent runs, split-comparison lanes) can branch off the same parent;
    // push a node down until its slot is free so siblings never sit on top of each other.
    const occupied = new Set<string>();

    return nodes.map((n) => {
      let position = n.position;
      const branchType = n.data.branch_type;
      const parentPos = n.data.parent_id ? posMap.get(n.data.parent_id) : undefined;

      if (!n.data.parent_id || branchType === "ROOT") {
        position = { x: 80, y: 220 };
      } else if (parentPos) {
        if (branchType === "SHADOW_REJECTED") {
          // Branch downward-right to (parent.x + 320, parent.y + 150)
          position = { x: parentPos.x + 320, y: parentPos.y + 150 };
        } else if (branchType === "COMMITTED_SAFE") {
          // Branch horizontally from parent to (parent.x + 320, parent.y)
          position = { x: parentPos.x + 320, y: parentPos.y };
        } else {
          position = { x: parentPos.x + 320, y: parentPos.y + 280 };
        }
      }

      while (occupied.has(`${position.x},${position.y}`)) {
        position = { x: position.x, y: position.y + 130 };
      }
      occupied.add(`${position.x},${position.y}`);
      posMap.set(n.id, position);

      // Determine node component type
      let type = "committedSafeNode";
      if (branchType === "SHADOW_REJECTED") {
        type = "shadowRejectedNode";
      } else if (branchType === "COMMITTED_SAFE") {
        type = "committedSafeNode";
      } else if (branchType === "ROOT") {
        type = "rootOriginNode";
      }

      return {
        id: n.id,
        type,
        position,
        data: n.data,
        selected: selectedNode?.id === n.id,
      };
    });
  }, [nodes, selectedNode]);

  /**
   * Deterministic Multiverse Edges:
   * - SHADOW_REJECTED: Animated red dashed SVG edge (#EF4444, strokeDasharray: "6 4").
   * - COMMITTED_SAFE: 3px solid emerald edge (#10B981, strokeWidth: 3).
   */
  const flowEdges: Edge[] = useMemo(() => {
    return edges.map((e) => {
      // Find target node to check branch type
      const targetNode = nodes.find((n) => n.id === e.target);
      const isRejected = targetNode?.data.branch_type === "SHADOW_REJECTED";

      if (isRejected) {
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          animated: true,
          type: "smoothstep",
          style: {
            stroke: "#EF4444",
            strokeWidth: 2.5,
            strokeDasharray: "6 4",
          },
        };
      }

      // COMMITTED_SAFE: 3px solid emerald edge
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        animated: false,
        type: "smoothstep",
        style: {
          stroke: "#10B981",
          strokeWidth: 3,
        },
      };
    });
  }, [edges, nodes]);

  const handleNodeClick: NodeMouseHandler = (_, node) => {
    onSelectNode(node.data as unknown as TelemetryNode);
  };

  return (
    <div className="relative flex-1 h-full w-full bg-[#090D16] overflow-hidden select-none">
      {/* Bypass Corruption Warning Banner */}
      {bypassAlert && (
        <div className="absolute top-4 left-6 right-6 z-20 flex items-center justify-between p-3 rounded-lg bg-red-950/90 border-2 border-[#EF4444] shadow-[0_0_25px_rgba(239,68,68,0.5)] animate-pulse">
          <div className="flex items-center gap-2 text-red-200 text-xs font-mono">
            <AlertTriangle className="w-5 h-5 text-[#EF4444] shrink-0" />
            <span className="font-bold uppercase tracking-wider text-[#EF4444]">
              CRITICAL UNVERIFIED BYPASS:
            </span>
            <span>{bypassAlert}</span>
          </div>
          {onDismissBypassAlert && (
            <button
              onClick={onDismissBypassAlert}
              className="p-1 rounded hover:bg-red-900/50 text-red-300 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      )}

      {/* Empty State Banner */}
      {nodes.length === 0 && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center pointer-events-none text-slate-500 font-mono text-center px-4">
          <div className="w-12 h-12 rounded-full border border-slate-800 bg-[#0F172A] flex items-center justify-center mb-3">
            <span className="w-3 h-3 rounded-full bg-cyan-400 animate-ping"></span>
          </div>
          <p className="text-sm font-semibold text-slate-200 mb-1">
            Multiverse DAG Ready
          </p>
          <p className="text-xs text-slate-500 max-w-sm">
            Listening on ws://127.0.0.1:8000/ws/telemetry. Press Run Scenario (Space) to send the agent&apos;s tool call through the kernel and watch the shadow branch fork, prove and self-heal.
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
        fitViewOptions={{ padding: 0.35, maxZoom: 1.1 }}
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
