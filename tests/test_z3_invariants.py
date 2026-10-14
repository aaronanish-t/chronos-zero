"""Formal invariant verification test suite for CHRONOS-ZERO.

Contains 30 deterministic unit tests (10 per domain cartridge):
- Cartridge 1: HEALTHCARE_FHIR (INV_MED_01, INV_MED_02, INV_MED_03)
- Cartridge 2: FINTECH_ESCROW (INV_FIN_01, INV_FIN_02)
- Cartridge 3: CLOUD_DEVOPS (INV_OPS_01, INV_OPS_02)

Validates:
1. Pure SAT valid mutations
2. Single-invariant UNSAT violations
3. Multi-invariant simultaneous UNSAT violations (verifying unsat_core returns every violated rule ID)
4. Exact mathematical boundary values (eGFR == 30.0, daily_spent + transfer == 5000.0, vendor_latency_ms == 200.0, row_delta == 0)
5. Strict performance guarantee: every single test completes in < 5.0 milliseconds.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Set

import pytest

# Ensure repository root and verifier directory are on sys.path
REPO_ROOT = str(Path(__file__).resolve().parents[1])
VERIFIER_DIR = str(Path(__file__).resolve().parents[1] / "services" / "z3-verifier")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if VERIFIER_DIR not in sys.path:
    sys.path.insert(0, VERIFIER_DIR)

from invariants.cloud_devops import evaluate_cloud_devops_invariants
from invariants.fintech_escrow import evaluate_fintech_invariants
from invariants.healthcare_fhir import evaluate_healthcare_invariants
from prover_core import prewarm_solvers, verify_state_diff


@pytest.fixture(scope="session", autouse=True)
def prewarm_z3_engine():
    """Prewarm Z3 C++ solver pool at session start to ensure sub-millisecond execution."""
    prewarm_solvers()


def get_rule_ids(verdict: Dict[str, Any]) -> Set[str]:
    """Helper to extract the set of violated rule IDs from an invariant result."""
    return {v["rule_id"] for v in verdict.get("violated_invariants", [])}


# ===========================================================================
# Cartridge 1: HEALTHCARE_FHIR Invariants (10 Tests)
# ===========================================================================

def test_healthcare_01_sat_valid_metformin_normal_egfr():
    """Pure SAT: Standard Metformin prescription with safe renal function and no claim."""
    res = evaluate_healthcare_invariants(
        state_pre={},
        state_post={
            "patient_egfr_ml_min": 60.0,
            "prescribed_drug": "Metformin",
            "prescribed_dose_mg": 1000,
            "claim_submitted": False,
            "conservative_therapy_weeks": 6,
        },
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []
    assert res["proof_latency_ms"] < 5.0
    assert len(res["sha256_proof_hash"]) == 64


def test_healthcare_02_sat_valid_non_metformin_low_egfr():
    """Pure SAT: Severe renal impairment (eGFR 20.0) but non-metformin drug (metformin_dose == 0)."""
    res = evaluate_healthcare_invariants(
        state_pre={},
        state_post={
            "patient_egfr_ml_min": 20.0,
            "prescribed_drug": "Linagliptin",
            "prescribed_dose_mg": 5,
            "prescribed_dose_metformin": 0,
            "claim_submitted": False,
            "conservative_therapy_weeks": 6,
        },
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []
    assert res["proof_latency_ms"] < 5.0


def test_healthcare_03_sat_valid_payer_claim_with_therapy():
    """Pure SAT: Payer claim submitted with documented 8 weeks conservative therapy (> 6 weeks)."""
    res = evaluate_healthcare_invariants(
        state_pre={},
        state_post={
            "patient_egfr_ml_min": 55.0,
            "prescribed_drug": "Metformin",
            "prescribed_dose_mg": 500,
            "claim_submitted": True,
            "conservative_therapy_weeks": 8,
        },
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []
    assert res["proof_latency_ms"] < 5.0


def test_healthcare_04_unsat_renal_safety_single():
    """Single UNSAT: Metformin dosing contraindicated for low eGFR (24.0 < 30.0 mL/min)."""
    res = evaluate_healthcare_invariants(
        state_pre={},
        state_post={
            "patient_egfr_ml_min": 24.0,
            "prescribed_drug": "Metformin",
            "prescribed_dose_mg": 1000,
            "claim_submitted": False,
            "conservative_therapy_weeks": 6,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_MED_01_RENAL_SAFETY"}
    assert res["proof_latency_ms"] < 5.0
    assert "patient_egfr_ml_min=24.0" in res["violated_invariants"][0]["counterexample"]


def test_healthcare_05_unsat_payer_auth_single():
    """Single UNSAT: Insurance claim submitted with insufficient conservative therapy (2 < 6 weeks)."""
    res = evaluate_healthcare_invariants(
        state_pre={},
        state_post={
            "patient_egfr_ml_min": 45.0,
            "prescribed_drug": "Metformin",
            "prescribed_dose_mg": 500,
            "claim_submitted": True,
            "conservative_therapy_weeks": 2,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_MED_02_PAYER_AUTH"}
    assert res["proof_latency_ms"] < 5.0
    assert "conservative_therapy_weeks=2" in res["violated_invariants"][0]["counterexample"]


def test_healthcare_06_unsat_max_daily_dose_single():
    """Single UNSAT: Prescribed dose of 2500 mg exceeds 2000 mg ceiling."""
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
    assert get_rule_ids(res) == {"INV_MED_03_MAX_DAILY_DOSE"}
    assert res["proof_latency_ms"] < 5.0
    assert "prescribed_dose_mg=2500" in res["violated_invariants"][0]["counterexample"]


def test_healthcare_07_unsat_multi_renal_and_payer_auth():
    """Multi UNSAT: Both renal impairment (eGFR 22.0) and lack of payer therapy (2 weeks) broken."""
    res = evaluate_healthcare_invariants(
        state_pre={},
        state_post={
            "patient_egfr_ml_min": 22.0,
            "prescribed_drug": "Metformin",
            "prescribed_dose_mg": 1000,
            "claim_submitted": True,
            "conservative_therapy_weeks": 2,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_MED_01_RENAL_SAFETY", "INV_MED_02_PAYER_AUTH"}
    assert res["proof_latency_ms"] < 5.0


def test_healthcare_08_unsat_multi_all_three_rules_broken():
    """Multi UNSAT: All 3 healthcare rules violated simultaneously."""
    res = evaluate_healthcare_invariants(
        state_pre={},
        state_post={
            "patient_egfr_ml_min": 18.0,
            "prescribed_drug": "Metformin",
            "prescribed_dose_mg": 3000,
            "claim_submitted": True,
            "conservative_therapy_weeks": 1,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {
        "INV_MED_01_RENAL_SAFETY",
        "INV_MED_02_PAYER_AUTH",
        "INV_MED_03_MAX_DAILY_DOSE",
    }
    assert res["proof_latency_ms"] < 5.0


def test_healthcare_09_boundary_exact_egfr_30_passes():
    """Exact Boundary: eGFR == 30.0 exactly passes (rule is strictly patient_egfr_ml_min < 30.0)."""
    res = evaluate_healthcare_invariants(
        state_pre={},
        state_post={
            "patient_egfr_ml_min": 30.0,
            "prescribed_drug": "Metformin",
            "prescribed_dose_mg": 1000,
            "claim_submitted": False,
            "conservative_therapy_weeks": 6,
        },
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []
    assert res["proof_latency_ms"] < 5.0


def test_healthcare_10_boundary_exact_limits_pass():
    """Exact Boundary: conservative_therapy_weeks == 6 and prescribed_dose_mg == 2000 pass."""
    res = evaluate_healthcare_invariants(
        state_pre={},
        state_post={
            "patient_egfr_ml_min": 45.0,
            "prescribed_drug": "Metformin",
            "prescribed_dose_mg": 2000,
            "claim_submitted": True,
            "conservative_therapy_weeks": 6,
        },
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []
    assert res["proof_latency_ms"] < 5.0


# ===========================================================================
# Cartridge 2: FINTECH_ESCROW Invariants (10 Tests)
# ===========================================================================

def test_fintech_01_sat_valid_normal_transfer():
    """Pure SAT: Wire well within daily limits with verified SLA and allowlisted IBAN."""
    res = evaluate_fintech_invariants(
        state_pre={"daily_escrow_spent_usd": 1000.0, "daily_escrow_limit_usd": 50000.0},
        state_post={
            "transfer_amount_usd": 2500.0,
            "vendor_latency_ms": 85.0,
            "iban_allowlisted": True,
        },
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []
    assert res["proof_latency_ms"] < 5.0
    assert len(res["sha256_proof_hash"]) == 64


def test_fintech_02_sat_zero_transfer_with_untrusted_vendor():
    """Pure SAT: Transfer amount of $0 does not trigger SLA or allowlist requirements."""
    res = evaluate_fintech_invariants(
        state_pre={"daily_escrow_spent_usd": 1000.0, "daily_escrow_limit_usd": 50000.0},
        state_post={
            "transfer_amount_usd": 0.0,
            "vendor_latency_ms": 500.0,
            "iban_allowlisted": False,
        },
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []
    assert res["proof_latency_ms"] < 5.0


def test_fintech_03_unsat_escrow_cap_single():
    """Single UNSAT: Proposed wire of $15,000 exceeds remaining $10,000 daily capacity."""
    res = evaluate_fintech_invariants(
        state_pre={"daily_escrow_spent_usd": 40000.0, "daily_escrow_limit_usd": 50000.0},
        state_post={
            "transfer_amount_usd": 15000.0,
            "vendor_latency_ms": 100.0,
            "iban_allowlisted": True,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_FIN_01_ESCROW_CAP"}
    assert res["proof_latency_ms"] < 5.0
    hint = res["violated_invariants"][0]["remediation_hint"]
    assert "10,000.00" in hint


def test_fintech_04_unsat_sla_latency_single():
    """Single UNSAT: Counterparty latency of 250ms exceeds 200.0ms zkTLS threshold."""
    res = evaluate_fintech_invariants(
        state_pre={"daily_escrow_spent_usd": 1000.0, "daily_escrow_limit_usd": 50000.0},
        state_post={
            "transfer_amount_usd": 500.0,
            "vendor_latency_ms": 250.0,
            "iban_allowlisted": True,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_FIN_02_SLA_ATTESTATION"}
    assert res["proof_latency_ms"] < 5.0
    assert "vendor_latency_ms=250.0" in res["violated_invariants"][0]["counterexample"]


def test_fintech_05_unsat_iban_unallowlisted_single():
    """Single UNSAT: Destination IBAN is not present on treasury allowlist."""
    res = evaluate_fintech_invariants(
        state_pre={"daily_escrow_spent_usd": 1000.0, "daily_escrow_limit_usd": 50000.0},
        state_post={
            "transfer_amount_usd": 500.0,
            "vendor_latency_ms": 95.0,
            "iban_allowlisted": False,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_FIN_02_SLA_ATTESTATION"}
    assert res["proof_latency_ms"] < 5.0
    assert "iban_allowlisted=False" in res["violated_invariants"][0]["counterexample"]


def test_fintech_06_unsat_multi_cap_and_latency():
    """Multi UNSAT: Both daily escrow cap and vendor SLA latency violated."""
    res = evaluate_fintech_invariants(
        state_pre={"daily_escrow_spent_usd": 45000.0, "daily_escrow_limit_usd": 50000.0},
        state_post={
            "transfer_amount_usd": 8000.0,
            "vendor_latency_ms": 320.0,
            "iban_allowlisted": True,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_FIN_01_ESCROW_CAP", "INV_FIN_02_SLA_ATTESTATION"}
    assert res["proof_latency_ms"] < 5.0


def test_fintech_07_unsat_multi_spoofed_wire_12k():
    """Multi UNSAT: Spoofed $12,000 wire exceeding $5,000 cap with slow latency and unallowlisted IBAN."""
    res = evaluate_fintech_invariants(
        state_pre={"daily_escrow_spent_usd": 4200.0, "daily_escrow_limit_usd": 5000.0},
        state_post={
            "transfer_amount_usd": 12000.0,
            "vendor_latency_ms": 640.0,
            "iban_allowlisted": False,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_FIN_01_ESCROW_CAP", "INV_FIN_02_SLA_ATTESTATION"}
    assert res["proof_latency_ms"] < 5.0


def test_fintech_08_boundary_exact_daily_spent_plus_transfer_5000_passes():
    """Exact Boundary: daily_spent + transfer == 5000.0 exactly matches limit and passes."""
    res = evaluate_fintech_invariants(
        state_pre={"daily_escrow_spent_usd": 4000.0, "daily_escrow_limit_usd": 5000.0},
        state_post={
            "transfer_amount_usd": 1000.0,
            "vendor_latency_ms": 150.0,
            "iban_allowlisted": True,
        },
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []
    assert res["proof_latency_ms"] < 5.0


def test_fintech_09_boundary_exact_daily_spent_plus_transfer_exceeds_by_one_cent():
    """Exact Boundary Failure: daily_spent + transfer == 5000.01 exceeds limit by one cent."""
    res = evaluate_fintech_invariants(
        state_pre={"daily_escrow_spent_usd": 4000.0, "daily_escrow_limit_usd": 5000.0},
        state_post={
            "transfer_amount_usd": 1000.01,
            "vendor_latency_ms": 150.0,
            "iban_allowlisted": True,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_FIN_01_ESCROW_CAP"}
    assert res["proof_latency_ms"] < 5.0


def test_fintech_10_boundary_exact_vendor_latency_200_passes():
    """Exact Boundary: vendor_latency_ms == 200.0 exactly satisfies <= 200.0ms invariant."""
    res = evaluate_fintech_invariants(
        state_pre={"daily_escrow_spent_usd": 1000.0, "daily_escrow_limit_usd": 50000.0},
        state_post={
            "transfer_amount_usd": 2000.0,
            "vendor_latency_ms": 200.0,
            "iban_allowlisted": True,
        },
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []
    assert res["proof_latency_ms"] < 5.0


# ===========================================================================
# Cartridge 3: CLOUD_DEVOPS Invariants (10 Tests)
# ===========================================================================

def test_cloud_devops_01_sat_valid_row_growth():
    """Pure SAT: Production table grew after migration with secure non-admin port."""
    res = evaluate_cloud_devops_invariants(
        state_pre={"prod_table_row_count_pre": 10000},
        state_post={
            "prod_table_row_count_post": 12500,
            "cidr_open_world": False,
            "port_number": 443,
        },
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []
    assert res["proof_latency_ms"] < 5.0
    assert len(res["sha256_proof_hash"]) == 64


def test_cloud_devops_02_sat_valid_closed_world_ssh():
    """Pure SAT: SSH port 22 is permitted when CIDR is restricted (cidr_open_world == False)."""
    res = evaluate_cloud_devops_invariants(
        state_pre={"prod_table_row_count_pre": 15420},
        state_post={
            "prod_table_row_count_post": 15420,
            "cidr_open_world": False,
            "port_number": 22,
        },
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []
    assert res["proof_latency_ms"] < 5.0


def test_cloud_devops_03_sat_valid_open_world_web_port():
    """Pure SAT: Public ingress (0.0.0.0/0) is permitted on standard web port 80."""
    res = evaluate_cloud_devops_invariants(
        state_pre={"prod_table_row_count_pre": 1000},
        state_post={
            "prod_table_row_count_post": 1000,
            "cidr_open_world": True,
            "port_number": 80,
        },
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []
    assert res["proof_latency_ms"] < 5.0


def test_cloud_devops_04_unsat_zero_data_loss_single():
    """Single UNSAT: Schema migration caused row count regression from 15,420 to 14,000."""
    res = evaluate_cloud_devops_invariants(
        state_pre={"prod_table_row_count_pre": 15420},
        state_post={
            "prod_table_row_count_post": 14000,
            "cidr_open_world": False,
            "port_number": 443,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_OPS_01_ZERO_DATA_LOSS"}
    assert res["proof_latency_ms"] < 5.0
    assert "delta: -1420" in res["violated_invariants"][0]["remediation_hint"]


def test_cloud_devops_05_unsat_admin_port_single():
    """Single UNSAT: Security group opened world ingress (0.0.0.0/0) on admin port 22."""
    res = evaluate_cloud_devops_invariants(
        state_pre={"prod_table_row_count_pre": 15420},
        state_post={
            "prod_table_row_count_post": 15420,
            "cidr_open_world": True,
            "port_number": 22,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_OPS_02_NO_PUBLIC_ADMIN_PORT"}
    assert res["proof_latency_ms"] < 5.0
    assert "port_number=22" in res["violated_invariants"][0]["counterexample"]


def test_cloud_devops_06_unsat_table_truncate_single():
    """Single UNSAT: Catastrophic table truncate dropped all 50,000 rows to 0."""
    res = evaluate_cloud_devops_invariants(
        state_pre={"prod_table_row_count_pre": 50000},
        state_post={
            "prod_table_row_count_post": 0,
            "cidr_open_world": False,
            "port_number": 443,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_OPS_01_ZERO_DATA_LOSS"}
    assert res["proof_latency_ms"] < 5.0


def test_cloud_devops_07_unsat_multi_row_loss_and_admin_port():
    """Multi UNSAT: Both table drop to 0 and open world SSH port 22 violated simultaneously."""
    res = evaluate_cloud_devops_invariants(
        state_pre={"prod_table_row_count_pre": 15420},
        state_post={
            "prod_table_row_count_post": 0,
            "cidr_open_world": True,
            "port_number": 22,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_OPS_01_ZERO_DATA_LOSS", "INV_OPS_02_NO_PUBLIC_ADMIN_PORT"}
    assert res["proof_latency_ms"] < 5.0


def test_cloud_devops_08_unsat_multi_partial_loss_and_admin_port():
    """Multi UNSAT: Partial row regression (20,000 to 19,500) and open SSH port 22 violated."""
    res = evaluate_cloud_devops_invariants(
        state_pre={"prod_table_row_count_pre": 20000},
        state_post={
            "prod_table_row_count_post": 19500,
            "cidr_open_world": True,
            "port_number": 22,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_OPS_01_ZERO_DATA_LOSS", "INV_OPS_02_NO_PUBLIC_ADMIN_PORT"}
    assert res["proof_latency_ms"] < 5.0


def test_cloud_devops_09_boundary_exact_row_delta_zero_passes():
    """Exact Boundary: row_delta == 0 (post == pre == 15420) satisfies post >= pre and passes."""
    res = evaluate_cloud_devops_invariants(
        state_pre={"prod_table_row_count_pre": 15420},
        state_post={
            "prod_table_row_count_post": 15420,
            "cidr_open_world": False,
            "port_number": 22,
        },
    )
    assert res["status"] == "SAT"
    assert res["violated_invariants"] == []
    assert res["proof_latency_ms"] < 5.0


def test_cloud_devops_10_boundary_exact_row_delta_minus_one_fails():
    """Exact Boundary Failure: row_delta == -1 (post == 15419, pre == 15420) off-by-one regression."""
    res = evaluate_cloud_devops_invariants(
        state_pre={"prod_table_row_count_pre": 15420},
        state_post={
            "prod_table_row_count_post": 15419,
            "cidr_open_world": False,
            "port_number": 443,
        },
    )
    assert res["status"] == "UNSAT"
    assert get_rule_ids(res) == {"INV_OPS_01_ZERO_DATA_LOSS"}
    assert res["proof_latency_ms"] < 5.0


@pytest.mark.parametrize("drop_key, where", [("daily_escrow_limit_usd", "pre"), ("vendor_latency_ms", "post")])
def test_fintech_missing_cap_or_sla_fails_closed(drop_key, where):
    """A wire whose cap or SLA latency is unknown is rejected, never passed on a default value."""
    pre = {"daily_escrow_spent_usd": 0.0, "daily_escrow_limit_usd": 5000.0}
    post = {"transfer_amount_usd": 100.0, "vendor_latency_ms": 50.0, "iban_allowlisted": True}
    (pre if where == "pre" else post).pop(drop_key)
    verdict = verify_state_diff({
        "trace_id": "tr_missing", "shadow_branch_id": "cow_branch_missing", "cartridge_id": "FINTECH_ESCROW",
        "cow_fork_latency_ms": 0.1, "state_pre": pre, "state_post_shadow": post,
    })
    assert verdict["status"] == "UNSAT"
    assert [v["rule_id"] for v in verdict["violated_invariants"]] == ["INV_SYS_00_MALFORMED_STATE"]
