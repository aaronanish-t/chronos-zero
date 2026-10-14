"""Property-based fuzzing and stress test suite for CHRONOS-ZERO Z3 Formal Prover.

Uses Hypothesis to fuzz all three domain cartridge evaluators:
- HEALTHCARE_FHIR (INV_MED_01, INV_MED_02, INV_MED_03)
- FINTECH_ESCROW (INV_FIN_01, INV_FIN_02)
- CLOUD_DEVOPS (INV_OPS_01, INV_OPS_02)

Verifies:
1. Zero unhandled exceptions on 1,000+ randomized float/int/boolean payloads
   (including negative numbers, zero, extreme floats, NaN/Inf, and missing keys).
2. Zero memory leaks across 1,000 sequential proof executions via tracemalloc.
3. 100% strict adherence to the 50ms solver timeout ceiling per AGENTS.md Section 4.2.
"""

from __future__ import annotations

import gc
import random
import resource
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

# Ensure repository root and verifier directory are on sys.path
REPO_ROOT = str(Path(__file__).resolve().parents[1])
VERIFIER_DIR = str(Path(__file__).resolve().parents[1] / "services" / "z3-verifier")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if VERIFIER_DIR not in sys.path:
    sys.path.insert(0, VERIFIER_DIR)

from contracts.schemas import StateDiffRequest
from invariants.cloud_devops import evaluate_cloud_devops_invariants
from invariants.fintech_escrow import evaluate_fintech_invariants
from invariants.healthcare_fhir import evaluate_healthcare_invariants
from prover_core import dispatch_verification, prewarm_solvers


@pytest.fixture(scope="session", autouse=True)
def prewarm_z3_session():
    """Prewarm Z3 C++ engine at session start."""
    prewarm_solvers()


# ---------------------------------------------------------------------------
# Custom Hypothesis Strategies for Edge Case Generation
# ---------------------------------------------------------------------------

# Floats: normal, extreme (1e300, -1e300), subnormal, zero, negative, NaN, Inf, and None (missing)
fuzz_floats = (
    st.floats(allow_nan=True, allow_infinity=True)
    | st.sampled_from([-1e300, -1e10, -100.0, -1.0, -0.0, 0.0, 1.0, 30.0, 100.0, 1e10, 1e300])
    | st.none()
)

# Integers: negative, zero, boundary, extreme 64-bit and 32-bit, and None (missing)
fuzz_integers = (
    st.integers(min_value=-2**31, max_value=2**31 - 1)
    | st.sampled_from([-1000, -1, 0, 1, 6, 22, 80, 443, 2000, 2500, 15419, 15420, 65535])
    | st.none()
)

# Booleans: True, False, and None (missing)
fuzz_booleans = st.booleans() | st.none()


# ---------------------------------------------------------------------------
# 1. Healthcare FHIR Invariants Fuzzing (1,000 Hypothesis Examples)
# ---------------------------------------------------------------------------

@settings(
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
@given(
    egfr=fuzz_floats,
    drug=st.sampled_from(["Metformin", "Linagliptin", "Insulin", "", "UnknownDrug", "METFORMIN"]) | st.none(),
    dose_mg=fuzz_integers,
    dose_metformin=fuzz_integers,
    claim=fuzz_booleans,
    weeks=fuzz_integers,
)
def test_fuzz_healthcare_fhir_invariants(
    egfr: Optional[float],
    drug: Optional[str],
    dose_mg: Optional[int],
    dose_metformin: Optional[int],
    claim: Optional[bool],
    weeks: Optional[int],
):
    """Fuzz Healthcare FHIR evaluator with 1,000 randomized dictionaries including extreme floats and missing keys."""
    state_post: Dict[str, Any] = {}
    if egfr is not None:
        state_post["patient_egfr_ml_min"] = egfr
    if drug is not None:
        state_post["prescribed_drug"] = drug
    if dose_mg is not None:
        state_post["prescribed_dose_mg"] = dose_mg
    if dose_metformin is not None:
        state_post["prescribed_dose_metformin"] = dose_metformin
    if claim is not None:
        state_post["claim_submitted"] = claim
    if weeks is not None:
        state_post["conservative_therapy_weeks"] = weeks

    # Zero unhandled exceptions allowed
    res = evaluate_healthcare_invariants(state_pre={}, state_post=state_post)

    # 100% adherence to Contract 3 and 50ms solver timeout ceiling
    assert res["status"] in ("SAT", "UNSAT"), f"Invalid verdict status: {res['status']}"
    assert 0.0 <= res["proof_latency_ms"] <= 50.0, f"Latency ceiling exceeded: {res['proof_latency_ms']}ms > 50ms"
    assert isinstance(res["violated_invariants"], list)
    assert len(res["sha256_proof_hash"]) == 64


# ---------------------------------------------------------------------------
# 2. Fintech Escrow Invariants Fuzzing (1,000 Hypothesis Examples)
# ---------------------------------------------------------------------------

@settings(
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
@given(
    spent=fuzz_floats,
    limit=fuzz_floats,
    transfer=fuzz_floats,
    latency=fuzz_floats,
    allowlisted=fuzz_booleans,
)
def test_fuzz_fintech_escrow_invariants(
    spent: Optional[float],
    limit: Optional[float],
    transfer: Optional[float],
    latency: Optional[float],
    allowlisted: Optional[bool],
):
    """Fuzz Fintech Escrow evaluator with 1,000 randomized dictionaries including negative wires and missing keys."""
    state_pre: Dict[str, Any] = {}
    if spent is not None:
        state_pre["daily_escrow_spent_usd"] = spent
    if limit is not None:
        state_pre["daily_escrow_limit_usd"] = limit

    state_post: Dict[str, Any] = {}
    if transfer is not None:
        state_post["transfer_amount_usd"] = transfer
    if latency is not None:
        state_post["vendor_latency_ms"] = latency
    if allowlisted is not None:
        state_post["iban_allowlisted"] = allowlisted

    # Zero unhandled exceptions allowed
    res = evaluate_fintech_invariants(state_pre=state_pre, state_post=state_post)

    # 100% adherence to Contract 3 and 50ms solver timeout ceiling
    assert res["status"] in ("SAT", "UNSAT"), f"Invalid verdict status: {res['status']}"
    assert 0.0 <= res["proof_latency_ms"] <= 50.0, f"Latency ceiling exceeded: {res['proof_latency_ms']}ms > 50ms"
    assert isinstance(res["violated_invariants"], list)
    assert len(res["sha256_proof_hash"]) == 64


# ---------------------------------------------------------------------------
# 3. Cloud DevOps Invariants Fuzzing (1,000 Hypothesis Examples)
# ---------------------------------------------------------------------------

@settings(
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
@given(
    rows_pre=fuzz_integers,
    rows_post=fuzz_integers,
    cidr=fuzz_booleans,
    port=fuzz_integers,
)
def test_fuzz_cloud_devops_invariants(
    rows_pre: Optional[int],
    rows_post: Optional[int],
    cidr: Optional[bool],
    port: Optional[int],
):
    """Fuzz Cloud DevOps evaluator with 1,000 randomized dictionaries including negative row counts and missing keys."""
    state_pre: Dict[str, Any] = {}
    if rows_pre is not None:
        state_pre["prod_table_row_count_pre"] = rows_pre

    state_post: Dict[str, Any] = {}
    if rows_post is not None:
        state_post["prod_table_row_count_post"] = rows_post
    if cidr is not None:
        state_post["cidr_open_world"] = cidr
    if port is not None:
        state_post["port_number"] = port

    # Zero unhandled exceptions allowed
    res = evaluate_cloud_devops_invariants(state_pre=state_pre, state_post=state_post)

    # 100% adherence to Contract 3 and 50ms solver timeout ceiling
    assert res["status"] in ("SAT", "UNSAT"), f"Invalid verdict status: {res['status']}"
    assert 0.0 <= res["proof_latency_ms"] <= 50.0, f"Latency ceiling exceeded: {res['proof_latency_ms']}ms > 50ms"
    assert isinstance(res["violated_invariants"], list)
    assert len(res["sha256_proof_hash"]) == 64


# ---------------------------------------------------------------------------
# 4. Zero Memory Leak & 50ms Timeout Ceiling Across 1,000 Mixed Evaluations
# ---------------------------------------------------------------------------

def test_fuzz_zero_memory_leak_and_timeout_ceiling_1000_iterations():
    """Execute 1,000 sequential randomized state diff requests across all 3 cartridges.

    Verifies:
    - Zero memory leaks: traced memory growth after GC is essentially zero (< 500 KB).
    - 100% adherence to 50ms solver timeout ceiling.
    - Zero unhandled exceptions across all 1,000 calls.
    """
    gc.collect()
    tracemalloc.start()
    baseline_mem, _ = tracemalloc.get_traced_memory()
    start_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    cartridges = ["HEALTHCARE_FHIR", "FINTECH_ESCROW", "CLOUD_DEVOPS"]

    for i in range(1000):
        c_id = cartridges[i % 3]

        if c_id == "HEALTHCARE_FHIR":
            payload = {
                "trace_id": f"tr_fuzz_{i}",
                "shadow_branch_id": f"cow_branch_fuzz_{i}",
                "cartridge_id": c_id,
                "cow_fork_latency_ms": 0.1,
                "state_pre": {},
                "state_post_shadow": {
                    "patient_egfr_ml_min": random.choice([-50.0, -0.0, 0.0, 15.0, 29.99, 30.0, 60.0, 1e20, -1e20]),
                    "prescribed_drug": random.choice(["Metformin", "Linagliptin", "Insulin", ""]),
                    "prescribed_dose_mg": random.choice([-500, 0, 500, 2000, 2500, 100000]),
                    "claim_submitted": random.choice([True, False]),
                    "conservative_therapy_weeks": random.choice([-10, 0, 2, 5, 6, 12, 100]),
                },
            }
        elif c_id == "FINTECH_ESCROW":
            payload = {
                "trace_id": f"tr_fuzz_{i}",
                "shadow_branch_id": f"cow_branch_fuzz_{i}",
                "cartridge_id": c_id,
                "cow_fork_latency_ms": 0.1,
                "state_pre": {
                    "daily_escrow_spent_usd": random.choice([-1000.0, 0.0, 1000.0, 49000.0, 1e12]),
                    "daily_escrow_limit_usd": random.choice([0.0, 5000.0, 50000.0, 1e15]),
                },
                "state_post_shadow": {
                    "transfer_amount_usd": random.choice([-100.0, 0.0, 1000.0, 5000.0, 12000.0, 1e12]),
                    "vendor_latency_ms": random.choice([-50.0, 0.0, 50.0, 200.0, 250.0, 1e6]),
                    "iban_allowlisted": random.choice([True, False]),
                },
            }
        else:
            payload = {
                "trace_id": f"tr_fuzz_{i}",
                "shadow_branch_id": f"cow_branch_fuzz_{i}",
                "cartridge_id": c_id,
                "cow_fork_latency_ms": 0.1,
                "state_pre": {
                    "prod_table_row_count_pre": random.choice([-100, 0, 1000, 15420, 10000000])
                },
                "state_post_shadow": {
                    "prod_table_row_count_post": random.choice([-100, 0, 1000, 15419, 15420, 20000000]),
                    "cidr_open_world": random.choice([True, False]),
                    "port_number": random.choice([-1, 0, 22, 80, 443, 8080, 65535]),
                },
            }

        # Dispatch through prover core entrypoint
        verdict = dispatch_verification(payload)

        # Invariant checks per iteration
        assert verdict.status in ("SAT", "UNSAT")
        assert verdict.proof_latency_ms <= 50.0, f"Iteration {i} exceeded 50ms: {verdict.proof_latency_ms}ms"
        assert len(verdict.sha256_proof_hash) == 64

    gc.collect()
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    end_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    mem_growth_kb = (current_mem - baseline_mem) / 1024.0
    rss_growth_mb = (end_rss_kb - start_rss_kb) / 1024.0

    # Memory leak assertions: residual memory growth must be negligible (< 500 KB)
    assert mem_growth_kb < 500.0, f"Potential memory leak detected: {mem_growth_kb:.2f} KB growth"
    assert rss_growth_mb < 20.0, f"RSS memory growth too high: {rss_growth_mb:.2f} MB"
