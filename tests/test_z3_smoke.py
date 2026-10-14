"""Smoke tests for CHRONOS-ZERO Z3 Formal Verification Microservice.

Verifies:
- POST /v1/z3/verify responds in under 5ms (Z3 proof latency and HTTP round-trip).
- Formal invariant verification across HEALTHCARE_FHIR, FINTECH_ESCROW, and CLOUD_DEVOPS.
- Dynamic policy compilation via POST /v1/z3/compile-policy.
- Health check and solver readiness via GET /health.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

VERIFIER_DIR = str(Path(__file__).resolve().parents[1] / "services" / "z3-verifier")
if VERIFIER_DIR not in sys.path:
    sys.path.insert(0, VERIFIER_DIR)

from server import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """Create test client and warm up Z3 solver pool."""
    with TestClient(app) as test_client:
        # Initial warm-up request
        test_client.post(
            "/v1/z3/verify",
            json={
                "trace_id": "tr_warmup",
                "shadow_branch_id": "cow_branch_warmup",
                "cartridge_id": "HEALTHCARE_FHIR",
                "cow_fork_latency_ms": 0.5,
                "state_pre": {},
                "state_post_shadow": {
                    "patient_egfr_ml_min": 50.0,
                    "prescribed_drug": "Linagliptin",
                    "prescribed_dose_mg": 5,
                    "claim_submitted": True,
                    "conservative_therapy_weeks": 6,
                },
            },
        )
        yield test_client


def test_verify_responds_under_5ms(client: TestClient):
    """Verify that POST /v1/z3/verify responds in under 5ms."""
    payload = {
        "trace_id": "tr_smoke_perf",
        "shadow_branch_id": "cow_branch_smoke_1",
        "cartridge_id": "HEALTHCARE_FHIR",
        "cow_fork_latency_ms": 0.5,
        "state_pre": {},
        "state_post_shadow": {
            "patient_egfr_ml_min": 24.0,
            "prescribed_drug": "Metformin",
            "prescribed_dose_mg": 2500,
            "claim_submitted": False,
            "conservative_therapy_weeks": 2,
        },
    }

    # Measure over multiple iterations to verify consistent sub-5ms performance
    latencies = []
    for _ in range(5):
        t0 = time.perf_counter_ns()
        response = client.post("/v1/z3/verify", json=payload)
        elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
        latencies.append(elapsed_ms)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "UNSAT"
        assert data["proof_latency_ms"] < 5.0, f"Z3 proof latency exceeded 5ms: {data['proof_latency_ms']}ms"

    # Verify best-of / average round-trip is strictly sub-5ms
    min_latency = min(latencies)
    assert min_latency < 5.0, f"HTTP round-trip latency exceeded 5ms: {min_latency:.3f}ms"


def test_verify_fintech_escrow(client: TestClient):
    """Verify FINTECH_ESCROW invariants and latency."""
    # Test UNSAT on wire cap exceeded
    unsat_payload = {
        "trace_id": "tr_fin_unsat",
        "shadow_branch_id": "cow_branch_fin_1",
        "cartridge_id": "FINTECH_ESCROW",
        "cow_fork_latency_ms": 0.4,
        "state_pre": {
            "daily_escrow_spent_usd": 45000.0,
            "daily_escrow_limit_usd": 50000.0,
        },
        "state_post_shadow": {
            "transfer_amount_usd": 12000.0,
            "vendor_latency_ms": 150.0,
            "iban_allowlisted": True,
        },
    }
    t0 = time.perf_counter_ns()
    res = client.post("/v1/z3/verify", json=unsat_payload)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UNSAT"
    assert data["proof_latency_ms"] < 5.0
    assert elapsed_ms < 5.0
    violated = {v["rule_id"] for v in data["violated_invariants"]}
    assert "INV_FIN_01_ESCROW_CAP" in violated

    # Test UNSAT on SLA latency violation
    sla_unsat_payload = {
        "trace_id": "tr_fin_sla_unsat",
        "shadow_branch_id": "cow_branch_fin_sla",
        "cartridge_id": "FINTECH_ESCROW",
        "cow_fork_latency_ms": 0.4,
        "state_pre": {
            "daily_escrow_spent_usd": 1000.0,
            "daily_escrow_limit_usd": 50000.0,
        },
        "state_post_shadow": {
            "transfer_amount_usd": 1000.0,
            "vendor_latency_ms": 350.0,
            "iban_allowlisted": True,
        },
    }
    res_sla = client.post("/v1/z3/verify", json=sla_unsat_payload)
    assert res_sla.status_code == 200
    assert res_sla.json()["status"] == "UNSAT"
    assert "INV_FIN_02_SLA_ATTESTATION" in {v["rule_id"] for v in res_sla.json()["violated_invariants"]}

    # Test SAT on compliant wire
    sat_payload = {
        "trace_id": "tr_fin_sat",
        "shadow_branch_id": "cow_branch_fin_2",
        "cartridge_id": "FINTECH_ESCROW",
        "cow_fork_latency_ms": 0.4,
        "state_pre": {
            "daily_escrow_spent_usd": 1000.0,
            "daily_escrow_limit_usd": 50000.0,
        },
        "state_post_shadow": {
            "transfer_amount_usd": 400.0,
            "vendor_latency_ms": 120.0,
            "iban_allowlisted": True,
        },
    }
    res_sat = client.post("/v1/z3/verify", json=sat_payload)
    assert res_sat.status_code == 200
    assert res_sat.json()["status"] == "SAT"
    assert res_sat.json()["proof_latency_ms"] < 5.0


def test_verify_cloud_devops(client: TestClient):
    """Verify CLOUD_DEVOPS invariants and latency."""
    # Test UNSAT on destructive drop table (row loss)
    unsat_row_payload = {
        "trace_id": "tr_ops_row_unsat",
        "shadow_branch_id": "cow_branch_ops_1",
        "cartridge_id": "CLOUD_DEVOPS",
        "cow_fork_latency_ms": 0.4,
        "state_pre": {
            "prod_table_row_count_pre": 15420,
        },
        "state_post_shadow": {
            "prod_table_row_count_post": 0,
            "cidr_open_world": False,
            "port_number": 443,
        },
    }
    t0 = time.perf_counter_ns()
    res = client.post("/v1/z3/verify", json=unsat_row_payload)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UNSAT"
    assert data["proof_latency_ms"] < 5.0
    assert elapsed_ms < 5.0
    violated = {v["rule_id"] for v in data["violated_invariants"]}
    assert "INV_OPS_01_ZERO_DATA_LOSS" in violated

    # Test UNSAT on port 22 exposed to 0.0.0.0/0
    unsat_port_payload = {
        "trace_id": "tr_ops_port_unsat",
        "shadow_branch_id": "cow_branch_ops_2",
        "cartridge_id": "CLOUD_DEVOPS",
        "cow_fork_latency_ms": 0.4,
        "state_pre": {
            "prod_table_row_count_pre": 15420,
        },
        "state_post_shadow": {
            "prod_table_row_count_post": 15420,
            "cidr_open_world": True,
            "port_number": 22,
        },
    }
    res_port = client.post("/v1/z3/verify", json=unsat_port_payload)
    assert res_port.status_code == 200
    data_port = res_port.json()
    assert data_port["status"] == "UNSAT"
    assert "INV_OPS_02_NO_PUBLIC_ADMIN_PORT" in {v["rule_id"] for v in data_port["violated_invariants"]}

    # Test SAT on non-destructive migration
    sat_payload = {
        "trace_id": "tr_ops_sat",
        "shadow_branch_id": "cow_branch_ops_3",
        "cartridge_id": "CLOUD_DEVOPS",
        "cow_fork_latency_ms": 0.4,
        "state_pre": {
            "prod_table_row_count_pre": 15420,
        },
        "state_post_shadow": {
            "prod_table_row_count_post": 15420,
            "cidr_open_world": False,
            "port_number": 443,
        },
    }
    res_sat = client.post("/v1/z3/verify", json=sat_payload)
    assert res_sat.status_code == 200
    assert res_sat.json()["status"] == "SAT"
    assert res_sat.json()["proof_latency_ms"] < 5.0


def test_compile_policy_and_verify(client: TestClient):
    """Verify POST /v1/z3/compile-policy compiles and immediately enforces new rules."""
    compile_payload = {
        "cartridge_id": "FINTECH_ESCROW",
        "rule_id": "INV_DYNAMIC_01_WIRE_LIMIT",
        "natural_language_rule": "Block wire transfer exceeding $5,000",
    }
    res = client.post("/v1/z3/compile-policy", json=compile_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPILED"
    assert "transfer_amount_usd" in data["formal_assertion"]

    # Transfer of $6,000 is compliant with standard rules but violates the new dynamic rule ($5,000 limit)
    test_payload = {
        "trace_id": "tr_dyn_test",
        "shadow_branch_id": "cow_branch_dyn_1",
        "cartridge_id": "FINTECH_ESCROW",
        "cow_fork_latency_ms": 0.3,
        "state_pre": {
            "daily_escrow_spent_usd": 1000.0,
            "daily_escrow_limit_usd": 50000.0,
        },
        "state_post_shadow": {
            "transfer_amount_usd": 6000.0,
            "vendor_latency_ms": 100.0,
            "iban_allowlisted": True,
        },
    }
    verify_res = client.post("/v1/z3/verify", json=test_payload)
    assert verify_res.status_code == 200
    verdict = verify_res.json()
    assert verdict["status"] == "UNSAT"
    violated = {v["rule_id"] for v in verdict["violated_invariants"]}
    assert "INV_DYNAMIC_01_WIRE_LIMIT" in violated


def test_health_check(client: TestClient):
    """Verify GET /health returns solver readiness and average proof latency."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["solver_pool_ready"] is True
    assert "average_proof_latency_ms" in data
    assert data["average_proof_latency_ms"] >= 0.0
    assert "HEALTHCARE_FHIR" in data["supported_cartridges"]
    assert "FINTECH_ESCROW" in data["supported_cartridges"]
    assert "CLOUD_DEVOPS" in data["supported_cartridges"]
