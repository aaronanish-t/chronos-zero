import sys
from pathlib import Path

# Service dirs use hyphens (per AGENTS.md), so they are not importable as packages.
# Put the repo root (for `contracts`) and each service dir on sys.path instead.
ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "services" / "kernel-proxy", ROOT / "services" / "z3-verifier"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
