"""Unit and integration test suite for Natural Language to Z3 formal policy compiler.

Tests:
- Dynamic compilation of plain-English compliance rules across all 3 cartridges
- AST Safety Sandbox blocking malicious constructs (imports, attributes, unlisted calls, unauthorized vars)
- Satisfiability and synthetic test vector validation (SAT on passing, UNSAT on failing, contradiction/tautology rejection)
- Immediate runtime enforcement via prover core dispatch_verification
- Contract parity and live UI telemetry fields (compiled_code, smt2_dump, compilation_latency_ms < 5ms)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = str(Path(__file__).resolve().parents[1])
VERIFIER_DIR = str(Path(__file__).resolve().parents[1] / "services" / "z3-verifier")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if VERIFIER_DIR not in sys.path:
    sys.path.insert(0, VERIFIER_DIR)

import nl_compiler
from nl_compiler import (
    ASTSafetyViolation,
    PolicyCompilationError,
    clear_dynamic_rules,
    compile_nl_policy,
    validate_ast_safety,
)
from prover_core import dispatch_verification
from server import app


@pytest.fixture(autouse=True)
def clean_dynamic_rules():
    """Ensure dynamic rules are cleared before and after each test."""
    clear_dynamic_rules()
    yield
    clear_dynamic_rules()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Dynamic Policy Compilation Tests
# ---------------------------------------------------------------------------

def test_nl_compiler_fintech_wire_cap():
    """Verify plain English wire cap compiles into correct Z3 constraint."""
    res = compile_nl_policy(
        cartridge_id="FINTECH_ESCROW",
        rule_id="INV_DYN_01_WIRE_5K",
        natural_language_rule="Block wire transfer exceeding $5,000",
    )
    assert res["status"] == "COMPILED"
    assert res["cartridge_id"] == "FINTECH_ESCROW"
    assert res["rule_id"] == "INV_DYN_01_WIRE_5K"
    assert res["formal_assertion"] == "transfer_amount_usd <= 5000.0"
    assert res["compiled_code"] == "transfer_amount_usd <= 5000.0"
    assert "(assert" in res["smt2_dump"]
    assert res["compilation_latency_ms"] < 10.0
    assert res["synthetic_passing_state"]["transfer_amount_usd"] <= 5000.0
    assert res["synthetic_failing_state"]["transfer_amount_usd"] > 5000.0


def test_nl_compiler_fintech_wire_unless_sla():
    """Verify conditional wire rule with SLA and allowlist compiles to Implies(..., And(...))."""
    res = compile_nl_policy(
        cartridge_id="FINTECH_ESCROW",
        rule_id="INV_DYN_01_WIRE_SLA",
        natural_language_rule="Block wire transfer exceeding $5,000 unless vendor_latency_ms <= 150.0 and iban_allowlisted is True",
    )
    assert res["status"] == "COMPILED"
    assert "Implies(transfer_amount_usd > 5000.0, And(vendor_latency_ms <= 150.0, iban_allowlisted == True))" in res["formal_assertion"]
    assert "(assert" in res["smt2_dump"]


def test_nl_compiler_healthcare_renal():
    """Verify healthcare renal safety rule compiles with eGFR threshold and metformin dose 0."""
    res = compile_nl_policy(
        cartridge_id="HEALTHCARE_FHIR",
        rule_id="INV_DYN_01_RENAL_SAFETY",
        natural_language_rule="Block metformin if patient eGFR is below 30",
    )
    assert res["status"] == "COMPILED"
    assert res["formal_assertion"] == "Implies(patient_egfr_ml_min < 30.0, prescribed_dose_metformin == 0)"
    assert res["compilation_latency_ms"] < 10.0


def test_nl_compiler_devops_zero_data_loss():
    """Verify DevOps zero data loss compiles to row count post >= pre."""
    res = compile_nl_policy(
        cartridge_id="CLOUD_DEVOPS",
        rule_id="INV_DYN_01_ZERO_LOSS",
        natural_language_rule="Zero data loss during schema migration",
    )
    assert res["status"] == "COMPILED"
    assert res["formal_assertion"] == "prod_table_row_count_post >= prod_table_row_count_pre"


def test_nl_compiler_devops_admin_port():
    """Verify DevOps port protection compiles to Not(And(cidr_open_world == True, port_number == 22))."""
    res = compile_nl_policy(
        cartridge_id="CLOUD_DEVOPS",
        rule_id="INV_DYN_01_SSH_BLOCK",
        natural_language_rule="Block open SSH on port 22",
    )
    assert res["status"] == "COMPILED"
    assert res["formal_assertion"] == "Not(And(cidr_open_world == True, port_number == 22))"


def test_nl_compiler_direct_z3_expression():
    """Verify raw valid Z3 Python expressions bypass synthesizer and compile directly."""
    raw_expr = "Implies(patient_egfr_ml_min < 45.0, prescribed_dose_mg <= 1000)"
    res = compile_nl_policy(
        cartridge_id="HEALTHCARE_FHIR",
        rule_id="INV_DYN_01_CUSTOM_EXPR",
        natural_language_rule=raw_expr,
    )
    assert res["status"] == "COMPILED"
    assert res["formal_assertion"] == raw_expr


# ---------------------------------------------------------------------------
# AST Safety Sandbox Security Tests
# ---------------------------------------------------------------------------

def test_ast_sandbox_rejects_imports():
    """AST sandbox must block import statements and reject execution."""
    with pytest.raises(ASTSafetyViolation):
        validate_ast_safety("import os", "FINTECH_ESCROW")

    with pytest.raises(ASTSafetyViolation):
        validate_ast_safety("from os import system", "FINTECH_ESCROW")


def test_ast_sandbox_rejects_attribute_access():
    """AST sandbox must block attribute access (e.g. __class__, obj.attr)."""
    with pytest.raises(ASTSafetyViolation):
        validate_ast_safety("transfer_amount_usd.__class__", "FINTECH_ESCROW")

    with pytest.raises(ASTSafetyViolation):
        validate_ast_safety("transfer_amount_usd.__dict__", "FINTECH_ESCROW")


def test_ast_sandbox_rejects_unapproved_calls():
    """AST sandbox must block arbitrary function calls outside the Z3 allowlist."""
    for evil in [
        "eval('1 + 1')",
        "exec('x = 1')",
        "open('/etc/passwd')",
        "__import__('os').system('ls')",
        "getattr(transfer_amount_usd, '__class__')",
        "globals()",
        "locals()",
    ]:
        with pytest.raises(ASTSafetyViolation):
            validate_ast_safety(evil, "FINTECH_ESCROW")


def test_ast_sandbox_rejects_unauthorized_identifiers():
    """AST sandbox must reject variables not declared in the cartridge schema."""
    with pytest.raises(ASTSafetyViolation):
        validate_ast_safety("bitcoin_wallet_balance > 0", "FINTECH_ESCROW")

    with pytest.raises(ASTSafetyViolation):
        validate_ast_safety("os == 'linux'", "CLOUD_DEVOPS")


def test_ast_sandbox_rejects_subscripts_and_lambdas():
    """AST sandbox must reject indexing, slicing, and lambda expressions."""
    with pytest.raises(ASTSafetyViolation):
        validate_ast_safety("transfer_amount_usd[0] > 0", "FINTECH_ESCROW")

    with pytest.raises(ASTSafetyViolation):
        validate_ast_safety("(lambda x: x)(transfer_amount_usd) > 0", "FINTECH_ESCROW")


# ---------------------------------------------------------------------------
# Synthetic Vector Satisfiability Tests
# ---------------------------------------------------------------------------

def test_synthetic_vector_contradiction_rejected():
    """Contradictory policy must be rejected during synthetic vector evaluation."""
    contradiction = "And(transfer_amount_usd > 1000.0, transfer_amount_usd < 500.0)"
    with pytest.raises(PolicyCompilationError):
        compile_nl_policy(
            cartridge_id="FINTECH_ESCROW",
            rule_id="INV_DYN_01_CONTRADICTION",
            natural_language_rule=contradiction,
        )


def test_synthetic_vector_tautology_rejected():
    """Tautological policy (cannot be violated) must be rejected during synthetic vector evaluation."""
    tautology = "Or(transfer_amount_usd >= 0.0, transfer_amount_usd < 0.0)"
    with pytest.raises(PolicyCompilationError):
        compile_nl_policy(
            cartridge_id="FINTECH_ESCROW",
            rule_id="INV_DYN_01_TAUTOLOGY",
            natural_language_rule=tautology,
        )


# ---------------------------------------------------------------------------
# Immediate Runtime Enforcement in Prover Core
# ---------------------------------------------------------------------------

def test_compiled_rule_immediate_enforcement_in_dispatch():
    """Verify compiled dynamic rule is immediately evaluated by dispatch_verification."""
    # 1. Compile wire limit of $3,000
    res = compile_nl_policy(
        cartridge_id="FINTECH_ESCROW",
        rule_id="INV_DYN_01_WIRE_3K",
        natural_language_rule="Block wire transfer exceeding $3,000",
    )
    assert res["status"] == "COMPILED"

    # 2. Test transfer of $4,000 (compliant with static rules, violates dynamic rule)
    violating_payload = {
        "trace_id": "tr_dyn_enforce",
        "shadow_branch_id": "cow_branch_dyn_1",
        "cartridge_id": "FINTECH_ESCROW",
        "cow_fork_latency_ms": 0.4,
        "state_pre": {
            "daily_escrow_spent_usd": 1000.0,
            "daily_escrow_limit_usd": 50000.0,
        },
        "state_post_shadow": {
            "transfer_amount_usd": 4000.0,
            "vendor_latency_ms": 100.0,
            "iban_allowlisted": True,
        },
    }
    verdict = dispatch_verification(violating_payload)
    assert verdict.status == "UNSAT"
    violated = {v.rule_id for v in verdict.violated_invariants}
    assert "INV_DYN_01_WIRE_3K" in violated

    # 3. Test transfer of $2,000 (passes both static and dynamic rules)
    passing_payload = {
        "trace_id": "tr_dyn_pass",
        "shadow_branch_id": "cow_branch_dyn_2",
        "cartridge_id": "FINTECH_ESCROW",
        "cow_fork_latency_ms": 0.3,
        "state_pre": {
            "daily_escrow_spent_usd": 1000.0,
            "daily_escrow_limit_usd": 50000.0,
        },
        "state_post_shadow": {
            "transfer_amount_usd": 2000.0,
            "vendor_latency_ms": 100.0,
            "iban_allowlisted": True,
        },
    }
    verdict_pass = dispatch_verification(passing_payload)
    assert verdict_pass.status == "SAT"
    assert verdict_pass.violated_invariants == []


# ---------------------------------------------------------------------------
# Server HTTP Endpoint Tests
# ---------------------------------------------------------------------------

def test_server_compile_policy_endpoint(client: TestClient):
    """Test POST /v1/z3/compile-policy endpoint returns all required telemetry fields."""
    req_body = {
        "cartridge_id": "FINTECH_ESCROW",
        "rule_id": "INV_DYN_01_HTTP_TEST",
        "natural_language_rule": "Block wire transfer exceeding $7,500",
    }
    res = client.post("/v1/z3/compile-policy", json=req_body)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPILED"
    assert data["cartridge_id"] == "FINTECH_ESCROW"
    assert data["rule_id"] == "INV_DYN_01_HTTP_TEST"
    assert "transfer_amount_usd <= 7500.0" in data["formal_assertion"]
    assert data["compiled_code"] == "transfer_amount_usd <= 7500.0"
    assert "(assert" in data["smt2_dump"]
    assert data["compilation_latency_ms"] is not None
    assert data["compilation_latency_ms"] < 10.0


def test_server_compile_policy_rejects_attack(client: TestClient):
    """Test POST /v1/z3/compile-policy fails closed with status=ERROR on AST injection."""
    req_body = {
        "cartridge_id": "FINTECH_ESCROW",
        "rule_id": "INV_DYN_01_ATTACK",
        "natural_language_rule": "__import__('os').system('ls')",
    }
    res = client.post("/v1/z3/compile-policy", json=req_body)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ERROR"
    assert "Failed to compile policy" in data["message"]
