"""Adversarial self-healing scenarios, one module per cartridge.

Each module exposes CARTRIDGE_ID, PROMPT, EXPECTED_TURN1_VIOLATIONS, hazard() -> tool_call
and async heal(conn) -> tool_call (reads the safe recovery record from the cartridge DB).
"""
from . import cloud_devops_scenario, fintech_scenario, healthcare_scenario

SCENARIOS = {m.CARTRIDGE_ID: m for m in (healthcare_scenario, fintech_scenario, cloud_devops_scenario)}
