import asyncio
import dataclasses

import httpx
import psycopg
import pytest

from crypto_audit import GENESIS_HASH, AuditChain, AuditEntry, entry_hash, export_entries, merkle_root, verify_entries
from pg_support import reset_audit, run
from saga_ledger import CompensationFailed, SagaLedger


def _entry(index, prev, trace_id, status, ts, smt2="(check-sat)", branch="cow_branch_x"):
    return AuditEntry(index, trace_id, branch, status, ts, smt2, prev, entry_hash(prev, trace_id, smt2, status, ts))


def test_chain_links_and_verifies():
    a = _entry(0, GENESIS_HASH, "tr_1", "SAT", 1)
    b = _entry(1, a.entry_hash, "tr_2", "UNSAT", 2)
    log = export_entries([a, b])
    assert log["verified"] is True
    assert log["head_hash"] == b.entry_hash
    assert log["merkle_root"] == merkle_root([a.entry_hash, b.entry_hash])


def test_tampering_is_detected():
    a = _entry(0, GENESIS_HASH, "tr_1", "UNSAT", 1)
    b = _entry(1, a.entry_hash, "tr_2", "SAT", 2)
    assert verify_entries([dataclasses.replace(a, status="SAT"), b]) is False
    assert verify_entries([b]) is False  # dropped or reordered entries break the chain too


def test_field_boundaries_cannot_be_shifted():
    assert entry_hash(GENESIS_HASH, "tr_1", "ab", "SAT", 1) != entry_hash(GENESIS_HASH, "tr_1a", "b", "SAT", 1)


def test_empty_chain():
    log = export_entries([])
    assert (log["length"], log["head_hash"], log["merkle_root"], log["verified"]) == (0, GENESIS_HASH, GENESIS_HASH, True)


@pytest.fixture
def audit_dsn():
    return reset_audit()


def _with_chain(dsn, scenario):
    async def main():
        chain = AuditChain(dsn)
        await chain.open()
        try:
            return await scenario(chain)
        finally:
            await chain.close()
    return run(main())


def test_postgres_chain_persists_across_instances(audit_dsn):
    async def write(chain):
        await chain.append("tr_1", "cow_branch_a", "(assert true)", "SAT", 1_791_926_400_000_000_000)
        await chain.append("tr_2", "cow_branch_b", "(assert false)", "UNSAT", 1_791_926_400_000_000_001)

    _with_chain(audit_dsn, write)
    log = _with_chain(audit_dsn, lambda chain: chain.export())  # fresh instance, same database
    assert log["length"] == 2 and log["verified"] is True
    assert [e["timestamp_ns"] for e in log["entries"]] == [1_791_926_400_000_000_000, 1_791_926_400_000_000_001]
    assert log["entries"][1]["prev_hash"] == log["entries"][0]["entry_hash"]


def test_postgres_chain_concurrent_appends_stay_linear(audit_dsn):
    async def burst(chain):
        await asyncio.gather(*(chain.append(f"tr_{i}", f"cow_branch_{i}", "(x)", "SAT", i) for i in range(20)))
        return await chain.export()

    log = _with_chain(audit_dsn, burst)
    assert log["length"] == 20 and log["verified"] is True


def test_postgres_chain_is_append_only(audit_dsn):
    _with_chain(audit_dsn, lambda chain: chain.append("tr_1", "cow_branch_a", "(x)", "UNSAT", 1))
    with psycopg.connect(audit_dsn, autocommit=True) as conn:
        for sql in ("UPDATE audit_chain SET status = 'SAT'", "DELETE FROM audit_chain", "TRUNCATE audit_chain"):
            with pytest.raises(psycopg.errors.RaiseException):
                conn.execute(sql)


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_compensations_run_newest_first():
    calls = []

    def api(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(200)

    ledger = SagaLedger()
    ledger.record("cow_branch_x", "POST", "/v1/fhir/Claim", {"id": "clm_1"})
    ledger.record("cow_branch_x", "post", "/v1/wires", {"id": "wire_9"})

    async def go():
        async with _client(api) as client:
            return await ledger.compensate("cow_branch_x", client, "http://twin")

    results = asyncio.run(go())
    assert calls == [("POST", "/v1/wires/wire_9/reverse"), ("DELETE", "/v1/fhir/Claim/clm_1")]
    assert all(r.ok for r in results)
    assert ledger.pending("cow_branch_x") == []


def test_commit_drops_compensations():
    ledger = SagaLedger()
    ledger.record("cow_branch_x", "POST", "/v1/wires", {"id": "wire_9"})
    ledger.commit("cow_branch_x")
    assert ledger.pending("cow_branch_x") == []


def test_failed_compensation_still_attempts_the_rest():
    calls = []

    def api(request):
        calls.append(request.url.path)
        return httpx.Response(500 if "wires" in request.url.path else 204)

    ledger = SagaLedger()
    ledger.record("b", "POST", "/v1/fhir/Claim", {"id": "clm_1"})
    ledger.record("b", "POST", "/v1/wires", {"id": "wire_9"})

    async def go():
        async with _client(api) as client:
            await ledger.compensate("b", client, "http://twin")

    with pytest.raises(CompensationFailed) as info:
        asyncio.run(go())
    assert calls == ["/v1/wires/wire_9/reverse", "/v1/fhir/Claim/clm_1"]
    assert [f.step.resource_id for f in info.value.failures] == ["wire_9"]


def test_irreversible_endpoint_must_be_held():
    ledger = SagaLedger()
    assert ledger.is_reversible("POST", "/v1/wires")
    assert not ledger.is_reversible("POST", "/v1/email/send")
    with pytest.raises(LookupError):
        ledger.record("b", "POST", "/v1/email/send", {"id": "m1"})


@pytest.mark.parametrize("bad_id", ["", "../admin", "a/b", "x?y=1"])
def test_unsafe_resource_ids_rejected(bad_id):
    with pytest.raises(ValueError):
        SagaLedger().record("b", "POST", "/v1/wires", {"id": bad_id})
