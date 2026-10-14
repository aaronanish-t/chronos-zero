"""Minimal JSON Schema validator for the keywords used in contracts/*.schema.json.

No third-party dependency, so `make test-contracts` and `make demo-verify` run on the stage
laptop with no network. Supports: type, required, properties, additionalProperties(false),
enum, pattern, minimum, minLength, items.
"""

import json
import re
from pathlib import Path

CONTRACTS_DIR = Path(__file__).resolve().parents[1] / "contracts"

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "integer": int,
    "number": (int, float),
}


def load_schema(name: str) -> dict:
    return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


def errors(instance, schema: dict, path: str = "$") -> list[str]:
    out: list[str] = []
    t = schema.get("type")
    if t:
        ok = isinstance(instance, _TYPES[t]) and not (t in ("integer", "number") and isinstance(instance, bool))
        if not ok:
            return [f"{path}: expected {t}, got {type(instance).__name__}"]
    if "enum" in schema and instance not in schema["enum"]:
        out.append(f"{path}: {instance!r} not in {schema['enum']}")
    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            out.append(f"{path}: {instance!r} does not match {schema['pattern']}")
        if len(instance) < schema.get("minLength", 0):
            out.append(f"{path}: shorter than minLength {schema['minLength']}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            out.append(f"{path}: {instance} < minimum {schema['minimum']}")
    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                out.append(f"{path}: missing required key {key!r}")
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    out.append(f"{path}: unexpected key {key!r}")
        for key, sub in props.items():
            if key in instance:
                out.extend(errors(instance[key], sub, f"{path}.{key}"))
    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            out.extend(errors(item, schema["items"], f"{path}[{i}]"))
    return out


def assert_valid(instance, schema_name: str) -> None:
    problems = errors(instance, load_schema(schema_name))
    assert not problems, f"{schema_name} violations:\n" + "\n".join(problems)
