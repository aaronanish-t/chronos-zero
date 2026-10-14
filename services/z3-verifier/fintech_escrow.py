"""Formal invariants for FINTECH_ESCROW cartridge.

Enforces:
- INV_FIN_01_ESCROW_CAP: Daily spend plus proposed transfer must not exceed daily escrow limit.
- INV_FIN_02_SLA_ATTESTATION: Outgoing transfers require vendor SLA latency <= 200ms and allowlisted IBAN.
"""

from typing import Any, Tuple
from z3 import And, Bool, BoolVal, Implies, Real, RealVal, Solver

SOLVER_TIMEOUT_MS = 50

RULE_REGISTRY = {
    "INV_FIN_01_ESCROW_CAP": {
        "formal": "daily_escrow_spent_usd + transfer_amount_usd <= daily_escrow_limit_usd",
        "remediation": (
            "Requested wire of ${transfer:,.2f} exceeds remaining daily escrow limit "
            "(${remaining_cap:,.2f} remaining out of ${limit:,.2f} limit). "
            "Reduce transfer_amount_usd to <= {remaining_cap:,.2f} USD or split into milestone tranches."
        ),
    },
    "INV_FIN_02_SLA_ATTESTATION": {
        "formal": "Implies(transfer_amount_usd > 0, And(vendor_latency_ms <= 200.0, iban_allowlisted == True))",
        "remediation": (
            "Counterparty failed zkTLS SLA check (latency {vendor_latency_ms}ms > 200.0ms) "
            "or IBAN is not on treasury allowlist (allowlisted={iban_allowlisted}). "
            "Route payout to verified backup vendor."
        ),
    },
}


def build_fintech_solver(state_pre: dict[str, Any], state_post: dict[str, Any]) -> Tuple[Solver, dict[str, Any]]:
    """Build Z3 solver with tracked invariants for FINTECH_ESCROW."""
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

    spent = Real("daily_escrow_spent_usd")
    transfer = Real("transfer_amount_usd")
    limit = Real("daily_escrow_limit_usd")
    latency = Real("vendor_latency_ms")
    allowlisted = Bool("iban_allowlisted")

    s.add(spent == RealVal(spent_val))
    s.add(transfer == RealVal(transfer_val))
    s.add(limit == RealVal(limit_val))
    s.add(latency == RealVal(latency_val))
    s.add(allowlisted == BoolVal(allowlisted_val))

    s.assert_and_track(spent + transfer <= limit, "INV_FIN_01_ESCROW_CAP")
    s.assert_and_track(
        Implies(
            transfer > RealVal(0.0),
            And(latency <= RealVal(200.0), allowlisted == BoolVal(True)),
        ),
        "INV_FIN_02_SLA_ATTESTATION",
    )

    remaining_cap = max(0.0, limit_val - spent_val)
    context = {
        "spent": spent_val,
        "limit": limit_val,
        "transfer": transfer_val,
        "vendor_latency_ms": latency_val,
        "iban_allowlisted": allowlisted_val,
        "remaining_cap": remaining_cap,
    }
    return s, context
