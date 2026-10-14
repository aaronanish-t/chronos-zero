"""Contract parity (AGENTS.md section 3), run by `make test-contracts`.

Every contract is defined three times: JSON Schema (contracts/*.schema.json), Pydantic
(contracts/schemas.py) and TypeScript (services/multiverse-ui/src/types/contracts.ts).
These tests fail on any key or enum drift between them, and validate real verifier
output against the JSON Schema (patterns included, which Pydantic does not enforce).
"""

import re
import typing
from pathlib import Path

import pytest
from pydantic import BaseModel

from contracts import schemas
from contract_validator import assert_valid, load_schema

ROOT = Path(__file__).resolve().parents[1]
TS_SOURCE = (ROOT / "services" / "multiverse-ui" / "src" / "types" / "contracts.ts").read_text(encoding="utf-8")

CONTRACT_MODELS = {
    "intercept_payload.schema.json": schemas.InterceptRequest,
    "state_diff.schema.json": schemas.StateDiffRequest,
    "z3_verdict.schema.json": schemas.Z3VerdictResponse,
    "ws_telemetry.schema.json": schemas.TelemetryEvent,
}

# TS interface that mirrors each JSON Schema object (path inside the schema -> interface name).
TS_INTERFACES = {
    ("intercept_payload.schema.json", ()): "InterceptPayload",
    ("intercept_payload.schema.json", ("tool_call",)): "ToolCall",
    ("state_diff.schema.json", ()): "StateDiffPayload",
    ("z3_verdict.schema.json", ()): "Z3VerdictPayload",
    ("z3_verdict.schema.json", ("violated_invariants", "[]")): "ViolatedInvariant",
    ("ws_telemetry.schema.json", ()): "TelemetryEvent",
    ("ws_telemetry.schema.json", ("node",)): "TelemetryNodePayload",
}

# TS union type that mirrors each JSON Schema enum.
TS_UNIONS = {
    ("intercept_payload.schema.json", ("cartridge_id",)): "CartridgeId",
    ("intercept_payload.schema.json", ("chronos_mode",)): "ChronosMode",
    ("z3_verdict.schema.json", ("status",)): "Z3Status",
    ("ws_telemetry.schema.json", ("event_type",)): "TelemetryEventType",
    ("ws_telemetry.schema.json", ("node", "branch_type")): "BranchType",
    ("ws_telemetry.schema.json", ("node", "z3_verdict")): "NodeZ3Verdict",
}


def _sub(schema: dict, path: tuple) -> dict:
    for step in path:
        schema = schema["items"] if step == "[]" else schema["properties"][step]
    return schema


def _ts_union(name: str) -> set[str]:
    m = re.search(rf"export type {name}\s*=\s*([^;]+);", TS_SOURCE)
    assert m, f"type {name} not found in contracts.ts"
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def _ts_fields(name: str) -> dict[str, bool]:
    """Interface field -> required (no '?')."""
    m = re.search(rf"export interface {name}\s*\{{(.*?)\n\}}", TS_SOURCE, re.S)
    assert m, f"interface {name} not found in contracts.ts"
    fields = {}
    for line in m.group(1).splitlines():
        f = re.match(r"\s*([a-z_][a-z0-9_]*)(\?)?\s*:", line)
        if f:
            fields[f.group(1)] = f.group(2) is None
    return fields


def _model_for(model: type[BaseModel], path: tuple) -> type[BaseModel]:
    for step in path:
        if step == "[]":
            continue
        ann = model.model_fields[step].annotation
        args = typing.get_args(ann)
        model = args[0] if args else ann
    return model


@pytest.mark.parametrize("schema_name", list(CONTRACT_MODELS))
def test_pydantic_matches_json_schema(schema_name):
    def walk(schema: dict, model: type[BaseModel], where: str):
        props = schema["properties"]
        fields = model.model_fields
        assert set(props) == set(fields), f"{where}: schema {sorted(props)} != pydantic {sorted(fields)}"
        assert set(schema["required"]) == {k for k, f in fields.items() if f.is_required()}, where
        assert model.model_config.get("extra") == "forbid", f"{where}: pydantic must forbid extra keys"
        for key, sub in props.items():
            ann = fields[key].annotation
            if "enum" in sub:
                assert set(sub["enum"]) == set(typing.get_args(ann)), f"{where}.{key} enum drift"
            if sub.get("type") == "object" and "properties" in sub:
                walk(sub, ann, f"{where}.{key}")
            if sub.get("type") == "array" and "properties" in sub.get("items", {}):
                walk(sub["items"], typing.get_args(ann)[0], f"{where}.{key}[]")

    walk(load_schema(schema_name), CONTRACT_MODELS[schema_name], schema_name)


@pytest.mark.parametrize("key", list(TS_INTERFACES), ids=lambda k: TS_INTERFACES[k])
def test_typescript_interfaces_match_json_schema(key):
    schema_name, path = key
    sub = _sub(load_schema(schema_name), path)
    ts = _ts_fields(TS_INTERFACES[key])
    assert set(ts) == set(sub["properties"]), f"{TS_INTERFACES[key]}: TS {sorted(ts)} != schema {sorted(sub['properties'])}"
    assert {k for k, req in ts.items() if req} == set(sub["required"]), f"{TS_INTERFACES[key]} optionality drift"


@pytest.mark.parametrize("key", list(TS_UNIONS), ids=lambda k: TS_UNIONS[k])
def test_typescript_unions_match_json_schema_enums(key):
    schema_name, path = key
    assert _ts_union(TS_UNIONS[key]) == set(_sub(load_schema(schema_name), path)["enum"])


def test_typescript_runtime_guard_matches_contract_4_enums():
    node = load_schema("ws_telemetry.schema.json")["properties"]["node"]["properties"]
    for const, enum in (("BRANCH_TYPES", node["branch_type"]["enum"]), ("NODE_VERDICTS", node["z3_verdict"]["enum"])):
        m = re.search(rf"const {const}[^=]*=\s*\[([^\]]*)\]", TS_SOURCE)
        assert m and set(re.findall(r'"([^"]+)"', m.group(1))) == set(enum), const


VERIFIER_CASES = {
    "healthcare_hazard": ("HEALTHCARE_FHIR", {"patient_egfr_ml_min": 24.0, "prescribed_drug": "Metformin",
                                              "prescribed_dose_mg": 2500, "claim_submitted": True,
                                              "conservative_therapy_weeks": 2}),
    "healthcare_heal": ("HEALTHCARE_FHIR", {"patient_egfr_ml_min": 24.0, "prescribed_drug": "Linagliptin",
                                            "prescribed_dose_mg": 5, "claim_submitted": True,
                                            "conservative_therapy_weeks": 6}),
    "malformed": ("HEALTHCARE_FHIR", {}),
    "devops_hazard": ("CLOUD_DEVOPS", {"prod_table_row_count": 0, "cidr_open_world": True, "port_number": 22}),
}


@pytest.mark.parametrize("case", list(VERIFIER_CASES))
def test_live_verifier_output_validates_against_contract_3(case):
    from prover_core import dispatch_verification

    cartridge, post = VERIFIER_CASES[case]
    pre = {"prod_table_row_count": 15420} if cartridge == "CLOUD_DEVOPS" else {}
    verdict = dispatch_verification({
        "trace_id": "tr_parity", "shadow_branch_id": "cow_branch_parity", "cartridge_id": cartridge,
        "cow_fork_latency_ms": 1.0, "state_pre": pre, "state_post_shadow": post,
    })
    assert_valid(verdict.model_dump(mode="json"), "z3_verdict.schema.json")
