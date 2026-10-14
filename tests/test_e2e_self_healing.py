"""Self-healing loop against a fake kernel (E1's /v1/kernel/execute isn't built yet).

The fake kernel returns UNSAT for each scenario's hazardous call and SAT for anything else,
so these tests prove the orchestrator heals in exactly one retry turn using seeded DB state.
"""
import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "cartridges"))
import orchestrator  # noqa: E402
import seed_databases  # noqa: E402

HAZARDS = {cid: s["hazard"]() for cid, s in orchestrator.SCENARIOS.items()}


def fake_kernel(request: httpx.Request) -> httpx.Response:
    body = __import__("json").loads(request.content)
    assert set(body) == {"trace_id", "timestamp_ns", "cartridge_id", "chronos_mode", "agent_id", "tool_call"}
    assert body["trace_id"].startswith("tr_")
    unsat = body["chronos_mode"] == "ACTIVE" and body["tool_call"] == HAZARDS[body["cartridge_id"]]
    return httpx.Response(200, json={
        "trace_id": body["trace_id"],
        "shadow_branch_id": "cow_branch_test",
        "status": "UNSAT" if unsat else "SAT",
        "proof_latency_ms": 1.2,
        "violated_invariants": [{
            "rule_id": "INV_TST_01_FAKE", "formal_assertion": "x <= 1",
            "counterexample": "x=2", "remediation_hint": "lower x",
        }] if unsat else [],
        "smt2_dump": "",
        "sha256_proof_hash": "0" * 64,
    })


def run(cartridge_id, mode):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(fake_kernel)) as client:
            return await orchestrator.ChronosAgentRunner(cartridge_id, mode, client=client).run()
    return asyncio.run(go())


@pytest.fixture(autouse=True)
def seeded():
    seed_databases.seed_all()


@pytest.mark.parametrize("cartridge_id", list(orchestrator.SCENARIOS))
def test_active_heals_in_one_turn(cartridge_id):
    result = run(cartridge_id, "ACTIVE")
    assert [t["verdict"]["status"] for t in result["turns"]] == ["UNSAT", "SAT"]
    assert result["self_healed"]
    correction = next(m for m in result["messages"] if m["role"] == "system")["content"]
    for key in ("INV_TST_01_FAKE", "x <= 1", "x=2", "lower x", "cow_branch_test"):
        assert key in correction


def test_turn2_uses_safe_state():
    args = {cid: run(cid, "ACTIVE")["turns"][1]["tool_call"]["arguments"] for cid in orchestrator.SCENARIOS}
    assert args["HEALTHCARE_FHIR"]["drug_name"] == "Linagliptin"
    assert args["HEALTHCARE_FHIR"]["attached_encounter_ids"] == ["Encounter/enc_108"]
    assert args["FINTECH_ESCROW"] == {"vendor_id": "vnd_verified", "amount_usd": 800.0}
    assert args["CLOUD_DEVOPS"]["sql"].startswith("ALTER TABLE users ADD COLUMN")


def test_bypass_does_not_heal():
    result = run("FINTECH_ESCROW", "BYPASS")
    assert len(result["turns"]) == 1 and not result["self_healed"]


def test_endpoint_returns_502_when_kernel_down(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(orchestrator, "KERNEL_URL", "http://127.0.0.1:9/v1/kernel/execute")
    resp = TestClient(orchestrator.app).post("/v1/agent/run-scenario", json={"cartridge_id": "CLOUD_DEVOPS"})
    assert resp.status_code == 502
