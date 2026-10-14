"""Formal invariants for FINTECH_ESCROW cartridge.

Enforces:
- INV_FIN_01_ESCROW_CAP: Daily spend plus proposed transfer must not exceed daily escrow limit.
- INV_FIN_02_SLA_ATTESTATION: Outgoing transfers require vendor SLA latency <= 200ms and allowlisted IBAN.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Tuple
from z3 import And, Bool, BoolVal, Implies, Real, RealVal, Solver, unknown, unsat

SOLVER_TIMEOUT_MS = 50

RULE_REGISTRY: Dict[str, Dict[str, str]] = {
    "INV_FIN_01_ESCROW_CAP": {
        "formal": "daily_escrow_spent_usd + transfer_amount_usd <= daily_escrow_limit_usd",
        "remediation": (
            "Requested wire of ${transfer:,.2f} exceeds remaining daily escrow capacity "
            "(${remaining_cap:,.2f} remaining out of ${limit:,.2f} limit). "
            "Reduce transfer_amount_usd to <= {remaining_cap:,.2f} USD or split into milestone tranches."
        ),
    },
    "INV_FIN_02_SLA_ATTESTATION": {
        "formal": "Implies(transfer_amount_usd > 0, And(vendor_latency_ms <= 200.0, iban_allowlisted == True))",
        "remediation": (
            "Counterparty failed zkTLS SLA verification (vendor_latency_ms={vendor_latency_ms}ms > 200.0ms) "
            "or destination IBAN is not on treasury allowlist (iban_allowlisted={iban_allowlisted}). "
            "Route payout to verified backup vendor on allowlist meeting <= 200.0ms SLA."
        ),
    },
}


def build_fintech_solver(
    state_pre: Dict[str, Any], state_post: Dict[str, Any]
) -> Tuple[Solver, Dict[str, Any], List[Tuple[str, Any]]]:
    """Build Z3 solver instance with tracked invariants for FINTECH_ESCROW."""
    s = Solver()
    s.set("timeout", SOLVER_TIMEOUT_MS)

    spent_val = float(state_pre.get("daily_escrow_spent_usd", state_pre.get("daily_spent", 0.0)))
    limit_val = float(state_pre.get("daily_escrow_limit_usd", state_pre.get("daily_limit", 50000.0)))

    # Handle transfer amount field variations
    transfer_raw = state_post.get("transfer_amount_usd")
    if transfer_raw is None:
        transfer_raw = state_post.get("last_transfer_amount_usd", state_post.get("transfer_amount", 0.0))
    transfer_val = float(transfer_raw)

    latency_raw = state_post.get("vendor_latency_ms", state_post.get("vendor_sla_latency_ms", 0.0))
    latency_val = float(latency_raw)

    allowlisted_val = bool(state_post.get("iban_allowlisted", False))

    # Declare typed Z3 variables
    spent = Real("daily_escrow_spent_usd")
    transfer = Real("transfer_amount_usd")
    limit = Real("daily_escrow_limit_usd")
    latency = Real("vendor_latency_ms")
    allowlisted = Bool("iban_allowlisted")

    # Cast and add exact value bindings
    s.add(spent == RealVal(spent_val))
    s.add(transfer == RealVal(transfer_val))
    s.add(limit == RealVal(limit_val))
    s.add(latency == RealVal(latency_val))
    s.add(allowlisted == BoolVal(allowlisted_val))

    # Tracked assertions
    tracked_rules = [
        ("INV_FIN_01_ESCROW_CAP", spent + transfer <= limit),
        (
            "INV_FIN_02_SLA_ATTESTATION",
            Implies(
                transfer > RealVal(0.0),
                And(latency <= RealVal(200.0), allowlisted == BoolVal(True)),
            ),
        ),
    ]

    remaining_cap = max(0.0, limit_val - spent_val)
    context = {
        "spent": spent_val,
        "daily_escrow_spent_usd": spent_val,
        "limit": limit_val,
        "daily_escrow_limit_usd": limit_val,
        "transfer": transfer_val,
        "transfer_amount_usd": transfer_val,
        "vendor_latency_ms": latency_val,
        "iban_allowlisted": allowlisted_val,
        "remaining_cap": remaining_cap,
    }
    return s, context, tracked_rules


def evaluate_fintech_invariants(
    state_pre: Dict[str, Any], state_post: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute formal verification against FINTECH_ESCROW invariants.

    Identifies ALL broken rules when multiple invariants fail simultaneously (e.g. $12,000 wire to spoofed IBAN).
    """
    t0 = time.perf_counter_ns()
    violated: List[Dict[str, str]] = []
    smt2_str = ""

    try:
        s, context, tracked_rules = build_fintech_solver(state_pre, state_post)

        failed_ids = []
        for r_id, expr in tracked_rules:
            s.push()
            s.assert_and_track(expr, r_id)
            if s.check() == unsat:
                failed_ids.extend([str(c) for c in s.unsat_core()])
            s.pop()

        # Add all rules for SMT2 dump
        for r_id, expr in tracked_rules:
            s.assert_and_track(expr, r_id)
        smt2_str = s.to_smt2()

        if failed_ids:
            status = "UNSAT"
            for r_id in sorted(list(set(failed_ids))):
                meta = RULE_REGISTRY.get(r_id, {"formal": r_id, "remediation": f"{r_id} violated."})
                if r_id == "INV_FIN_01_ESCROW_CAP":
                    cex = (
                        f"daily_escrow_spent_usd={context['spent']}, "
                        f"transfer_amount_usd={context['transfer']}, "
                        f"daily_escrow_limit_usd={context['limit']}"
                    )
                elif r_id == "INV_FIN_02_SLA_ATTESTATION":
                    cex = (
                        f"transfer_amount_usd={context['transfer']}, "
                        f"vendor_latency_ms={context['vendor_latency_ms']}, "
                        f"iban_allowlisted={context['iban_allowlisted']}"
                    )
                else:
                    cex = str(context)

                violated.append({
                    "rule_id": r_id,
                    "formal_assertion": meta["formal"],
                    "counterexample": cex,
                    "remediation_hint": meta["remediation"].format(**context),
                })
        else:
            status = "SAT"

    except Exception as e:
        status = "UNSAT"
        smt2_str = ""
        violated.append({
            "rule_id": "STATE_ERROR",
            "formal_assertion": "valid_state_delta",
            "counterexample": str(e),
            "remediation_hint": f"Malformed state payload rejected: {str(e)}",
        })

    proof_ms = round((time.perf_counter_ns() - t0) / 1_000_000.0, 3)
    proof_hash = hashlib.sha256(smt2_str.encode("utf-8")).hexdigest()

    return {
        "status": status,
        "proof_latency_ms": proof_ms,
        "violated_invariants": violated,
        "smt2_dump": smt2_str,
        "sha256_proof_hash": proof_hash,
    }
