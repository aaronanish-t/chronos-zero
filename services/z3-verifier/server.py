"""CHRONOS-ZERO Z3 Formal Verification Microservice.

Runs on port 8001. Provides deterministic SMT mathematical proof evaluations
for speculative Copy-on-Write shadow branches with sub-2.5ms latency.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

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


# ---------------------------------------------------------------------------
# Policy Studio Request / Response models (local to Z3 verifier service)
# ---------------------------------------------------------------------------

class PolicyCompileRequest(BaseModel):
    cartridge_id: str
    rule_id: str
    natural_language_rule: str


class PolicyCompileResponse(BaseModel):
    status: str
    cartridge_id: str
    rule_id: str
    formal_assertion: str
    smt2_template: Optional[str] = None
    message: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prewarm solver pool on server startup to guarantee sub-millisecond execution."""
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
        verdict = dispatch_verification(payload)
        return verdict
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
        result = nl_compiler.compile_nl_rule(
            cartridge_id=payload.cartridge_id,
            rule_id=payload.rule_id,
            nl_text=payload.natural_language_rule,
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


@app.get(
    "/health",
    summary="Check prover readiness and proof performance metrics",
)
def health() -> Dict[str, Any]:
    """Return solver pool readiness, average proof latency, and supported cartridges."""
    metrics = get_solver_metrics()
    return {
        "status": "healthy",
        "service": "chronos-z3-verifier",
        **metrics,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
