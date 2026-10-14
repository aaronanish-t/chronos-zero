"""CHRONOS-ZERO kernel interceptor (port 8000).

POST /v1/kernel/execute               Contract 1 in; Contract 3 out (ACTIVE) or an unverified result (BYPASS).
POST /v1/kernel/run-split-comparison  Same steps through BYPASS (on a disposable copy) and ACTIVE, in parallel.
POST /v1/kernel/reset                 One-click stage reset: reseed, clear DAG history, rotate audit chain.
GET  /v1/kernel/audit-log             The verifiable SHA-256 audit chain.
WS   /ws/telemetry                    Contract 4 events for the Multiverse UI.

ACTIVE mode fails closed: if the Z3 verifier is unreachable, errors, or returns anything other
than a valid SAT/UNSAT verdict for this branch, the shadow branch is rolled back.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Literal, Optional

import httpx
import psycopg
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from psycopg import errors as pg_errors
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

REPO_ROOT = str(Path(__file__).resolve().parents[2])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from contracts.schemas import (  # noqa: E402
    InterceptRequest,
    StateDiffRequest,
    TelemetryEvent,
    TelemetryNodePayload,
    ToolCallPayload,
    Z3VerdictResponse,
)
from cow_engine import CARTRIDGE_HANDLERS, CARTRIDGE_IDS, CoWBranchEngine  # noqa: E402
from crypto_audit import AuditChain  # noqa: E402
from saga_ledger import SagaLedger  # noqa: E402

Z3_VERIFY_URL = os.environ.get("CHRONOS_Z3_URL", "http://127.0.0.1:8001/v1/z3/verify")
Z3_TIMEOUT_S = 2.0
ROOT_NODE_ID = "node_root"
MONEY_ARG_KEYS = ("claim_amount_usd", "amount_usd")

# Engineer 3's seeder; must define seed_all() that rebuilds every cartridge DB via CHRONOS_PG_DSN.
SEEDER_PATH = os.environ.get("CHRONOS_SEEDER_PATH") or str(
    Path(REPO_ROOT) / "services" / "cartridges" / "seed_databases.py"
)
RESET_BUDGET_MS = 300.0
RESET_DRAIN_TIMEOUT_S = 2.0
SPLIT_MAX_STEPS = 20


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


class StageGate:
    """Lets a stage reset drain in-flight work and turn away new work while it runs."""

    def __init__(self) -> None:
        self.resetting = False
        self._inflight = 0
        self._idle = asyncio.Event()
        self._idle.set()
        self._reset_lock = asyncio.Lock()

    @asynccontextmanager
    async def work(self) -> AsyncIterator[None]:
        if self.resetting:
            raise HTTPException(status_code=409, detail="stage reset in progress; retry")
        self._inflight += 1
        self._idle.clear()
        try:
            yield
        finally:
            self._inflight -= 1
            if self._inflight == 0:
                self._idle.set()

    @asynccontextmanager
    async def exclusive(self) -> AsyncIterator[None]:
        async with self._reset_lock:
            self.resetting = True
            try:
                try:
                    await asyncio.wait_for(self._idle.wait(), RESET_DRAIN_TIMEOUT_S)
                except asyncio.TimeoutError:
                    pass  # stragglers' pinned branches are rolled back by the reset itself
                yield
            finally:
                self.resetting = False


class SplitComparisonRequest(BaseModel):
    """Not a frozen contract: one scenario (e.g. hazard then self-healed retry) run through both modes."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str
    timestamp_ns: int
    cartridge_id: Literal["HEALTHCARE_FHIR", "FINTECH_ESCROW", "CLOUD_DEVOPS"]
    agent_id: str
    steps: list[ToolCallPayload] = Field(min_length=1, max_length=SPLIT_MAX_STEPS)


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


def _load_seeder(path: str) -> Callable[[], Any]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"seeder not found at {path}")
    spec = importlib.util.spec_from_file_location("chronos_seed_databases", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seed_all = getattr(module, "seed_all", None)
    if not callable(seed_all):
        raise AttributeError(f"{path} does not define seed_all()")
    return seed_all


def create_app(
    z3_verify_url: str = Z3_VERIFY_URL,
    transport: Optional[httpx.AsyncBaseTransport] = None,
    pg_dsn: Optional[str] = None,
    audit_dsn: Optional[str] = None,
    seeder_path: str = SEEDER_PATH,
) -> FastAPI:
    engine = CoWBranchEngine(pg_dsn)
    hub = TelemetryHub()
    audit = AuditChain(audit_dsn)
    saga = SagaLedger()  # compensation registry for non-SQL external API tools
    gate = StageGate()
    # In-memory DAG history: timeline key -> id of that timeline's last production change.
    last_committed_node: dict[str, str] = {}
    seeder: dict[str, Callable[[], Any]] = {}  # loaded on first reset, then cached

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # One persistent HTTP client, one Postgres pool per cartridge, and one for the audit chain.
        await engine.open()
        await audit.open()
        try:
            async with httpx.AsyncClient(timeout=Z3_TIMEOUT_S, transport=transport) as client:
                app.state.z3_client = client
                yield
        finally:
            await engine.close()
            await audit.close()

    app = FastAPI(title="CHRONOS-ZERO Kernel Proxy", version="0.4.0", lifespan=lifespan)
    app.state.engine = engine
    app.state.hub = hub
    app.state.audit = audit
    app.state.saga = saga
    app.state.gate = gate
    app.state.dag_history = last_committed_node

    def _node(req: InterceptRequest, timeline: str, node_id: str, **fields: Any) -> TelemetryNodePayload:
        return TelemetryNodePayload(
            id=node_id,
            parent_id=last_committed_node.get(timeline, ROOT_NODE_ID),
            action_label=f"{req.tool_call.tool_name}({req.tool_call.target_resource})",
            **fields,
        )

    def _handler_for(req: InterceptRequest):
        handler = CARTRIDGE_HANDLERS.get((req.cartridge_id, req.tool_call.tool_name))
        if handler is None:
            raise HTTPException(
                status_code=404,
                detail=f"no handler for tool '{req.tool_call.tool_name}' in cartridge {req.cartridge_id}",
            )
        return handler

    async def _execute_bypass(
        req: InterceptRequest, timeline: str, sandbox_schema: Optional[str] = None
    ) -> dict[str, Any]:
        t0 = time.perf_counter_ns()
        handler = _handler_for(req)
        tool_call = req.tool_call.model_dump()
        state_pre, state_post, _ = await _run_engine(
            engine.execute_direct(req.cartridge_id, handler.state_reader, handler.mutation, tool_call, sandbox_schema)
        )
        total_ms = _elapsed_ms(t0)
        node = _node(
            req,
            timeline,
            f"node_bypass_{uuid.uuid4().hex[:8]}",
            branch_type="BYPASS_CORRUPTED",
            total_latency_ms=total_ms,
            z3_verdict="BYPASS",
            violated_rules=[],
            financial_loss_prevented_usd=0.0,
            clinical_hazard_prevented=False,
        )
        last_committed_node[timeline] = node.id
        await hub.broadcast(TelemetryEvent(
            event_type="BYPASS_CORRUPTED", trace_id=req.trace_id, cartridge_id=req.cartridge_id, node=node,
        ))
        return {
            "trace_id": req.trace_id,
            "chronos_mode": "BYPASS",
            "verified": False,
            "committed": True,
            "node_id": node.id,
            "state_pre": state_pre,
            "state_post": state_post,
            "corruption": _corruption_metrics(state_pre, state_post, tool_call["arguments"]),
            "total_latency_ms": total_ms,
        }

    async def _execute_active(req: InterceptRequest, timeline: str) -> Z3VerdictResponse:
        t0 = time.perf_counter_ns()
        handler = _handler_for(req)
        tool_call = req.tool_call.model_dump()
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
        failure: Optional[str] = None
        try:
            verdict = await _verify(app.state.z3_client, z3_verify_url, diff)
            try:
                # Receipt first: nothing commits without an audit entry.
                await audit.append(req.trace_id, branch_id, verdict.smt2_dump, verdict.status, req.timestamp_ns)
            except Exception as exc:
                failure = f"audit chain append failed: {exc}"
        except Exception as exc:  # fail closed: any verifier problem means no commit
            failure = f"Z3 verification failed: {exc}"
        finally:
            # Always resolve, so the pinned connection (and its row locks) is released.
            # A failed COMMIT (e.g. 40001) is rolled back by the engine and surfaces as 409.
            commit = failure is None and verdict is not None and verdict.status == "SAT"
            await _run_engine(engine.resolve(branch_id, commit))

        if failure is not None:
            raise HTTPException(status_code=503, detail=f"{failure}; shadow branch {branch_id} rolled back")

        unsat = verdict.status == "UNSAT"
        node = _node(
            req,
            timeline,
            f"node_{branch_id}",
            branch_type="SHADOW_REJECTED" if unsat else "COMMITTED_SAFE",
            total_latency_ms=_elapsed_ms(t0),
            z3_verdict=verdict.status,
            violated_rules=[v.rule_id for v in verdict.violated_invariants],
            financial_loss_prevented_usd=_money_at_risk(tool_call["arguments"]) if unsat else 0.0,
            clinical_hazard_prevented=unsat and req.cartridge_id == "HEALTHCARE_FHIR",
        )
        if not unsat:
            last_committed_node[timeline] = node.id
        await hub.broadcast(TelemetryEvent(
            event_type="BRANCH_EVALUATED", trace_id=req.trace_id, cartridge_id=req.cartridge_id, node=node,
        ))
        return verdict

    @app.post("/v1/kernel/execute")
    async def execute(req: InterceptRequest) -> dict[str, Any]:
        async with gate.work():
            if req.chronos_mode == "BYPASS":
                return await _execute_bypass(req, timeline=req.agent_id)
            return (await _execute_active(req, timeline=req.agent_id)).model_dump(mode="json")

    @app.post("/v1/kernel/run-split-comparison")
    async def run_split_comparison(req: SplitComparisonRequest) -> dict[str, Any]:
        """Run the same steps through BYPASS and ACTIVE at the same time for the stage split screen.

        BYPASS runs on a disposable copy of the cartridge DB taken before either lane starts, so
        both lanes begin from identical state and production only ever sees ACTIVE commits.
        Each lane is its own DAG timeline; the UI tells them apart by event_type.
        """
        async with gate.work():
            t0 = time.perf_counter_ns()
            sandbox = await _run_engine(engine.create_disposable_copy(req.cartridge_id))

            def step_request(step: ToolCallPayload, mode: str) -> InterceptRequest:
                return InterceptRequest(
                    trace_id=req.trace_id,
                    timestamp_ns=req.timestamp_ns,
                    cartridge_id=req.cartridge_id,
                    chronos_mode=mode,
                    agent_id=req.agent_id,
                    tool_call=step,
                )

            async def bypass_lane() -> list[dict[str, Any]]:
                results = []
                for i, step in enumerate(req.steps):
                    try:
                        out = await _execute_bypass(step_request(step, "BYPASS"), f"{req.agent_id}:bypass", sandbox)
                        results.append({"step": i, **out})
                    except HTTPException as exc:
                        results.append({"step": i, "status_code": exc.status_code, "error": exc.detail})
                return results

            async def active_lane() -> list[dict[str, Any]]:
                results = []
                for i, step in enumerate(req.steps):
                    try:
                        verdict = await _execute_active(step_request(step, "ACTIVE"), f"{req.agent_id}:active")
                        results.append({"step": i, "verdict": verdict.model_dump(mode="json")})
                    except HTTPException as exc:
                        results.append({"step": i, "status_code": exc.status_code, "error": exc.detail})
                return results

            try:
                bypass_steps, active_steps = await asyncio.gather(bypass_lane(), active_lane())
            finally:
                await _run_engine(engine.drop_disposable_copy(req.cartridge_id, sandbox))

            corrupted = [s for s in bypass_steps if "corruption" in s]
            verdicts = [s["verdict"]["status"] for s in active_steps if "verdict" in s]
            return {
                "trace_id": req.trace_id,
                "cartridge_id": req.cartridge_id,
                "bypass": {
                    "isolated_copy": sandbox,
                    "steps": bypass_steps,
                    "capital_exposed_usd": sum(s["corruption"]["capital_exposed_usd"] for s in corrupted),
                    "rows_lost": sum(s["corruption"]["rows_lost"] for s in corrupted),
                },
                "active": {
                    "steps": active_steps,
                    "blocked": verdicts.count("UNSAT"),
                    "committed": verdicts.count("SAT"),
                },
                "total_latency_ms": _elapsed_ms(t0),
            }

    @app.post("/v1/kernel/reset")
    async def reset() -> dict[str, Any]:
        """One-click stage reset: reseed all cartridges, clear DAG history, rotate the audit chain."""
        if "seed_all" not in seeder:
            try:
                seeder["seed_all"] = _load_seeder(seeder_path)
            except (OSError, AttributeError, ImportError) as exc:
                raise HTTPException(status_code=503, detail=f"cannot reset: {exc}") from exc

        async with gate.exclusive():
            t0 = time.perf_counter_ns()
            rolled_back = await engine.rollback_all()
            try:
                sandboxes_dropped = await engine.drop_all_disposable_copies()
                t_seed = time.perf_counter_ns()
                await run_in_threadpool(seeder["seed_all"])
                seed_ms = _elapsed_ms(t_seed)
                archived = await audit.rotate()
            except Exception as exc:
                raise HTTPException(status_code=503, detail=f"stage reset failed: {exc}") from exc
            last_committed_node.clear()

            reset_ms = _elapsed_ms(t0)
            trace_id = f"tr_reset{uuid.uuid4().hex[:12]}"
            for cartridge_id in CARTRIDGE_IDS:
                await hub.broadcast(TelemetryEvent(
                    event_type="DEMO_RESET",
                    trace_id=trace_id,
                    cartridge_id=cartridge_id,
                    node=TelemetryNodePayload(
                        id=f"node_reset_{uuid.uuid4().hex[:8]}",
                        parent_id=ROOT_NODE_ID,
                        branch_type="SYSTEM_EVENT",
                        action_label="DEMO_RESET",
                        total_latency_ms=reset_ms,
                        z3_verdict="N/A",
                        violated_rules=[],
                        financial_loss_prevented_usd=0.0,
                        clinical_hazard_prevented=False,
                    ),
                ))
            total_ms = _elapsed_ms(t0)
            return {
                "status": "RESET",
                "trace_id": trace_id,
                "reset_latency_ms": total_ms,
                "within_budget": total_ms < RESET_BUDGET_MS,
                "seed_ms": seed_ms,
                "rolled_back_branches": rolled_back,
                "sandboxes_dropped": sandboxes_dropped,
                "archived_audit_chain": archived,
            }

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

    @app.get("/v1/kernel/audit-log")
    async def audit_log() -> dict[str, Any]:
        try:
            return await audit.export()
        except (PoolTimeout, psycopg.Error) as exc:
            raise HTTPException(status_code=503, detail=f"audit chain unavailable: {exc}") from exc

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "resetting" if gate.resetting else "healthy",
            "service": "chronos-kernel-proxy",
            "active_shadow_branches": engine.active_branch_count,
            "telemetry_clients": hub.client_count,
            "z3_verify_url": z3_verify_url,
        }

    return app
