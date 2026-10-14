"""CHRONOS-ZERO kernel interceptor (port 8000).

POST /v1/kernel/execute  Contract 1 in; Contract 3 out (ACTIVE) or an unverified result (BYPASS).
WS   /ws/telemetry       Contract 4 events for the Multiverse UI.

ACTIVE mode fails closed: if the Z3 verifier is unreachable, errors, or returns anything other
than a valid SAT/UNSAT verdict for this branch, the shadow branch is rolled back.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Awaitable, Optional

import httpx
import psycopg
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from psycopg import errors as pg_errors
from psycopg_pool import PoolTimeout

REPO_ROOT = str(Path(__file__).resolve().parents[2])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from contracts.schemas import (  # noqa: E402
    InterceptRequest,
    StateDiffRequest,
    TelemetryEvent,
    TelemetryNodePayload,
    Z3VerdictResponse,
)
from cow_engine import CARTRIDGE_HANDLERS, CoWBranchEngine  # noqa: E402

Z3_VERIFY_URL = os.environ.get("CHRONOS_Z3_URL", "http://127.0.0.1:8001/v1/z3/verify")
Z3_TIMEOUT_S = 2.0
ROOT_NODE_ID = "node_root"
MONEY_ARG_KEYS = ("claim_amount_usd", "amount_usd")


class TelemetryHub:
    """Fan-out of Contract 4 events to every connected WebSocket client."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, event: TelemetryEvent) -> None:
        message = event.model_dump(mode="json")
        for ws in list(self._clients):
            try:
                await ws.send_json(message)
            except Exception:
                self._clients.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)


def _elapsed_ms(t0_ns: int) -> float:
    return round((time.perf_counter_ns() - t0_ns) / 1_000_000.0, 3)


def _money_at_risk(arguments: dict[str, Any]) -> float:
    for key in MONEY_ARG_KEYS:
        if key in arguments:
            return max(0.0, float(arguments[key]))
    return 0.0


def _corruption_metrics(state_pre: dict[str, Any], state_post: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    rows_lost = 0
    if "prod_table_row_count" in state_pre:
        rows_lost = max(0, int(state_pre["prod_table_row_count"]) - int(state_post.get("prod_table_row_count", 0)))
    return {
        "changed_fields": {
            k: {"pre": state_pre.get(k), "post": v} for k, v in state_post.items() if state_pre.get(k) != v
        },
        "capital_exposed_usd": _money_at_risk(arguments),
        "rows_lost": rows_lost,
    }


# Concurrency conflicts: another branch holds or already changed the rows (AGENTS.md §4.1).
_CONFLICT_ERRORS = (pg_errors.SerializationFailure, pg_errors.LockNotAvailable, pg_errors.QueryCanceled)


async def _run_engine(call: Awaitable[Any]) -> Any:
    """Await an engine operation and map tool/database errors to HTTP errors.

    The engine has already rolled the transaction back when any of these surface.
    """
    try:
        return await call
    except PoolTimeout as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
    except (LookupError, ValueError, TypeError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=f"tool call rejected: {exc}") from exc
    except _CONFLICT_ERRORS as exc:
        raise HTTPException(status_code=409, detail=f"conflicting branch, rolled back: {exc}") from exc
    except psycopg.Error as exc:
        raise HTTPException(status_code=422, detail=f"mutation failed: {exc}") from exc


async def _verify(client: httpx.AsyncClient, url: str, diff: StateDiffRequest) -> Z3VerdictResponse:
    response = await client.post(url, json=diff.model_dump(mode="json"))
    response.raise_for_status()
    verdict = Z3VerdictResponse.model_validate(response.json())
    if verdict.trace_id != diff.trace_id or verdict.shadow_branch_id != diff.shadow_branch_id:
        raise ValueError("verdict does not match the shadow branch it was requested for")
    return verdict


def create_app(
    z3_verify_url: str = Z3_VERIFY_URL,
    transport: Optional[httpx.AsyncBaseTransport] = None,
    pg_dsn: Optional[str] = None,
) -> FastAPI:
    engine = CoWBranchEngine(pg_dsn)
    hub = TelemetryHub()
    last_committed_node: dict[str, str] = {}  # agent_id -> id of the agent's last production change

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # One persistent HTTP client and one Postgres pool per cartridge for the life of the service.
        await engine.open()
        try:
            async with httpx.AsyncClient(timeout=Z3_TIMEOUT_S, transport=transport) as client:
                app.state.z3_client = client
                yield
        finally:
            await engine.close()

    app = FastAPI(title="CHRONOS-ZERO Kernel Proxy", version="0.2.0", lifespan=lifespan)
    app.state.engine = engine
    app.state.hub = hub

    def _node(req: InterceptRequest, node_id: str, **fields: Any) -> TelemetryNodePayload:
        return TelemetryNodePayload(
            id=node_id,
            parent_id=last_committed_node.get(req.agent_id, ROOT_NODE_ID),
            action_label=f"{req.tool_call.tool_name}({req.tool_call.target_resource})",
            **fields,
        )

    @app.post("/v1/kernel/execute")
    async def execute(req: InterceptRequest) -> dict[str, Any]:
        t0 = time.perf_counter_ns()
        handler = CARTRIDGE_HANDLERS.get((req.cartridge_id, req.tool_call.tool_name))
        if handler is None:
            raise HTTPException(
                status_code=404,
                detail=f"no handler for tool '{req.tool_call.tool_name}' in cartridge {req.cartridge_id}",
            )
        tool_call = req.tool_call.model_dump()
        arguments = tool_call["arguments"]

        if req.chronos_mode == "BYPASS":
            state_pre, state_post, _ = await _run_engine(
                engine.execute_direct(req.cartridge_id, handler.state_reader, handler.mutation, tool_call)
            )
            total_ms = _elapsed_ms(t0)
            node = _node(
                req,
                f"node_bypass_{uuid.uuid4().hex[:8]}",
                branch_type="BYPASS_CORRUPTED",
                total_latency_ms=total_ms,
                z3_verdict="BYPASS",
                violated_rules=[],
                financial_loss_prevented_usd=0.0,
                clinical_hazard_prevented=False,
            )
            last_committed_node[req.agent_id] = node.id
            await hub.broadcast(TelemetryEvent(
                event_type="BYPASS_CORRUPTED", trace_id=req.trace_id, cartridge_id=req.cartridge_id, node=node,
            ))
            return {
                "trace_id": req.trace_id,
                "chronos_mode": "BYPASS",
                "verified": False,
                "committed": True,
                "state_pre": state_pre,
                "state_post": state_post,
                "corruption": _corruption_metrics(state_pre, state_post, arguments),
                "total_latency_ms": total_ms,
            }

        # ACTIVE: fork -> verify -> resolve.
        branch_id, state_pre, state_post, fork_ms = await _run_engine(
            engine.fork_and_mutate(req.cartridge_id, handler.state_reader, handler.mutation, tool_call)
        )
        diff = StateDiffRequest(
            trace_id=req.trace_id,
            shadow_branch_id=branch_id,
            cartridge_id=req.cartridge_id,
            cow_fork_latency_ms=fork_ms,
            state_pre=state_pre,
            state_post_shadow=state_post,
        )

        verdict: Optional[Z3VerdictResponse] = None
        verify_error: Optional[Exception] = None
        try:
            verdict = await _verify(app.state.z3_client, z3_verify_url, diff)
        except Exception as exc:  # fail closed: any verifier problem means no commit
            verify_error = exc
        finally:
            # Always resolve, so the pinned connection (and its row locks) is released.
            # A failed COMMIT (e.g. 40001) is rolled back by the engine and surfaces as 409.
            await _run_engine(engine.resolve(branch_id, verdict is not None and verdict.status == "SAT"))

        if verdict is None:
            raise HTTPException(
                status_code=503,
                detail=f"Z3 verification failed; shadow branch {branch_id} rolled back: {verify_error}",
            )

        unsat = verdict.status == "UNSAT"
        node = _node(
            req,
            f"node_{branch_id}",
            branch_type="SHADOW_REJECTED" if unsat else "COMMITTED_SAFE",
            total_latency_ms=_elapsed_ms(t0),
            z3_verdict=verdict.status,
            violated_rules=[v.rule_id for v in verdict.violated_invariants],
            financial_loss_prevented_usd=_money_at_risk(arguments) if unsat else 0.0,
            clinical_hazard_prevented=unsat and req.cartridge_id == "HEALTHCARE_FHIR",
        )
        if not unsat:
            last_committed_node[req.agent_id] = node.id
        await hub.broadcast(TelemetryEvent(
            event_type="BRANCH_EVALUATED", trace_id=req.trace_id, cartridge_id=req.cartridge_id, node=node,
        ))
        return verdict.model_dump(mode="json")

    @app.websocket("/ws/telemetry")
    async def telemetry(ws: WebSocket) -> None:
        await hub.connect(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            hub.disconnect(ws)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "service": "chronos-kernel-proxy",
            "active_shadow_branches": engine.active_branch_count,
            "telemetry_clients": hub.client_count,
            "z3_verify_url": z3_verify_url,
        }

    return app
