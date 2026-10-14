"""Five custom policies judges commonly type into the Live Policy Studio.

Each one is pre-recorded in the replay cache so the demo survives a Wi-Fi drop even when a
judge picks a custom rule. Turn 1 is the cartridge's usual hazard; Turn 2 is the default heal
with turn2_arguments merged on top, so the healed call also satisfies the judge's rule.
"""
import hashlib
import re

JUDGE_POLICIES = [
    {"cartridge_id": "FINTECH_ESCROW", "text": "No single wire transfer may exceed $500.",
     "turn2_arguments": {}},  # the default $400 micro-escrow heal already complies
    {"cartridge_id": "FINTECH_ESCROW", "text": "Only pay vendors whose SLA latency is under 100 ms.",
     "turn2_arguments": {}},
    {"cartridge_id": "HEALTHCARE_FHIR", "text": "Never prescribe Metformin to a patient with eGFR below 45.",
     "turn2_arguments": {}},
    {"cartridge_id": "CLOUD_DEVOPS", "text": "Never drop or truncate a production table.",
     "turn2_arguments": {}},
    {"cartridge_id": "CLOUD_DEVOPS", "text": "SSH port 22 must never be open to the internet.",
     "turn2_arguments": {}},
]


def scenario_key(custom_policy: str | None) -> str:
    """Cache key for a run: 'default', or a hash of the policy text ignoring case, spacing and punctuation."""
    if not custom_policy:
        return "default"
    normalized = re.sub(r"[^a-z0-9]+", " ", custom_policy.lower()).strip()
    return "policy:" + hashlib.sha256(normalized.encode()).hexdigest()[:16]


def match_policy(cartridge_id: str, custom_policy: str | None) -> dict | None:
    key = scenario_key(custom_policy)
    return next((p for p in JUDGE_POLICIES
                 if p["cartridge_id"] == cartridge_id and scenario_key(p["text"]) == key), None)
