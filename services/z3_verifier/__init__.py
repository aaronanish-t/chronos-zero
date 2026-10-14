"""Import alias for the runnable ``services/z3-verifier`` service."""

from pathlib import Path
import sys

_LEGACY_DIR = Path(__file__).resolve().parents[1] / "z3-verifier"
__path__.append(str(_LEGACY_DIR))
if str(_LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(_LEGACY_DIR))
