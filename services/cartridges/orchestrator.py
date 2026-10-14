"""Self-healing agent orchestrator for the three cartridge scenarios.

Turn 1 sends the hazardous tool call a naive agent would make. On UNSAT (ACTIVE mode)
the kernel's violated_invariants go into the message history as a correction prompt,
the agent reads the safe recovery record from the cartridge DB, and Turn 2 re-submits.

Run: python services/cartridges/orchestrator.py   (serves POST /v1/agent/run-scenario on :8002)
"""
import asyncio
import json
import os
import time
import uuid
from typing import Literal, Optional

import httpx
import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from scenarios import SCENARIOS
from seed_databases import db_dsn

KERNEL_URL = os.environ.get("CHRONOS_KERNEL_URL", "http://localhost:8000") + "/v1/kernel/execute"
AGENT_ID = "agent_e3_orchestrator"

CartridgeId = Literal["HEALTHCARE_FHIR", "FINTECH_ESCROW", "CLOUD_DEVOPS"]
ChronosMode = Literal["ACTIVE", "BYPASS"]


# shortcut: tool calls are scripted per scenario, not LLM-generated; swap in the LLM + DeterministicReplayMiddleware here.


def correction_prompt(verdict: dict) -> str:
    rules = "\n".join(
        f"- {v['rule_id']}: {v['formal_assertion']} | counterexample: {v['counterexample']} | fix: {v['remediation_hint']}"
        for v in verdict["violated_invariants"]
    )
    return (
        f"CHRONOS KERNEL INTERCEPTION (UNSAT in {verdict['proof_latency_ms']}ms): Your action was rolled back in "
        f"shadow branch {verdict['shadow_branch_id']}. Violated Invariants: {json.dumps(verdict['violated_invariants'])}.\n"
        f"{rules}\nRe-issue the tool call immediately satisfying all remediation hints."
    )


class ChronosAgentRunner:
    def __init__(self, cartridge_id: CartridgeId, chronos_mode: ChronosMode, custom_prompt: Optional[str] = None,
                 client: Optional[httpx.AsyncClient] = None):
        if cartridge_id not in SCENARIOS:
            raise ValueError(f"unknown cartridge_id: {cartridge_id}")
        self.cartridge_id = cartridge_id
        self.chronos_mode = chronos_mode
        self.scenario = SCENARIOS[cartridge_id]
        self.prompt = custom_prompt or self.scenario.PROMPT
        self.trace_id = f"tr_{uuid.uuid4().hex[:12]}"
        self.client = client
        self.messages: list[dict] = [{"role": "user", "content": self.prompt}]

    async def _execute(self, client: httpx.AsyncClient, tool_call: dict) -> dict:
        payload = {
            "trace_id": self.trace_id,
            "timestamp_ns": time.time_ns(),
            "cartridge_id": self.cartridge_id,
            "chronos_mode": self.chronos_mode,
            "agent_id": AGENT_ID,
            "tool_call": tool_call,
        }
        self.messages.append({"role": "assistant", "tool_call": tool_call})
        resp = await client.post(KERNEL_URL, json=payload, timeout=10.0)
        resp.raise_for_status()
        verdict = resp.json()
        self.messages.append({"role": "tool", "content": verdict})
        return verdict

    async def _read_safe_state(self) -> dict:
        async with await psycopg.AsyncConnection.connect(db_dsn(self.cartridge_id), connect_timeout=3) as conn:
            await conn.set_read_only(True)
            return await self.scenario.heal(conn)

    async def run(self) -> dict:
        client = self.client or httpx.AsyncClient()
        turns = []
        try:
            hazard = self.scenario.hazard()
            turns.append({"turn": 1, "tool_call": hazard, "verdict": await self._execute(client, hazard)})
            first = turns[0]["verdict"]
            if self.chronos_mode == "ACTIVE" and first.get("status") == "UNSAT":
                self.messages.append({"role": "system", "priority": "high", "content": correction_prompt(first)})
                corrected = await self._read_safe_state()
                turns.append({"turn": 2, "tool_call": corrected, "verdict": await self._execute(client, corrected)})
        finally:
            if self.client is None:
                await client.aclose()
        return {
            "trace_id": self.trace_id,
            "cartridge_id": self.cartridge_id,
            "chronos_mode": self.chronos_mode,
            "turns": turns,
            "self_healed": len(turns) == 2 and turns[1]["verdict"].get("status") == "SAT",
            "messages": self.messages,
        }


class RunScenarioRequest(BaseModel):
    cartridge_id: CartridgeId
    chronos_mode: ChronosMode = "ACTIVE"
    custom_prompt: Optional[str] = None


app = FastAPI(title="Chronos-Zero Agent Orchestrator")
# The Next.js UI calls this from the browser, on a different port.
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_methods=["POST"], allow_headers=["Content-Type"])


@app.post("/v1/agent/run-scenario")
async def run_scenario(req: RunScenarioRequest) -> dict:
    try:
        return await ChronosAgentRunner(req.cartridge_id, req.chronos_mode, req.custom_prompt).run()
    except httpx.HTTPStatusError as exc:
        # Pass the kernel's own rejection (404 unknown tool, 400 bad call, 503 verifier down) to the UI.
        raise HTTPException(status_code=502, detail={"kernel_status": exc.response.status_code,
                                                     "kernel_detail": exc.response.text})
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"kernel unreachable: {exc!r}")
    except psycopg.Error as exc:
        raise HTTPException(status_code=500, detail=f"cartridge DB not ready (run seed_databases.py): {exc}")


if __name__ == "__main__":
    import uvicorn

    # uvicorn picks the Proactor loop on Windows, which async psycopg can't use.
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8002))
    asyncio.run(server.serve(), loop_factory=asyncio.SelectorEventLoop)
