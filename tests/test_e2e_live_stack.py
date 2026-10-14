"""Live end-to-end stack: real kernel + real Z3 verifier + real agent orchestrator + real Postgres.

Nothing is mocked. The three ASGI apps are wired in-process (orchestrator -> kernel -> Z3) and
every Contract 3 verdict and Contract 4 WebSocket event is validated against the JSON Schema.
An airplane-mode guard records any socket connection off the loopback interface; the whole
demo must make none (OFFLINE_MODE=1, a dummy API key set to prove nothing reaches out).

Run with `make demo-verify` (Postgres up: `make db-up`).
"""

import socket
import sys
from pathlib import Path

import httpx
import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "cartridges"))

import orchestrator  # noqa: E402
import seed_databases  # noqa: E402
from contract_validator import assert_valid  # noqa: E402
from pg_support import reset_audit, run  # noqa: E402
from replay_middleware import DeterministicReplayMiddleware  # noqa: E402

LOOPBACK = {"127.0.0.1", "::1", "localhost"}


class _CaptureSocket:
    """Stands in for a UI WebSocket client on the kernel's TelemetryHub."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.events.append(message)


@pytest.fixture
def airplane_mode(monkeypatch):
    attempts: list = []
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def guard(addr):
        host = addr[0] if isinstance(addr, tuple) else addr
        if host not in LOOPBACK:
            attempts.append(addr)
            raise OSError(f"airplane mode: blocked connection to {addr}")

    def connect(self, addr):
        guard(addr)
        return real_connect(self, addr)

    def connect_ex(self, addr):
        guard(addr)
        return real_connect_ex(self, addr)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setenv("OFFLINE_MODE", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-offline-guard")
    return attempts


@pytest.fixture
def seeded():
    try:
        seed_databases.seed_all()
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL unreachable at CHRONOS_PG_DSN (run `make db-up`): {exc}")
    reset_audit()


def query(cartridge_id: str, sql: str):
    with psycopg.connect(seed_databases.db_dsn(cartridge_id), autocommit=True) as conn:
        return conn.execute(sql).fetchall()


async def _stack(body):
    """Start the kernel (with its lifespan) wired to the Z3 app; hand body() the clients."""
    import server as z3_server
    from interceptor import create_app

    z3 = httpx.ASGITransport(app=z3_server.app)
    kernel_app = create_app(transport=z3, seeder_path=str(ROOT / "services" / "cartridges" / "seed_databases.py"))
    ws = _CaptureSocket()
    async with kernel_app.router.lifespan_context(kernel_app):
        kernel_app.state.hub._clients.add(ws)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=kernel_app), base_url="http://127.0.0.1:8000") as kernel, \
                httpx.AsyncClient(transport=z3, base_url="http://127.0.0.1:8001") as z3_client:
            result = await body(kernel_app, kernel, z3_client, ws)
        assert kernel_app.state.engine.active_branch_count == 0, "a shadow branch was left pinned"
    return result


def _runner(cartridge_id, mode, kernel, tmp_path, policy=None):
    replay = DeterministicReplayMiddleware(path=tmp_path / "replay.sqlite", offline=False, record=False)
    return orchestrator.ChronosAgentRunner(cartridge_id, mode, policy, client=kernel, replay=replay)


def _check_events(ws: _CaptureSocket):
    assert ws.events, "kernel broadcast no telemetry"
    for event in ws.events:
        assert_valid(event, "ws_telemetry.schema.json")


@pytest.mark.parametrize("cartridge_id", list(orchestrator.SCENARIOS))
def test_active_scenario_self_heals_live(seeded, airplane_mode, tmp_path, cartridge_id):
    async def body(app, kernel, z3, ws):
        return await _runner(cartridge_id, "ACTIVE", kernel, tmp_path).run(), ws

    result, ws = run(_stack(body))
    turns = result["turns"]
    assert [t["verdict"]["status"] for t in turns] == ["UNSAT", "SAT"]
    assert result["self_healed"]
    violated = {v["rule_id"] for v in turns[0]["verdict"]["violated_invariants"]}
    assert orchestrator.SCENARIOS[cartridge_id].EXPECTED_TURN1_VIOLATIONS <= violated
    for t in turns:
        assert_valid(t["verdict"], "z3_verdict.schema.json")
        assert t["verdict"]["smt2_dump"].strip()
    _check_events(ws)
    branch_types = [e["node"]["branch_type"] for e in ws.events]
    assert branch_types == ["SHADOW_REJECTED", "COMMITTED_SAFE"]
    assert airplane_mode == []

    # Production holds the healed state and none of the hazard.
    if cartridge_id == "HEALTHCARE_FHIR":
        assert query(cartridge_id, "SELECT drug_name FROM prescriptions ORDER BY id") == [("Linagliptin",)]
    elif cartridge_id == "FINTECH_ESCROW":
        assert query(cartridge_id, "SELECT vendor_id, amount_usd FROM transfers") == [("vnd_verified", 400.0)]
        assert query(cartridge_id, "SELECT daily_spent_usd FROM treasury") == [(4600.0,)]
    else:
        assert query(cartridge_id, "SELECT count(*) FROM users") == [(15420,)]
        assert query(cartridge_id, "SELECT port, cidr_open_world FROM security_groups") == [(443, 0)]


def test_scenarios_rerun_without_reset(seeded, airplane_mode, tmp_path):
    """The pilot may run a cartridge twice on stage; the heals are re-runnable."""
    async def body(app, kernel, z3, ws):
        out = []
        for cartridge_id in orchestrator.SCENARIOS:
            for _ in range(2):
                out.append((cartridge_id, (await _runner(cartridge_id, "ACTIVE", kernel, tmp_path).run())["self_healed"]))
        return out

    assert all(healed for _, healed in run(_stack(body))), "a second run did not self-heal"
    assert airplane_mode == []


def test_live_policy_studio_rule_is_enforced(seeded, airplane_mode, tmp_path):
    """Judge types a rule, it compiles offline, and the very next kernel call is held to it."""
    async def body(app, kernel, z3, ws):
        compiled = (await z3.post("/v1/z3/compile-policy", json={
            "cartridge_id": "FINTECH_ESCROW", "rule_id": "INV_POL_01_FIN",
            "natural_language_rule": "No single wire transfer may exceed $500.",
        })).json()
        try:
            # A $600 wire to the verified vendor passes every static rule but breaks the judge's.
            blocked = (await kernel.post("/v1/kernel/execute", json={
                "trace_id": "tr_policy01", "timestamp_ns": 1, "cartridge_id": "FINTECH_ESCROW",
                "chronos_mode": "ACTIVE", "agent_id": "judge",
                "tool_call": {"tool_name": "wire_transfer", "target_resource": "Vendor/vnd_verified",
                              "arguments": {"vendor_id": "vnd_verified", "amount_usd": 600.0}},
            })).json()
            healed = await _runner("FINTECH_ESCROW", "ACTIVE", kernel, tmp_path,
                                   policy="No single wire transfer may exceed $500.").run()
        finally:
            await z3.post("/v1/z3/policies/clear")
        return compiled, blocked, healed

    compiled, blocked, healed = run(_stack(body))
    assert compiled["status"] == "COMPILED", compiled
    assert blocked["status"] == "UNSAT"
    assert [v["rule_id"] for v in blocked["violated_invariants"]] == ["INV_POL_01_FIN"]
    assert_valid(blocked, "z3_verdict.schema.json")
    assert healed["self_healed"]
    assert airplane_mode == []


@pytest.mark.parametrize("text, cartridge_id", [
    ("No single wire transfer may exceed $500.", "FINTECH_ESCROW"),
    ("Only pay vendors whose SLA latency is under 100 ms.", "FINTECH_ESCROW"),
    ("Never prescribe Metformin to a patient with eGFR below 45.", "HEALTHCARE_FHIR"),
    ("Never drop or truncate a production table.", "CLOUD_DEVOPS"),
    ("SSH port 22 must never be open to the internet.", "CLOUD_DEVOPS"),
])
def test_every_judge_preset_compiles_offline_and_still_heals(seeded, airplane_mode, tmp_path, text, cartridge_id):
    async def body(app, kernel, z3, ws):
        compiled = (await z3.post("/v1/z3/compile-policy", json={
            "cartridge_id": cartridge_id, "rule_id": "INV_POL_02_PRESET", "natural_language_rule": text,
        })).json()
        try:
            result = await _runner(cartridge_id, "ACTIVE", kernel, tmp_path, policy=text).run()
        finally:
            await z3.post("/v1/z3/policies/clear")
        return compiled, result

    compiled, result = run(_stack(body))
    assert compiled["status"] == "COMPILED", compiled
    assert result["turns"][0]["verdict"]["status"] == "UNSAT"
    assert result["self_healed"], result["turns"][-1]["verdict"]
    assert airplane_mode == []


def test_bypass_corrupts_then_reset_restores(seeded, airplane_mode, tmp_path):
    async def body(app, kernel, z3, ws):
        bypass = await _runner("FINTECH_ESCROW", "BYPASS", kernel, tmp_path).run()
        spent_after_bypass = query("FINTECH_ESCROW", "SELECT daily_spent_usd FROM treasury")
        reset = (await kernel.post("/v1/kernel/reset")).json()
        return bypass, spent_after_bypass, reset, ws

    bypass, spent_after_bypass, reset, ws = run(_stack(body))
    assert len(bypass["turns"]) == 1 and not bypass["self_healed"]
    assert bypass["turns"][0]["verdict"]["corruption"]["capital_exposed_usd"] == 12000.0
    assert spent_after_bypass == [(16200.0,)]
    assert reset["status"] == "RESET"
    assert query("FINTECH_ESCROW", "SELECT daily_spent_usd FROM treasury") == [(4200.0,)]
    _check_events(ws)
    assert [e["event_type"] for e in ws.events][0] == "BYPASS_CORRUPTED"
    assert {e["event_type"] for e in ws.events[1:]} == {"DEMO_RESET"}
    assert airplane_mode == []


def test_split_comparison_live(seeded, airplane_mode):
    async def body(app, kernel, z3, ws):
        hazard = orchestrator.SCENARIOS["CLOUD_DEVOPS"].hazard()
        return (await kernel.post("/v1/kernel/run-split-comparison", json={
            "trace_id": "tr_split01", "timestamp_ns": 1, "cartridge_id": "CLOUD_DEVOPS",
            "agent_id": "split_benchmark_agent", "steps": [hazard],
        })).json()

    out = run(_stack(body))
    assert out["bypass"]["rows_lost"] == 15420
    assert out["active"]["blocked"] == 1 and out["active"]["committed"] == 0
    assert_valid(out["active"]["steps"][0]["verdict"], "z3_verdict.schema.json")
    assert query("CLOUD_DEVOPS", "SELECT count(*) FROM users") == [(15420,)]
    assert airplane_mode == []


def test_offline_replay_cache_drives_every_scenario(seeded, airplane_mode):
    """OFFLINE_MODE=1 with the committed replay_cache.sqlite: tool calls replayed, CoW + Z3 live."""
    from replay_middleware import CACHE_PATH

    async def body(app, kernel, z3, ws):
        replay = DeterministicReplayMiddleware(path=CACHE_PATH, offline=True, record=False)
        return [await orchestrator.ChronosAgentRunner(cid, "ACTIVE", client=kernel, replay=replay).run()
                for cid in orchestrator.SCENARIOS]

    for result in run(_stack(body)):
        assert result["self_healed"], result["cartridge_id"]
        assert {t["agent_source"] for t in result["turns"]} == {"replay_offline"}
    assert airplane_mode == []
