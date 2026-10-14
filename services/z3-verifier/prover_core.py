"""Z3 prover core: verifies a shadow-branch state against cartridge invariants.

Every invariant is added with assert_and_track so that an UNSAT result names
the violated rules via solver.unsat_core().
"""

import hashlib
import json
import time

from z3 import Bool, Implies, Int, Real, Solver, unknown, unsat

SOLVER_TIMEOUT_MS = 50

REMEDIATION = {
    "INV_MED_01_RENAL_SAFETY": (
        "Patient eGFR is below 30 mL/min. Metformin is contraindicated due to "
        "lactic acidosis risk. Substitute a renal-safe agent or follow the renal dosing protocol."
    ),
    "INV_MED_02_PAYER_AUTH": (
        "Payer policy requires at least 6 weeks of documented conservative therapy "
        "before claim submission. Attach the historical PT encounter log."
    ),
}


def _healthcare_check(state_post: dict):
    """Build the solver and tracked invariants for the healthcare cartridge."""
    s = Solver()
    s.set("timeout", SOLVER_TIMEOUT_MS)

    egfr = Real("patient_egfr")
    metformin_dose = Int("metformin_dose")
    claim_submitted = Bool("claim_submitted")
    therapy_weeks = Int("therapy_weeks")

    s.add(egfr == float(state_post["patient_egfr_ml_min"]))
    is_metformin = state_post.get("prescribed_drug") == "Metformin"
    s.add(metformin_dose == (int(state_post["prescribed_dose_mg"]) if is_metformin else 0))
    s.add(claim_submitted == bool(state_post["claim_submitted"]))
    s.add(therapy_weeks == int(state_post["conservative_therapy_weeks"]))

    s.assert_and_track(Implies(egfr < 30.0, metformin_dose == 0), "INV_MED_01_RENAL_SAFETY")
    s.assert_and_track(Implies(claim_submitted, therapy_weeks >= 6), "INV_MED_02_PAYER_AUTH")
    return s


def _verdict_hash(trace_id: str, status: str, violated: list) -> str:
    body = json.dumps({"trace_id": trace_id, "status": status, "violated": violated}, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()


def verify_state_diff(payload: dict) -> dict:
    """Return a Contract 3 verdict for a Contract 2 payload.

    Fails closed: a solver timeout or malformed state is reported as TIMEOUT/ERROR,
    never as SAT.
    """
    t0 = time.perf_counter_ns()
    trace_id = payload.get("trace_id", "")
    branch_id = payload.get("shadow_branch_id", "")
    violated = []
    try:
        s = _healthcare_check(payload["state_post_shadow"])
        result = s.check()
        if result == unsat:
            status = "UNSAT"
            for core in s.unsat_core():
                rule_id = str(core)
                violated.append({
                    "rule_id": rule_id,
                    "formal_assertion": rule_id,
                    "counterexample": "see smt2_dump",
                    "remediation_hint": REMEDIATION.get(rule_id, "Invariant violated."),
                })
        elif result == unknown:
            status = "TIMEOUT"
        else:
            status = "SAT"
        smt2 = s.to_smt2()
    except (KeyError, TypeError, ValueError):
        status = "ERROR"
        smt2 = ""

    latency_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
    return {
        "trace_id": trace_id,
        "shadow_branch_id": branch_id,
        "status": status,
        "proof_latency_ms": round(latency_ms, 3),
        "violated_invariants": violated,
        "smt2_dump": smt2,
        "sha256_proof_hash": _verdict_hash(trace_id, status, [v["rule_id"] for v in violated]),
    }
