"""CoW + Z3 latency benchmark (AGENTS.md §5 gate: P50 < 3.5ms, P99 < 8.0ms).

Run: make bench   (or: pytest tests/test_cow_latency.py -s)

Measures the kernel's own work per cycle, in process:
  fork      CoW branch fork (pooled connection, REPEATABLE READ txn, SAVEPOINT) + state diff extraction
  z3        Z3 proof generation (prover_core called directly, no HTTP hop to :8001)
  resolve   RELEASE + COMMIT on SAT, ROLLBACK on UNSAT
  total     wall time of the whole cycle

Storage is PostgreSQL 16 (AGENTS.md §4.1 supersedes the original /dev/shm SQLite plan).
The gate applies to the sequential run's total. The concurrent run is reported, not gated:
with 50 branches in flight, its totals include time queued behind the other branches.
Results go to contracts/benchmark_report.json for the UI header.
"""

import asyncio
import json
import math
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import psycopg
import z3

import prover_core
from contracts.schemas import StateDiffRequest
from cow_engine import CARTRIDGE_HANDLERS, CoWBranchEngine
from pg_support import cartridge_dsn, reset_databases, run

SEQUENTIAL_CYCLES = 500
CONCURRENT_CYCLES = 50
WARMUP_CYCLES = 20
P50_GATE_MS = 3.5
P99_GATE_MS = 8.0
REPORT_PATH = Path(__file__).resolve().parents[1] / "contracts" / "benchmark_report.json"

PHASES = (
    ("fork_ms", "CoW Savepoint Fork + State Diff Extraction"),
    ("z3_ms", "Z3 SMT Solver Proof Generation"),
    ("resolve_ms", "Savepoint Commit / Rollback Resolution"),
    ("total_ms", "Total End-to-End Kernel Overhead"),
)


def _tool_call(tool_name: str, target: str, **arguments: Any) -> dict[str, Any]:
    return {"tool_name": tool_name, "target_resource": target, "arguments": arguments}


# Each cartridge alternates an unsafe call (UNSAT -> rollback) with a safe one (SAT -> commit).
WORKLOADS: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    "HEALTHCARE_FHIR": (
        _tool_call("prescribe_medication_and_submit_claim", "Patient/pat_402", drug_name="Metformin",
                   daily_dose_mg=2500, claim_amount_usd=1450.0, conservative_therapy_weeks_documented=2),
        _tool_call("prescribe_medication_and_submit_claim", "Patient/pat_402", drug_name="Linagliptin",
                   daily_dose_mg=5, claim_amount_usd=1450.0, conservative_therapy_weeks_documented=2,
                   attached_encounter_ids=["Encounter/enc_108"]),
    ),
    "FINTECH_ESCROW": (
        _tool_call("wire_transfer", "Vendor/vnd_spoof", amount_usd=12000.0),
        _tool_call("wire_transfer", "Vendor/vnd_verified", amount_usd=1.0),
    ),
    "CLOUD_DEVOPS": (
        _tool_call("update_security_group", "SecurityGroup/sg_prod", sg_id="sg_prod", port=22, cidr="0.0.0.0/0"),
        _tool_call("update_security_group", "SecurityGroup/sg_prod", sg_id="sg_prod", port=443, cidr="10.0.0.0/8"),
    ),
}


def _z3_backend() -> tuple[Callable[[dict[str, Any]], str], tuple[str, ...]]:
    """Use E2's dispatch_verification when present (all cartridges), else the healthcare-only prover."""
    if hasattr(prover_core, "dispatch_verification"):
        return (lambda diff: prover_core.dispatch_verification(StateDiffRequest(**diff)).status), tuple(WORKLOADS)
    return (lambda diff: prover_core.verify_state_diff(diff)["status"]), ("HEALTHCARE_FHIR",)


VERIFY, SEQUENTIAL_CARTRIDGES = _z3_backend()


async def _cycle(engine: CoWBranchEngine, cartridge_id: str, tool_call: dict[str, Any], index: int) -> dict[str, float]:
    handler = CARTRIDGE_HANDLERS[(cartridge_id, tool_call["tool_name"])]
    t0 = time.perf_counter_ns()
    branch_id, pre, post, fork_ms = await engine.fork_and_mutate(
        cartridge_id, handler.state_reader, handler.mutation, tool_call
    )
    tz = time.perf_counter_ns()
    status = VERIFY({
        "trace_id": f"tr_bench{index}", "shadow_branch_id": branch_id, "cartridge_id": cartridge_id,
        "cow_fork_latency_ms": fork_ms, "state_pre": pre, "state_post_shadow": post,
    })
    z3_ms = (time.perf_counter_ns() - tz) / 1_000_000.0
    resolve_ms = await engine.resolve(branch_id, commit=status == "SAT")
    return {
        "fork_ms": fork_ms,
        "z3_ms": z3_ms,
        "resolve_ms": resolve_ms,
        "total_ms": (time.perf_counter_ns() - t0) / 1_000_000.0,
        "status": status,
    }


def _workload(i: int, cartridges: tuple[str, ...]) -> tuple[str, dict[str, Any]]:
    cartridge_id = cartridges[i % len(cartridges)]
    return cartridge_id, WORKLOADS[cartridge_id][(i // len(cartridges)) % 2]


ROUNDTRIP_SAMPLES = 200


async def _db_roundtrips(engine: CoWBranchEngine) -> list[float]:
    """Baseline: one `SELECT 1` round trip on this machine. A fork costs several of these, so this
    separates the host's network/virtualization cost from the kernel's own work."""
    samples = []
    async with engine._pools["HEALTHCARE_FHIR"].connection() as conn:
        for _ in range(ROUNDTRIP_SAMPLES):
            t0 = time.perf_counter_ns()
            await conn.execute("SELECT 1")
            samples.append((time.perf_counter_ns() - t0) / 1_000_000.0)
        await conn.rollback()
    return samples


async def _benchmark(dsn: str) -> dict[str, Any]:
    engine = CoWBranchEngine(dsn)
    await engine.open()
    try:
        roundtrips = await _db_roundtrips(engine)
        for i in range(WARMUP_CYCLES):  # pool connections, Z3 context, plan caches
            await _cycle(engine, *_workload(i, SEQUENTIAL_CARTRIDGES), i)
        sequential = [
            await _cycle(engine, *_workload(i, SEQUENTIAL_CARTRIDGES), i) for i in range(SEQUENTIAL_CYCLES)
        ]
        # Concurrent writers on one treasury / security-group row serialize by design under
        # REPEATABLE READ, so the concurrent run uses the insert-only healthcare workload.
        concurrent = await asyncio.gather(*(
            _cycle(engine, *_workload(i, ("HEALTHCARE_FHIR",)), SEQUENTIAL_CYCLES + i) for i in range(CONCURRENT_CYCLES)
        ))
    finally:
        await engine.close()
    return {"roundtrips": roundtrips, "runs": {"sequential": sequential, "concurrent": list(concurrent)}}


def _percentile(sorted_values: list[float], q: float) -> float:
    """Nearest-rank percentile."""
    return sorted_values[max(0, math.ceil(q * len(sorted_values)) - 1)]


def _stats(samples: list[dict[str, float]], key: str) -> dict[str, float]:
    values = sorted(s[key] for s in samples)
    return {
        "min": round(values[0], 3),
        "p50": round(_percentile(values, 0.50), 3),
        "p90": round(_percentile(values, 0.90), 3),
        "p99": round(_percentile(values, 0.99), 3),
        "max": round(values[-1], 3),
    }


def _table(title: str, phases: dict[str, dict[str, float]]) -> str:
    label_width = max(len(label) for _, label in PHASES)
    columns = ("min", "p50", "p90", "p99", "max")
    rule = "+" + "-" * (label_width + 2) + "+" + "+".join("-" * 10 for _ in columns) + "+"
    header = f"| {title:<{label_width}} |" + "|".join(f"{c.upper():>9} " for c in columns) + "|"
    rows = [
        f"| {label:<{label_width}} |" + "|".join(f"{phases[key][c]:>9.3f} " for c in columns) + "|"
        for key, label in PHASES
    ]
    return "\n".join([rule, header, rule, *rows, rule])


def _postgres_version(dsn: str) -> str:
    with psycopg.connect(dsn, autocommit=True) as conn:
        return conn.execute("SHOW server_version").fetchone()[0]


def test_cow_z3_latency_gate():
    dsn = reset_databases()
    measured = run(_benchmark(dsn))
    results = measured["runs"]
    roundtrip = _stats([{"rt": v} for v in measured["roundtrips"]], "rt")

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": {
            "platform": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "postgres": _postgres_version(cartridge_dsn("HEALTHCARE_FHIR")),
            "z3": z3.get_version_string(),
            "z3_mode": "in-process prover_core (excludes HTTP hop to the :8001 verifier)",
            "db_roundtrip_ms": roundtrip,  # SELECT 1 baseline for this host
            "unit": "ms",
        },
        "runs": {},
    }
    tables = []
    for run_name, samples in results.items():
        phases = {key: _stats(samples, key) for key, _ in PHASES}
        cartridges = SEQUENTIAL_CARTRIDGES if run_name == "sequential" else ("HEALTHCARE_FHIR",)
        statuses = [s["status"] for s in samples]
        report["runs"][run_name] = {
            "cycles": len(samples),
            "cartridges": list(cartridges),
            "verdicts": {"SAT": statuses.count("SAT"), "UNSAT": statuses.count("UNSAT")},
            "phases": phases,
        }
        tables.append(_table(f"{run_name.capitalize()} (n={len(samples)})", phases))

    total = report["runs"]["sequential"]["phases"]["total_ms"]
    report["gate"] = {
        "applies_to": "sequential.total_ms",
        "p50_limit_ms": P50_GATE_MS,
        "p99_limit_ms": P99_GATE_MS,
        "p50_ms": total["p50"],
        "p99_ms": total["p99"],
        "passed": total["p50"] < P50_GATE_MS and total["p99"] < P99_GATE_MS,
    }
    # Written before asserting, so a failing run still leaves its numbers for the UI and the team.
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")

    print("\n" + "\n\n".join(tables))
    print(f"\nDB round trip baseline (SELECT 1): P50 {roundtrip['p50']}ms, P99 {roundtrip['p99']}ms")
    print(f"\nGate (sequential total): P50 {total['p50']}ms < {P50_GATE_MS}ms, "
          f"P99 {total['p99']}ms < {P99_GATE_MS}ms -> {'PASS' if report['gate']['passed'] else 'FAIL'}")
    print(f"Report: {REPORT_PATH}")

    assert all(s["status"] in ("SAT", "UNSAT") for run_samples in results.values() for s in run_samples)
    assert total["p50"] < P50_GATE_MS, f"P50 {total['p50']}ms >= {P50_GATE_MS}ms"
    assert total["p99"] < P99_GATE_MS, f"P99 {total['p99']}ms >= {P99_GATE_MS}ms"
