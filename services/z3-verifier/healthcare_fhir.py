"""Formal invariants for HEALTHCARE_FHIR cartridge.

Enforces:
- INV_MED_01_RENAL_SAFETY: eGFR < 30 mL/min contraindicates Metformin.
- INV_MED_02_PAYER_AUTH: Claims require >= 6 weeks conservative therapy.
"""

from typing import Any, Tuple
from z3 import Bool, BoolVal, Implies, Int, IntVal, Real, RealVal, Solver

SOLVER_TIMEOUT_MS = 50

RULE_REGISTRY = {
    "INV_MED_01_RENAL_SAFETY": {
        "formal": "Implies(patient_egfr_ml_min < 30.0, metformin_dose == 0)",
        "remediation": (
            "Patient eGFR is below 30 mL/min ({egfr} mL/min). Metformin is "
            "contraindicated due to lactic acidosis risk. Substitute a renal-safe agent "
            "(e.g. Linagliptin 5mg) or follow renal dosing protocol."
        ),
    },
    "INV_MED_02_PAYER_AUTH": {
        "formal": "Implies(claim_submitted == True, conservative_therapy_weeks >= 6)",
        "remediation": (
            "Payer policy requires at least 6 weeks of documented conservative therapy "
            "before claim submission (found {therapy_weeks} weeks). Attach historical PT "
            "encounter log (e.g. Encounter/enc_108)."
        ),
    },
}


def build_healthcare_solver(state_pre: dict[str, Any], state_post: dict[str, Any]) -> Tuple[Solver, dict[str, Any]]:
    """Build Z3 solver with tracked invariants for HEALTHCARE_FHIR."""
    s = Solver()
    s.set("timeout", SOLVER_TIMEOUT_MS)

    if "patient_egfr_ml_min" not in state_post:
        raise KeyError("patient_egfr_ml_min is required in state_post_shadow")

    egfr_val = float(state_post["patient_egfr_ml_min"])
    prescribed_drug = state_post.get("prescribed_drug", "")
    is_metformin = prescribed_drug == "Metformin"
    dose_val = int(state_post.get("prescribed_dose_mg", 0)) if is_metformin else 0
    claim_val = bool(state_post.get("claim_submitted", False))
    therapy_weeks_val = int(state_post.get("conservative_therapy_weeks", 0))

    # Declare Z3 variables
    egfr = Real("patient_egfr_ml_min")
    metformin_dose = Int("metformin_dose")
    claim_submitted = Bool("claim_submitted")
    therapy_weeks = Int("conservative_therapy_weeks")

    # Explicit Value Bindings
    s.add(egfr == RealVal(egfr_val))
    s.add(metformin_dose == IntVal(dose_val))
    s.add(claim_submitted == BoolVal(claim_val))
    s.add(therapy_weeks == IntVal(therapy_weeks_val))

    # Tracked Invariants
    s.assert_and_track(
        Implies(egfr < RealVal(30.0), metformin_dose == IntVal(0)),
        "INV_MED_01_RENAL_SAFETY",
    )
    s.assert_and_track(
        Implies(claim_submitted == BoolVal(True), therapy_weeks >= IntVal(6)),
        "INV_MED_02_PAYER_AUTH",
    )

    context = {
        "egfr": egfr_val,
        "dose": dose_val,
        "drug": prescribed_drug,
        "claim_submitted": claim_val,
        "therapy_weeks": therapy_weeks_val,
    }
    return s, context
