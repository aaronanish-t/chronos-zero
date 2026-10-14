"""Cartridge service package usable from repository-root imports."""

from pathlib import Path
import sys

_SERVICE_DIR = Path(__file__).resolve().parent
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))
