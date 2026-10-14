import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "z3-verifier"))

from prover_core import verify_state_diff  # noqa: E402


def payload(egfr=24.0, drug="Metformin", dose=2500, claim=True, weeks=2):
    return {
        "trace_id": "tr_test",
        "shadow_branch_id": "cow_branch_test",
        "cartridge_id": "HEALTHCARE_FHIR",
        "cow_fork_latency_ms": 1.0,
        "state_pre": {},
        "state_post_shadow": {
            "patient_egfr_ml_min": egfr,
            "prescribed_drug": drug,
            "prescribed_dose_mg": dose,
            "claim_submitted": claim,
            "conservative_therapy_weeks": weeks,
        },
    }


def rules(verdict):
    return {v["rule_id"] for v in verdict["violated_invariants"]}


def test_renal_safety_true_negative_unsat():
    v = verify_state_diff(payload(egfr=24.0, drug="Metformin", dose=2500, claim=False))
    assert v["status"] == "UNSAT"
    assert rules(v) == {"INV_MED_01_RENAL_SAFETY"}


def test_payer_auth_true_negative_unsat():
    v = verify_state_diff(payload(egfr=45.0, drug="Linagliptin", dose=5, claim=True, weeks=2))
    assert v["status"] == "UNSAT"
    assert rules(v) == {"INV_MED_02_PAYER_AUTH"}


def test_true_positive_sat():
    v = verify_state_diff(payload(egfr=45.0, drug="Metformin", dose=1000, claim=True, weeks=6))
    assert v["status"] == "SAT"
    assert v["violated_invariants"] == []


def test_boundary_exact_egfr_30_is_not_renal_violation():
    v = verify_state_diff(payload(egfr=30.0, drug="Metformin", dose=1000, claim=False))
    assert v["status"] == "SAT"


def test_boundary_exact_six_weeks_passes():
    v = verify_state_diff(payload(egfr=45.0, drug="Linagliptin", dose=5, claim=True, weeks=6))
    assert v["status"] == "SAT"


def test_malformed_state_fails_closed():
    bad = payload()
    del bad["state_post_shadow"]["patient_egfr_ml_min"]
    v = verify_state_diff(bad)
    assert v["status"] == "ERROR"
    assert v["status"] != "SAT"


def test_verdict_hash_is_sha256_hex():
    v = verify_state_diff(payload())
    assert len(v["sha256_proof_hash"]) == 64
