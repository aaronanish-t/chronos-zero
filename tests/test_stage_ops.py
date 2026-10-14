import asyncio
import hashlib
import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from interceptor import StageGate, create_app
from pg_support import LOOP_FACTORY, USER_COUNT, pg_query, reset_databases, run

# Stand-in for E3's seeder: same contract (seed_all() rebuilds every cartridge DB).
SEEDER_SOURCE = """
import psycopg
from pg_support import SCHEMAS, cartridge_dsn

def seed_all():
    for cartridge_id, script in SCHEMAS.items():
        with psycopg.connect(cartridge_dsn(cartridge_id), autocommit=True) as conn:
            conn.execute(script)
"""


@pytest.fixture
def seeder(tmp_path):
    reset_databases()
    path = tmp_path / "seed_databases.py"
    path.write_text(SEEDER_SOURCE)
    return str(path)


def allowlist_verifier(request: httpx.Request) -> httpx.Response:
    """Mock Z3: UNSAT when the payout IBAN is not allowlisted or users rows were lost, else SAT."""
    diff = json.loads(request.content)
    pre, post = diff["state_pre"], diff["state_post_shadow"]
    broken = []
    if post.get("iban_allowlisted") is False:
        broken.append("INV_FIN_02_SLA_ATTESTATION")
    if post.get("prod_table_row_count", 0) < pre.get("prod_table_row_count", 0):
        broken.append("INV_OPS_01_ZERO_DATA_LOSS")
    return httpx.Response(200, json={
        "trace_id": diff["trace_id"],
        "shadow_branch_id": diff["shadow_branch_id"],
        "status": "UNSAT" if broken else "SAT",
        "proof_latency_ms": 0.4,
        "violated_invariants": [
            {"rule_id": r, "formal_assertion": r, "counterexample": "x", "remediation_hint": "fix"} for r in broken
        ],
        "smt2_dump": "(check-sat)",
        "sha256_proof_hash": hashlib.sha256(b"(check-sat)").hexdigest(),
    })


def make_client(seeder_path):
    backend_options = {"loop_factory": LOOP_FACTORY} if LOOP_FACTORY else {}
    app = create_app(transport=httpx.MockTransport(allowlist_verifier), seeder_path=seeder_path)
    return TestClient(app, backend_options=backend_options)


def tool_call(tool_name, target, **arguments):
    return {"tool_name": tool_name, "target_resource": target, "arguments": arguments}


def execute(client, call, mode="ACTIVE"):
    return client.post("/v1/kernel/execute", json={
        "trace_id": "tr_stage01", "timestamp_ns": 1_791_926_400_000_000_000, "cartridge_id": "FINTECH_ESCROW",
        "chronos_mode": mode, "agent_id": "agent_01", "tool_call": call,
    })


SPOOF_WIRE = tool_call("wire_transfer", "Vendor/vnd_spoof", amount_usd=12000.0)
VERIFIED_WIRE = tool_call("wire_transfer", "Vendor/vnd_verified", amount_usd=400.0)


def split(client, cartridge_id, steps):
    return client.post("/v1/kernel/run-split-comparison", json={
        "trace_id": "tr_split01", "timestamp_ns": 1_791_926_400_000_000_000,
        "cartridge_id": cartridge_id, "agent_id": "agent_01", "steps": steps,
    })


def sandbox_schemas(cartridge_id):
    return pg_query(cartridge_id, "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'bypass\\_%'")


# --- POST /v1/kernel/reset --------------------------------------------------

def test_reset_restores_state_rotates_audit_and_broadcasts(seeder):
    with make_client(seeder) as client, client.websocket_connect("/ws/telemetry") as ws:
        execute(client, VERIFIED_WIRE)                 # committed + audited
        execute(client, SPOOF_WIRE, mode="BYPASS")    # corrupts production
        ws.receive_json(), ws.receive_json()
        assert client.get("/v1/kernel/audit-log").json()["length"] == 1
        assert client.app.state.dag_history

        r = client.post("/v1/kernel/reset")
        assert r.status_code == 200, r.text
        body = r.json()
        events = [ws.receive_json() for _ in range(3)]

        assert pg_query("FINTECH_ESCROW", "SELECT balance_usd, daily_spent_usd FROM treasury") == [(50000.0, 4200.0)]
        assert pg_query("FINTECH_ESCROW", "SELECT COUNT(*) FROM transfers") == [(0,)]
        log = client.get("/v1/kernel/audit-log").json()
        assert (log["length"], log["verified"]) == (0, True)
        assert body["archived_audit_chain"].startswith("audit_archive.chain_")
        assert client.app.state.dag_history == {}
        assert {e["event_type"] for e in events} == {"DEMO_RESET"}
        assert {e["cartridge_id"] for e in events} == {"HEALTHCARE_FHIR", "FINTECH_ESCROW", "CLOUD_DEVOPS"}
        assert all(e["node"]["branch_type"] == "SYSTEM_EVENT" for e in events)
        print(f"\nreset_latency_ms={body['reset_latency_ms']} seed_ms={body['seed_ms']}")
        assert body["within_budget"], body

        # The chain restarts from genesis and stays verifiable.
        execute(client, VERIFIED_WIRE)
        log = client.get("/v1/kernel/audit-log").json()
        assert (log["length"], log["verified"], log["entries"][0]["index"]) == (1, True, 0)


def test_archived_chain_is_still_append_only(seeder):
    with make_client(seeder) as client:
        for _ in range(2):  # repeated rotations must not collide in the archive schema
            execute(client, VERIFIED_WIRE)
            r = client.post("/v1/kernel/reset")
            assert r.status_code == 200, r.text
        archived = r.json()["archived_audit_chain"]
    import psycopg
    from pg_support import AUDIT_DSN
    with psycopg.connect(AUDIT_DSN, autocommit=True) as conn:
        assert conn.execute(f"SELECT COUNT(*) FROM {archived}").fetchone() == (1,)
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute(f"DELETE FROM {archived}")


def test_reset_without_seeder_changes_nothing(seeder, tmp_path):
    with make_client(str(tmp_path / "missing.py")) as client:
        execute(client, VERIFIED_WIRE)
        r = client.post("/v1/kernel/reset")
        assert r.status_code == 503
        assert client.get("/v1/kernel/audit-log").json()["length"] == 1
    assert pg_query("FINTECH_ESCROW", "SELECT balance_usd FROM treasury") == [(49600.0,)]


def test_reset_rolls_back_pinned_branches(seeder):
    async def tool_noop_reader(conn, _):
        return {}

    async def debit(conn, _):
        await conn.execute("UPDATE treasury SET balance_usd = 0")

    with make_client(seeder) as client:
        engine = client.app.state.engine
        client.portal.call(engine.fork_and_mutate, "FINTECH_ESCROW", tool_noop_reader, debit, {})
        assert engine.active_branch_count == 1
        body = client.post("/v1/kernel/reset").json()
        assert body["rolled_back_branches"] == 1
        assert engine.active_branch_count == 0
    assert pg_query("FINTECH_ESCROW", "SELECT balance_usd FROM treasury") == [(50000.0,)]


def test_gate_refuses_work_during_reset_and_waits_for_inflight():
    async def scenario():
        gate = StageGate()
        order = []

        async def request():
            async with gate.work():
                await asyncio.sleep(0.05)
                order.append("request done")

        async def reset():
            await asyncio.sleep(0.01)
            async with gate.exclusive():
                order.append("reset ran")
                with pytest.raises(HTTPException) as info:
                    async with gate.work():
                        pass
                assert info.value.status_code == 409

        await asyncio.gather(request(), reset())
        return order

    assert run(scenario()) == ["request done", "reset ran"]


# --- POST /v1/kernel/run-split-comparison -----------------------------------

def test_split_fintech_bypass_corrupts_copy_active_protects_production(seeder):
    with make_client(seeder) as client, client.websocket_connect("/ws/telemetry") as ws:
        r = split(client, "FINTECH_ESCROW", [SPOOF_WIRE, VERIFIED_WIRE])
        assert r.status_code == 200, r.text
        events = [ws.receive_json() for _ in range(4)]
    body = r.json()

    assert [s["committed"] for s in body["bypass"]["steps"]] == [True, True]
    assert body["bypass"]["capital_exposed_usd"] == 12400.0
    assert [s["verdict"]["status"] for s in body["active"]["steps"]] == ["UNSAT", "SAT"]
    assert (body["active"]["blocked"], body["active"]["committed"]) == (1, 1)

    # Production only saw the ACTIVE lane's verified $400; the BYPASS copy is gone.
    assert pg_query("FINTECH_ESCROW", "SELECT balance_usd, daily_spent_usd FROM treasury") == [(49600.0, 4600.0)]
    assert pg_query("FINTECH_ESCROW", "SELECT vendor_id, amount_usd FROM transfers") == [("vnd_verified", 400.0)]
    assert sandbox_schemas("FINTECH_ESCROW") == []

    kinds = [e["event_type"] for e in events]
    assert kinds.count("BYPASS_CORRUPTED") == 2 and kinds.count("BRANCH_EVALUATED") == 2
    bypass_nodes = [e["node"] for e in events if e["event_type"] == "BYPASS_CORRUPTED"]
    assert bypass_nodes[1]["parent_id"] == bypass_nodes[0]["id"]  # separate timeline per lane


def test_split_devops_drop_table_only_hits_the_copy(seeder):
    with make_client(seeder) as client:
        body = split(client, "CLOUD_DEVOPS", [
            tool_call("run_migration", "Table/users", sql="DROP TABLE users CASCADE"),
            tool_call("run_migration", "Table/users", sql="ALTER TABLE users ADD COLUMN last_login_at TEXT"),
        ]).json()
    assert body["bypass"]["rows_lost"] == USER_COUNT
    assert body["bypass"]["steps"][1]["status_code"] == 422  # table already gone in the copy
    assert [s["verdict"]["status"] for s in body["active"]["steps"]] == ["UNSAT", "SAT"]
    assert pg_query("CLOUD_DEVOPS", "SELECT COUNT(*) FROM users") == [(USER_COUNT,)]
    assert pg_query("CLOUD_DEVOPS", "SELECT COUNT(*) FROM information_schema.columns "
                                    "WHERE table_schema = 'public' AND table_name = 'users' "
                                    "AND column_name = 'last_login_at'") == [(1,)]
    assert sandbox_schemas("CLOUD_DEVOPS") == []


def test_split_copy_cannot_reach_production_by_schema_name(seeder):
    with make_client(seeder) as client:
        body = split(client, "CLOUD_DEVOPS", [
            tool_call("run_migration", "Table/users", sql="DROP TABLE public.users CASCADE"),
        ]).json()
    assert body["bypass"]["steps"][0]["status_code"] == 400
    assert pg_query("CLOUD_DEVOPS", "SELECT COUNT(*) FROM users") == [(USER_COUNT,)]


def test_split_sandbox_serials_do_not_touch_production_sequences(seeder):
    rx = tool_call("prescribe_medication_and_submit_claim", "Patient/pat_402",
                   drug_name="Linagliptin", daily_dose_mg=5, claim_amount_usd=0)
    with make_client(seeder) as client:
        split(client, "HEALTHCARE_FHIR", [rx, rx, rx])
    # ACTIVE lane committed 3 rows with ids 1..3; the BYPASS copy's inserts used its own sequence.
    assert pg_query("HEALTHCARE_FHIR", "SELECT id FROM prescriptions ORDER BY id") == [(1,), (2,), (3,)]
