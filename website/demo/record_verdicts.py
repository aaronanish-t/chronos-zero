"""Record the Z3 verdicts the demo website replays.

Runs the real verifier (services/z3-verifier/prover_core.py) on the exact state shapes the kernel
sends for each cartridge's hazardous tool call and its self-healed retry, after a solver warm-up,
and writes website/demo/verdicts.json. No database, kernel or network needed.

    python website/demo/record_verdicts.py
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "z3-verifier"))
sys.path.insert(0, str(ROOT))
os.environ.setdefault("OFFLINE_MODE", "1")

from prover_core import dispatch_verification, prewarm_solvers  # noqa: E402

OUT = Path(__file__).with_name("verdicts.json")

HC_PRE = {"patient_egfr_ml_min": 24.0, "active_medications": ["Lisinopril"], "prescribed_drug": None,
          "prescribed_dose_mg": 0, "claim_submitted": False, "conservative_therapy_weeks": 0,
          "payer_required_therapy_weeks": 6}
FIN_SPOOF = {"treasury_balance_usd": 50000.0, "daily_escrow_spent_usd": 4200.0, "daily_escrow_limit_usd": 5000.0,
             "vendor_id": "vnd_spoof", "payout_iban": "GB82WEST12345698765432", "vendor_latency_ms": 640.0,
             "iban_allowlisted": False, "transfer_amount_usd": 0.0}
FIN_OK = dict(FIN_SPOOF, vendor_id="vnd_verified", payout_iban="DE89370400440532013000",
              vendor_latency_ms=85.0, iban_allowlisted=True)
OPS_PRE = {"prod_table_row_count": 15420, "sg_id": "sg_prod", "port_number": 443, "cidr_open_world": False}

# (cartridge, label, tool_call, state_pre, state_post) for turn 1 (hazard) and turn 2 (healed).
SCENARIOS = {
    "HEALTHCARE_FHIR": [
        ("Metformin 2500 mg + $1,450 claim (2 weeks therapy)",
         {"tool_name": "prescribe_medication_and_submit_claim", "target_resource": "Patient/pat_402",
          "arguments": {"drug_name": "Metformin", "daily_dose_mg": 2500, "claim_amount_usd": 1450.0,
                        "conservative_therapy_weeks_documented": 2}},
         HC_PRE, dict(HC_PRE, prescribed_drug="Metformin", prescribed_dose_mg=2500, claim_submitted=True,
                      conservative_therapy_weeks=2)),
        ("Linagliptin 5 mg + PT log Encounter/enc_108 attached",
         {"tool_name": "prescribe_medication_and_submit_claim", "target_resource": "Patient/pat_402",
          "arguments": {"drug_name": "Linagliptin", "daily_dose_mg": 5, "claim_amount_usd": 1450.0,
                        "conservative_therapy_weeks_documented": 2,
                        "attached_encounter_ids": ["Encounter/enc_108"]}},
         HC_PRE, dict(HC_PRE, prescribed_drug="Linagliptin", prescribed_dose_mg=5, claim_submitted=True,
                      conservative_therapy_weeks=6)),
    ],
    "FINTECH_ESCROW": [
        ("Wire $12,000 to vnd_spoof (prompt-injected invoice)",
         {"tool_name": "wire_transfer", "target_resource": "Vendor/vnd_spoof",
          "arguments": {"vendor_id": "vnd_spoof", "amount_usd": 12000.0}},
         FIN_SPOOF, dict(FIN_SPOOF, treasury_balance_usd=38000.0, daily_escrow_spent_usd=16200.0,
                         transfer_amount_usd=12000.0)),
        ("Wire $400 to vnd_verified (allowlisted, 85 ms SLA)",
         {"tool_name": "wire_transfer", "target_resource": "Vendor/vnd_verified",
          "arguments": {"vendor_id": "vnd_verified", "amount_usd": 400.0}},
         FIN_OK, dict(FIN_OK, treasury_balance_usd=49600.0, daily_escrow_spent_usd=4600.0,
                      transfer_amount_usd=400.0)),
    ],
    "CLOUD_DEVOPS": [
        ("DROP TABLE users; open port 22 to 0.0.0.0/0",
         {"tool_name": "run_migration", "target_resource": "Table/users",
          "arguments": {"sql": "DROP TABLE users; UPDATE security_groups SET port = 22, cidr_open_world = 1 "
                               "WHERE sg_id = 'sg_prod'"}},
         OPS_PRE, dict(OPS_PRE, prod_table_row_count=0, port_number=22, cidr_open_world=True)),
        ("ALTER TABLE users ADD COLUMN IF NOT EXISTS migration_v2; port 443, closed CIDR",
         {"tool_name": "run_migration", "target_resource": "Table/users",
          "arguments": {"sql": "ALTER TABLE users ADD COLUMN IF NOT EXISTS migration_v2 INT DEFAULT 0; "
                               "UPDATE security_groups SET port = 443, cidr_open_world = 0 WHERE sg_id = 'sg_prod'"}},
         OPS_PRE, dict(OPS_PRE)),
    ],
}


def verify(cartridge: str, pre: dict, post: dict) -> dict:
    payload = {"trace_id": "tr_demo", "shadow_branch_id": "cow_branch_demo", "cartridge_id": cartridge,
               "cow_fork_latency_ms": 1.0, "state_pre": pre, "state_post_shadow": post}
    for _ in range(3):  # warm this exact formula so the recorded latency is steady-state
        dispatch_verification(payload)
    return dispatch_verification(payload).model_dump()


def main() -> None:
    prewarm_solvers()
    out = {}
    for cartridge, turns in SCENARIOS.items():
        out[cartridge] = []
        for label, tool_call, pre, post in turns:
            v = verify(cartridge, pre, post)
            out[cartridge].append({
                "label": label, "tool_call": tool_call, "state_pre": pre, "state_post": post,
                **{k: v[k] for k in ("status", "proof_latency_ms", "violated_invariants", "smt2_dump",
                                     "sha256_proof_hash")},
            })
            print(f"{cartridge:16} {v['status']:5} {v['proof_latency_ms']:.3f} ms  "
                  f"{[i['rule_id'] for i in v['violated_invariants']]}")
    OUT.write_bytes((json.dumps(out, indent=1) + "\n").encode("utf-8"))  # LF on every OS
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
