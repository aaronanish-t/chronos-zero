"""DeterministicReplayMiddleware failover. No Postgres or kernel needed."""
import asyncio
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "cartridges"))
from replay_middleware import DeterministicReplayMiddleware, ReplayMiss  # noqa: E402
from scenarios.judge_policies import JUDGE_POLICIES, match_policy, scenario_key  # noqa: E402

CALL = {"tool_name": "wire_transfer", "target_resource": "Vendor/vnd_verified",
        "arguments": {"vendor_id": "vnd_verified", "amount_usd": 800.0}}
OTHER = {**CALL, "arguments": {"vendor_id": "vnd_spoof", "amount_usd": 12000.0}}


def mw(tmp_path, **kw):
    return DeterministicReplayMiddleware(path=tmp_path / "replay.sqlite", **kw)


def call(m, live_fn, turn=2):
    return asyncio.run(m.tool_call("FINTECH_ESCROW", "default", turn, live_fn))


async def instant(result=CALL):
    return result


def test_record_then_offline_replay(tmp_path):
    assert call(mw(tmp_path, offline=False, record=True), instant) == (CALL, "live")

    async def must_not_run():
        raise AssertionError("offline mode must not call the LLM")
    assert call(mw(tmp_path, offline=True, record=False), must_not_run) == (CALL, "replay_offline")


def test_offline_miss_raises(tmp_path):
    with pytest.raises(ReplayMiss):
        call(mw(tmp_path, offline=True, record=False), instant)


def test_slow_llm_fails_over_within_timeout(tmp_path):
    call(mw(tmp_path, offline=False, record=True), instant)

    async def slow():
        await asyncio.sleep(5)
        return OTHER
    t0 = time.perf_counter()
    assert call(mw(tmp_path, offline=False, record=False, timeout_ms=200), slow) == (CALL, "replay_timeout")
    assert time.perf_counter() - t0 < 2


def test_llm_error_fails_over(tmp_path):
    call(mw(tmp_path, offline=False, record=True), instant)

    async def boom():
        raise ConnectionError("wifi down")
    assert call(mw(tmp_path, offline=False, record=False), boom) == (CALL, "replay_error")


def test_no_cache_waits_for_slow_llm_and_does_not_record(tmp_path):
    m = mw(tmp_path, offline=False, record=False, timeout_ms=50)

    async def slowish():
        await asyncio.sleep(0.2)
        return OTHER
    assert call(m, slowish) == (OTHER, "live")
    with pytest.raises(ReplayMiss):
        call(mw(tmp_path, offline=True, record=False), instant)


def test_judge_policy_keys():
    assert len(JUDGE_POLICIES) == 5
    assert scenario_key(None) == "default"
    typed = "  no SINGLE wire-transfer may exceed 500 "
    assert scenario_key(typed) == scenario_key("No single wire transfer may exceed $500.")
    assert match_policy("FINTECH_ESCROW", typed)["turn2_arguments"] == {"amount_usd": 500.0}
    assert match_policy("CLOUD_DEVOPS", typed) is None
    assert len({scenario_key(p["text"]) for p in JUDGE_POLICIES}) == 5
