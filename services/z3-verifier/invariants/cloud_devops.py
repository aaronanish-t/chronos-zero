"""Formal invariants for CLOUD_DEVOPS cartridge.

Enforces:
- INV_OPS_01_ZERO_DATA_LOSS: Production table row count must not decrease across migrations.
- INV_OPS_02_NO_PUBLIC_ADMIN_PORT: Administrative port 22 cannot be exposed to 0.0.0.0/0.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Tuple
from z3 import And, Bool, BoolVal, Int, IntVal, Not, Solver, unknown, unsat

SOLVER_TIMEOUT_MS = 50

RULE_REGISTRY: Dict[str, Dict[str, str]] = {
    "INV_OPS_01_ZERO_DATA_LOSS": {
        "formal": "prod_table_row_count_post >= prod_table_row_count_pre",
        "remediation": (
            "Destructive migration detected. Production row count decreased from "
            "{rows_pre} to {rows_post} (delta: {delta} rows). "
            "Use non-destructive ALTER TABLE ADD COLUMN instead of DROP TABLE."
        ),
    },
    "INV_OPS_02_NO_PUBLIC_ADMIN_PORT": {
        "formal": "Not(And(cidr_open_world == True, port_number == 22))",
        "remediation": (
            "Public administrative port exposure detected: Port {port_number} is open to 0.0.0.0/0 "
            "(cidr_open_world={cidr_open_world}). Restrict ingress CIDR to internal corporate VPN bastion."
        ),
    },
}


def build_devops_solver(
    state_pre: Dict[str, Any], state_post: Dict[str, Any]
) -> Tuple[Solver, Dict[str, Any], List[Tuple[str, Any]]]:
    """Build Z3 solver instance with tracked invariants for CLOUD_DEVOPS."""
    s = Solver()
    s.set("timeout", SOLVER_TIMEOUT_MS)

    rows_pre_raw = state_pre.get("prod_table_row_count_pre")
    if rows_pre_raw is None:
        rows_pre_raw = state_pre.get("prod_table_row_count", state_pre.get("row_count", 15420))
    rows_pre_val = int(rows_pre_raw)

    rows_post_raw = state_post.get("prod_table_row_count_post")
    if rows_post_raw is None:
        rows_post_raw = state_post.get("prod_table_row_count", state_post.get("row_count", 0))
    rows_post_val = int(rows_post_raw)

    cidr_raw = state_post.get("cidr_open_world")
    if cidr_raw is None:
        cidr_str = str(state_post.get("cidr", state_post.get("ingress_cidr", "")))
        cidr_raw = cidr_str == "0.0.0.0/0"
    cidr_open_val = bool(cidr_raw)

    port_raw = state_post.get("port_number", state_post.get("port", 0))
    port_val = int(port_raw)

    # Declare typed Z3 variables
    rows_pre = Int("prod_table_row_count_pre")
    rows_post = Int("prod_table_row_count_post")
    cidr_open = Bool("cidr_open_world")
    port = Int("port_number")

    # Cast and add exact value bindings
    s.add(rows_pre == IntVal(rows_pre_val))
    s.add(rows_post == IntVal(rows_post_val))
    s.add(cidr_open == BoolVal(cidr_open_val))
    s.add(port == IntVal(port_val))

    # Tracked assertions
    tracked_rules = [
        ("INV_OPS_01_ZERO_DATA_LOSS", rows_post >= rows_pre),
        (
            "INV_OPS_02_NO_PUBLIC_ADMIN_PORT",
            Not(And(cidr_open == BoolVal(True), port == IntVal(22))),
        ),
    ]

    delta = rows_post_val - rows_pre_val
    context = {
        "rows_pre": rows_pre_val,
        "prod_table_row_count_pre": rows_pre_val,
        "rows_post": rows_post_val,
        "prod_table_row_count_post": rows_post_val,
        "delta": delta,
        "cidr_open_world": cidr_open_val,
        "port_number": port_val,
    }
    return s, context, tracked_rules


def evaluate_cloud_devops_invariants(
    state_pre: Dict[str, Any], state_post: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute formal verification against CLOUD_DEVOPS invariants.

    Identifies ALL broken rules when multiple invariants fail simultaneously.
    """
    t0 = time.perf_counter_ns()
    violated: List[Dict[str, str]] = []
    smt2_str = ""

    try:
        s, context, tracked_rules = build_devops_solver(state_pre, state_post)

        failed_ids = []
        for r_id, expr in tracked_rules:
            s.push()
            s.assert_and_track(expr, r_id)
            result = s.check()
            if result == unsat:
                failed_ids.extend([str(c) for c in s.unsat_core()] or [r_id])
            elif result == unknown:  # 50 ms timeout: fail closed
                failed_ids.append(r_id)
            s.pop()

        # Add all rules for SMT2 dump
        for r_id, expr in tracked_rules:
            s.assert_and_track(expr, r_id)
        smt2_str = s.to_smt2()

        if failed_ids:
            status = "UNSAT"
            for r_id in sorted(list(set(failed_ids))):
                meta = RULE_REGISTRY.get(r_id, {"formal": r_id, "remediation": f"{r_id} violated."})
                if r_id == "INV_OPS_01_ZERO_DATA_LOSS":
                    cex = (
                        f"prod_table_row_count_pre={context['rows_pre']}, "
                        f"prod_table_row_count_post={context['rows_post']}, "
                        f"delta={context['delta']}"
                    )
                elif r_id == "INV_OPS_02_NO_PUBLIC_ADMIN_PORT":
                    cex = (
                        f"cidr_open_world={context['cidr_open_world']}, "
                        f"port_number={context['port_number']}"
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
        fail_closed_solver = Solver()
        fail_closed_solver.set("timeout", SOLVER_TIMEOUT_MS)
        fail_closed_solver.assert_and_track(BoolVal(False), "INV_SYS_00_MALFORMED_STATE")
        smt2_str = fail_closed_solver.to_smt2()
        violated.append({
            "rule_id": "INV_SYS_00_MALFORMED_STATE",
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
