"""CHRONOS-ZERO Z3 Formal Verification Microservice.

Runs on port 8001. Provides deterministic SMT mathematical proof evaluations
for speculative Copy-on-Write shadow branches with sub-2.5ms latency.
"""

from __future__ import annotations

import os
import re
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import uvicorn

# Ensure repository root is on sys.path
REPO_ROOT = str(Path(__file__).resolve().parents[2])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

VERIFIER_DIR = str(Path(__file__).resolve().parent)
if VERIFIER_DIR not in sys.path:
    sys.path.insert(0, VERIFIER_DIR)

from contracts.schemas import (  # noqa: E402
    StateDiffRequest,
    Z3VerdictResponse,
)
from prover_core import (  # noqa: E402
    dispatch_verification,
    get_solver_metrics,
    prewarm_solvers,
)
import nl_compiler  # noqa: E402

# Z3's Python API shares one global context, which is not thread-safe: concurrent solvers on
# FastAPI's worker threads crash the process (ASSERTION VIOLATION / access violation). Every
# route that touches Z3 runs under this lock; a proof takes ~2 ms, so the queue stays short.
_Z3_LOCK = threading.Lock()

# Contract 3 rule_id pattern (contracts/z3_verdict.schema.json); compiled rules end up there.
RULE_ID_PATTERN = re.compile(r"^INV_[A-Z]+_[0-9]{2}_[A-Z0-9_]+$")


# ---------------------------------------------------------------------------
# Policy Studio Request / Response models (local to Z3 verifier service)
# ---------------------------------------------------------------------------

class PolicyCompileRequest(BaseModel):
    cartridge_id: Literal["HEALTHCARE_FHIR", "FINTECH_ESCROW", "CLOUD_DEVOPS"]
    rule_id: str = Field(pattern=RULE_ID_PATTERN.pattern)
    natural_language_rule: str = Field(min_length=1, max_length=500)


class PolicyCompileResponse(BaseModel):
    status: str
    cartridge_id: str
    rule_id: str
    formal_assertion: str
    compiled_code: Optional[str] = None
    z3_code: Optional[str] = None
    smt2_dump: Optional[str] = None
    smt2_template: Optional[str] = None
    compilation_latency_ms: Optional[float] = None
    latency_ms: Optional[float] = None
    remediation_hint: Optional[str] = None
    message: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prewarm solver pool on server startup to guarantee sub-millisecond execution."""
    with _Z3_LOCK:
        prewarm_solvers()
    yield


app = FastAPI(
    title="CHRONOS-ZERO Formal Math & Z3 Prover Kernel",
    description="Deterministic SMT verification microservice powering speculative CoW kernel execution",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post(
    "/v1/z3/verify",
    response_model=Z3VerdictResponse,
    summary="Verify speculative CoW shadow state diff against formal invariants",
)
def verify_state(payload: StateDiffRequest) -> Z3VerdictResponse:
    """Accept Contract 2 StateDiffRequest and return Contract 3 Z3VerdictResponse."""
    try:
        with _Z3_LOCK:
            return dispatch_verification(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Z3 verification internal error: {str(e)}",
        )


@app.post(
    "/v1/z3/compile-policy",
    response_model=PolicyCompileResponse,
    summary="Compile natural-language compliance policy into active Z3 prover loop",
)
def compile_policy(payload: PolicyCompileRequest) -> PolicyCompileResponse:
    """Accept natural language policy string and compile into a tracked Z3 assertion."""
    try:
        with _Z3_LOCK:
            result = nl_compiler.compile_nl_policy(
                cartridge_id=payload.cartridge_id,
                rule_id=payload.rule_id,
                natural_language_rule=payload.natural_language_rule,
            )
        return PolicyCompileResponse(**result)
    except Exception as e:
        return PolicyCompileResponse(
            status="ERROR",
            cartridge_id=payload.cartridge_id,
            rule_id=payload.rule_id,
            formal_assertion="",
            message=f"Failed to compile policy: {str(e)}",
        )


@app.post(
    "/v1/z3/policies/clear",
    summary="Unload every compiled Live Policy Studio rule (stage reset)",
)
def clear_policies() -> Dict[str, Any]:
    """Return the prover to its static cartridge rules, as `make seed` does for state."""
    with _Z3_LOCK:
        cleared = sum(len(nl_compiler.get_dynamic_rules(c)) for c in nl_compiler.DYNAMIC_RULES)
        nl_compiler.clear_dynamic_rules()
    return {"status": "CLEARED", "cleared_rules": cleared}


@app.get(
    "/health",
    summary="Check prover readiness and proof performance metrics",
)
def health() -> Dict[str, Any]:
    """Return solver pool readiness, average proof latency, and supported cartridges."""
    metrics = get_solver_metrics()
    return {
        "offline_mode": os.environ.get("OFFLINE_MODE") == "1",
        "status": "healthy",
        "service": "chronos-z3-verifier",
        **metrics,
    }


if __name__ == "__main__":
    # Loopback only, like the kernel: nothing on the venue network can reach the prover, and
    # Windows does not raise a firewall prompt mid-demo.
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("CHRONOS_Z3_PORT", "8001")))
