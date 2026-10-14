"""DeterministicReplayMiddleware: stage-proof agent tool calls.

Wraps whatever produces the agent's tool call (the LLM; today the scripted scenario functions).
- RECORD_REPLAY=1: every live tool call is saved to replay_cache.sqlite.
- OFFLINE_MODE=1: the cached tool call is returned without calling the LLM at all.
- Online: the live call gets LIVE_TIMEOUT_MS; if it is slower or fails, the cached call is
  returned immediately (if one exists).
Only the agent's tool-call emission is replayed. The kernel's Postgres CoW branch and the Z3
proof still run live on every call.

Record the demo trajectories (Postgres seeded, no kernel needed):
    RECORD_REPLAY=1 python services/cartridges/replay_middleware.py
"""
import asyncio
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Awaitable, Callable

CACHE_PATH = Path(__file__).with_name("replay_cache.sqlite")
LIVE_TIMEOUT_MS = 1200


class ReplayMiss(LookupError):
    """Offline mode with no recorded tool call for this cartridge/scenario/turn."""


class DeterministicReplayMiddleware:
    def __init__(self, path: Path = CACHE_PATH, timeout_ms: float = LIVE_TIMEOUT_MS,
                 offline: bool | None = None, record: bool | None = None):
        self.path = path
        self.timeout_s = timeout_ms / 1000.0
        self.offline = os.environ.get("OFFLINE_MODE") == "1" if offline is None else offline
        self.record = os.environ.get("RECORD_REPLAY") == "1" if record is None else record
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS replay (cartridge_id TEXT, scenario_key TEXT, turn_index INTEGER, "
                "tool_call_json TEXT NOT NULL, recorded_at_ns INTEGER, "
                "PRIMARY KEY (cartridge_id, scenario_key, turn_index))"
            )

    def _get(self, key: tuple) -> dict | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT tool_call_json FROM replay WHERE cartridge_id = ? AND scenario_key = ? AND turn_index = ?", key
            ).fetchone()
        return json.loads(row[0]) if row else None

    def _put(self, key: tuple, tool_call: dict) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT OR REPLACE INTO replay VALUES (?, ?, ?, ?, ?)",
                         (*key, json.dumps(tool_call, sort_keys=True), time.time_ns()))

    async def tool_call(self, cartridge_id: str, scenario_key: str, turn_index: int,
                        live_fn: Callable[[], Awaitable[dict]]) -> tuple[dict, str]:
        """Return (tool_call, source); source is 'live', 'replay_offline', 'replay_timeout' or 'replay_error'."""
        key = (cartridge_id, scenario_key, turn_index)
        # Local file reads/writes go to a thread so they never block the event loop.
        cached = await asyncio.to_thread(self._get, key)
        if self.offline:
            if cached is None:
                raise ReplayMiss(f"OFFLINE_MODE=1 but nothing recorded for {key}")
            return cached, "replay_offline"

        live = asyncio.ensure_future(live_fn())
        done, _ = await asyncio.wait({live}, timeout=self.timeout_s)
        if not done and cached is not None:
            live.cancel()
            return cached, "replay_timeout"
        try:
            result = await live  # no cache to fall back to: wait for the live call however long it takes
        except Exception:
            if cached is None:
                raise
            return cached, "replay_error"
        if self.record:
            await asyncio.to_thread(self._put, key, result)
        return result, "live"


async def record_demo_trajectories() -> list[tuple]:
    """Run every default scenario and judge policy through the scripted agent and save both turns."""
    from orchestrator import ChronosAgentRunner
    from scenarios import SCENARIOS
    from scenarios.judge_policies import JUDGE_POLICIES

    replay = DeterministicReplayMiddleware(offline=False, record=True, timeout_ms=60_000)
    runs = [(cid, None) for cid in SCENARIOS] + [(p["cartridge_id"], p["text"]) for p in JUDGE_POLICIES]
    recorded = []
    for cartridge_id, policy in runs:
        runner = ChronosAgentRunner(cartridge_id, "ACTIVE", policy, replay=replay)
        for turn in (1, 2):
            call, _ = await runner.agent_tool_call(turn)
            recorded.append((cartridge_id, runner.scenario_key, turn, call["tool_name"]))
    return recorded


if __name__ == "__main__":
    # psycopg async (used by Turn 2's safe-state read) can't use Windows' default Proactor loop.
    for row in asyncio.run(record_demo_trajectories(), loop_factory=asyncio.SelectorEventLoop):
        print(*row)
    print(f"recorded into {CACHE_PATH}")
