"""Formal invariants for HEALTHCARE_FHIR cartridge.

Enforces:
- INV_MED_01_RENAL_SAFETY: eGFR < 30 mL/min contraindicates Metformin.
- INV_MED_02_PAYER_AUTH: Claims require >= 6 weeks documented conservative therapy.
- INV_MED_03_MAX_DAILY_DOSE: Prescribed dose must not exceed absolute daily cap (2000 mg).
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Tuple
from z3 import Bool, BoolVal, Implies, Int, IntVal, Real, RealVal, Solver, unknown, unsat

SOLVER_TIMEOUT_MS = 50

RULE_REGISTRY: Dict[str, Dict[str, str]] = {
    "INV_MED_01_RENAL_SAFETY": {
        "formal": "Implies(patient_egfr_ml_min < 30.0, prescribed_dose_metformin == 0)",
        "remediation": (
            "Patient eGFR is {egfr} mL/min (< 30.0 mL/min threshold). Metformin is "
            "contraindicated due to lactic acidosis risk. Reduce prescribed_dose_metformin "
            "to 0 mg or switch to renal-safe agent (e.g. Linagliptin 5mg)."
        ),
    },
    "INV_MED_02_PAYER_AUTH": {
        "formal": "Implies(claim_submitted == True, conservative_therapy_weeks >= 6)",
        "remediation": (
            "Payer policy requires at least 6 weeks of documented conservative therapy "
            "before claim submission (found {therapy_weeks} weeks). Attach historical PT "
            "encounter log (e.g. Encounter/enc_108) or complete conservative therapy."
        ),
    },
    "INV_MED_03_MAX_DAILY_DOSE": {
        "formal": "prescribed_dose_mg <= 2000",
        "remediation": (
            "Prescribed dose of {dose_mg} mg exceeds the absolute maximum daily limit "
            "of 2000 mg. Reduce prescribed_dose_mg to <= 2000 mg."
        ),
    },
}


def build_healthcare_solver(
    state_pre: Dict[str, Any], state_post: Dict[str, Any]
) -> Tuple[Solver, Dict[str, Any]]:
    """Build Z3 solver instance with tracked invariants for HEALTHCARE_FHIR."""
    s = Solver()
    s.set("timeout", SOLVER_TIMEOUT_MS)

    if "patient_egfr_ml_min" not in state_post:
        raise KeyError("patient_egfr_ml_min is required in state_post_shadow")

    egfr_val = float(state_post["patient_egfr_ml_min"])

    # Metformin dose handling
    prescribed_drug = state_post.get("prescribed_drug", "")
    if "prescribed_dose_metformin" in state_post:
        metformin_dose_val = int(state_post["prescribed_dose_metformin"])
    elif prescribed_drug == "Metformin":
        metformin_dose_val = int(state_post.get("prescribed_dose_mg", 0))
    else:
        metformin_dose_val = 0

    dose_mg_val = int(state_post.get("prescribed_dose_mg", metformin_dose_val))
    claim_val = bool(state_post.get("claim_submitted", False))
    therapy_weeks_val = int(state_post.get("conservative_therapy_weeks", 0))

    # Z3 Variable Declarations
    egfr = Real("patient_egfr_ml_min")
    metformin_dose = Int("prescribed_dose_metformin")
    claim_submitted = Bool("claim_submitted")
    therapy_weeks = Int("conservative_therapy_weeks")
    dose_mg = Int("prescribed_dose_mg")

    # Value Bindings
    s.add(egfr == RealVal(egfr_val))
    s.add(metformin_dose == IntVal(metformin_dose_val))
    s.add(claim_submitted == BoolVal(claim_val))
    s.add(therapy_weeks == IntVal(therapy_weeks_val))
    s.add(dose_mg == IntVal(dose_mg_val))

    # Tracked Formal Assertions
    s.assert_and_track(
        Implies(egfr < RealVal(30.0), metformin_dose == IntVal(0)),
        "INV_MED_01_RENAL_SAFETY",
    )
    s.assert_and_track(
        Implies(claim_submitted == BoolVal(True), therapy_weeks >= IntVal(6)),
        "INV_MED_02_PAYER_AUTH",
    )
    s.assert_and_track(
        dose_mg <= IntVal(2000),
        "INV_MED_03_MAX_DAILY_DOSE",
    )

    context = {
        "egfr": egfr_val,
        "metformin_dose": metformin_dose_val,
        "prescribed_dose_metformin": metformin_dose_val,
        "dose_mg": dose_mg_val,
        "prescribed_dose_mg": dose_mg_val,
        "prescribed_drug": prescribed_drug,
        "claim_submitted": claim_val,
        "therapy_weeks": therapy_weeks_val,
        "conservative_therapy_weeks": therapy_weeks_val,
    }
    return s, context


def evaluate_healthcare_invariants(
    state_pre: Dict[str, Any], state_post: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute formal verification against HEALTHCARE_FHIR invariants."""
    t0 = time.perf_counter_ns()
    violated: List[Dict[str, str]] = []
    smt2_str = ""

    try:
        s, context = build_healthcare_solver(state_pre, state_post)
        verdict = s.check()
        smt2_str = s.to_smt2()

        if verdict == unsat:
            status = "UNSAT"
            for core_item in s.unsat_core():
                r_id = str(core_item)
                meta = RULE_REGISTRY.get(r_id, {"formal": r_id, "remediation": f"{r_id} violated."})
                if r_id == "INV_MED_01_RENAL_SAFETY":
                    cex = f"patient_egfr_ml_min={context['egfr']}, prescribed_dose_metformin={context['metformin_dose']}"
                elif r_id == "INV_MED_02_PAYER_AUTH":
                    cex = f"claim_submitted={context['claim_submitted']}, conservative_therapy_weeks={context['therapy_weeks']}"
                elif r_id == "INV_MED_03_MAX_DAILY_DOSE":
                    cex = f"prescribed_dose_mg={context['dose_mg']}"
                else:
                    cex = str(context)

                violated.append({
                    "rule_id": r_id,
                    "formal_assertion": meta["formal"],
                    "counterexample": cex,
                    "remediation_hint": meta["remediation"].format(**context),
                })
        elif verdict == unknown:
            status = "TIMEOUT"
        else:
            status = "SAT"
    except Exception:
        status = "ERROR"
        smt2_str = ""

    proof_ms = round((time.perf_counter_ns() - t0) / 1_000_000.0, 3)
    proof_hash = hashlib.sha256(smt2_str.encode("utf-8")).hexdigest()

    return {
        "status": status,
        "proof_latency_ms": proof_ms,
        "violated_invariants": violated,
        "smt2_dump": smt2_str,
        "sha256_proof_hash": proof_hash,
    }
