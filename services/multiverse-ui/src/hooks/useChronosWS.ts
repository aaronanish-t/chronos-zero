"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  TelemetryEvent,
  TelemetryNode,
  CartridgeId,
  ChronosMode,
  RunScenarioResponse,
  isTelemetryEvent,
} from "../types/contracts";

export interface NodePosition {
  x: number;
  y: number;
}

export interface DAGNode {
  id: string;
  data: TelemetryNode;
  position: NodePosition;
  type: string;
}

export interface DAGEdge {
  id: string;
  source: string;
  target: string;
  animated?: boolean;
  style?: React.CSSProperties;
  type?: string;
}

export interface TelemetryMetrics {
  totalBranches: number;
  unsatRollbacks: number;
  satCommitted: number;
  bypassCorrupted: number;
  financialLossPreventedUsd: number;
  clinicalHazardsPrevented: number;
  avgTotalLatencyMs: number;
  lastProofLatencyMs: number;
}

export type WSConnectionStatus =
  | "CONNECTING"
  | "CONNECTED"
  | "DISCONNECTED"
  | "RECONNECTING";

export interface RunStatus {
  phase: "IDLE" | "RESETTING" | "RUNNING" | "DONE" | "ERROR";
  cartridge?: CartridgeId;
  mode?: ChronosMode;
  selfHealed?: boolean;
  agentSource?: string;
  message?: string;
  violatedRules?: string[]; // Turn 1 unsat core (real rule IDs)
  healProofMs?: number; // Z3 proof latency of the self-healed turn
}

export interface ActivePolicy {
  cartridge: CartridgeId;
  ruleId: string;
  text: string;
}

// Kernel telemetry is a WebSocket straight to the kernel; every HTTP call goes through the
// Next.js same-origin rewrites in next.config.ts (kernel :8000, Z3 :8001, agent :8002).
const WS_URL = process.env.NEXT_PUBLIC_CHRONOS_WS_URL ?? "ws://127.0.0.1:8000/ws/telemetry";
const ROOT_NODE_ID = "node_root"; // the kernel's parent_id for a timeline's first node
const RUN_TIMEOUT_MS = 15000;
const RESET_TIMEOUT_MS = 6000;

const EMPTY_METRICS: TelemetryMetrics = {
  totalBranches: 0,
  unsatRollbacks: 0,
  satCommitted: 0,
  bypassCorrupted: 0,
  financialLossPreventedUsd: 0,
  clinicalHazardsPrevented: 0,
  avgTotalLatencyMs: 0,
  lastProofLatencyMs: 0,
};

function rootNode(cartridge: CartridgeId): TelemetryNode {
  return {
    id: ROOT_NODE_ID,
    parent_id: "",
    branch_type: "ROOT",
    action_label: `Production timeline [${cartridge}]`,
    total_latency_ms: 0,
    z3_verdict: "N/A",
    violated_rules: [],
    financial_loss_prevented_usd: 0,
    clinical_hazard_prevented: false,
    cartridge_id: cartridge,
  };
}

function nodeType(branchType: TelemetryNode["branch_type"]): string {
  if (branchType === "SHADOW_REJECTED") return "shadowRejectedNode";
  if (branchType === "ROOT") return "rootOriginNode";
  return "committedSafeNode";
}

function describeRunError(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === "object" && "kernel_status" in detail) {
    const d = detail as { kernel_status: number; kernel_detail: string };
    let text = d.kernel_detail;
    try {
      text = JSON.parse(d.kernel_detail).detail ?? text;
    } catch {
      // kernel_detail was not JSON
    }
    return `Kernel ${d.kernel_status}: ${text}`;
  }
  if (typeof detail === "string") return `Agent ${status}: ${detail}`;
  return `Agent orchestrator returned HTTP ${status}`;
}

async function postJson(url: string, body: unknown, timeoutMs: number): Promise<Response> {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  });
}

export function useChronosWS() {
  const [status, setStatus] = useState<WSConnectionStatus>("DISCONNECTED");
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [nodes, setNodes] = useState<DAGNode[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [activeCartridge, setActiveCartridge] = useState<CartridgeId>("HEALTHCARE_FHIR");
  const [chronosMode, setChronosMode] = useState<ChronosMode>("ACTIVE");
  const [isRunning, setIsRunning] = useState(false);
  const [runStatus, setRunStatus] = useState<RunStatus>({ phase: "IDLE" });
  const [bypassActiveAlert, setBypassActiveAlert] = useState<string | null>(null);
  const [activePolicy, setActivePolicy] = useState<ActivePolicy | null>(null);
  const [metrics, setMetrics] = useState<TelemetryMetrics>(EMPTY_METRICS);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCountRef = useRef(0);
  const unmountedRef = useRef(false);
  const runningRef = useRef(false);
  // A BYPASS run writes straight to production; the next run reseeds first.
  const productionDirtyRef = useRef(false);

  const clearLocalState = useCallback(() => {
    setNodes([]);
    setEvents([]);
    setSelectedNodeId(null);
    setBypassActiveAlert(null);
    setMetrics(EMPTY_METRICS);
  }, []);

  /** Merge proof details (from the Contract 3 verdict) into an existing DAG node. */
  const mergeNodeDetails = useCallback((nodeId: string, details: Partial<TelemetryNode>) => {
    setNodes((current) =>
      current.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...details } } : n))
    );
  }, []);

  // Reducer for Contract 4 events from the kernel.
  const processTelemetryEvent = useCallback((event: TelemetryEvent) => {
    setEvents((prev) => [event, ...prev.slice(0, 99)]);

    if (event.event_type === "DEMO_RESET") {
      setNodes([]);
      setSelectedNodeId(null);
      setBypassActiveAlert(null);
      setMetrics(EMPTY_METRICS);
      return;
    }
    if (event.event_type === "POLICY_COMPILED" || event.node.branch_type === "SYSTEM_EVENT") {
      return; // not a branch of the production timeline
    }

    const wire = event.node;
    setMetrics((prev) => {
      const total = prev.totalBranches + 1;
      return {
        ...prev,
        totalBranches: total,
        unsatRollbacks: prev.unsatRollbacks + (wire.z3_verdict === "UNSAT" ? 1 : 0),
        satCommitted: prev.satCommitted + (wire.z3_verdict === "SAT" ? 1 : 0),
        bypassCorrupted: prev.bypassCorrupted + (wire.branch_type === "BYPASS_CORRUPTED" ? 1 : 0),
        financialLossPreventedUsd: prev.financialLossPreventedUsd + wire.financial_loss_prevented_usd,
        clinicalHazardsPrevented: prev.clinicalHazardsPrevented + (wire.clinical_hazard_prevented ? 1 : 0),
        avgTotalLatencyMs: Number(
          ((prev.avgTotalLatencyMs * prev.totalBranches + wire.total_latency_ms) / total).toFixed(2)
        ),
      };
    });

    if (wire.branch_type === "BYPASS_CORRUPTED") {
      setBypassActiveAlert(
        `BYPASS: "${wire.action_label}" was written to production with no shadow branch and no Z3 proof.`
      );
    }

    setNodes((current) => {
      if (current.some((n) => n.id === wire.id)) return current;
      const next = [...current];
      if (!next.some((n) => n.id === ROOT_NODE_ID)) {
        next.unshift({ id: ROOT_NODE_ID, data: rootNode(event.cartridge_id), position: { x: 80, y: 220 }, type: "rootOriginNode" });
      }
      // A parent the UI never saw (e.g. committed before a page reload) hangs off the root.
      const parentKnown = next.some((n) => n.id === wire.parent_id);
      const data: TelemetryNode = {
        ...wire,
        parent_id: parentKnown ? wire.parent_id : ROOT_NODE_ID,
        cartridge_id: event.cartridge_id,
        trace_id: event.trace_id,
        timestamp: Date.now(),
      };
      next.push({ id: wire.id, data, position: { x: 0, y: 0 }, type: nodeType(wire.branch_type) });
      return next;
    });
    setSelectedNodeId((prev) => prev ?? wire.id);
  }, []);

  // Edges are derived from parent_id so nodes and edges can never disagree.
  const edges: DAGEdge[] = useMemo(
    () =>
      nodes
        .filter((n) => n.data.parent_id)
        .map((n) => {
          const isRejected = n.data.branch_type === "SHADOW_REJECTED";
          const isCorrupted = n.data.branch_type === "BYPASS_CORRUPTED";
          return {
            id: `e-${n.data.parent_id}-${n.id}`,
            source: n.data.parent_id,
            target: n.id,
            animated: isRejected,
            style: {
              stroke: isRejected ? "#EF4444" : isCorrupted ? "#F59E0B" : "#10B981",
              strokeWidth: isRejected ? 2.5 : 3,
              strokeDasharray: isRejected ? "6 4" : undefined,
            },
          };
        }),
    [nodes]
  );

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId)?.data ?? null,
    [nodes, selectedNodeId]
  );
  const setSelectedNode = useCallback((node: TelemetryNode | null) => {
    setSelectedNodeId(node ? node.id : null);
  }, []);

  // WebSocket connection with capped exponential backoff.
  const connectWebSocket = useCallback(() => {
    if (unmountedRef.current) return;
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }
    setStatus(retryCountRef.current === 0 ? "CONNECTING" : "RECONNECTING");

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      // Handlers ignore a superseded socket (React StrictMode mounts effects twice in dev),
      // so a stale connection can neither double-count events nor clobber the live one.
      ws.onopen = () => {
        if (wsRef.current !== ws) return;
        setStatus("CONNECTED");
        retryCountRef.current = 0;
      };

      ws.onmessage = (message) => {
        if (wsRef.current !== ws) return;
        try {
          const payload: unknown = JSON.parse(message.data);
          if (isTelemetryEvent(payload)) {
            processTelemetryEvent(payload);
          } else {
            console.error("[ChronosWS] Dropped message that does not match Contract 4:", payload);
          }
        } catch (e) {
          console.error("[ChronosWS] Failed to parse message:", e);
        }
      };

      ws.onclose = () => {
        if (wsRef.current !== ws) return;
        wsRef.current = null;
        setStatus("DISCONNECTED");
        if (unmountedRef.current) return;
        const delay = Math.min(1000 * Math.pow(1.5, retryCountRef.current), 8000);
        retryCountRef.current += 1;
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(connectWebSocket, delay);
      };
    } catch {
      setStatus("DISCONNECTED");
    }
  }, [processTelemetryEvent]);

  useEffect(() => {
    unmountedRef.current = false;
    connectWebSocket();
    return () => {
      unmountedRef.current = true;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      const ws = wsRef.current;
      wsRef.current = null;
      ws?.close();
    };
  }, [connectWebSocket]);

  /** POST /v1/kernel/reset (reseed all cartridges, rotate audit chain) and clear compiled policies. */
  const resetKernel = useCallback(async (): Promise<string | null> => {
    try {
      const [kernel] = await Promise.all([
        postJson("/v1/kernel/reset", undefined, RESET_TIMEOUT_MS),
        postJson("/v1/z3/policies/clear", undefined, RESET_TIMEOUT_MS).catch(() => null),
      ]);
      if (!kernel.ok) {
        const body = await kernel.json().catch(() => null);
        return `Kernel reset failed (HTTP ${kernel.status}): ${body?.detail ?? "unknown error"}`;
      }
      productionDirtyRef.current = false;
      setActivePolicy(null);
      return null;
    } catch (e) {
      return `Kernel unreachable on :8000 (${(e as Error).message})`;
    }
  }, []);

  const resetDAG = useCallback(async () => {
    clearLocalState();
    setRunStatus({ phase: "RESETTING" });
    const error = await resetKernel();
    setRunStatus(error ? { phase: "ERROR", message: error } : { phase: "IDLE", message: "Stage reset: all cartridges reseeded" });
  }, [clearLocalState, resetKernel]);

  /**
   * Run the cartridge's real scenario through E3's agent orchestrator:
   * hazardous tool call -> kernel CoW fork -> Z3 -> (UNSAT) remediation -> self-healed retry.
   * The DAG fills from the kernel's live WebSocket events; the HTTP response adds each
   * turn's Contract 3 proof (SMT-LIB2, unsat core, SHA-256 receipt) to its node.
   */
  const runScenario = useCallback(
    async (cartridge: CartridgeId, mode: ChronosMode) => {
      if (runningRef.current) return;
      runningRef.current = true;
      setIsRunning(true);
      setActiveCartridge(cartridge);
      try {
        if (productionDirtyRef.current) {
          setRunStatus({ phase: "RESETTING", cartridge, mode, message: "Reseeding production after the BYPASS run" });
          const error = await resetKernel();
          if (error) throw new Error(error);
          clearLocalState();
        }
        setRunStatus({ phase: "RUNNING", cartridge, mode });
        const policy = activePolicy && activePolicy.cartridge === cartridge ? activePolicy.text : null;

        let res: Response;
        try {
          res = await postJson(
            "/v1/agent/run-scenario",
            { cartridge_id: cartridge, chronos_mode: mode, custom_prompt: policy },
            RUN_TIMEOUT_MS
          );
        } catch (e) {
          throw new Error(`Agent orchestrator unreachable on :8002 (${(e as Error).message})`);
        }
        const body = await res.json().catch(() => null);
        if (!res.ok) throw new Error(describeRunError(res.status, body));
        const run = body as RunScenarioResponse;

        let firstNodeId: string | null = null;
        for (const turn of run.turns) {
          const v = turn.verdict;
          const nodeId =
            typeof v.shadow_branch_id === "string"
              ? `node_${v.shadow_branch_id}`
              : typeof v.node_id === "string"
              ? (v.node_id as string)
              : null;
          if (!nodeId) continue;
          firstNodeId = firstNodeId ?? nodeId;
          mergeNodeDetails(nodeId, {
            tool_call: turn.tool_call,
            agent_source: turn.agent_source,
            ...(v.status
              ? {
                  proof_latency_ms: v.proof_latency_ms,
                  smt2_dump: v.smt2_dump,
                  sha256_proof_hash: v.sha256_proof_hash,
                  violated_invariants: v.violated_invariants,
                }
              : {
                  state_pre: v.state_pre as Record<string, unknown>,
                  state_post_shadow: v.state_post as Record<string, unknown>,
                }),
          });
          if (typeof v.proof_latency_ms === "number") {
            setMetrics((prev) => ({ ...prev, lastProofLatencyMs: v.proof_latency_ms as number }));
          }
        }
        if (firstNodeId) setSelectedNodeId(firstNodeId);
        if (mode === "BYPASS") productionDirtyRef.current = true;

        setRunStatus({
          phase: "DONE",
          cartridge,
          mode,
          selfHealed: run.self_healed,
          agentSource: run.turns.map((t) => t.agent_source).join(" / "),
          violatedRules: (run.turns[0]?.verdict.violated_invariants ?? []).map((v) => v.rule_id),
          healProofMs: run.turns[1]?.verdict.proof_latency_ms,
          message:
            mode === "BYPASS"
              ? "Unverified write committed to production (next run reseeds first)"
              : run.self_healed
              ? "Blocked in shadow, self-healed in 1 turn, committed with SHA-256 receipt"
              : run.turns[0]?.verdict.status === "SAT"
              ? "Proven SAT on the first turn and committed"
              : "Self-healing retry was also rejected",
        });
      } catch (e) {
        setRunStatus({ phase: "ERROR", cartridge, mode, message: (e as Error).message });
      } finally {
        runningRef.current = false;
        setIsRunning(false);
      }
    },
    [activePolicy, clearLocalState, mergeNodeDetails, resetKernel]
  );

  const toggleChronosMode = useCallback(() => {
    setChronosMode((prev) => {
      const nextMode = prev === "ACTIVE" ? "BYPASS" : "ACTIVE";
      setBypassActiveAlert(
        nextMode === "BYPASS"
          ? "Kernel switched to BYPASS: the next run writes straight to production with no shadow branch and no Z3 proof."
          : null
      );
      return nextMode;
    });
  }, []);

  return {
    status,
    events,
    nodes,
    edges,
    selectedNode,
    setSelectedNode,
    metrics,
    activeCartridge,
    setActiveCartridge,
    chronosMode,
    setChronosMode,
    toggleChronosMode,
    isRunning,
    runStatus,
    bypassActiveAlert,
    dismissBypassAlert: () => setBypassActiveAlert(null),
    resetDAG,
    runScenario,
    activePolicy,
    setActivePolicy,
  };
}
