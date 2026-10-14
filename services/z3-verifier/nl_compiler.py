"""Natural Language to Z3 formal policy compiler.

Translates plain-English compliance rules or formal logic expressions into
tracked Z3 assertions. Validates expressions via an AST Safety Sandbox, verifies
satisfiability against synthetic passing and failing state vectors, and registers
compiled policies into the active prover loop for immediate enforcement.
"""

from __future__ import annotations

import ast
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from z3 import (
    And,
    Bool,
    BoolVal,
    If,
    Implies,
    Int,
    IntVal,
    Not,
    Or,
    Real,
    RealVal,
    Solver,
    is_true,
    sat,
    unsat,
)

# ---------------------------------------------------------------------------
# Cartridge Schemas, Variables, and Synthetic Test Vectors
# ---------------------------------------------------------------------------

CARTRIDGE_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "HEALTHCARE_FHIR": {
        "variables": {
            "patient_egfr_ml_min": {
                "type": "Real",
                "z3_type": Real,
                "desc": "Patient estimated glomerular filtration rate (mL/min/1.73m2)",
            },
            "prescribed_dose_mg": {
                "type": "Int",
                "z3_type": Int,
                "desc": "Prescribed medication dose in milligrams",
            },
            "prescribed_dose_metformin": {
                "type": "Int",
                "z3_type": Int,
                "desc": "Prescribed metformin dose in milligrams (0 if not Metformin)",
            },
            "claim_submitted": {
                "type": "Bool",
                "z3_type": Bool,
                "desc": "Whether an insurance reimbursement claim is submitted",
            },
            "conservative_therapy_weeks": {
                "type": "Int",
                "z3_type": Int,
                "desc": "Documented prior conservative physical therapy duration in weeks",
            },
        },
        "aliases": {
            "metformin_dose": "prescribed_dose_metformin",
            "dose_mg": "prescribed_dose_mg",
            "egfr": "patient_egfr_ml_min",
            "therapy_weeks": "conservative_therapy_weeks",
        },
        "synthetic_passing_state": {
            "patient_egfr_ml_min": 60.0,
            "prescribed_dose_mg": 500,
            "prescribed_dose_metformin": 0,
            "claim_submitted": False,
            "conservative_therapy_weeks": 6,
        },
        "synthetic_failing_state": {
            "patient_egfr_ml_min": 20.0,
            "prescribed_dose_mg": 2500,
            "prescribed_dose_metformin": 1000,
            "claim_submitted": True,
            "conservative_therapy_weeks": 2,
        },
    },
    "FINTECH_ESCROW": {
        "variables": {
            "daily_escrow_spent_usd": {
                "type": "Real",
                "z3_type": Real,
                "desc": "Cumulative escrow disbursement today in USD",
            },
            "daily_escrow_limit_usd": {
                "type": "Real",
                "z3_type": Real,
                "desc": "Daily escrow disbursement cap in USD",
            },
            "transfer_amount_usd": {
                "type": "Real",
                "z3_type": Real,
                "desc": "Current transaction wire transfer amount in USD",
            },
            "vendor_latency_ms": {
                "type": "Real",
                "z3_type": Real,
                "desc": "zkTLS counterparty SLA latency in milliseconds",
            },
            "iban_allowlisted": {
                "type": "Bool",
                "z3_type": Bool,
                "desc": "Whether counterparty destination IBAN is on treasury allowlist",
            },
        },
        "aliases": {
            "transfer": "transfer_amount_usd",
            "last_transfer_amount_usd": "transfer_amount_usd",
            "spent": "daily_escrow_spent_usd",
            "limit": "daily_escrow_limit_usd",
        },
        "synthetic_passing_state": {
            "daily_escrow_spent_usd": 1000.0,
            "daily_escrow_limit_usd": 50000.0,
            "transfer_amount_usd": 2000.0,
            "vendor_latency_ms": 50.0,
            "iban_allowlisted": True,
        },
        "synthetic_failing_state": {
            "daily_escrow_spent_usd": 48000.0,
            "daily_escrow_limit_usd": 50000.0,
            "transfer_amount_usd": 12000.0,
            "vendor_latency_ms": 350.0,
            "iban_allowlisted": False,
        },
    },
    "CLOUD_DEVOPS": {
        "variables": {
            "prod_table_row_count_pre": {
                "type": "Int",
                "z3_type": Int,
                "desc": "Production table row count prior to schema migration",
            },
            "prod_table_row_count_post": {
                "type": "Int",
                "z3_type": Int,
                "desc": "Production table row count after schema migration",
            },
            "cidr_open_world": {
                "type": "Bool",
                "z3_type": Bool,
                "desc": "Whether security group CIDR allows world ingress (0.0.0.0/0)",
            },
            "port_number": {
                "type": "Int",
                "z3_type": Int,
                "desc": "Target network port number (e.g. 22 for SSH, 3389 for RDP)",
            },
        },
        "aliases": {
            "rows_pre": "prod_table_row_count_pre",
            "rows_post": "prod_table_row_count_post",
        },
        "synthetic_passing_state": {
            "prod_table_row_count_pre": 10000,
            "prod_table_row_count_post": 10000,
            "cidr_open_world": False,
            "port_number": 443,
        },
        "synthetic_failing_state": {
            "prod_table_row_count_pre": 10000,
            "prod_table_row_count_post": 8500,
            "cidr_open_world": True,
            "port_number": 22,
        },
    },
}

# Contract 3 rule_id pattern (contracts/z3_verdict.schema.json): compiled rules surface there.
RULE_ID_PATTERN = re.compile(r"^INV_[A-Z]+_[0-9]{2}_[A-Z0-9_]+$")

# Active dynamic rules registry keyed by cartridge_id
DYNAMIC_RULES: Dict[str, List[Dict[str, Any]]] = {
    "HEALTHCARE_FHIR": [],
    "FINTECH_ESCROW": [],
    "CLOUD_DEVOPS": [],
}

# Backward compatibility alias
DYNAMIC_POLICY_REGISTRY = DYNAMIC_RULES


# ---------------------------------------------------------------------------
# Exceptions & AST Safety Sandbox
# ---------------------------------------------------------------------------

class ASTSafetyViolation(ValueError):
    """Raised when an expression contains unauthorized AST nodes, calls, or attribute access."""
    pass


class PolicyCompilationError(ValueError):
    """Raised when a natural language rule cannot be compiled or verified."""
    pass


ALLOWED_Z3_FUNCTIONS: Set[str] = {
    "Implies",
    "And",
    "Or",
    "Not",
    "RealVal",
    "IntVal",
    "BoolVal",
    "If",
}

FORBIDDEN_AST_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Attribute,
    ast.Subscript,
    ast.Lambda,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.Yield,
    ast.YieldFrom,
    ast.Await,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Delete,
    ast.Assign,
    ast.AugAssign,
    ast.AnnAssign,
    ast.With,
    ast.AsyncWith,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.NamedExpr,
    ast.Starred,
    ast.Slice,
)


def validate_ast_safety(expr_str: str, cartridge_id: str) -> ast.AST:
    """Parse expression and enforce strict AST safety sandboxing:
    - Reject all imports (ast.Import, ast.ImportFrom)
    - Reject all attribute access (ast.Attribute)
    - Reject calls outside allowed Z3 primitives (Implies, And, Or, Not, RealVal, IntVal, BoolVal, If)
    - Reject any variable name not defined in the cartridge schema or aliases
    - Reject complex Python statements, assignments, indexing, or comprehensions
    """
    if not expr_str or not expr_str.strip():
        raise ASTSafetyViolation("Policy expression string cannot be empty.")

    schema = CARTRIDGE_SCHEMAS.get(cartridge_id)
    if not schema:
        raise ValueError(f"Unknown cartridge_id: '{cartridge_id}'")

    allowed_vars = set(schema["variables"].keys()) | set(schema.get("aliases", {}).keys())
    allowed_names = allowed_vars | ALLOWED_Z3_FUNCTIONS | {"True", "False"}

    try:
        tree = ast.parse(expr_str.strip(), mode="eval")
    except SyntaxError as e:
        raise ASTSafetyViolation(f"Syntax error in policy expression: {str(e)}") from e

    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_AST_NODES):
            raise ASTSafetyViolation(
                f"Forbidden AST node '{type(node).__name__}' detected in expression. "
                "Only pure Z3 relational and logical operations are permitted."
            )

        if isinstance(node, ast.Attribute):
            raise ASTSafetyViolation(
                f"Attribute access is forbidden in Z3 policy expressions: '{ast.dump(node)}'."
            )

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ASTSafetyViolation(
                    f"Complex function invocation is forbidden: '{ast.dump(node.func)}'."
                )
            if node.func.id not in ALLOWED_Z3_FUNCTIONS:
                raise ASTSafetyViolation(
                    f"Function call '{node.func.id}' is not in allowed Z3 primitives: "
                    f"{sorted(ALLOWED_Z3_FUNCTIONS)}."
                )

        if isinstance(node, ast.Name):
            if node.id not in allowed_names:
                raise ASTSafetyViolation(
                    f"Identifier '{node.id}' is not an authorized variable for cartridge '{cartridge_id}'. "
                    f"Allowed variables: {sorted(allowed_vars)}."
                )

        if isinstance(node, ast.Compare):
            for op in node.ops:
                if not isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)):
                    raise ASTSafetyViolation(f"Forbidden comparison operator: '{type(op).__name__}'.")

        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                raise ASTSafetyViolation(f"Forbidden binary operator: '{type(node.op).__name__}'.")

        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, (ast.USub, ast.UAdd, ast.Not)):
                raise ASTSafetyViolation(f"Forbidden unary operator: '{type(node.op).__name__}'.")

    return tree


def build_evaluation_scope(cartridge_id: str) -> Dict[str, Any]:
    """Construct safe evaluation scope containing Z3 constructors and typed cartridge variables."""
    schema = CARTRIDGE_SCHEMAS[cartridge_id]
    scope: Dict[str, Any] = {
        "Implies": Implies,
        "And": And,
        "Or": Or,
        "Not": Not,
        "RealVal": RealVal,
        "IntVal": IntVal,
        "BoolVal": BoolVal,
        "If": If,
        "True": True,
        "False": False,
    }
    for var_name, var_info in schema["variables"].items():
        scope[var_name] = var_info["z3_type"](var_name)
    for alias_name, target_name in schema.get("aliases", {}).items():
        scope[alias_name] = scope[target_name]
    return scope


def check_state_satisfies(
    cartridge_id: str,
    rule_id: str,
    state: Dict[str, Any],
    code_obj: Any,
) -> bool:
    """Evaluate whether a concrete state satisfies the compiled Z3 invariant."""
    schema = CARTRIDGE_SCHEMAS[cartridge_id]
    s = Solver()
    s.set("timeout", 50)
    scope = build_evaluation_scope(cartridge_id)

    for var_name, var_info in schema["variables"].items():
        if var_name in state:
            val = state[var_name]
            z_var = scope[var_name]
            if var_info["type"] == "Real":
                s.add(z_var == RealVal(float(val)))
            elif var_info["type"] == "Int":
                s.add(z_var == IntVal(int(val)))
            elif var_info["type"] == "Bool":
                s.add(z_var == BoolVal(bool(val)))

    expr = eval(code_obj, {"__builtins__": {}}, scope)
    s.assert_and_track(expr, rule_id)
    return s.check() == sat


def evaluate_synthetic_vectors(
    cartridge_id: str,
    rule_id: str,
    code_obj: Any,
    formal_str: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Verify satisfiability of the compiled rule against synthetic passing and failing state vectors."""
    schema = CARTRIDGE_SCHEMAS[cartridge_id]
    scope = build_evaluation_scope(cartridge_id)
    z3_expr = eval(code_obj, {"__builtins__": {}}, scope)

    # 1. Mathematical satisfiability check (reject contradictions)
    s_sat = Solver()
    s_sat.set("timeout", 50)
    s_sat.add(z3_expr)
    if s_sat.check() == unsat:
        raise PolicyCompilationError(
            f"Rule '{rule_id}' is inherently unsatisfiable (logical contradiction): {formal_str}"
        )
    sat_model = s_sat.model()

    # 2. Mathematical violation check (reject tautologies)
    s_unsat = Solver()
    s_unsat.set("timeout", 50)
    s_unsat.add(Not(z3_expr))
    if s_unsat.check() == unsat:
        raise PolicyCompilationError(
            f"Rule '{rule_id}' is a tautology (cannot be violated): {formal_str}"
        )
    unsat_model = s_unsat.model()

    # 3. Passing state evaluation
    passing_state = schema["synthetic_passing_state"].copy()
    if not check_state_satisfies(cartridge_id, rule_id, passing_state, code_obj):
        # Update passing state with model values to satisfy rule
        for d in sat_model.decls():
            name = d.name()
            if name in schema["variables"]:
                val = sat_model[d]
                v_type = schema["variables"][name]["type"]
                if v_type == "Real":
                    try:
                        passing_state[name] = float(val.as_decimal(4).replace("?", ""))
                    except Exception:
                        passing_state[name] = float(str(val))
                elif v_type == "Int":
                    passing_state[name] = val.as_long()
                elif v_type == "Bool":
                    passing_state[name] = is_true(val)

        if not check_state_satisfies(cartridge_id, rule_id, passing_state, code_obj):
            raise PolicyCompilationError(
                f"Failed to find a valid passing state for rule '{rule_id}': {formal_str}"
            )

    # 4. Failing state evaluation
    failing_state = schema["synthetic_failing_state"].copy()
    if check_state_satisfies(cartridge_id, rule_id, failing_state, code_obj):
        # Update failing state with model values that violate rule
        for d in unsat_model.decls():
            name = d.name()
            if name in schema["variables"]:
                val = unsat_model[d]
                v_type = schema["variables"][name]["type"]
                if v_type == "Real":
                    try:
                        failing_state[name] = float(val.as_decimal(4).replace("?", ""))
                    except Exception:
                        failing_state[name] = float(str(val))
                elif v_type == "Int":
                    failing_state[name] = val.as_long()
                elif v_type == "Bool":
                    failing_state[name] = is_true(val)

        if check_state_satisfies(cartridge_id, rule_id, failing_state, code_obj):
            raise PolicyCompilationError(
                f"Failed to find a valid failing state for rule '{rule_id}': {formal_str}"
            )

    return passing_state, failing_state


def make_rule_builder(
    cartridge_id: str,
    rule_id: str,
    code_obj: Any,
) -> Callable[[Solver, Dict[str, Any], Dict[str, Any], Dict[str, Any]], None]:
    """Construct solver builder function for prover_core.py execution loop."""
    schema = CARTRIDGE_SCHEMAS[cartridge_id]

    def builder(s: Solver, state_pre: Dict[str, Any], state_post: Dict[str, Any], ctx: Dict[str, Any]) -> None:
        merged = {**state_pre, **state_post}
        scope = build_evaluation_scope(cartridge_id)

        for var_name, var_info in schema["variables"].items():
            z_var = scope[var_name]
            val = None
            # Prefer the value the cartridge's static solver already bound (ctx): the dynamic rule
            # shares that solver, and a second, different binding for the same variable (e.g.
            # post-transfer daily_escrow_spent_usd vs the pre-transfer value) makes every check
            # unsat with an empty core, which silently disabled compiled rules on real kernel diffs.
            if var_name in ctx:
                val = ctx[var_name]
            elif var_name in state_post:
                val = state_post[var_name]
            elif var_name in state_pre:
                val = state_pre[var_name]
            elif var_name in merged:
                val = merged[var_name]
            else:
                for alias_name, target in schema.get("aliases", {}).items():
                    if target == var_name and alias_name in merged:
                        val = merged[alias_name]
                        break

            # Handle healthcare metformin dose fallback
            if var_name == "prescribed_dose_metformin" and val is None:
                if state_post.get("prescribed_drug") == "Metformin":
                    val = state_post.get("prescribed_dose_mg", 0)
                else:
                    val = 0

            # Default fallback if missing
            if val is None:
                val = schema["synthetic_passing_state"].get(var_name, 0)

            if var_info["type"] == "Real":
                s.add(z_var == RealVal(float(val)))
                ctx[var_name] = float(val)
            elif var_info["type"] == "Int":
                s.add(z_var == IntVal(int(val)))
                ctx[var_name] = int(val)
            elif var_info["type"] == "Bool":
                s.add(z_var == BoolVal(bool(val)))
                ctx[var_name] = bool(val)

        expr = eval(code_obj, {"__builtins__": {}}, scope)
        s.assert_and_track(expr, rule_id)

    return builder


# ---------------------------------------------------------------------------
# LLM Prompting & Deterministic Synthesis Engine
# ---------------------------------------------------------------------------

def format_llm_prompt(cartridge_id: str, natural_language_rule: str) -> str:
    """Format LLM prompt providing exact schema variables and allowed Z3 primitives."""
    schema = CARTRIDGE_SCHEMAS[cartridge_id]
    var_lines = [
        f"  - {v_name} ({v_info['type']}): {v_info['desc']}"
        for v_name, v_info in schema["variables"].items()
    ]
    vars_desc = "\n".join(var_lines)
    return (
        f"You are the formal logic compiler for CHRONOS-ZERO.\n"
        f"Translate the following natural language compliance policy into a pure Python Z3 constraint expression.\n\n"
        f"Cartridge: {cartridge_id}\n"
        f"Available Variables for this Cartridge:\n{vars_desc}\n\n"
        f"Allowed Z3 Primitives:\n"
        f"  - Logical: Implies, And, Or, Not\n"
        f"  - Comparisons: <, <=, >, >=, ==\n"
        f"  - Booleans: True, False\n"
        f"  - Numeric literals (integers and floats)\n\n"
        f"Requirements:\n"
        f"  1. Emit ONLY the single line Python Z3 boolean expression.\n"
        f"  2. Do NOT include markdown code blocks, imports, or explanations.\n"
        f"  3. Use only the exact variable names provided above.\n\n"
        f"Natural Language Policy:\n"
        f"\"{natural_language_rule}\"\n\n"
        f"Z3 Expression:"
    )


def _call_llm_api(prompt: str) -> Optional[str]:
    """Invoke external LLM with 1500ms timeout per AGENTS.md Section 4.3."""
    if os.environ.get("OFFLINE_MODE") == "1":
        return None

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            import httpx
            headers = {
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            body = {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 128,
                "messages": [{"role": "user", "content": prompt}],
            }
            with httpx.Client(timeout=1.5) as client:
                res = client.post("https://api.anthropic.com/v1/messages", json=body, headers=headers)
                if res.status_code == 200:
                    text = res.json()["content"][0]["text"].strip()
                    text = re.sub(r"^```(?:python)?\s*", "", text)
                    text = re.sub(r"\s*```$", "", text).strip()
                    return text
        except Exception:
            pass

    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            import httpx
            headers = {
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            }
            body = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 128,
                "temperature": 0.0,
            }
            with httpx.Client(timeout=1.5) as client:
                res = client.post("https://api.openai.com/v1/chat/completions", json=body, headers=headers)
                if res.status_code == 200:
                    text = res.json()["choices"][0]["message"]["content"].strip()
                    text = re.sub(r"^```(?:python)?\s*", "", text)
                    text = re.sub(r"\s*```$", "", text).strip()
                    return text
        except Exception:
            pass

    return None


def _synthesize_pattern_expression(cartridge_id: str, text: str) -> str:
    """Deterministic pattern-based Z3 rule synthesizer for zero-Wi-Fi and offline demo mode."""
    lower = text.lower()

    # 1. Fintech wire + SLA / allowlist conditional
    m_sla = re.search(
        r"(?:block|prevent|disallow).*wire.*(?:exceeding|over|>)\s*\$?([0-9,]+(?:\.[0-9]+)?).*unless\s+(.*)",
        lower,
    )
    if m_sla and cartridge_id == "FINTECH_ESCROW":
        amt = float(m_sla.group(1).replace(",", ""))
        cond = m_sla.group(2)
        has_latency = "latency" in cond
        has_iban = "iban" in cond or "allowlist" in cond
        if has_latency and has_iban:
            lat_m = re.search(r"([0-9]+(?:\.[0-9]+)?)", cond)
            lat = float(lat_m.group(1)) if lat_m else 200.0
            return f"Implies(transfer_amount_usd > {amt}, And(vendor_latency_ms <= {lat}, iban_allowlisted == True))"
        elif has_iban:
            return f"Implies(transfer_amount_usd > {amt}, iban_allowlisted == True)"
        elif has_latency:
            lat_m = re.search(r"([0-9]+(?:\.[0-9]+)?)", cond)
            lat = float(lat_m.group(1)) if lat_m else 200.0
            return f"Implies(transfer_amount_usd > {amt}, vendor_latency_ms <= {lat})"

    # 1b. Fintech vendor SLA latency bound ("Only pay vendors whose SLA latency is under 100 ms")
    if cartridge_id == "FINTECH_ESCROW" and "latency" in lower:
        m_lat = re.search(
            r"(under|below|less than|<=|<|at most|no more than|within|over|above|exceeding|exceeds|exceed|>)"
            r"\s*([0-9]+(?:\.[0-9]+)?)\s*ms",
            lower,
        )
        if m_lat:
            op = "<" if m_lat.group(1) in ("under", "below", "less than", "<") else "<="
            return f"Implies(transfer_amount_usd > 0, vendor_latency_ms {op} {float(m_lat.group(2))})"

    # 2. Fintech wire cap
    if cartridge_id == "FINTECH_ESCROW" and ("wire" in lower or "transfer" in lower):
        m_amt = re.search(r"(?:exceeding|over|>|above|limit|cap|to)\s*\$?([0-9,]+(?:\.[0-9]+)?)", lower)
        if not m_amt:
            m_amt = re.search(r"\$([0-9,]+(?:\.[0-9]+)?)", lower)
        if m_amt:
            amt = float(m_amt.group(1).replace(",", ""))
            return f"transfer_amount_usd <= {amt}"

    # 3. Fintech daily escrow cap
    if cartridge_id == "FINTECH_ESCROW" and ("daily" in lower or "spent" in lower or "limit" in lower):
        return "daily_escrow_spent_usd + transfer_amount_usd <= daily_escrow_limit_usd"

    # 4. Healthcare eGFR & metformin
    if cartridge_id == "HEALTHCARE_FHIR" and "egfr" in lower and ("metformin" in lower or "dose" in lower):
        m_egfr = re.search(r"(?:below|<|less than)\s*([0-9]+(?:\.[0-9]+)?)", lower)
        threshold = float(m_egfr.group(1)) if m_egfr else 30.0
        return f"Implies(patient_egfr_ml_min < {threshold}, prescribed_dose_metformin == 0)"

    # 5. Healthcare dose limit
    if cartridge_id == "HEALTHCARE_FHIR" and "dose" in lower:
        m_dose = re.search(r"([0-9]+)\s*(?:mg)?", lower)
        dose = int(m_dose.group(1)) if m_dose else 2000
        return f"prescribed_dose_mg <= {dose}"

    # 6. Healthcare payer auth
    if cartridge_id == "HEALTHCARE_FHIR" and ("claim" in lower or "therapy" in lower or "prior" in lower):
        m_w = re.search(r"([0-9]+)\s*(?:weeks)?", lower)
        w = int(m_w.group(1)) if m_w else 6
        return f"Implies(claim_submitted == True, conservative_therapy_weeks >= {w})"

    # 7. Cloud DevOps zero data loss
    if cartridge_id == "CLOUD_DEVOPS" and any(
        k in lower for k in ("zero data loss", "row", "loss", "drop", "truncate", "delete", "destructive")
    ):
        return "prod_table_row_count_post >= prod_table_row_count_pre"

    # 8. Cloud DevOps admin port
    if cartridge_id == "CLOUD_DEVOPS" and ("ssh" in lower or "admin" in lower or "port" in lower or "cidr" in lower):
        m_p = re.search(r"port\s*([0-9]+)", lower)
        port = int(m_p.group(1)) if m_p else 22
        return f"Not(And(cidr_open_world == True, port_number == {port}))"

    return text


def _generate_z3_expression(cartridge_id: str, nl_text: str) -> str:
    """Generate pure Python Z3 constraint expression using direct parsing, LLM, or deterministic synthesis."""
    cleaned = nl_text.strip()

    # 1. Direct pass-through if already valid Z3 expression
    try:
        validate_ast_safety(cleaned, cartridge_id)
        return cleaned
    except Exception:
        pass

    # 2. External LLM translation if configured
    prompt = format_llm_prompt(cartridge_id, cleaned)
    llm_resp = _call_llm_api(prompt)
    if llm_resp:
        try:
            validate_ast_safety(llm_resp, cartridge_id)
            return llm_resp
        except Exception:
            pass

    # 3. Deterministic pattern synthesis
    synthesized = _synthesize_pattern_expression(cartridge_id, cleaned)
    validate_ast_safety(synthesized, cartridge_id)
    return synthesized


def generate_remediation_hint(cartridge_id: str, rule_id: str, formal_str: str, nl_text: str) -> str:
    """Generate human- and LLM-actionable remediation instructions for unsat verdicts."""
    lower = nl_text.lower()
    if cartridge_id == "FINTECH_ESCROW":
        m_amt = re.search(r"\$?([0-9,]+(?:\.[0-9]+)?)", nl_text)
        amt_str = m_amt.group(1) if m_amt else "limit"
        if "unless" in lower:
            return (
                f"Transfer amount exceeds ${amt_str} threshold without required counterparty SLA and allowlisted IBAN. "
                "Route wire to verified backup counterparty meeting SLA requirements."
            )
        return (
            f"Transfer amount exceeds dynamic policy limit of ${amt_str}. "
            f"Reduce transfer amount to <= ${amt_str} USD."
        )
    elif cartridge_id == "HEALTHCARE_FHIR":
        if "metformin" in lower or "egfr" in lower:
            return (
                "Patient renal function contraindicates metformin dosing according to dynamic safety policy. "
                "Discontinue metformin or select renal-safe alternative."
            )
        if "dose" in lower:
            return "Prescribed dose exceeds maximum daily threshold allowed by dynamic policy."
        return f"Healthcare dynamic policy '{rule_id}' violated: {formal_str}."
    elif cartridge_id == "CLOUD_DEVOPS":
        if "row" in lower or "data" in lower:
            return "Dynamic zero-data-loss policy violated: post-migration row count is less than pre-migration count."
        if "port" in lower or "ssh" in lower or "cidr" in lower:
            return "Security policy violated: world ingress (0.0.0.0/0) on sensitive port is forbidden."
        return f"DevOps dynamic policy '{rule_id}' violated: {formal_str}."
    return f"Dynamic compliance policy '{rule_id}' violated: {formal_str}."


# ---------------------------------------------------------------------------
# Public Compiler Interface
# ---------------------------------------------------------------------------

def compile_nl_policy(
    cartridge_id: str,
    rule_id: str,
    natural_language_rule: str,
) -> Dict[str, Any]:
    """Compile natural-language rule into a tracked Z3 assertion, validate AST, test synthetic vectors, and register."""
    t0 = time.perf_counter_ns()
    text = natural_language_rule.strip()

    if not RULE_ID_PATTERN.match(rule_id):
        raise ValueError(
            f"rule_id '{rule_id}' must match the Contract 3 pattern {RULE_ID_PATTERN.pattern}"
        )
    if cartridge_id not in CARTRIDGE_SCHEMAS:
        raise ValueError(
            f"Invalid cartridge_id '{cartridge_id}'. Must be one of: {list(CARTRIDGE_SCHEMAS.keys())}"
        )

    # 1. Generate Python Z3 constraint expression
    z3_expr_str = _generate_z3_expression(cartridge_id, text)

    # 2. AST Safety Sandbox Validation
    tree = validate_ast_safety(z3_expr_str, cartridge_id)
    code_obj = compile(tree, filename=f"<z3_policy_{rule_id}>", mode="eval")

    # 3. Evaluate against synthetic passing and failing state vectors
    passing_state, failing_state = evaluate_synthetic_vectors(
        cartridge_id=cartridge_id,
        rule_id=rule_id,
        code_obj=code_obj,
        formal_str=z3_expr_str,
    )

    # 4. Generate SMT-LIB2 representation
    sandbox_solver = Solver()
    sandbox_solver.set("timeout", 50)
    builder_fn = make_rule_builder(cartridge_id, rule_id, code_obj)
    sandbox_solver.push()
    builder_fn(sandbox_solver, {}, passing_state, {})
    sandbox_solver.check()
    smt2_dump = sandbox_solver.to_smt2()
    sandbox_solver.pop()

    # 5. Measure latency
    elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
    latency_ms = round(elapsed_ms, 3)

    remediation_hint = generate_remediation_hint(cartridge_id, rule_id, z3_expr_str, text)

    # 6. Register into DYNAMIC_RULES[cartridge_id]
    compiled_entry = {
        "rule_id": rule_id,
        "natural_language_rule": text,
        "formal_assertion": z3_expr_str,
        "compiled_code": z3_expr_str,
        "z3_code": z3_expr_str,
        "remediation_hint": remediation_hint,
        "builder": builder_fn,
        "smt2_dump": smt2_dump,
        "smt2_template": smt2_dump,
        "compilation_latency_ms": latency_ms,
        "latency_ms": latency_ms,
        "synthetic_passing_state": passing_state,
        "synthetic_failing_state": failing_state,
    }

    if cartridge_id not in DYNAMIC_RULES:
        DYNAMIC_RULES[cartridge_id] = []

    existing_idx = next(
        (i for i, r in enumerate(DYNAMIC_RULES[cartridge_id]) if r["rule_id"] == rule_id),
        None,
    )
    if existing_idx is not None:
        DYNAMIC_RULES[cartridge_id][existing_idx] = compiled_entry
    else:
        DYNAMIC_RULES[cartridge_id].append(compiled_entry)

    return {
        "status": "COMPILED",
        "cartridge_id": cartridge_id,
        "rule_id": rule_id,
        "formal_assertion": z3_expr_str,
        "compiled_code": z3_expr_str,
        "z3_code": z3_expr_str,
        "smt2_dump": smt2_dump,
        "smt2_template": smt2_dump,
        "compilation_latency_ms": latency_ms,
        "latency_ms": latency_ms,
        "synthetic_passing_state": passing_state,
        "synthetic_failing_state": failing_state,
        "remediation_hint": remediation_hint,
        "message": f"Policy '{rule_id}' compiled and loaded into {cartridge_id} active registry.",
    }


def compile_nl_rule(cartridge_id: str, rule_id: str, nl_text: str) -> Dict[str, Any]:
    """Backward compatibility alias for compile_nl_policy."""
    return compile_nl_policy(cartridge_id, rule_id, nl_text)


def get_dynamic_rules(cartridge_id: str) -> List[Dict[str, Any]]:
    """Return all compiled dynamic rules for a cartridge."""
    return DYNAMIC_RULES.get(cartridge_id, [])


def clear_dynamic_rules(cartridge_id: Optional[str] = None) -> None:
    """Clear dynamic rules for a specific cartridge or all cartridges."""
    if cartridge_id:
        if cartridge_id in DYNAMIC_RULES:
            DYNAMIC_RULES[cartridge_id].clear()
    else:
        for cat in DYNAMIC_RULES:
            DYNAMIC_RULES[cat].clear()
