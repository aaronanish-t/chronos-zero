import sys
from pathlib import Path

import pytest

# Service dirs use hyphens (per AGENTS.md), so they are not importable as packages.
# Put the repo root (for `contracts`) and each service dir on sys.path instead.
ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "services" / "kernel-proxy", ROOT / "services" / "z3-verifier"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


@pytest.fixture(autouse=True)
def _unload_compiled_policies():
    """Compiled Live Policy Studio rules live in a process-wide registry and are enforced on every
    later verdict for their cartridge. Unload them after each test so no test's verdicts depend on
    which tests ran before it."""
    yield
    nl_compiler = sys.modules.get("nl_compiler")
    if nl_compiler is not None:
        nl_compiler.clear_dynamic_rules()
