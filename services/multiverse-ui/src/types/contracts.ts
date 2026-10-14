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

// Contract 3 status is locked to SAT | UNSAT (AGENTS.md section 3): the verifier fails closed to UNSAT.
export type Z3Status = "SAT" | "UNSAT";

// Contract 4 node.z3_verdict (contracts/ws_telemetry.schema.json).
export type NodeZ3Verdict = "SAT" | "UNSAT" | "BYPASS" | "N/A";

// Contract 4 node.branch_type. SYSTEM_EVENT carries DEMO_RESET.
export type BranchType =
  | "SHADOW_REJECTED"
  | "COMMITTED_SAFE"
  | "BYPASS_CORRUPTED"
  | "SYSTEM_EVENT";

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

// Exactly the Contract 4 node, as the kernel sends it.
export interface TelemetryNodePayload {
  id: string;
  parent_id: string;
  branch_type: BranchType;
  action_label: string;
  total_latency_ms: number;
  z3_verdict: NodeZ3Verdict;
  violated_rules: string[];
  financial_loss_prevented_usd: number;
  clinical_hazard_prevented: boolean;
}

export interface TelemetryEvent {
  event_type: TelemetryEventType;
  trace_id: string;
  cartridge_id: CartridgeId;
  node: TelemetryNodePayload;
}

// UI-side DAG node: a Contract 4 node plus proof details merged in from the matching
// Contract 3 verdict (node id == "node_" + shadow_branch_id). "ROOT" is the UI's own
// session-origin node and never appears on the wire.
export interface TelemetryNode extends Omit<TelemetryNodePayload, "branch_type"> {
  branch_type: BranchType | "ROOT";
  cartridge_id?: CartridgeId;
  trace_id?: string;
  proof_latency_ms?: number;
  smt2_dump?: string;
  sha256_proof_hash?: string;
  violated_invariants?: ViolatedInvariant[];
  tool_call?: ToolCall;
  agent_source?: string;
  timestamp?: number;
  [key: string]: unknown;
}

const CARTRIDGE_IDS: readonly string[] = ["HEALTHCARE_FHIR", "FINTECH_ESCROW", "CLOUD_DEVOPS"];
const EVENT_TYPES: readonly string[] = ["BRANCH_EVALUATED", "BYPASS_CORRUPTED", "POLICY_COMPILED", "DEMO_RESET"];
const BRANCH_TYPES: readonly string[] = ["SHADOW_REJECTED", "COMMITTED_SAFE", "BYPASS_CORRUPTED", "SYSTEM_EVENT"];
const NODE_VERDICTS: readonly string[] = ["SAT", "UNSAT", "BYPASS", "N/A"];

/** Runtime Contract 4 check: the DAG only ever renders events that match the schema. */
export function isTelemetryEvent(value: unknown): value is TelemetryEvent {
  if (typeof value !== "object" || value === null) return false;
  const e = value as Record<string, unknown>;
  const n = e.node as Record<string, unknown> | undefined;
  return (
    EVENT_TYPES.includes(e.event_type as string) &&
    typeof e.trace_id === "string" &&
    CARTRIDGE_IDS.includes(e.cartridge_id as string) &&
    typeof n === "object" &&
    n !== null &&
    typeof n.id === "string" &&
    typeof n.parent_id === "string" &&
    BRANCH_TYPES.includes(n.branch_type as string) &&
    typeof n.action_label === "string" &&
    typeof n.total_latency_ms === "number" &&
    NODE_VERDICTS.includes(n.z3_verdict as string) &&
    Array.isArray(n.violated_rules) &&
    typeof n.financial_loss_prevented_usd === "number" &&
    typeof n.clinical_hazard_prevented === "boolean"
  );
}

// ==========================================
// Kernel Tamper-Evident Audit Log (GET /v1/kernel/audit-log)
// ==========================================

export interface AuditEntry {
  index: number;
  trace_id: string;
  shadow_branch_id: string;
  status: string;
  timestamp_ns: string; // kept as digits: nanoseconds exceed Number.MAX_SAFE_INTEGER
  smt2_dump: string;
  prev_hash: string;
  entry_hash: string;
}

export interface AuditLogResponse {
  length: number;
  genesis_hash: string;
  head_hash: string;
  merkle_root: string;
  verified: boolean;
  entries: AuditEntry[];
}

// ==========================================
// Kernel Split Comparison (POST /v1/kernel/run-split-comparison)
// ==========================================

export interface SplitComparisonRequest {
  trace_id: string;
  timestamp_ns: number;
  cartridge_id: CartridgeId;
  agent_id: string;
  steps: ToolCall[];
}

export interface SplitBypassStep {
  step: number;
  committed?: boolean;
  status_code?: number;
  error?: string;
  corruption?: {
    capital_exposed_usd: number;
    rows_lost: number;
    changed_fields?: Record<string, { pre: unknown; post: unknown }>;
  };
  [key: string]: unknown;
}

export interface SplitActiveStep {
  step: number;
  verdict?: {
    trace_id: string;
    shadow_branch_id: string;
    status: Z3Status;
    proof_latency_ms: number;
    violated_invariants: ViolatedInvariant[];
    smt2_dump: string;
    sha256_proof_hash: string;
  };
  status_code?: number;
  error?: string;
  [key: string]: unknown;
}

export interface SplitBypassResult {
  isolated_copy?: string;
  steps: SplitBypassStep[];
  capital_exposed_usd: number;
  rows_lost: number;
}

export interface SplitActiveResult {
  steps: SplitActiveStep[];
  blocked: number;
  committed: number;
}

export interface SplitComparisonResponse {
  trace_id: string;
  cartridge_id: CartridgeId;
  bypass: SplitBypassResult;
  active: SplitActiveResult;
  total_latency_ms: number;
}

// ==========================================
// Kernel Reset (POST /v1/kernel/reset)
// ==========================================

export interface KernelResetResponse {
  status: string;
  trace_id: string;
  reset_latency_ms: number;
  within_budget: boolean;
  seed_ms: number;
  rolled_back_branches: number;
  sandboxes_dropped: number;
  archived_audit_chain: string | null;
}

// ==========================================
// Agent Orchestrator (POST /v1/agent/run-scenario on :8002, E3)
// ==========================================

export interface RunScenarioRequest {
  cartridge_id: CartridgeId;
  chronos_mode: ChronosMode;
  custom_prompt?: string | null;
}

export interface ScenarioTurn {
  turn: number;
  tool_call: ToolCall;
  agent_source: string;
  // ACTIVE: a Contract 3 verdict. BYPASS: the kernel's unverified result (no status field).
  verdict: Partial<Z3VerdictPayload> & Record<string, unknown>;
}

export interface RunScenarioResponse {
  trace_id: string;
  cartridge_id: CartridgeId;
  chronos_mode: ChronosMode;
  turns: ScenarioTurn[];
  self_healed: boolean;
}

// ==========================================
// Z3 Policy Studio (POST /v1/z3/compile-policy on :8001, E2)
// ==========================================

export interface PolicyCompileResponse {
  status: "COMPILED" | "ERROR";
  cartridge_id: string;
  rule_id: string;
  formal_assertion: string;
  compiled_code?: string | null;
  smt2_dump?: string | null;
  compilation_latency_ms?: number | null;
  remediation_hint?: string | null;
  message: string;
}


