import asyncio
import dataclasses

import httpx
import pytest

from crypto_audit import GENESIS_HASH, AuditChain, entry_hash, merkle_root
from saga_ledger import CompensationFailed, SagaLedger


def test_chain_links_and_verifies():
    chain = AuditChain()
    a = chain.append("tr_1", "cow_branch_a", "(assert true)", "SAT", 1)
    b = chain.append("tr_2", "cow_branch_b", "(assert false)", "UNSAT", 2)
    assert a.prev_hash == GENESIS_HASH
    assert b.prev_hash == a.entry_hash
    assert b.entry_hash == entry_hash(a.entry_hash, "tr_2", "(assert false)", "UNSAT", 2)
    log = chain.export()
    assert log["verified"] is True
    assert log["head_hash"] == b.entry_hash
    assert log["merkle_root"] == merkle_root([a.entry_hash, b.entry_hash])


def test_tampering_is_detected():
    chain = AuditChain()
    chain.append("tr_1", "cow_branch_a", "(assert true)", "UNSAT", 1)
    chain.append("tr_2", "cow_branch_b", "(assert true)", "SAT", 2)
    chain._entries[0] = dataclasses.replace(chain._entries[0], status="SAT")
    assert chain.verify() is False


def test_field_boundaries_cannot_be_shifted():
    assert entry_hash(GENESIS_HASH, "tr_1", "ab", "SAT", 1) != entry_hash(GENESIS_HASH, "tr_1a", "b", "SAT", 1)


def test_empty_chain():
    log = AuditChain().export()
    assert (log["length"], log["head_hash"], log["merkle_root"], log["verified"]) == (0, GENESIS_HASH, GENESIS_HASH, True)


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
