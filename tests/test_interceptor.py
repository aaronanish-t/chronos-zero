import hashlib
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from interceptor import create_app
from pg_support import LOOP_FACTORY, USER_COUNT, pg_query, reset_databases
from prover_core import verify_state_diff


@pytest.fixture
def db_dir():
    """PostgreSQL DSN base with freshly rebuilt cartridge databases (name kept from the SQLite era)."""
    return reset_databases()


def query(_dsn, cartridge_id, sql):
    return pg_query(cartridge_id, sql)


class FakeVerifier:
    """Mock Z3 service: records every Contract 2 request and answers with a fixed status."""

    def __init__(self, status="SAT", rules=(), mutate=None):
        self.status, self.rules, self.mutate = status, rules, mutate
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        diff = json.loads(request.content)
        self.requests.append(diff)
        verdict = {
            "trace_id": diff["trace_id"],
            "shadow_branch_id": diff["shadow_branch_id"],
            "status": self.status,
            "proof_latency_ms": 0.5,
            "violated_invariants": [
                {"rule_id": r, "formal_assertion": r, "counterexample": "x", "remediation_hint": "fix"}
                for r in self.rules
            ],
            "smt2_dump": "(check-sat)",
            "sha256_proof_hash": hashlib.sha256(b"(check-sat)").hexdigest(),
        }
        if self.mutate:
            self.mutate(verdict)
        return httpx.Response(200, json=verdict)


def real_z3(request: httpx.Request) -> httpx.Response:
    """Mock transport backed by the real Z3 prover (healthcare invariants)."""
    return httpx.Response(200, json=verify_state_diff(json.loads(request.content)))


def make_client(verifier):
    backend_options = {"loop_factory": LOOP_FACTORY} if LOOP_FACTORY else {}
    return TestClient(create_app(transport=httpx.MockTransport(verifier)), backend_options=backend_options)


def payload(cartridge_id, tool_name, target, arguments, mode="ACTIVE", trace="tr_test01"):
    return {
        "trace_id": trace,
        "timestamp_ns": 1_791_926_400_000_000_000,
        "cartridge_id": cartridge_id,
        "chronos_mode": mode,
        "agent_id": "agent_01",
        "tool_call": {"tool_name": tool_name, "target_resource": target, "arguments": arguments},
    }


METFORMIN = {
    "drug_name": "Metformin", "daily_dose_mg": 2500,
    "claim_amount_usd": 1450.0, "conservative_therapy_weeks_documented": 2,
}
LINAGLIPTIN_WITH_PT_LOG = {
    "drug_name": "Linagliptin", "daily_dose_mg": 5, "claim_amount_usd": 1450.0,
    "conservative_therapy_weeks_documented": 2, "attached_encounter_ids": ["Encounter/enc_108"],
}


def rx(**args):
    return payload("HEALTHCARE_FHIR", "prescribe_medication_and_submit_claim", "Patient/pat_402", args)


def test_healthcare_self_healing_loop_with_real_z3(db_dir):
    with make_client(real_z3) as client, client.websocket_connect("/ws/telemetry") as ws:
        blocked = client.post("/v1/kernel/execute", json=rx(**METFORMIN))
        assert blocked.status_code == 200
        assert blocked.json()["status"] == "UNSAT"
        assert {v["rule_id"] for v in blocked.json()["violated_invariants"]} >= {"INV_MED_01_RENAL_SAFETY"}
        assert query(db_dir, "HEALTHCARE_FHIR", "SELECT COUNT(*) FROM prescriptions") == [(0,)]

        event = ws.receive_json()
        assert event["event_type"] == "BRANCH_EVALUATED"
        assert event["node"]["branch_type"] == "SHADOW_REJECTED"
        assert event["node"]["parent_id"] == "node_root"
        assert event["node"]["financial_loss_prevented_usd"] == 1450.0
        assert event["node"]["clinical_hazard_prevented"] is True

        healed = client.post("/v1/kernel/execute", json=rx(**LINAGLIPTIN_WITH_PT_LOG))
        assert healed.json()["status"] == "SAT"
        assert query(db_dir, "HEALTHCARE_FHIR",
                     "SELECT drug_name, daily_dose_mg, claim_submitted, conservative_therapy_weeks FROM prescriptions"
                     ) == [("Linagliptin", 5, 1, 6)]

        committed = ws.receive_json()
        assert committed["node"]["branch_type"] == "COMMITTED_SAFE"
        assert committed["node"]["parent_id"] == "node_root"  # rejected branch never joined the timeline

        client.post("/v1/kernel/execute", json=rx(**LINAGLIPTIN_WITH_PT_LOG))
        assert ws.receive_json()["node"]["parent_id"] == committed["node"]["id"]
        assert client.app.state.engine.active_branch_count == 0

        log = client.get("/v1/kernel/audit-log").json()
        assert log["length"] == 3 and log["verified"] is True
        assert [e["status"] for e in log["entries"]] == ["UNSAT", "SAT", "SAT"]
        assert {e["timestamp_ns"] for e in log["entries"]} == {rx(**METFORMIN)["timestamp_ns"]}  # Contract 1 time


def test_healthcare_state_keys_match_contract_2(db_dir):
    fake = FakeVerifier()
    with make_client(fake) as client:
        client.post("/v1/kernel/execute", json=rx(**METFORMIN))
    diff = fake.requests[0]
    assert diff["cartridge_id"] == "HEALTHCARE_FHIR"
    assert diff["state_pre"]["patient_egfr_ml_min"] == 24.0
    assert diff["state_pre"]["active_medications"] == ["Lisinopril"]
    assert diff["state_post_shadow"] == {
        "patient_egfr_ml_min": 24.0,
        "active_medications": ["Lisinopril"],
        "prescribed_drug": "Metformin",
        "prescribed_dose_mg": 2500,
        "claim_submitted": True,
        "conservative_therapy_weeks": 2,
        "payer_required_therapy_weeks": 6,
    }


def test_fintech_spoofed_wire_blocked_and_rolled_back(db_dir):
    fake = FakeVerifier("UNSAT", ["INV_FIN_01_ESCROW_CAP", "INV_FIN_02_SLA_ATTESTATION"])
    with make_client(fake) as client, client.websocket_connect("/ws/telemetry") as ws:
        r = client.post("/v1/kernel/execute", json=payload(
            "FINTECH_ESCROW", "wire_transfer", "Vendor/vnd_spoof", {"amount_usd": 12000.0}))
        assert r.json()["status"] == "UNSAT"
        assert ws.receive_json()["node"]["financial_loss_prevented_usd"] == 12000.0

    pre, post = fake.requests[0]["state_pre"], fake.requests[0]["state_post_shadow"]
    assert pre["daily_escrow_spent_usd"] == 4200.0
    assert pre["daily_escrow_limit_usd"] == 5000.0
    assert pre["transfer_amount_usd"] == 0.0
    assert post["transfer_amount_usd"] == 12000.0
    assert post["vendor_latency_ms"] == 640.0
    assert post["iban_allowlisted"] is False
    assert query(db_dir, "FINTECH_ESCROW", "SELECT balance_usd, daily_spent_usd FROM treasury") == [(50000.0, 4200.0)]
    assert query(db_dir, "FINTECH_ESCROW", "SELECT COUNT(*) FROM transfers") == [(0,)]


def test_fintech_swapped_iban_is_not_allowlisted(db_dir):
    fake = FakeVerifier()
    with make_client(fake) as client:
        client.post("/v1/kernel/execute", json=payload(
            "FINTECH_ESCROW", "wire_transfer", "Vendor/vnd_verified",
            {"amount_usd": 400.0, "iban": "GB82WEST12345698765432"}))
    assert fake.requests[0]["state_post_shadow"]["iban_allowlisted"] is False


def test_fintech_verified_payout_commits(db_dir):
    with make_client(FakeVerifier("SAT")) as client:
        r = client.post("/v1/kernel/execute", json=payload(
            "FINTECH_ESCROW", "wire_transfer", "Vendor/vnd_verified", {"amount_usd": 400.0}))
    assert r.json()["status"] == "SAT"
    assert query(db_dir, "FINTECH_ESCROW", "SELECT balance_usd, daily_spent_usd FROM treasury") == [(49600.0, 4600.0)]


def test_devops_drop_table_cascade_rolled_back(db_dir):
    fake = FakeVerifier("UNSAT", ["INV_OPS_01_ZERO_DATA_LOSS"])
    with make_client(fake) as client:
        r = client.post("/v1/kernel/execute", json=payload(
            "CLOUD_DEVOPS", "run_migration", "Database/prod", {"sql": "DROP TABLE users CASCADE;"}))
    assert r.json()["status"] == "UNSAT"
    assert fake.requests[0]["state_pre"]["prod_table_row_count"] == USER_COUNT
    assert fake.requests[0]["state_post_shadow"]["prod_table_row_count"] == 0
    assert query(db_dir, "CLOUD_DEVOPS", "SELECT COUNT(*) FROM users") == [(USER_COUNT,)]


def test_devops_open_port_22_state(db_dir):
    fake = FakeVerifier("UNSAT", ["INV_OPS_02_NO_PUBLIC_ADMIN_PORT"])
    with make_client(fake) as client:
        client.post("/v1/kernel/execute", json=payload(
            "CLOUD_DEVOPS", "update_security_group", "SecurityGroup/sg_prod",
            {"sg_id": "sg_prod", "port": 22, "cidr": "0.0.0.0/0"}))
    post = fake.requests[0]["state_post_shadow"]
    assert (post["port_number"], post["cidr_open_world"]) == (22, True)
    assert query(db_dir, "CLOUD_DEVOPS", "SELECT port, cidr_open_world FROM security_groups") == [(443, 0)]


def test_devops_transaction_control_sql_rejected(db_dir):
    fake = FakeVerifier()
    with make_client(fake) as client:
        r = client.post("/v1/kernel/execute", json=payload(
            "CLOUD_DEVOPS", "run_migration", "Database/prod",
            {"sql": "DELETE FROM users; COMMIT; DROP TABLE users"}))
        assert client.app.state.engine.active_branch_count == 0
    assert r.status_code == 400
    assert fake.requests == []
    assert query(db_dir, "CLOUD_DEVOPS", "SELECT COUNT(*) FROM users") == [(USER_COUNT,)]


def test_bypass_commits_unverified_and_reports_corruption(db_dir):
    fake = FakeVerifier()
    with make_client(fake) as client, client.websocket_connect("/ws/telemetry") as ws:
        r = client.post("/v1/kernel/execute", json=payload(
            "FINTECH_ESCROW", "wire_transfer", "Vendor/vnd_spoof", {"amount_usd": 12000.0}, mode="BYPASS"))
        event = ws.receive_json()
    body = r.json()
    assert body["verified"] is False and body["committed"] is True
    assert body["corruption"]["capital_exposed_usd"] == 12000.0
    assert body["corruption"]["changed_fields"]["treasury_balance_usd"] == {"pre": 50000.0, "post": 38000.0}
    assert event["event_type"] == "BYPASS_CORRUPTED"
    assert event["node"]["branch_type"] == "BYPASS_CORRUPTED"
    assert event["node"]["z3_verdict"] == "BYPASS"
    assert fake.requests == []
    assert query(db_dir, "FINTECH_ESCROW", "SELECT balance_usd FROM treasury") == [(38000.0,)]


def test_bypass_drop_table_reports_rows_lost(db_dir):
    with make_client(FakeVerifier()) as client:
        r = client.post("/v1/kernel/execute", json=payload(
            "CLOUD_DEVOPS", "run_migration", "Database/prod", {"sql": "DROP TABLE users CASCADE"}, mode="BYPASS"))
    assert r.json()["corruption"]["rows_lost"] == USER_COUNT


def _assert_failed_closed(db_dir, client, response):
    assert response.status_code == 503
    assert "rolled back" in response.json()["detail"]
    assert client.app.state.engine.active_branch_count == 0
    assert query(db_dir, "FINTECH_ESCROW", "SELECT COUNT(*) FROM transfers") == [(0,)]


WIRE_400 = ("FINTECH_ESCROW", "wire_transfer", "Vendor/vnd_verified", {"amount_usd": 400.0})


def test_verifier_unreachable_fails_closed(db_dir):
    def down(request):
        raise httpx.ConnectError("connection refused")

    with make_client(down) as client:
        _assert_failed_closed(db_dir, client, client.post("/v1/kernel/execute", json=payload(*WIRE_400)))


def test_verifier_http_error_fails_closed(db_dir):
    with make_client(lambda request: httpx.Response(500, json={"detail": "boom"})) as client:
        _assert_failed_closed(db_dir, client, client.post("/v1/kernel/execute", json=payload(*WIRE_400)))


@pytest.mark.parametrize("status", ["TIMEOUT", "ERROR"])
def test_non_contract_status_fails_closed(db_dir, status):
    fake = FakeVerifier(mutate=lambda v: v.update(status=status))
    with make_client(fake) as client:
        _assert_failed_closed(db_dir, client, client.post("/v1/kernel/execute", json=payload(*WIRE_400)))


def test_verdict_for_another_branch_fails_closed(db_dir):
    fake = FakeVerifier("SAT", mutate=lambda v: v.update(shadow_branch_id="cow_branch_other"))
    with make_client(fake) as client:
        _assert_failed_closed(db_dir, client, client.post("/v1/kernel/execute", json=payload(*WIRE_400)))


def test_audit_unavailable_fails_closed(db_dir):
    backend_options = {"loop_factory": LOOP_FACTORY} if LOOP_FACTORY else {}
    app = create_app(
        transport=httpx.MockTransport(FakeVerifier("SAT")),
        audit_dsn="postgresql://chronos_kernel:chronos_kernel@127.0.0.1:1/chronos_audit",  # nothing listens here
    )
    with TestClient(app, backend_options=backend_options) as client:
        _assert_failed_closed(db_dir, client, client.post("/v1/kernel/execute", json=payload(*WIRE_400)))


def test_unknown_tool_404(db_dir):
    with make_client(FakeVerifier()) as client:
        r = client.post("/v1/kernel/execute", json=payload("CLOUD_DEVOPS", "rm_rf", "Host/prod", {}))
    assert r.status_code == 404


def test_unknown_patient_400(db_dir):
    with make_client(FakeVerifier()) as client:
        r = client.post("/v1/kernel/execute", json=payload(
            "HEALTHCARE_FHIR", "prescribe_medication_and_submit_claim", "Patient/pat_999", METFORMIN))
        assert client.app.state.engine.active_branch_count == 0
    assert r.status_code == 400


def test_contract_1_validation_422(db_dir):
    bad = payload(*WIRE_400)
    bad["cartridge_id"] = "CRYPTO"
    with make_client(FakeVerifier()) as client:
        assert client.post("/v1/kernel/execute", json=bad).status_code == 422
