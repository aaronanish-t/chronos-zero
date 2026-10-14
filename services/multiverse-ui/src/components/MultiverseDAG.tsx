"use client";

import React, { useMemo, useRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  Node,
  Edge,
  NodeMouseHandler,
  useReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { TelemetryNode } from "../types/contracts";
import { DAGNode, DAGEdge } from "../hooks/useChronosWS";
import { MultiverseNode } from "./MultiverseNode";

interface MultiverseDAGProps {
  nodes: DAGNode[];
  edges: DAGEdge[];
  selectedNode: TelemetryNode | null;
  onSelectNode: (node: TelemetryNode) => void;
  bypassAlert?: string | null;
  onDismissBypassAlert?: () => void;
}

function DAGCanvas({
  nodes,
  edges,
  selectedNode,
  onSelectNode,
  bypassAlert,
  onDismissBypassAlert,
}: MultiverseDAGProps) {
  const { zoomIn, zoomOut, fitView } = useReactFlow();

  const nodeTypes = useMemo(
    () => ({
      shadowRejectedNode: MultiverseNode,
      committedSafeNode: MultiverseNode,
      rootOriginNode: MultiverseNode,
      multiverseNode: MultiverseNode,
    }),
    []
  );

  /**
   * Deterministic Multiverse Layout Reducer:
   * - Root node at (80, 220).
   * - SHADOW_REJECTED branches downward-right to (parent.x + 360, parent.y + 140).
   * - COMMITTED_SAFE branches horizontally to (parent.x + 360, parent.y).
   */
  const flowNodes: Node<TelemetryNode>[] = useMemo(() => {
    const posMap = new Map<string, { x: number; y: number }>();
    const occupied = new Set<string>();

    return nodes.map((n) => {
      let position = n.position;
      const branchType = n.data.branch_type;
      const parentPos = n.data.parent_id ? posMap.get(n.data.parent_id) : undefined;

      if (!n.data.parent_id || branchType === "ROOT") {
        position = { x: 80, y: 220 };
      } else if (parentPos) {
        if (branchType === "SHADOW_REJECTED") {
          position = { x: parentPos.x + 360, y: parentPos.y + 140 };
        } else if (branchType === "COMMITTED_SAFE") {
          position = { x: parentPos.x + 360, y: parentPos.y };
        } else {
          position = { x: parentPos.x + 360, y: parentPos.y + 280 };
        }
      }

      while (occupied.has(`${position.x},${position.y}`)) {
        position = { x: position.x, y: position.y + 140 };
      }
      occupied.add(`${position.x},${position.y}`);
      posMap.set(n.id, position);

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
   * - SHADOW_REJECTED: Crimson dashed glowing edge (#EF4444).
   * - COMMITTED_SAFE: Solid emerald glowing edge (#10B981).
   */
  const flowEdges: Edge[] = useMemo(() => {
    return edges.map((e) => {
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
            stroke: "#ef4444",
            strokeWidth: 2.5,
            strokeDasharray: "6 4",
            filter: "url(#crimson-glow)",
          },
        };
      }

      return {
        id: e.id,
        source: e.source,
        target: e.target,
        animated: false,
        type: "smoothstep",
        style: {
          stroke: "#10b981",
          strokeWidth: 2.5,
          filter: "url(#emerald-glow)",
        },
      };
    });
  }, [edges, nodes]);

  const handleNodeClick: NodeMouseHandler = (_, node) => {
    onSelectNode(node.data as unknown as TelemetryNode);
  };

  const activeBranchId =
    selectedNode?.shadow_branch_id ||
    (nodes.length > 0 ? nodes[nodes.length - 1].data.shadow_branch_id : "mult_origin");

  return (
    <div className="relative flex-1 h-full w-full bg-surface-container-lowest overflow-hidden select-none flex flex-col bg-[radial-gradient(#1c1f29_1px,transparent_1px)] [background-size:24px_24px]">
      {/* Embedded SVG Filter Definitions for Emerald and Crimson path glows */}
      <svg
        style={{
          position: "absolute",
          width: 0,
          height: 0,
          overflow: "hidden",
          pointerEvents: "none",
        }}
        aria-hidden="true"
      >
        <defs>
          <filter id="emerald-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <filter id="crimson-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>
      </svg>

      {/* Canvas HUD Floating Header */}
      <div className="flex items-center justify-between p-3.5 z-20 pointer-events-auto">
        <div className="flex items-center gap-2 bg-surface-container/90 backdrop-blur-md px-3 py-1.5 rounded-DEFAULT shadow-md border border-white/5">
          <span className="material-symbols-outlined text-sm text-secondary">
            account_tree
          </span>
          <span className="font-label-sm text-label-sm uppercase tracking-wider font-semibold text-on-surface">
            Multiverse DAG Graph
          </span>
          <span className="text-outline font-mono text-[10px]">
            {"// snapshot_branch_id: " + activeBranchId}
          </span>
        </div>

        {/* Canvas Controls */}
        <div className="flex items-center gap-1 bg-surface-container/90 backdrop-blur-md p-1 rounded-DEFAULT shadow-md border border-white/5">
          <button
            onClick={() => zoomIn()}
            className="p-1 rounded-DEFAULT hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface transition-colors"
            title="Zoom In"
          >
            <span className="material-symbols-outlined text-sm leading-none">
              zoom_in
            </span>
          </button>
          <button
            onClick={() => zoomOut()}
            className="p-1 rounded-DEFAULT hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface transition-colors"
            title="Zoom Out"
          >
            <span className="material-symbols-outlined text-sm leading-none">
              zoom_out
            </span>
          </button>
          <button
            onClick={() => fitView({ padding: 0.3, duration: 400 })}
            className="p-1 rounded-DEFAULT hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface transition-colors"
            title="Fit to View"
          >
            <span className="material-symbols-outlined text-sm leading-none">
              fit_screen
            </span>
          </button>
          <div className="w-px h-3 bg-surface-container-highest mx-0.5" />
          <div className="px-2 py-0.5 font-label-sm text-label-sm text-outline flex items-center gap-1">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-primary" />
              SAT
            </span>
            <span className="flex items-center gap-1 ml-1.5">
              <span className="w-2 h-2 rounded-full bg-error" />
              UNSAT
            </span>
          </div>
        </div>
      </div>

      {/* Bypass Corruption Warning Banner */}
      {bypassAlert && (
        <div className="absolute top-16 left-6 right-6 z-30 flex items-center justify-between p-3 rounded-DEFAULT bg-error/20 border border-error shadow-[0_0_25px_rgba(239,68,68,0.5)] backdrop-blur-md animate-pulse">
          <div className="flex items-center gap-2 text-on-surface font-mono text-label-sm">
            <span className="material-symbols-outlined text-base text-error">
              warning
            </span>
            <span className="font-bold uppercase tracking-wider text-error">
              CRITICAL UNVERIFIED BYPASS:
            </span>
            <span>{bypassAlert}</span>
          </div>
          {onDismissBypassAlert && (
            <button
              onClick={onDismissBypassAlert}
              className="p-1 rounded hover:bg-error/30 text-on-surface-variant hover:text-on-surface transition-colors"
            >
              <span className="material-symbols-outlined text-sm">close</span>
            </button>
          )}
        </div>
      )}

      {/* Empty State Prompt */}
      {nodes.length === 0 && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center pointer-events-none text-outline font-mono text-center px-4">
          <div className="w-12 h-12 rounded-full border border-surface-container-high bg-surface-container flex items-center justify-center mb-3">
            <span className="w-2.5 h-2.5 rounded-full bg-primary animate-ping" />
          </div>
          <p className="font-label-md text-label-md font-semibold text-on-surface mb-1">
            Multiverse DAG Ready
          </p>
          <p className="font-label-sm text-label-sm text-on-surface-variant max-w-sm">
            Listening for live kernel telemetry. Press Run Scenario (Space) to
            send the agent&apos;s tool call through the kernel and watch the
            speculative shadow branch fork, prove and self-heal.
          </p>
        </div>
      )}

      {/* ReactFlow Core Viewport */}
      <div className="flex-1 w-full h-full relative">
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
            size={1.2}
            color="#262a34"
          />
          <Controls showInteractive={false} className="!bottom-4 !left-4" />
          <MiniMap
            nodeColor={(n) => {
              const nodeData = n.data as unknown as TelemetryNode;
              if (nodeData?.branch_type === "SHADOW_REJECTED") return "#ef4444";
              if (nodeData?.branch_type === "COMMITTED_SAFE") return "#10b981";
              if (nodeData?.branch_type === "BYPASS_CORRUPTED") return "#ff7a73";
              return "#4cd7f6";
            }}
            maskColor="rgba(10, 14, 23, 0.85)"
            className="!bottom-4 !right-4 !bg-surface-container !border !border-white/10 !rounded overflow-hidden"
            zoomable
            pannable
          />
        </ReactFlow>
      </div>

      {/* Canvas Footer Status indicators */}
      <div className="px-4 py-2 bg-surface-container-lowest/80 border-t border-surface-container-high/40 flex flex-wrap items-center justify-between gap-3 z-20 text-[11px] font-mono text-outline">
        <div className="flex items-center gap-2">
          <span>LAYOUT:</span>
          <span className="px-2 py-0.5 rounded-DEFAULT bg-surface-container text-on-surface">
            Deterministic Track // COW
          </span>
          <span className="px-2 py-0.5 rounded-DEFAULT bg-primary/10 text-primary font-semibold">
            Active Filter: All Invariants
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-primary" />
            SAT Target
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-error" />
            UNSAT Killed
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-secondary" />
            Self-Heal Arc
          </span>
        </div>
      </div>
    </div>
  );
}

export const MultiverseDAG: React.FC<MultiverseDAGProps> = (props) => {
  return (
    <ReactFlowProvider>
      <DAGCanvas {...props} />
    </ReactFlowProvider>
  );
};
