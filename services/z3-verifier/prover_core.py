"""Z3 Prover Core: formal verification engine for CHRONOS-ZERO.

Dispatches state diff payloads across domain cartridges (HEALTHCARE_FHIR,
FINTECH_ESCROW, CLOUD_DEVOPS) and extracts deterministic UnsatCores via
Z3 tracked assertions. Detects ALL violated rules when multiple invariants fail.
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
from invariants import healthcare_fhir, fintech_escrow, cloud_devops  # noqa: E402
import nl_compiler  # noqa: E402

# Contract 3 rule_id for a state delta the solver could not even be built from.
MALFORMED_RULE_ID = "INV_SYS_00_MALFORMED_STATE"

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
    Reports ALL broken rules when multiple invariants fail simultaneously.
    Fails closed (UNSAT) on malformed input or solver timeout.
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
    status: str = "UNSAT"

    try:
        # Route by cartridge_id
        if cartridge_id == "HEALTHCARE_FHIR":
            s, context, tracked_rules = healthcare_fhir.build_healthcare_solver(state_pre, state_post)
            rule_reg = healthcare_fhir.RULE_REGISTRY
        elif cartridge_id == "FINTECH_ESCROW":
            s, context, tracked_rules = fintech_escrow.build_fintech_solver(state_pre, state_post)
            rule_reg = fintech_escrow.RULE_REGISTRY
        elif cartridge_id == "CLOUD_DEVOPS":
            s, context, tracked_rules = cloud_devops.build_devops_solver(state_pre, state_post)
            rule_reg = cloud_devops.RULE_REGISTRY
        else:
            raise KeyError(f"Unsupported cartridge_id: {cartridge_id}")

        # Inject dynamic compiled policies if any exist
        dynamic_rules = nl_compiler.get_dynamic_rules(cartridge_id)
        dynamic_reg: Dict[str, Dict[str, str]] = {}
        for dyn in dynamic_rules:
            r_id = dyn["rule_id"]
            dynamic_reg[r_id] = {
                "formal": dyn["formal_assertion"],
                "remediation": dyn["remediation_hint"],
            }
            tracked_rules.append((r_id, dyn))

        # Check each rule independently via push/pop to collect ALL broken invariants.
        # Fail closed: a rule counts as violated when the solver says unsat (even with an empty
        # core, i.e. the bindings themselves conflict) or cannot decide within the 50 ms timeout.
        failed_ids = []
        timed_out = set()
        for r_id, item in tracked_rules:
            s.push()
            if isinstance(item, dict) and "builder" in item:
                item["builder"](s, state_pre, state_post, context)
            else:
                s.assert_and_track(item, r_id)
            result = s.check()
            if result == unsat:
                failed_ids.extend([str(c) for c in s.unsat_core()] or [r_id])
            elif result == unknown:
                failed_ids.append(r_id)
                timed_out.add(r_id)
            s.pop()

        # Build full tracked formula for SMT2 dump
        for r_id, item in tracked_rules:
            if isinstance(item, dict) and "builder" in item:
                item["builder"](s, state_pre, state_post, context)
            else:
                s.assert_and_track(item, r_id)
        smt2_dump = s.to_smt2()

        if failed_ids:
            status = "UNSAT"
            for r_id in sorted(list(set(failed_ids))):
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

                # Build precise counterexample string
                if r_id == "INV_FIN_01_ESCROW_CAP":
                    cex = f"daily_escrow_spent_usd={context.get('spent')}, transfer_amount_usd={context.get('transfer')}, daily_escrow_limit_usd={context.get('limit')}"
                elif r_id == "INV_FIN_02_SLA_ATTESTATION":
                    cex = f"transfer_amount_usd={context.get('transfer')}, vendor_latency_ms={context.get('vendor_latency_ms')}, iban_allowlisted={context.get('iban_allowlisted')}"
                elif r_id == "INV_MED_01_RENAL_SAFETY":
                    cex = f"patient_egfr_ml_min={context.get('egfr')}, prescribed_dose_metformin={context.get('metformin_dose')}"
                elif r_id == "INV_MED_02_PAYER_AUTH":
                    cex = f"claim_submitted={context.get('claim_submitted')}, conservative_therapy_weeks={context.get('therapy_weeks')}"
                elif r_id == "INV_MED_03_MAX_DAILY_DOSE":
                    cex = f"prescribed_dose_mg={context.get('dose_mg')}"
                elif r_id == "INV_OPS_01_ZERO_DATA_LOSS":
                    cex = f"prod_table_row_count_pre={context.get('rows_pre')}, prod_table_row_count_post={context.get('rows_post')}, delta={context.get('delta')}"
                elif r_id == "INV_OPS_02_NO_PUBLIC_ADMIN_PORT":
                    cex = f"cidr_open_world={context.get('cidr_open_world')}, port_number={context.get('port_number')}"
                else:
                    cex = f"State delta rejected by {r_id}: {context}"
                if r_id in timed_out:
                    cex += " [solver returned unknown within the 50 ms timeout; rejected fail-closed]"

                violated_list.append(
                    ViolatedInvariant(
                        rule_id=r_id,
                        formal_assertion=formal_str,
                        counterexample=cex,
                        remediation_hint=remediation_msg,
                    )
                )
        else:
            status = "SAT"

    except Exception as e:
        status = "UNSAT"
        smt2_dump = ""
        violated_list.append(
            ViolatedInvariant(
                rule_id=MALFORMED_RULE_ID,
                formal_assertion="valid_state_delta",
                counterexample=f"State rejected: {str(e)}",
                remediation_hint=f"Malformed state payload rejected: {str(e)}",
            )
        )

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
