# contracts/schemas.py
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


# --- CONTRACT 1: Interceptor Request Payload ---
class ToolCallPayload(StrictContractModel):
    tool_name: str
    target_resource: str
    arguments: dict[str, Any]


class InterceptRequest(StrictContractModel):
    trace_id: str
    timestamp_ns: int
    cartridge_id: Literal["HEALTHCARE_FHIR", "FINTECH_ESCROW", "CLOUD_DEVOPS"]
    chronos_mode: Literal["ACTIVE", "BYPASS"]
    agent_id: str
    tool_call: ToolCallPayload


# --- CONTRACT 2: Kernel-to-Z3 State Diff Payload ---
class StateDiffRequest(StrictContractModel):
    trace_id: str
    shadow_branch_id: str
    cartridge_id: Literal["HEALTHCARE_FHIR", "FINTECH_ESCROW", "CLOUD_DEVOPS"]
    cow_fork_latency_ms: float = Field(ge=0.0)
    state_pre: dict[str, Any]
    state_post_shadow: dict[str, Any]


# --- CONTRACT 3: Z3 Prover Verdict Payload ---
class ViolatedInvariant(StrictContractModel):
    rule_id: str
    formal_assertion: str
    counterexample: str
    remediation_hint: str


class Z3VerdictResponse(StrictContractModel):
    trace_id: str
    shadow_branch_id: str
    status: Literal["SAT", "UNSAT"]  # STRICT LOCK: Only SAT or UNSAT allowed
    proof_latency_ms: float = Field(ge=0.0)
    violated_invariants: list[ViolatedInvariant]
    smt2_dump: str
    sha256_proof_hash: str = Field(min_length=64, max_length=64)


# --- CONTRACT 4: WebSocket UI Telemetry Event ---
class TelemetryNodePayload(StrictContractModel):
    id: str
    parent_id: str
    branch_type: Literal["SHADOW_REJECTED", "COMMITTED_SAFE", "BYPASS_CORRUPTED", "SYSTEM_EVENT"]
    action_label: str
    total_latency_ms: float = Field(ge=0.0)
    z3_verdict: Literal["SAT", "UNSAT", "BYPASS", "N/A"]
    violated_rules: list[str]
    financial_loss_prevented_usd: float = Field(ge=0.0)
    clinical_hazard_prevented: bool


class TelemetryEvent(StrictContractModel):
    event_type: Literal[
        "BRANCH_EVALUATED",
        "BYPASS_CORRUPTED",
        "POLICY_COMPILED",
        "DEMO_RESET",
    ]
    trace_id: str
    cartridge_id: Literal["HEALTHCARE_FHIR", "FINTECH_ESCROW", "CLOUD_DEVOPS"]
    node: TelemetryNodePayload
