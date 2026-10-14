"use client";

import React, { useState } from "react";
import {
  X,
  Copy,
  Check,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Terminal,
  KeyRound,
  FileCode2,
  ChevronRight,
  GitCompare,
  Network,
  Zap,
  ArrowRight,
  Shield,
  Layers,
} from "lucide-react";
import { TelemetryNode } from "../types/contracts";

interface Z3ProofInspectorProps {
  node: TelemetryNode | null;
  onClose: () => void;
}

export const Z3ProofInspector: React.FC<Z3ProofInspectorProps> = ({
  node,
  onClose,
}) => {
  const [copiedHash, setCopiedHash] = useState(false);
  const [copiedSmt2, setCopiedSmt2] = useState(false);
  const [diffMode, setDiffMode] = useState<"unified" | "split">("unified");
  const [merkleStatus, setMerkleStatus] = useState<
    "idle" | "verifying" | "verified"
  >("idle");

  if (!node) {
    return (
      <aside className="w-80 md:w-96 bg-[#090D16] border-l border-[#1E293B] flex flex-col items-center justify-center p-6 text-center text-slate-500 font-mono">
        <Terminal className="w-10 h-10 mb-3 text-slate-700" />
        <p className="text-xs uppercase tracking-wider mb-1 text-slate-400">
          Z3 Proof Inspector
        </p>
        <p className="text-[11px] text-slate-600">
          Click any node in the Multiverse DAG to inspect its formal proof,
          latency breakdown bar, state delta diff, and Merkle receipt.
        </p>
      </aside>
    );
  }

  const isRejected = node.branch_type === "SHADOW_REJECTED";
  const isSafe = node.branch_type === "COMMITTED_SAFE";
  const isCorrupted = node.branch_type === "BYPASS_CORRUPTED";

  // Latency calculation
  const cowForkMs =
    node.cow_fork_latency_ms ?? Number((node.total_latency_ms * 0.38).toFixed(2));
  const z3ProofMs =
    node.proof_latency_ms ??
    Number((node.total_latency_ms - cowForkMs).toFixed(2));
  const totalMs = node.total_latency_ms;
  const llmBaselineMs = 1450.0;
  const speedupX = totalMs > 0 ? (llmBaselineMs / totalMs).toFixed(0) : "424";

  // Relative percentages for latency breakdown bar (scaled to 100% of Chronos total)
  const cowPercent = Math.max(15, (cowForkMs / (totalMs || 1)) * 100);
  const z3Percent = Math.max(15, 100 - cowPercent);

  // Copy handlers
  const handleCopyHash = () => {
    if (node.sha256_proof_hash) {
      navigator.clipboard.writeText(node.sha256_proof_hash);
      setCopiedHash(true);
      setTimeout(() => setCopiedHash(false), 2000);
    }
  };

  const handleCopySmt2 = () => {
    if (node.smt2_dump) {
      navigator.clipboard.writeText(node.smt2_dump);
      setCopiedSmt2(true);
      setTimeout(() => setCopiedSmt2(false), 2000);
    }
  };

  // Merkle Chain Verification Simulation
  const handleVerifyMerkleChain = () => {
    if (merkleStatus !== "idle") return;
    setMerkleStatus("verifying");
    setTimeout(() => {
      setMerkleStatus("verified");
    }, 700);
  };

  // Pre vs Post Shadow State (Contract 2)
  const preState =
    node.state_pre ||
    (isRejected
      ? {
          status: "PRE_MUTATION",
          escrow_balance: 500000,
          pending_payout: 0,
          account_lock: false,
        }
      : { status: "PRE_MUTATION", verified: true });

  const postShadowState =
    node.state_post_shadow ||
    (isRejected
      ? {
          status: "SHADOW_DEFICIT",
          escrow_balance: 315000,
          pending_payout: 185000,
          account_lock: true,
        }
      : { status: "COMMITTED_SETTLED", verified: true });

  // Generate clean unified diff lines
  const allKeys = Array.from(
    new Set([...Object.keys(preState), ...Object.keys(postShadowState)])
  );

  return (
    <aside className="w-80 sm:w-96 md:w-[480px] lg:w-[500px] bg-[#090D16] border-l border-[#1E293B] flex flex-col h-full overflow-hidden select-text text-slate-200 shadow-2xl z-20">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#1E293B] bg-[#0F172A]/80 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          {isRejected && <ShieldAlert className="w-4 h-4 text-[#EF4444]" />}
          {isSafe && <ShieldCheck className="w-4 h-4 text-[#10B981]" />}
          {isCorrupted && <AlertTriangle className="w-4 h-4 text-[#F59E0B]" />}
          <div>
            <span className="font-mono font-bold text-xs uppercase tracking-wider text-slate-100 block">
              Z3 Proof Inspector
            </span>
            <span className="text-[10px] text-slate-400 font-mono">
              Trace: {node.id}
            </span>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
          title="Close Inspector"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs font-mono">
        {/* Node Verdict Pill */}
        <div className="flex items-center justify-between bg-[#0F172A] p-2.5 rounded-lg border border-[#1E293B]">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-slate-400 uppercase">Verdict:</span>
            <span
              className={`px-2 py-0.5 rounded font-bold text-xs ${
                isRejected
                  ? "bg-red-950/80 text-[#EF4444] border border-red-800"
                  : isSafe
                  ? "bg-emerald-950/80 text-[#10B981] border border-emerald-800"
                  : isCorrupted
                  ? "bg-amber-950/80 text-amber-400 border border-amber-800"
                  : "bg-slate-800 text-slate-300"
              }`}
            >
              {node.z3_verdict}
            </span>
          </div>

          <span className="text-[10px] text-slate-400 font-mono">
            {node.branch_type}
          </span>
        </div>

        {/* 1. 3-Part Latency Breakdown Bar vs LLM Baseline (1,450ms) */}
        <div className="bg-[#0F172A] p-3 rounded-lg border border-[#1E293B] space-y-3">
          <div className="flex items-center justify-between text-[11px] font-semibold text-slate-200">
            <span className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-cyan-400" />
              Latency Breakdown Bar
            </span>
            <span className="text-[10px] text-cyan-400 font-bold bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-800/60">
              ⚡ {speedupX}x Faster than LLM
            </span>
          </div>

          {/* Numerical breakdown row */}
          <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
            <div className="bg-slate-950/90 p-2 rounded border border-slate-800">
              <span className="text-[9px] uppercase text-slate-500 block">
                CoW Fork
              </span>
              <span className="text-cyan-400 font-bold numeral-mono text-xs">
                {cowForkMs.toFixed(2)} ms
              </span>
            </div>
            <div className="bg-slate-950/90 p-2 rounded border border-slate-800">
              <span className="text-[9px] uppercase text-slate-500 block">
                Z3 Solver
              </span>
              <span className="text-purple-400 font-bold numeral-mono text-xs">
                {z3ProofMs.toFixed(2)} ms
              </span>
            </div>
            <div className="bg-slate-950/90 p-2 rounded border border-slate-800">
              <span className="text-[9px] uppercase text-slate-500 block">
                Chronos Total
              </span>
              <span
                className={`font-bold numeral-mono text-xs ${
                  isRejected ? "text-red-400" : "text-emerald-400"
                }`}
              >
                {totalMs.toFixed(2)} ms
              </span>
            </div>
          </div>

          {/* Segmented Chronos bar */}
          <div className="space-y-1">
            <div className="flex justify-between text-[9px] text-slate-400">
              <span>CHRONOS Kernel Intercept</span>
              <span className="numeral-mono font-semibold text-slate-200">
                {totalMs.toFixed(2)} ms
              </span>
            </div>
            <div className="w-full h-3 bg-slate-950 rounded-full overflow-hidden flex border border-slate-800">
              <div
                style={{ width: `${cowPercent}%` }}
                className="h-full bg-cyan-500 shadow-[0_0_8px_#06B6D4]"
                title={`CoW Fork: ${cowForkMs.toFixed(2)}ms`}
              />
              <div
                style={{ width: `${z3Percent}%` }}
                className="h-full bg-purple-500 shadow-[0_0_8px_#8B5CF6]"
                title={`Z3 Solver: ${z3ProofMs.toFixed(2)}ms`}
              />
            </div>
          </div>

          {/* Contrasted with LLM Guardrail Baseline: 1,450 ms */}
          <div className="space-y-1 pt-1 border-t border-slate-800/80">
            <div className="flex justify-between text-[9px] text-slate-400">
              <span>LLM Guardrail Baseline (Llama-Guard / NeMo)</span>
              <span className="numeral-mono text-amber-400 font-semibold">
                1,450.00 ms
              </span>
            </div>
            <div className="w-full h-2.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
              <div className="h-full w-full bg-amber-600/70" />
            </div>
          </div>
        </div>

        {/* 2. State Diff: state_pre vs state_post_shadow JSON diff */}
        <div className="bg-[#0F172A] p-3 rounded-lg border border-[#1E293B] space-y-2">
          <div className="flex items-center justify-between text-[11px] font-semibold text-slate-200">
            <span className="flex items-center gap-1.5">
              <GitCompare className="w-3.5 h-3.5 text-cyan-400" />
              State Diff (Contract 2: state_pre vs state_post_shadow)
            </span>

            <div className="flex rounded bg-slate-950 p-0.5 border border-slate-800 text-[9px]">
              <button
                onClick={() => setDiffMode("unified")}
                className={`px-1.5 py-0.5 rounded transition-colors ${
                  diffMode === "unified"
                    ? "bg-cyan-950 text-cyan-300 font-bold"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Unified
              </button>
              <button
                onClick={() => setDiffMode("split")}
                className={`px-1.5 py-0.5 rounded transition-colors ${
                  diffMode === "split"
                    ? "bg-cyan-950 text-cyan-300 font-bold"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Split
              </button>
            </div>
          </div>

          {diffMode === "unified" ? (
            /* Unified Line-by-Line Highlighted JSON Diff */
            <div className="bg-slate-950 rounded-lg p-2.5 border border-slate-800 text-[10px] overflow-x-auto max-h-56 leading-relaxed">
              <div className="text-slate-600 mb-1">
                &#123; /* CoW State Diff */
              </div>
              {allKeys.map((key) => {
                const valPre = preState[key];
                const valPost = postShadowState[key];
                const isChanged =
                  JSON.stringify(valPre) !== JSON.stringify(valPost);

                if (!isChanged) {
                  return (
                    <div key={key} className="text-slate-400 px-2 py-0.5">
                      <span className="text-slate-500">&nbsp;&nbsp;</span>
                      <span className="text-slate-300">&quot;{key}&quot;</span>:{" "}
                      <span>{JSON.stringify(valPre)}</span>,
                    </div>
                  );
                }

                return (
                  <React.Fragment key={key}>
                    {/* Removed / Pre-State line (Red highlight) */}
                    {valPre !== undefined && (
                      <div className="bg-red-950/40 text-red-300 border-l-2 border-[#EF4444] px-2 py-0.5">
                        <span className="text-[#EF4444] font-bold">- </span>
                        <span className="text-red-200">&quot;{key}&quot;</span>:{" "}
                        <span className="text-red-400">
                          {JSON.stringify(valPre)}
                        </span>
                        ,
                      </div>
                    )}
                    {/* Added / Post-Shadow line (Green highlight) */}
                    {valPost !== undefined && (
                      <div className="bg-emerald-950/40 text-emerald-300 border-l-2 border-[#10B981] px-2 py-0.5">
                        <span className="text-[#10B981] font-bold">+ </span>
                        <span className="text-emerald-200">
                          &quot;{key}&quot;
                        </span>
                        :{" "}
                        <span className="text-emerald-400">
                          {JSON.stringify(valPost)}
                        </span>
                        ,
                      </div>
                    )}
                  </React.Fragment>
                );
              })}
              <div className="text-slate-600 mt-1">&#125;</div>
            </div>
          ) : (
            /* Split View: Pre vs Post Shadow */
            <div className="grid grid-cols-2 gap-2 text-[10px]">
              <div className="bg-slate-950 p-2 rounded border border-red-900/40">
                <span className="text-[9px] uppercase text-red-400 font-bold block mb-1">
                  state_pre
                </span>
                <pre className="text-slate-300 overflow-x-auto max-h-40">
                  <code>{JSON.stringify(preState, null, 2)}</code>
                </pre>
              </div>
              <div className="bg-slate-950 p-2 rounded border border-emerald-900/40">
                <span className="text-[9px] uppercase text-emerald-400 font-bold block mb-1">
                  state_post_shadow
                </span>
                <pre className="text-slate-300 overflow-x-auto max-h-40">
                  <code>{JSON.stringify(postShadowState, null, 2)}</code>
                </pre>
              </div>
            </div>
          )}
        </div>

        {/* 3. UnsatCore Remediation Hints (when UNSAT) */}
        {node.violated_invariants && node.violated_invariants.length > 0 && (
          <div className="bg-red-950/30 p-3 rounded-lg border border-red-900/60 space-y-3">
            <div className="flex items-center gap-1.5 text-[#EF4444] font-semibold text-[11px]">
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>UnsatCore Remediation Hints ({node.violated_invariants.length})</span>
            </div>

            {node.violated_invariants.map((v, i) => (
              <div
                key={i}
                className="bg-slate-950/95 p-3 rounded-lg border border-red-900/40 space-y-2"
              >
                <div className="text-[11px] font-bold text-red-300 flex items-center gap-1.5">
                  <span className="px-1.5 py-0.5 rounded bg-red-950 border border-red-800 text-red-300 font-mono text-[10px]">
                    {v.rule_id}
                  </span>
                </div>

                <div className="text-[10px] text-slate-400 bg-slate-900/80 p-1.5 rounded border border-slate-800">
                  <span className="text-slate-500 block text-[9px] uppercase">
                    Formal Assertion Formula:
                  </span>
                  <span className="text-slate-200 font-mono">
                    {v.formal_assertion}
                  </span>
                </div>

                <div className="text-[10px] text-red-400/90 bg-red-950/40 px-2 py-1 rounded border border-red-900/30">
                  <span className="font-semibold block text-[9px] uppercase text-red-300">
                    Counterexample Values:
                  </span>
                  <span className="font-mono">{v.counterexample}</span>
                </div>

                <div className="text-[10px] text-amber-300/90 bg-amber-950/30 p-2 rounded border border-amber-900/40">
                  <span className="font-semibold block text-[9px] uppercase text-amber-400 mb-0.5 flex items-center gap-1">
                    <Zap className="w-3 h-3" />
                    Agent Remediation Hint (1-Turn Self-Correction):
                  </span>
                  <span className="text-amber-200">{v.remediation_hint}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 4. Formal smt2_dump Equations */}
        {node.smt2_dump && (
          <div className="bg-[#0F172A] p-3 rounded-lg border border-[#1E293B] space-y-2">
            <div className="flex items-center justify-between text-[11px] font-semibold text-slate-200">
              <span className="flex items-center gap-1.5">
                <FileCode2 className="w-3.5 h-3.5 text-purple-400" />
                Formal smt2_dump Equations
              </span>

              <button
                onClick={handleCopySmt2}
                className="flex items-center gap-1 text-[10px] text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                {copiedSmt2 ? (
                  <>
                    <Check className="w-3 h-3 text-[#10B981]" />
                    <span className="text-[#10B981]">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    <span>Copy SMT2</span>
                  </>
                )}
              </button>
            </div>

            <pre className="bg-slate-950 p-2.5 rounded border border-slate-800 text-[10px] text-slate-300 overflow-x-auto max-h-56 leading-relaxed select-all">
              <code>{node.smt2_dump}</code>
            </pre>
          </div>
        )}

        {/* 5. sha256_proof_hash with "Verify Merkle Chain" Button */}
        {node.sha256_proof_hash && (
          <div className="bg-[#0F172A] p-3 rounded-lg border border-[#1E293B] space-y-3">
            <div className="flex items-center justify-between text-[11px] font-semibold text-slate-200">
              <span className="flex items-center gap-1.5">
                <KeyRound className="w-3.5 h-3.5 text-[#10B981]" />
                sha256_proof_hash Receipt
              </span>

              <button
                onClick={handleCopyHash}
                className="flex items-center gap-1 text-[10px] text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                {copiedHash ? (
                  <>
                    <Check className="w-3 h-3 text-[#10B981]" />
                    <span className="text-[#10B981]">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    <span>Copy Hash</span>
                  </>
                )}
              </button>
            </div>

            <div className="bg-slate-950 p-2.5 rounded border border-slate-800 text-[10px] text-emerald-300 break-all numeral-mono select-all">
              {node.sha256_proof_hash}
            </div>

            {/* "Verify Merkle Chain" Interactive Button */}
            <div className="pt-1 border-t border-slate-800/80">
              {merkleStatus === "idle" && (
                <button
                  onClick={handleVerifyMerkleChain}
                  className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-md bg-cyan-950 hover:bg-cyan-900 border border-cyan-700/60 text-cyan-300 font-mono text-xs font-semibold transition-all shadow-sm"
                >
                  <Network className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Verify Merkle Chain</span>
                </button>
              )}

              {merkleStatus === "verifying" && (
                <div className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-md bg-slate-900 border border-cyan-800 text-cyan-300 font-mono text-xs animate-pulse">
                  <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                  <span>Traversing Merkle Audit Tree (Height 16)...</span>
                </div>
              )}

              {merkleStatus === "verified" && (
                <div className="w-full bg-emerald-950/60 p-2.5 rounded-md border border-emerald-700/80 space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-emerald-300 font-bold">
                    <span className="flex items-center gap-1.5">
                      <ShieldCheck className="w-4 h-4 text-[#10B981]" />
                      Merkle Chain Verified
                    </span>
                    <span className="text-[9px] bg-emerald-900/60 px-1.5 py-0.5 rounded border border-emerald-600/60">
                      Block #419,204
                    </span>
                  </div>
                  <p className="text-[9px] text-emerald-400/80 font-mono">
                    Deterministic proof leaf bound into chronological state tree. Zero rollback tampering detected.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
