/**
 * CHRONOS-ZERO Immutable Data Contracts
 * Mirroring JSON Schemas from /contracts/
 *
 * Contract 1: Interceptor Request Payload (POST /v1/kernel/execute)
 * Contract 2: Kernel-to-Z3 State Diff Payload (POST /v1/z3/verify)
 * Contract 3: Z3 Prover Verdict Payload
 * Contract 4: WebSocket UI Telemetry Event (ws://localhost:8000/ws/telemetry)
 */

// ==========================================
// Shared Primitive Enums & Literals
// ==========================================

export type CartridgeId = "HEALTHCARE_FHIR" | "FINTECH_ESCROW" | "CLOUD_DEVOPS";

export type ChronosMode = "ACTIVE" | "BYPASS";

export type Z3Status = "SAT" | "UNSAT" | "TIMEOUT" | "ERROR";

export type NodeZ3Verdict = "SAT" | "UNSAT" | "TIMEOUT" | "ERROR" | "NONE";

export type BranchType =
  | "ROOT"
  | "SHADOW_REJECTED"
  | "COMMITTED_SAFE"
  | "BYPASS_CORRUPTED";

export type TelemetryEventType =
  | "BRANCH_EVALUATED"
  | "BYPASS_CORRUPTED"
  | "POLICY_COMPILED"
  | "DEMO_RESET";

// ==========================================
// Contract 1: Interceptor Request Payload
// ==========================================

export interface ToolCall {
  tool_name: string;
  target_resource: string;
  arguments: Record<string, unknown>;
}

export interface InterceptPayload {
  trace_id: string; // pattern: ^tr_[A-Za-z0-9]+$
  timestamp_ns: number;
  cartridge_id: CartridgeId;
  chronos_mode: ChronosMode;
  agent_id: string;
  tool_call: ToolCall;
}

// ==========================================
// Contract 2: Kernel-to-Z3 State Diff Payload
// ==========================================

export interface StateDiffPayload {
  trace_id: string;
  shadow_branch_id: string;
  cartridge_id: CartridgeId;
  cow_fork_latency_ms: number;
  state_pre: Record<string, unknown>;
  state_post_shadow: Record<string, unknown>;
}

// ==========================================
// Contract 3: Z3 Prover Verdict Payload
// ==========================================

export interface ViolatedInvariant {
  rule_id: string; // pattern: ^INV_[A-Z]+_[0-9]{2}_[A-Z0-9_]+$
  formal_assertion: string;
  counterexample: string;
  remediation_hint: string;
}

export interface Z3VerdictPayload {
  trace_id: string;
  shadow_branch_id: string;
  status: Z3Status;
  proof_latency_ms: number;
  violated_invariants: ViolatedInvariant[];
  smt2_dump: string;
  sha256_proof_hash: string; // pattern: ^[a-f0-9]{64}$
}

// ==========================================
// Contract 4: WebSocket UI Telemetry Event
// ==========================================

export interface TelemetryNode {
  id: string;
  parent_id: string | null;
  branch_type: BranchType;
  action_label: string;
  total_latency_ms: number;
  z3_verdict: NodeZ3Verdict;
  violated_rules: string[];
  financial_loss_prevented_usd: number;
  clinical_hazard_prevented: boolean;
  // Extended fields for inspection / proof drawer UI
  cow_fork_latency_ms?: number;
  proof_latency_ms?: number;
  smt2_dump?: string;
  sha256_proof_hash?: string;
  violated_invariants?: ViolatedInvariant[];
  tool_call?: ToolCall;
  remediation_hint?: string;
  timestamp?: number;
  [key: string]: unknown;
}

export interface TelemetryEvent {
  event_type: TelemetryEventType;
  trace_id: string;
  cartridge_id: CartridgeId;
  node: TelemetryNode;
}
