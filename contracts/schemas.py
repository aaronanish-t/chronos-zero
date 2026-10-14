"""Pydantic v2 schemas for CHRONOS-ZERO inter-service contracts.

Strictly aligned with:
- /contracts/intercept_payload.schema.json (Contract 1)
- /contracts/state_diff.schema.json (Contract 2)
- /contracts/z3_verdict.schema.json (Contract 3)
- /contracts/ws_telemetry.schema.json (Contract 4)
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Contract 3 Supporting Models
# ---------------------------------------------------------------------------

class ViolatedInvariant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(
        ...,
        description="Formal invariant identifier, e.g. INV_MED_01_RENAL_SAFETY",
    )
    formal_assertion: str = Field(
        ...,
        description="Mathematical or logical assertion string represented in SMT/Python",
    )
    counterexample: str = Field(
        ...,
        description="Observed counterexample variables or failure context",
    )
    remediation_hint: str = Field(
        ...,
        description="Deterministic guidance for agent 1-turn self-healing retry",
    )


# ---------------------------------------------------------------------------
# Contract 1: Interceptor Request Payload (POST /v1/kernel/execute)
# ---------------------------------------------------------------------------

class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(..., min_length=1)
    target_resource: str = Field(..., min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class InterceptPayloadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str = Field(..., pattern=r"^tr_[A-Za-z0-9]+$")
    timestamp_ns: int = Field(..., ge=0, description="Unix timestamp in nanoseconds")
    cartridge_id: Literal["HEALTHCARE_FHIR", "FINTECH_ESCROW", "CLOUD_DEVOPS"]
    chronos_mode: Literal["ACTIVE", "BYPASS"]
    agent_id: str = Field(..., min_length=1)
    tool_call: ToolCall


# ---------------------------------------------------------------------------
# Contract 2: Kernel-to-Z3 State Diff Payload (POST /v1/z3/verify)
# ---------------------------------------------------------------------------

class StateDiffRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    trace_id: str
    shadow_branch_id: str
    cartridge_id: str
    cow_fork_latency_ms: float = Field(default=0.0, ge=0.0)
    state_pre: dict[str, Any] = Field(default_factory=dict)
    state_post_shadow: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Contract 3: Z3 Prover Verdict Payload (Response from POST /v1/z3/verify)
# ---------------------------------------------------------------------------

class Z3VerdictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    shadow_branch_id: str
    status: Literal["SAT", "UNSAT", "TIMEOUT", "ERROR"]
    proof_latency_ms: float = Field(..., ge=0.0)
    violated_invariants: list[ViolatedInvariant] = Field(default_factory=list)
    smt2_dump: str = Field(default="")
    sha256_proof_hash: str = Field(..., pattern=r"^[a-f0-9]{64}$")


# ---------------------------------------------------------------------------
# Policy Studio Compilation Request / Response
# ---------------------------------------------------------------------------

class PolicyCompileRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    cartridge_id: str
    rule_id: str
    natural_language_rule: str


class PolicyCompileResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Literal["COMPILED", "ERROR"]
    cartridge_id: str
    rule_id: str
    formal_assertion: str
    smt2_template: Optional[str] = None
    message: str = ""


# ---------------------------------------------------------------------------
# Contract 4: WebSocket Telemetry Payload (ws://localhost:8000/ws/telemetry)
# ---------------------------------------------------------------------------

class TelemetryNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    parent_id: Optional[str] = None
    branch_type: Literal["ROOT", "SHADOW_REJECTED", "COMMITTED_SAFE", "BYPASS_CORRUPTED"]
    action_label: str
    total_latency_ms: float = Field(..., ge=0.0)
    z3_verdict: Literal["SAT", "UNSAT", "TIMEOUT", "ERROR", "NONE"]
    violated_rules: list[str] = Field(default_factory=list)
    financial_loss_prevented_usd: float = Field(default=0.0, ge=0.0)
    clinical_hazard_prevented: bool = False


class WSTelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: Literal["BRANCH_EVALUATED", "BYPASS_CORRUPTED", "POLICY_COMPILED", "DEMO_RESET"]
    trace_id: str
    cartridge_id: str
    node: TelemetryNode
