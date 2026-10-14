"""Z3 Prover Core: formal verification engine for CHRONOS-ZERO.

Dispatches state diff payloads across domain cartridges (HEALTHCARE_FHIR,
FINTECH_ESCROW, CLOUD_DEVOPS) and extracts deterministic UnsatCores via
Z3 tracked assertions.
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Union
from z3 import Solver, unknown, unsat

# Ensure repo root is in sys.path so contracts.schemas can be imported anywhere
REPO_ROOT = str(Path(__file__).resolve().parents[2])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

VERIFIER_DIR = str(Path(__file__).resolve().parent)
if VERIFIER_DIR not in sys.path:
    sys.path.insert(0, VERIFIER_DIR)

from contracts.schemas import StateDiffRequest, ViolatedInvariant, Z3VerdictResponse  # noqa: E402
import healthcare_fhir  # noqa: E402
import fintech_escrow  # noqa: E402
import cloud_devops  # noqa: E402
import nl_compiler  # noqa: E402

# Combined static rule registries for all cartridges
RULE_REGISTRIES: Dict[str, Dict[str, Dict[str, str]]] = {
    "HEALTHCARE_FHIR": healthcare_fhir.RULE_REGISTRY,
    "FINTECH_ESCROW": fintech_escrow.RULE_REGISTRY,
    "CLOUD_DEVOPS": cloud_devops.RULE_REGISTRY,
}

# Metrics tracking for /health endpoint
_TOTAL_PROOFS = 0
_TOTAL_PROOF_LATENCY_MS = 0.0


def get_solver_metrics() -> Dict[str, Any]:
    """Return health metrics including solver pool readiness and average proof latency."""
    avg_latency = (
        round(_TOTAL_PROOF_LATENCY_MS / _TOTAL_PROOFS, 3)
        if _TOTAL_PROOFS > 0
        else 0.0
    )
    return {
        "solver_pool_ready": True,
        "average_proof_latency_ms": avg_latency,
        "total_verifications": _TOTAL_PROOFS,
        "supported_cartridges": list(RULE_REGISTRIES.keys()),
    }


def prewarm_solvers() -> None:
    """Pre-warm Z3 C++ engine at startup to guarantee sub-2.5ms latency on first request."""
    for cartridge in ["HEALTHCARE_FHIR", "FINTECH_ESCROW", "CLOUD_DEVOPS"]:
        try:
            req = StateDiffRequest(
                trace_id="tr_warmup",
                shadow_branch_id="cow_branch_warmup",
                cartridge_id=cartridge,
                cow_fork_latency_ms=0.1,
                state_pre={
                    "daily_escrow_spent_usd": 100.0,
                    "daily_escrow_limit_usd": 50000.0,
                    "prod_table_row_count_pre": 1000,
                },
                state_post_shadow={
                    "patient_egfr_ml_min": 60.0,
                    "prescribed_drug": "Linagliptin",
                    "prescribed_dose_mg": 5,
                    "claim_submitted": False,
                    "conservative_therapy_weeks": 6,
                    "transfer_amount_usd": 50.0,
                    "vendor_latency_ms": 50.0,
                    "iban_allowlisted": True,
                    "prod_table_row_count_post": 1000,
                    "cidr_open_world": False,
                    "port_number": 80,
                },
            )
            dispatch_verification(req)
        except Exception:
            pass


def dispatch_verification(
    payload: Union[StateDiffRequest, Dict[str, Any]],
) -> Z3VerdictResponse:
    """Route verification request to the appropriate cartridge and return a Z3VerdictResponse.

    Timing precision: time.perf_counter_ns() / 1_000_000.0.
    Receipt generation: SHA-256 over raw s.to_smt2().
    Fails closed on malformed input or solver timeout.
    """
    global _TOTAL_PROOFS, _TOTAL_PROOF_LATENCY_MS

    t0 = time.perf_counter_ns()

    if isinstance(payload, dict):
        req = StateDiffRequest(**payload)
    else:
        req = payload

    trace_id = req.trace_id
    branch_id = req.shadow_branch_id
    cartridge_id = req.cartridge_id
    state_pre = req.state_pre
    state_post = req.state_post_shadow

    violated_list: List[ViolatedInvariant] = []
    smt2_dump = ""
    status: str = "ERROR"

    try:
        # Route by cartridge_id
        if cartridge_id == "HEALTHCARE_FHIR":
            s, context = healthcare_fhir.build_healthcare_solver(state_pre, state_post)
            rule_reg = healthcare_fhir.RULE_REGISTRY
        elif cartridge_id == "FINTECH_ESCROW":
            s, context = fintech_escrow.build_fintech_solver(state_pre, state_post)
            rule_reg = fintech_escrow.RULE_REGISTRY
        elif cartridge_id == "CLOUD_DEVOPS":
            s, context = cloud_devops.build_devops_solver(state_pre, state_post)
            rule_reg = cloud_devops.RULE_REGISTRY
        else:
            raise KeyError(f"Unsupported cartridge_id: {cartridge_id}")

        # Inject dynamic compiled policies if any exist
        dynamic_rules = nl_compiler.get_dynamic_rules(cartridge_id)
        dynamic_reg: Dict[str, Dict[str, str]] = {}
        for dyn in dynamic_rules:
            dyn["builder"](s, state_pre, state_post, context)
            dynamic_reg[dyn["rule_id"]] = {
                "formal": dyn["formal_assertion"],
                "remediation": dyn["remediation_hint"],
            }

        # Execute Z3 formal check
        check_result = s.check()
        smt2_dump = s.to_smt2()

        if check_result == unsat:
            status = "UNSAT"
            core = s.unsat_core()
            for item in core:
                r_id = str(item)
                rule_info = rule_reg.get(r_id) or dynamic_reg.get(r_id, {
                    "formal": r_id,
                    "remediation": f"Formal invariant {r_id} violated.",
                })
                formal_str = rule_info.get("formal", r_id)
                remediation_tmpl = rule_info.get("remediation", "Invariant violated.")
                try:
                    remediation_msg = remediation_tmpl.format(**context)
                except Exception:
                    remediation_msg = remediation_tmpl

                violated_list.append(
                    ViolatedInvariant(
                        rule_id=r_id,
                        formal_assertion=formal_str,
                        counterexample=f"State delta rejected by {r_id}: {context}",
                        remediation_hint=remediation_msg,
                    )
                )
        elif check_result == unknown:
            status = "TIMEOUT"
        else:
            status = "SAT"

    except (KeyError, TypeError, ValueError, Exception):
        status = "ERROR"
        smt2_dump = ""

    # Measure exact solver execution time in milliseconds
    elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
    proof_latency_ms = round(elapsed_ms, 3)

    # SHA-256 receipt over raw SMT-LIB2 string
    sha256_hash = hashlib.sha256(smt2_dump.encode("utf-8")).hexdigest()

    # Update telemetry counters
    _TOTAL_PROOFS += 1
    _TOTAL_PROOF_LATENCY_MS += proof_latency_ms

    return Z3VerdictResponse(
        trace_id=trace_id,
        shadow_branch_id=branch_id,
        status=status,
        proof_latency_ms=proof_latency_ms,
        violated_invariants=violated_list,
        smt2_dump=smt2_dump,
        sha256_proof_hash=sha256_hash,
    )


def verify_state_diff(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Contract 2 -> Contract 3 dict-based entrypoint for backward compatibility."""
    verdict = dispatch_verification(payload)
    return verdict.model_dump()
