import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

// LLM guardrail round trip the pitch compares against (1,200-2,000 ms; midpoint used).
const LLM_GUARDRAIL_BASELINE_MS = 1450.0;

export interface BenchmarkSummary {
  available: boolean;
  badge_text: string;
  llm_guardrail_baseline_ms: number;
  generated_at?: string;
  platform?: string;
  cycles?: number;
  p50_ms?: number;
  p99_ms?: number;
  fork_p50_ms?: number;
  p50_limit_ms?: number;
  p99_limit_ms?: number;
  gate_passed?: boolean;
  speedup_factor?: number;
}

/**
 * Summarises contracts/benchmark_report.json (written by `make bench`, tests/test_cow_latency.py).
 * Only measured numbers are returned; with no report the badge says so instead of inventing one.
 */
export async function GET() {
  const candidatePaths = [
    path.resolve(process.cwd(), "../../contracts/benchmark_report.json"),
    path.resolve(process.cwd(), "contracts/benchmark_report.json"),
  ];

  for (const filePath of candidatePaths) {
    try {
      if (!fs.existsSync(filePath)) continue;
      const report = JSON.parse(fs.readFileSync(filePath, "utf-8"));
      const gate = report.gate ?? {};
      const sequential = report.runs?.sequential ?? {};
      const p50 = Number(gate.p50_ms);
      if (!Number.isFinite(p50) || p50 <= 0) continue;
      const speedup = Math.round(LLM_GUARDRAIL_BASELINE_MS / p50);
      const summary: BenchmarkSummary = {
        available: true,
        badge_text: `${speedup}x faster than an LLM guardrail`,
        llm_guardrail_baseline_ms: LLM_GUARDRAIL_BASELINE_MS,
        generated_at: report.generated_at,
        platform: report.environment?.platform,
        cycles: sequential.cycles,
        p50_ms: p50,
        p99_ms: Number(gate.p99_ms),
        fork_p50_ms: Number(sequential.phases?.fork_ms?.p50),
        p50_limit_ms: Number(gate.p50_limit_ms),
        p99_limit_ms: Number(gate.p99_limit_ms),
        gate_passed: Boolean(gate.passed),
        speedup_factor: speedup,
      };
      return NextResponse.json(summary);
    } catch {
      // unreadable report: try the next location
    }
  }

  const missing: BenchmarkSummary = {
    available: false,
    badge_text: "Benchmark not measured: run make bench",
    llm_guardrail_baseline_ms: LLM_GUARDRAIL_BASELINE_MS,
  };
  return NextResponse.json(missing);
}
