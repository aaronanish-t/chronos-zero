"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  TelemetryEvent,
  TelemetryNode,
  CartridgeId,
  ViolatedInvariant,
  KernelResetResponse,
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
  lastCowForkLatencyMs: number;
}

export type WSConnectionStatus =
  | "CONNECTING"
  | "CONNECTED"
  | "DISCONNECTED"
  | "RECONNECTING";

const WS_URL = "ws://localhost:8000/ws/telemetry";

export function useChronosWS() {
  const [status, setStatus] = useState<WSConnectionStatus>("DISCONNECTED");
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [nodes, setNodes] = useState<DAGNode[]>([]);
  const [edges, setEdges] = useState<DAGEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<TelemetryNode | null>(null);
  const [activeCartridge, setActiveCartridge] = useState<CartridgeId>("FINTECH_ESCROW");
  const [chronosMode, setChronosMode] = useState<"ACTIVE" | "BYPASS">("ACTIVE");
  const [isSimulating, setIsSimulating] = useState(false);
  const [bypassActiveAlert, setBypassActiveAlert] = useState<string | null>(null);

  const [metrics, setMetrics] = useState<TelemetryMetrics>({
    totalBranches: 0,
    unsatRollbacks: 0,
    satCommitted: 0,
    bypassCorrupted: 0,
    financialLossPreventedUsd: 0,
    clinicalHazardsPrevented: 0,
    avgTotalLatencyMs: 0,
    lastProofLatencyMs: 0,
    lastCowForkLatencyMs: 0,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const retryCountRef = useRef(0);
  const simulationTimersRef = useRef<NodeJS.Timeout[]>([]);

  // Calculate layout coordinates for a new node based on parent
  const calculateNodePosition = useCallback(
    (node: TelemetryNode, parentNode?: DAGNode): NodePosition => {
      if (!parentNode) {
        return { x: 80, y: 220 };
      }

      const pX = parentNode.position.x;
      const pY = parentNode.position.y;

      switch (node.branch_type) {
        case "SHADOW_REJECTED":
          // Branch downward-right (parent.x + 320, parent.y + 150)
          return { x: pX + 320, y: pY + 150 };
        case "COMMITTED_SAFE":
          // Continues on primary horizontal axis (0px Y delta)
          return { x: pX + 320, y: pY };
        case "BYPASS_CORRUPTED":
          return { x: pX + 320, y: pY + 280 };
        case "ROOT":
        default:
          return { x: pX + 320, y: pY };
      }
    },
    []
  );

  // Reducer to process incoming TelemetryEvent
  const processTelemetryEvent = useCallback(
    (event: TelemetryEvent) => {
      setEvents((prev) => [event, ...prev.slice(0, 99)]);

      // Handle stage reset event from kernel (POST /v1/kernel/reset broadcast)
      if (event.event_type === "DEMO_RESET" || event.node?.action_label === "DEMO_RESET") {
        setNodes([]);
        setEdges([]);
        setSelectedNode(null);
        setBypassActiveAlert(null);
        setMetrics({
          totalBranches: 0,
          unsatRollbacks: 0,
          satCommitted: 0,
          bypassCorrupted: 0,
          financialLossPreventedUsd: 0,
          clinicalHazardsPrevented: 0,
          avgTotalLatencyMs: 0,
          lastProofLatencyMs: 0,
          lastCowForkLatencyMs: 0,
        });
        return;
      }

      const rawNode = event.node;

      // Update metrics
      setMetrics((prev) => {
        const nextTotal = prev.totalBranches + 1;
        const newTotalLatency =
          (prev.avgTotalLatencyMs * prev.totalBranches + rawNode.total_latency_ms) /
          nextTotal;

        return {
          totalBranches: nextTotal,
          unsatRollbacks:
            prev.unsatRollbacks + (rawNode.z3_verdict === "UNSAT" ? 1 : 0),
          satCommitted:
            prev.satCommitted + (rawNode.z3_verdict === "SAT" ? 1 : 0),
          bypassCorrupted:
            prev.bypassCorrupted +
            (rawNode.branch_type === "BYPASS_CORRUPTED" ? 1 : 0),
          financialLossPreventedUsd:
            prev.financialLossPreventedUsd +
            (rawNode.financial_loss_prevented_usd || 0),
          clinicalHazardsPrevented:
            prev.clinicalHazardsPrevented +
            (rawNode.clinical_hazard_prevented ? 1 : 0),
          avgTotalLatencyMs: Number(newTotalLatency.toFixed(2)),
          lastProofLatencyMs: rawNode.proof_latency_ms ?? 0,
          lastCowForkLatencyMs: rawNode.cow_fork_latency_ms ?? 0,
        };
      });

      if (rawNode.branch_type === "BYPASS_CORRUPTED") {
        setBypassActiveAlert(
          `BYPASS CORRUPTED: Tool executed without Z3 formal verification! Action "${rawNode.action_label}" resulted in unverified state drift.`
        );
      }

      setNodes((currentNodes) => {
        // Prevent duplicate IDs
        if (currentNodes.some((n) => n.id === rawNode.id)) {
          return currentNodes;
        }

        const parentNode = rawNode.parent_id
          ? currentNodes.find((n) => n.id === rawNode.parent_id)
          : undefined;

        const position = calculateNodePosition(rawNode, parentNode);

        let nodeType = "committedSafeNode";
        if (rawNode.branch_type === "SHADOW_REJECTED") {
          nodeType = "shadowRejectedNode";
        } else if (rawNode.branch_type === "ROOT") {
          nodeType = "rootOriginNode";
        }

        const newDAGNode: DAGNode = {
          id: rawNode.id,
          data: rawNode,
          position,
          type: nodeType,
        };

        return [...currentNodes, newDAGNode];
      });

      // Add edge if parent exists
      if (rawNode.parent_id) {
        setEdges((currentEdges) => {
          const edgeId = `e-${rawNode.parent_id}-${rawNode.id}`;
          if (currentEdges.some((e) => e.id === edgeId)) {
            return currentEdges;
          }

          const isRejected = rawNode.branch_type === "SHADOW_REJECTED";
          const isCorrupted = rawNode.branch_type === "BYPASS_CORRUPTED";

          const edgeColor = isRejected
            ? "#EF4444"
            : isCorrupted
            ? "#F59E0B"
            : "#10B981";

          const newEdge: DAGEdge = {
            id: edgeId,
            source: rawNode.parent_id!,
            target: rawNode.id,
            animated: isRejected,
            style: {
              stroke: edgeColor,
              strokeWidth: isRejected ? 2.5 : 3,
              strokeDasharray: isRejected ? "6 4" : undefined,
            },
          };

          return [...currentEdges, newEdge];
        });
      }

      // Automatically select if it's the first or a rejected node
      setSelectedNode((prev) => (prev ? prev : rawNode));
    },
    [calculateNodePosition]
  );

  // Establish WebSocket connection
  const connectWebSocket = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setStatus(retryCountRef.current === 0 ? "CONNECTING" : "RECONNECTING");

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus("CONNECTED");
        retryCountRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const payload: TelemetryEvent = JSON.parse(event.data);
          processTelemetryEvent(payload);
        } catch (e) {
          console.error("[ChronosWS] Failed to parse message:", e);
        }
      };

      ws.onerror = () => {
        // Will trigger onclose
      };

      ws.onclose = () => {
        setStatus("DISCONNECTED");
        wsRef.current = null;

        // Exponential backoff reconnect: min 1000ms, max 16000ms
        const delay = Math.min(1000 * Math.pow(1.5, retryCountRef.current), 16000);
        retryCountRef.current += 1;

        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }
        reconnectTimeoutRef.current = setTimeout(() => {
          connectWebSocket();
        }, delay);
      };
    } catch {
      setStatus("DISCONNECTED");
    }
  }, [processTelemetryEvent]);

  // Clean initial connection attempt
  useEffect(() => {
    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      simulationTimersRef.current.forEach(clearTimeout);
    };
  }, [connectWebSocket]);

  // Reset DAG, metrics, and call live kernel stage reset (POST /v1/kernel/reset)
  const resetDAG = useCallback(() => {
    simulationTimersRef.current.forEach(clearTimeout);
    simulationTimersRef.current = [];
    setIsSimulating(false);
    setNodes([]);
    setEdges([]);
    setEvents([]);
    setSelectedNode(null);
    setBypassActiveAlert(null);
    setMetrics({
      totalBranches: 0,
      unsatRollbacks: 0,
      satCommitted: 0,
      bypassCorrupted: 0,
      financialLossPreventedUsd: 0,
      clinicalHazardsPrevented: 0,
      avgTotalLatencyMs: 0,
      lastProofLatencyMs: 0,
      lastCowForkLatencyMs: 0,
    });

    // Fire non-blocking POST /v1/kernel/reset
    const endpoints = ["http://localhost:8000/v1/kernel/reset", "/v1/kernel/reset"];
    (async () => {
      for (const url of endpoints) {
        try {
          const res = await fetch(url, {
            method: "POST",
            headers: { Accept: "application/json" },
            signal: AbortSignal.timeout(1500),
          });
          if (res.ok) {
            const data: KernelResetResponse = await res.json();
            console.log("[ChronosWS] Live kernel reset succeeded:", data);
            break;
          }
        } catch {
          // try next endpoint or fallback
        }
      }
    })();
  }, []);

  // 60fps Mock Simulation Engine
  const simulateMockTelemetry = useCallback(
    (cartridge: CartridgeId = "FINTECH_ESCROW") => {
      resetDAG();
      setIsSimulating(true);
      setActiveCartridge(cartridge);

      const rootNode: TelemetryNode = {
        id: "node_root",
        parent_id: null,
        branch_type: "ROOT",
        action_label: `Agent Session Init: [${cartridge}]`,
        total_latency_ms: 0.45,
        z3_verdict: "NONE",
        violated_rules: [],
        financial_loss_prevented_usd: 0,
        clinical_hazard_prevented: false,
        timestamp: Date.now(),
      };

      processTelemetryEvent({
        event_type: "BRANCH_EVALUATED",
        trace_id: `tr_${Date.now()}_001`,
        cartridge_id: cartridge,
        node: rootNode,
      });

      // Multi-turn scenarios
      const scenarios: Record<CartridgeId, TelemetryNode[]> = {
        FINTECH_ESCROW: [
          {
            id: "node_fin_turn1_unsat",
            parent_id: "node_root",
            branch_type: "SHADOW_REJECTED",
            action_label: "wire_transfer($185,000, IBAN_GB98_SPOOFED)",
            total_latency_ms: 3.42,
            cow_fork_latency_ms: 1.12,
            proof_latency_ms: 2.30,
            z3_verdict: "UNSAT",
            violated_rules: ["INV_FIN_01_ESCROW_CAP", "INV_FIN_02_SLA_ATTESTATION"],
            financial_loss_prevented_usd: 185000,
            clinical_hazard_prevented: false,
            smt2_dump: `; CHRONOS-ZERO Formal Proof Dump
(declare-const daily_escrow_spent_usd Real)
(declare-const transfer_amount_usd Real)
(declare-const daily_escrow_limit_usd Real)
(declare-const vendor_latency_ms Real)
(declare-const iban_allowlisted Bool)
(assert (= daily_escrow_spent_usd 75000.0))
(assert (= transfer_amount_usd 185000.0))
(assert (= daily_escrow_limit_usd 100000.0))
(assert (= vendor_latency_ms 324.5))
(assert (= iban_allowlisted false))
(assert (! (<= (+ daily_escrow_spent_usd transfer_amount_usd) daily_escrow_limit_usd) :named INV_FIN_01_ESCROW_CAP))
(assert (! (=> (> transfer_amount_usd 0.0) (and (<= vendor_latency_ms 200.0) (= iban_allowlisted true))) :named INV_FIN_02_SLA_ATTESTATION))
(check-sat)
; unsat core: (INV_FIN_01_ESCROW_CAP INV_FIN_02_SLA_ATTESTATION)`,
            sha256_proof_hash: "a4f892cb61e0b57e793cb8975de361b7b057863bc97a92df456740b61d3e891c",
            tool_call: {
              tool_name: "wire_transfer",
              target_resource: "escrow_payout_queue",
              arguments: {
                amount_usd: 185000,
                recipient_iban: "GB98_SPOOFED",
                vendor_id: "unverified_external_09",
              },
            },
            remediation_hint: "Requested wire exceeds remaining daily escrow limit ($25,000 USD remaining). In addition, counterparty failed zkTLS SLA check (324.5ms > 200ms) and is not allowlisted.",
            violated_invariants: [
              {
                rule_id: "INV_FIN_01_ESCROW_CAP",
                formal_assertion: "daily_escrow_spent_usd + transfer_amount_usd <= daily_escrow_limit_usd",
                counterexample: "spent=75000.0, transfer=185000.0, limit=100000.0 (sum=260000 > 100000)",
                remediation_hint: "Reduce transfer_amount_usd to <= 25000.0 USD or split into milestone tranches.",
              },
              {
                rule_id: "INV_FIN_02_SLA_ATTESTATION",
                formal_assertion: "Implies(transfer_amount_usd > 0, And(vendor_latency_ms <= 200.0, iban_allowlisted == True))",
                counterexample: "transfer=185000.0, latency=324.5ms, allowlisted=false",
                remediation_hint: "Route payout to verified backup vendor on treasury allowlist.",
              },
            ],
            state_pre: {
              escrow_id: "escrow_tx_9012",
              daily_escrow_spent_usd: 75000.0,
              daily_escrow_limit_usd: 100000.0,
              remaining_daily_allowance_usd: 25000.0,
              vendor_latency_ms: 324.5,
              iban_allowlisted: false,
              target_iban: "GB98_SPOOFED_UNVERIFIED",
              escrow_status: "LOCKED",
            },
            state_post_shadow: {
              escrow_id: "escrow_tx_9012",
              daily_escrow_spent_usd: 260000.0,
              daily_escrow_limit_usd: 100000.0,
              remaining_daily_allowance_usd: -160000.0,
              last_transfer_amount_usd: 185000.0,
              vendor_latency_ms: 324.5,
              iban_allowlisted: false,
              target_iban: "GB98_SPOOFED_UNVERIFIED",
              escrow_status: "DEFICIT_ROLLBACK_REQUIRED",
            },
            timestamp: Date.now(),
          },
          {
            id: "node_fin_turn2_sat",
            parent_id: "node_root",
            branch_type: "COMMITTED_SAFE",
            action_label: "wire_transfer($25,000, IBAN_GB12_VERIFIED_BACKUP)",
            total_latency_ms: 2.18,
            cow_fork_latency_ms: 0.94,
            proof_latency_ms: 1.24,
            z3_verdict: "SAT",
            violated_rules: [],
            financial_loss_prevented_usd: 0,
            clinical_hazard_prevented: false,
            smt2_dump: `; CHRONOS-ZERO Formal Proof Dump
(declare-const daily_escrow_spent_usd Real)
(declare-const transfer_amount_usd Real)
(declare-const daily_escrow_limit_usd Real)
(declare-const vendor_latency_ms Real)
(declare-const iban_allowlisted Bool)
(assert (= daily_escrow_spent_usd 75000.0))
(assert (= transfer_amount_usd 25000.0))
(assert (= daily_escrow_limit_usd 100000.0))
(assert (= vendor_latency_ms 48.2))
(assert (= iban_allowlisted true))
(assert (! (<= (+ daily_escrow_spent_usd transfer_amount_usd) daily_escrow_limit_usd) :named INV_FIN_01_ESCROW_CAP))
(assert (! (=> (> transfer_amount_usd 0.0) (and (<= vendor_latency_ms 200.0) (= iban_allowlisted true))) :named INV_FIN_02_SLA_ATTESTATION))
(check-sat)
; sat`,
            sha256_proof_hash: "7bc321e90d234a9ef1c469f3750d481284d720b7ea1e345fc5e7f12a39c09bf8",
            tool_call: {
              tool_name: "wire_transfer",
              target_resource: "escrow_payout_queue",
              arguments: {
                amount_usd: 25000,
                recipient_iban: "GB12_VERIFIED_BACKUP",
                vendor_id: "treasury_allowlisted_vendor_01",
              },
            },
            remediation_hint: "None. Self-healing completed cleanly within 1 turn.",
            violated_invariants: [],
            state_pre: {
              escrow_id: "escrow_tx_9012",
              daily_escrow_spent_usd: 75000.0,
              daily_escrow_limit_usd: 100000.0,
              remaining_daily_allowance_usd: 25000.0,
              vendor_latency_ms: 48.2,
              iban_allowlisted: true,
              target_iban: "GB12_VERIFIED_BACKUP",
              escrow_status: "LOCKED",
            },
            state_post_shadow: {
              escrow_id: "escrow_tx_9012",
              daily_escrow_spent_usd: 100000.0,
              daily_escrow_limit_usd: 100000.0,
              remaining_daily_allowance_usd: 0.0,
              last_transfer_amount_usd: 25000.0,
              vendor_latency_ms: 48.2,
              iban_allowlisted: true,
              target_iban: "GB12_VERIFIED_BACKUP",
              escrow_status: "DISBURSED_SETTLED",
            },
            timestamp: Date.now(),
          },
        ],
        HEALTHCARE_FHIR: [
          {
            id: "node_health_turn1_unsat",
            parent_id: "node_root",
            branch_type: "SHADOW_REJECTED",
            action_label: "prescribe_medication(Patient_449, Ibuprofen_800mg)",
            total_latency_ms: 2.85,
            cow_fork_latency_ms: 1.05,
            proof_latency_ms: 1.80,
            z3_verdict: "UNSAT",
            violated_rules: ["INV_HEALTH_01_EGFR_CONTRAINDICATION"],
            financial_loss_prevented_usd: 0,
            clinical_hazard_prevented: true,
            smt2_dump: `; CHRONOS-ZERO Clinical Safety Proof Dump
(declare-const egfr_ml_min Real)
(declare-const medication_is_nsaid Bool)
(declare-const acute_kidney_injury_risk Bool)
(assert (= egfr_ml_min 28.5))
(assert (= medication_is_nsaid true))
(assert (! (=> medication_is_nsaid (> egfr_ml_min 30.0)) :named INV_HEALTH_01_EGFR_CONTRAINDICATION))
(check-sat)
; unsat core: (INV_HEALTH_01_EGFR_CONTRAINDICATION)`,
            sha256_proof_hash: "55e2d148e6a1009bf33c09f302b17f8582d92c7302c34d58850a5814571ef99b",
            tool_call: {
              tool_name: "prescribe_medication",
              target_resource: "fhir_medication_request",
              arguments: {
                patient_id: "p_449",
                medication: "Ibuprofen 800mg Oral Tablet",
                dosage: "q8h prn pain",
              },
            },
            remediation_hint: "Patient eGFR (28.5 mL/min/1.73m²) violates minimum threshold (> 30.0) for high-dose NSAID. Substitute with renal-safe analgesic (Acetaminophen) and schedule Physical Therapy encounter.",
            violated_invariants: [
              {
                rule_id: "INV_HEALTH_01_EGFR_CONTRAINDICATION",
                formal_assertion: "Implies(medication_is_nsaid, egfr_ml_min > 30.0)",
                counterexample: "medication_is_nsaid=true, egfr=28.5 (<= 30.0)",
                remediation_hint: "Prescribe renal-safe Acetaminophen 500mg or order nephrology clearance.",
              },
            ],
            state_pre: {
              patient_id: "p_449",
              patient_status: "INPATIENT_NEPHROLOGY",
              egfr_ml_min: 28.5,
              chronic_kidney_disease_stage: 4,
              medication_active: "None",
              medication_is_nsaid: false,
              acute_kidney_injury_risk: false,
            },
            state_post_shadow: {
              patient_id: "p_449",
              patient_status: "INPATIENT_NEPHROLOGY",
              egfr_ml_min: 28.5,
              chronic_kidney_disease_stage: 4,
              medication_active: "Ibuprofen 800mg Oral Tablet",
              medication_is_nsaid: true,
              acute_kidney_injury_risk: true,
            },
            timestamp: Date.now(),
          },
          {
            id: "node_health_turn2_sat",
            parent_id: "node_root",
            branch_type: "COMMITTED_SAFE",
            action_label: "prescribe_medication(Patient_449, Acetaminophen_500mg) + schedule_pt(enc_108)",
            total_latency_ms: 1.94,
            cow_fork_latency_ms: 0.88,
            proof_latency_ms: 1.06,
            z3_verdict: "SAT",
            violated_rules: [],
            financial_loss_prevented_usd: 0,
            clinical_hazard_prevented: false,
            smt2_dump: `; CHRONOS-ZERO Clinical Safety Proof Dump
(declare-const egfr_ml_min Real)
(declare-const medication_is_nsaid Bool)
(assert (= egfr_ml_min 28.5))
(assert (= medication_is_nsaid false))
(assert (! (=> medication_is_nsaid (> egfr_ml_min 30.0)) :named INV_HEALTH_01_EGFR_CONTRAINDICATION))
(check-sat)
; sat`,
            sha256_proof_hash: "31fa6b98e21a2c4e908da8bc983d95ef581290378bcdef7642890fa389bb6241",
            tool_call: {
              tool_name: "prescribe_medication",
              target_resource: "fhir_medication_request",
              arguments: {
                patient_id: "p_449",
                medication: "Acetaminophen 500mg Oral Tablet",
                ancillary_order: "enc_108_physical_therapy",
              },
            },
            remediation_hint: "None. Self-healing verified clinical safety.",
            violated_invariants: [],
            state_pre: {
              patient_id: "p_449",
              patient_status: "INPATIENT_NEPHROLOGY",
              egfr_ml_min: 28.5,
              chronic_kidney_disease_stage: 4,
              medication_active: "None",
              medication_is_nsaid: false,
              acute_kidney_injury_risk: false,
            },
            state_post_shadow: {
              patient_id: "p_449",
              patient_status: "INPATIENT_NEPHROLOGY",
              egfr_ml_min: 28.5,
              chronic_kidney_disease_stage: 4,
              medication_active: "Acetaminophen 500mg Oral Tablet",
              medication_is_nsaid: false,
              acute_kidney_injury_risk: false,
              scheduled_encounter: "enc_108_physical_therapy",
            },
            timestamp: Date.now(),
          },
        ],
        CLOUD_DEVOPS: [
          {
            id: "node_ops_turn1_unsat",
            parent_id: "node_root",
            branch_type: "SHADOW_REJECTED",
            action_label: "execute_sql_migration(DROP TABLE users_v1;)",
            total_latency_ms: 3.12,
            cow_fork_latency_ms: 1.15,
            proof_latency_ms: 1.97,
            z3_verdict: "UNSAT",
            violated_rules: ["INV_OPS_01_DESTRUCTIVE_DDL"],
            financial_loss_prevented_usd: 350000,
            clinical_hazard_prevented: false,
            smt2_dump: `; CHRONOS-ZERO DevOps Migration Proof Dump
(declare-const is_production Bool)
(declare-const contains_destructive_drop Bool)
(assert (= is_production true))
(assert (= contains_destructive_drop true))
(assert (! (not (and is_production contains_destructive_drop)) :named INV_OPS_01_DESTRUCTIVE_DDL))
(check-sat)
; unsat core: (INV_OPS_01_DESTRUCTIVE_DDL)`,
            sha256_proof_hash: "98e4f1a27b82cd6739ea0411835bc4598d135790abce34199850123984faef42",
            tool_call: {
              tool_name: "execute_sql_migration",
              target_resource: "prod_aurora_cluster",
              arguments: {
                sql: "DROP TABLE users_v1;",
                environment: "production",
              },
            },
            remediation_hint: "Destructive table drop blocked on production cluster. Refactor to expand-and-contract zero downtime migration (ADD COLUMN with deprecation flag).",
            violated_invariants: [
              {
                rule_id: "INV_OPS_01_DESTRUCTIVE_DDL",
                formal_assertion: "Not(And(is_production == True, contains_destructive_drop == True))",
                counterexample: "is_production=true, contains_destructive_drop=true",
                remediation_hint: "Rewrite migration using non-destructive shadow column pattern.",
              },
            ],
            state_pre: {
              cluster_id: "aurora_prod_primary",
              is_production: true,
              active_tables: ["users_v1", "accounts", "transactions"],
              table_count: 3,
              destructive_ddl_executed: false,
            },
            state_post_shadow: {
              cluster_id: "aurora_prod_primary",
              is_production: true,
              active_tables: ["accounts", "transactions"],
              table_count: 2,
              contains_destructive_drop: true,
              destructive_ddl_executed: true,
              dropped_entity: "users_v1",
            },
            timestamp: Date.now(),
          },
          {
            id: "node_ops_turn2_sat",
            parent_id: "node_root",
            branch_type: "COMMITTED_SAFE",
            action_label: "execute_sql_migration(ALTER TABLE users ADD COLUMN v2_compat;)",
            total_latency_ms: 2.38,
            cow_fork_latency_ms: 0.98,
            proof_latency_ms: 1.40,
            z3_verdict: "SAT",
            violated_rules: [],
            financial_loss_prevented_usd: 0,
            clinical_hazard_prevented: false,
            smt2_dump: `; CHRONOS-ZERO DevOps Migration Proof Dump
(declare-const is_production Bool)
(declare-const contains_destructive_drop Bool)
(assert (= is_production true))
(assert (= contains_destructive_drop false))
(assert (! (not (and is_production contains_destructive_drop)) :named INV_OPS_01_DESTRUCTIVE_DDL))
(check-sat)
; sat`,
            sha256_proof_hash: "28409bdaef6134a091ef74892cfa419823419854728956bbaef0912480129571",
            tool_call: {
              tool_name: "execute_sql_migration",
              target_resource: "prod_aurora_cluster",
              arguments: {
                sql: "ALTER TABLE users ADD COLUMN v2_compat BOOLEAN DEFAULT true;",
                environment: "production",
              },
            },
            remediation_hint: "None. Zero-downtime migration committed safely.",
            violated_invariants: [],
            state_pre: {
              cluster_id: "aurora_prod_primary",
              is_production: true,
              active_tables: ["users_v1", "accounts", "transactions"],
              table_count: 3,
              destructive_ddl_executed: false,
            },
            state_post_shadow: {
              cluster_id: "aurora_prod_primary",
              is_production: true,
              active_tables: ["users_v1", "accounts", "transactions"],
              table_count: 3,
              contains_destructive_drop: false,
              destructive_ddl_executed: false,
              added_column: "users_v1.v2_compat",
            },
            timestamp: Date.now(),
          },
        ],
      };

      const scenarioNodes = scenarios[cartridge] || scenarios.FINTECH_ESCROW;

      // Stream turn 1 (UNSAT Shadow Rejected) after 400ms
      const t1 = setTimeout(() => {
        processTelemetryEvent({
          event_type: "BRANCH_EVALUATED",
          trace_id: `tr_${Date.now()}_002`,
          cartridge_id: cartridge,
          node: scenarioNodes[0],
        });
        setSelectedNode(scenarioNodes[0]);
      }, 400);

      // Stream turn 2 (SAT Committed Safe) after 1100ms
      const t2 = setTimeout(() => {
        processTelemetryEvent({
          event_type: "BRANCH_EVALUATED",
          trace_id: `tr_${Date.now()}_003`,
          cartridge_id: cartridge,
          node: scenarioNodes[1],
        });
        setIsSimulating(false);
      }, 1100);

      simulationTimersRef.current.push(t1, t2);
    },
    [processTelemetryEvent, resetDAG]
  );

  // Simulate Bypass Mode Corrupted State (Demonstrates what happens without Chronos)
  const simulateBypassCorruption = useCallback(() => {
    resetDAG();
    setIsSimulating(true);

    const rootNode: TelemetryNode = {
      id: "node_bypass_root",
      parent_id: null,
      branch_type: "ROOT",
      action_label: "Bypass Mode Active: Raw Agent Interception Disabled",
      total_latency_ms: 0.12,
      z3_verdict: "NONE",
      violated_rules: [],
      financial_loss_prevented_usd: 0,
      clinical_hazard_prevented: false,
      timestamp: Date.now(),
    };

    processTelemetryEvent({
      event_type: "BRANCH_EVALUATED",
      trace_id: `tr_${Date.now()}_root`,
      cartridge_id: activeCartridge,
      node: rootNode,
    });

    const corruptNode: TelemetryNode = {
      id: "node_corrupted_live",
      parent_id: "node_bypass_root",
      branch_type: "BYPASS_CORRUPTED",
      action_label: "FATAL: execute_unverified_wire($1,250,000 -> SANCTIONED_IBAN)",
      total_latency_ms: 0.95,
      cow_fork_latency_ms: 0,
      proof_latency_ms: 0,
      z3_verdict: "NONE",
      violated_rules: ["BYPASS_CIRCUIT_BROKEN", "UNCHECKED_SANCTIONS_COLLAPSE"],
      financial_loss_prevented_usd: 0,
      clinical_hazard_prevented: false,
      smt2_dump: "; NO FORMAL PROOF GENERATED: Kernel was operating in BYPASS mode.\n; State mutated directly on production database without Copy-on-Write isolation or Z3 verification.",
      sha256_proof_hash: "0000000000000000000000000000000000000000000000000000000000000000",
      tool_call: {
        tool_name: "raw_db_execute",
        target_resource: "prod_ledger",
        arguments: {
          statement: "UPDATE accounts SET balance = balance - 1250000 WHERE id = 'treasury';",
          sanction_check_bypassed: true,
        },
      },
      remediation_hint: "CATASTROPHIC STATE CORRUPTION: In BYPASS mode, the autonomous agent executed an unverified mutation causing permanent financial/compliance damage.",
      violated_invariants: [
        {
          rule_id: "INV_CRITICAL_BYPASS",
          formal_assertion: "chronos_mode == 'ACTIVE'",
          counterexample: "chronos_mode='BYPASS'",
          remediation_hint: "Re-enable CHRONOS ACTIVE kernel mode to enforce mathematical pre-execution invariants.",
        },
      ],
      timestamp: Date.now(),
    };

    const t1 = setTimeout(() => {
      processTelemetryEvent({
        event_type: "BYPASS_CORRUPTED",
        trace_id: `tr_${Date.now()}_corrupt`,
        cartridge_id: activeCartridge,
        node: corruptNode,
      });
      setSelectedNode(corruptNode);
      setIsSimulating(false);
    }, 600);

    simulationTimersRef.current.push(t1);
  }, [activeCartridge, processTelemetryEvent, resetDAG]);

  const toggleChronosMode = useCallback(() => {
    setChronosMode((prev) => {
      const nextMode = prev === "ACTIVE" ? "BYPASS" : "ACTIVE";
      if (nextMode === "BYPASS") {
        setBypassActiveAlert(
          "WARNING: Master Kernel switched to BYPASS mode. Tool executions bypass Copy-on-Write and Z3 formal proofs, exposing production databases to unverified mutations."
        );
      } else {
        setBypassActiveAlert(null);
      }
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
    isSimulating,
    bypassActiveAlert,
    dismissBypassAlert: () => setBypassActiveAlert(null),
    resetDAG,
    simulateMockTelemetry,
    simulateBypassCorruption,
  };
}
