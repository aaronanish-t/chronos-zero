"""Formal invariants for CLOUD_DEVOPS cartridge.

Enforces:
- INV_OPS_01_ZERO_DATA_LOSS: Production table row count must not decrease across migrations.
- INV_OPS_02_NO_PUBLIC_ADMIN_PORT: Administrative port 22 cannot be exposed to 0.0.0.0/0.
"""

from typing import Any, Tuple
from z3 import And, Bool, BoolVal, Int, IntVal, Not, Solver

SOLVER_TIMEOUT_MS = 50

RULE_REGISTRY = {
    "INV_OPS_01_ZERO_DATA_LOSS": {
        "formal": "prod_table_row_count_post >= prod_table_row_count_pre",
        "remediation": (
            "Destructive migration detected. Production row count decreased from "
            "{rows_pre} to {rows_post} (delta = {delta}). "
            "Use non-destructive ALTER TABLE ADD COLUMN instead of DROP TABLE."
        ),
    },
    "INV_OPS_02_NO_PUBLIC_ADMIN_PORT": {
        "formal": "Not(And(cidr_open_world == True, port_number == 22))",
        "remediation": (
            "Public administrative port exposure detected: Port 22 is open to 0.0.0.0/0 "
            "(cidr_open_world == True). Restrict ingress CIDR to internal VPN bastion."
        ),
    },
}


def build_devops_solver(state_pre: dict[str, Any], state_post: dict[str, Any]) -> Tuple[Solver, dict[str, Any]]:
    """Build Z3 solver with tracked invariants for CLOUD_DEVOPS."""
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

    rows_pre = Int("prod_table_row_count_pre")
    rows_post = Int("prod_table_row_count_post")
    cidr_open = Bool("cidr_open_world")
    port = Int("port_number")

    s.add(rows_pre == IntVal(rows_pre_val))
    s.add(rows_post == IntVal(rows_post_val))
    s.add(cidr_open == BoolVal(cidr_open_val))
    s.add(port == IntVal(port_val))

    s.assert_and_track(rows_post >= rows_pre, "INV_OPS_01_ZERO_DATA_LOSS")
    s.assert_and_track(
        Not(And(cidr_open == BoolVal(True), port == IntVal(22))),
        "INV_OPS_02_NO_PUBLIC_ADMIN_PORT",
    )

    delta = rows_post_val - rows_pre_val
    context = {
        "rows_pre": rows_pre_val,
        "rows_post": rows_post_val,
        "delta": delta,
        "cidr_open_world": cidr_open_val,
        "port_number": port_val,
    }
    return s, context
