"""Formal invariant verification test suite for CHRONOS-ZERO.

Validates Z3 SMT mathematical proofs across all 3 domain cartridges:
- HEALTHCARE_FHIR (INV_MED_01, INV_MED_02, INV_MED_03)
- FINTECH_ESCROW (INV_FIN_01, INV_FIN_02)
- CLOUD_DEVOPS (INV_OPS_01, INV_OPS_02)

Checks SAT, UNSAT, exact boundary conditions, UnsatCore extraction, and SHA-256 receipts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "z3-verifier"))

from prover_core import verify_state_diff  # noqa: E402
from invariants.healthcare_fhir import evaluate_healthcare_invariants  # noqa: E402
from invariants.fintech_escrow import evaluate_fintech_invariants  # noqa: E402
from invariants.cloud_devops import evaluate_cloud_devops_invariants  # noqa: E402


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


# ---------------------------------------------------------------------------
# Healthcare FHIR Invariants Tests
# ---------------------------------------------------------------------------

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


def test_healthcare_max_daily_dose_unsat():
    """Verify INV_MED_03_MAX_DAILY_DOSE blocks doses > 2000 mg even when renal function is safe."""
    res = evaluate_healthcare_invariants(
        state_pre={},
        state_post={
            "patient_egfr_ml_min": 60.0,
            "prescribed_drug": "Metformin",
            "prescribed_dose_mg": 2500,
            "claim_submitted": False,
            "conservative_therapy_weeks": 6,
        },
    )
    assert res["status"] == "UNSAT"
    violated = {v["rule_id"] for v in res["violated_invariants"]}
    assert "INV_MED_03_MAX_DAILY_DOSE" in violated
    assert "2500" in res["violated_invariants"][0]["counterexample"]
    assert len(res["sha256_proof_hash"]) == 64


def test_healthcare_max_daily_dose_boundary():
    """Exact 2000 mg dose passes INV_MED_03."""
    res = evaluate_healthcare_invariants(
        state_pre={},
        state_post={
            "patient_egfr_ml_min": 60.0,
            "prescribed_drug": "Metformin",
            "prescribed_dose_mg": 2000,
            "claim_submitted": False,
            "conservative_therapy_weeks": 6,
        },
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []


def test_malformed_state_fails_closed():
    bad = payload()
    del bad["state_post_shadow"]["patient_egfr_ml_min"]
    v = verify_state_diff(bad)
    assert v["status"] == "ERROR"
    assert v["status"] != "SAT"


def test_verdict_hash_is_sha256_hex():
    v = verify_state_diff(payload())
    assert len(v["sha256_proof_hash"]) == 64


# ---------------------------------------------------------------------------
# Fintech Escrow Invariants Tests
# ---------------------------------------------------------------------------

def test_fintech_escrow_cap_unsat():
    res = evaluate_fintech_invariants(
        state_pre={"daily_escrow_spent_usd": 40000.0, "daily_escrow_limit_usd": 50000.0},
        state_post={"transfer_amount_usd": 15000.0, "vendor_latency_ms": 100.0, "iban_allowlisted": True},
    )
    assert res["status"] == "UNSAT"
    violated = {v["rule_id"] for v in res["violated_invariants"]}
    assert "INV_FIN_01_ESCROW_CAP" in violated
    hint = res["violated_invariants"][0]["remediation_hint"]
    assert "10,000.00" in hint
    assert len(res["sha256_proof_hash"]) == 64


def test_fintech_sla_attestation_unsat():
    res = evaluate_fintech_invariants(
        state_pre={"daily_escrow_spent_usd": 1000.0, "daily_escrow_limit_usd": 50000.0},
        state_post={"transfer_amount_usd": 500.0, "vendor_latency_ms": 250.0, "iban_allowlisted": True},
    )
    assert res["status"] == "UNSAT"
    assert "INV_FIN_02_SLA_ATTESTATION" in {v["rule_id"] for v in res["violated_invariants"]}


def test_fintech_boundary_exact_cap_passes():
    """Exact remaining cap spend + transfer == limit passes."""
    res = evaluate_fintech_invariants(
        state_pre={"daily_escrow_spent_usd": 40000.0, "daily_escrow_limit_usd": 50000.0},
        state_post={"transfer_amount_usd": 10000.0, "vendor_latency_ms": 150.0, "iban_allowlisted": True},
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []


# ---------------------------------------------------------------------------
# Cloud DevOps Invariants Tests
# ---------------------------------------------------------------------------

def test_cloud_devops_zero_data_loss_unsat():
    res = evaluate_cloud_devops_invariants(
        state_pre={"prod_table_row_count_pre": 15420},
        state_post={"prod_table_row_count_post": 1000, "cidr_open_world": False, "port_number": 443},
    )
    assert res["status"] == "UNSAT"
    assert "INV_OPS_01_ZERO_DATA_LOSS" in {v["rule_id"] for v in res["violated_invariants"]}
    assert "delta: -14420" in res["violated_invariants"][0]["remediation_hint"]


def test_cloud_devops_admin_port_unsat():
    res = evaluate_cloud_devops_invariants(
        state_pre={"prod_table_row_count_pre": 15420},
        state_post={"prod_table_row_count_post": 15420, "cidr_open_world": True, "port_number": 22},
    )
    assert res["status"] == "UNSAT"
    assert "INV_OPS_02_NO_PUBLIC_ADMIN_PORT" in {v["rule_id"] for v in res["violated_invariants"]}


def test_cloud_devops_boundary_equal_row_count_passes():
    res = evaluate_cloud_devops_invariants(
        state_pre={"prod_table_row_count_pre": 15420},
        state_post={"prod_table_row_count_post": 15420, "cidr_open_world": False, "port_number": 22},
    )
    assert res["status"] == "SAT"
