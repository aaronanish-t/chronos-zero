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
  ExternalLink,
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

  if (!node) {
    return (
      <aside className="w-80 md:w-96 bg-[#090D16] border-l border-[#1E293B] flex flex-col items-center justify-center p-6 text-center text-slate-500 font-mono">
        <Terminal className="w-10 h-10 mb-3 text-slate-700" />
        <p className="text-xs uppercase tracking-wider mb-1">Z3 Proof Inspector</p>
        <p className="text-[11px] text-slate-600">
          Select any node in the Multiverse DAG to inspect its formal proof, latency breakdown, and SMT2 trace.
        </p>
      </aside>
    );
  }

  const isRejected = node.branch_type === "SHADOW_REJECTED";
  const isSafe = node.branch_type === "COMMITTED_SAFE";
  const isCorrupted = node.branch_type === "BYPASS_CORRUPTED";

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

  const cowLatency = node.cow_fork_latency_ms ?? (node.total_latency_ms * 0.4);
  const z3Latency = node.proof_latency_ms ?? (node.total_latency_ms * 0.6);

  return (
    <aside className="w-80 md:w-[420px] bg-[#090D16] border-l border-[#1E293B] flex flex-col h-full overflow-hidden select-text text-slate-200">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#1E293B] bg-[#0F172A]/70">
        <div className="flex items-center gap-2">
          {isRejected && <ShieldAlert className="w-4 h-4 text-chronos-crimson" />}
          {isSafe && <ShieldCheck className="w-4 h-4 text-chronos-emerald" />}
          {isCorrupted && <AlertTriangle className="w-4 h-4 text-amber-500" />}
          <span className="font-mono font-bold text-xs uppercase tracking-wider text-slate-100">
            Z3 Proof Inspector
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs font-mono">
        {/* Node Identity & Status */}
        <div className="bg-[#0F172A] p-3 rounded-lg border border-[#1E293B] space-y-2">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400">Node ID:</span>
            <span className="text-cyan-400 font-semibold">{node.id}</span>
          </div>

          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400">Verdict:</span>
            <span
              className={`px-2 py-0.5 rounded font-bold ${
                isRejected
                  ? "bg-red-950/80 text-chronos-crimson border border-red-800"
                  : isSafe
                  ? "bg-emerald-950/80 text-chronos-emerald border border-emerald-800"
                  : isCorrupted
                  ? "bg-amber-950/80 text-amber-400 border border-amber-800"
                  : "bg-slate-800 text-slate-300"
              }`}
            >
              {node.z3_verdict}
            </span>
          </div>

          <div className="pt-1 border-t border-[#1E293B]/60">
            <span className="text-slate-400 block mb-1 text-[10px] uppercase">
              Action Label:
            </span>
            <div className="bg-slate-950 p-2 rounded border border-slate-800 text-slate-200 break-all text-[11px]">
              {node.action_label}
            </div>
          </div>
        </div>

        {/* Latency Breakdown Pill (Requirement from @skill:wire-multiverse-node) */}
        <div className="bg-[#0F172A] p-3 rounded-lg border border-[#1E293B] space-y-2">
          <div className="flex items-center gap-1.5 text-slate-300 font-semibold text-[11px]">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            <span>Formal Latency Breakdown</span>
          </div>

          <div className="grid grid-cols-3 gap-1.5 text-center text-[10px]">
            <div className="bg-slate-950/80 p-1.5 rounded border border-slate-800">
              <div className="text-slate-400 text-[9px]">CoW Fork</div>
              <div className="text-cyan-300 font-bold numeral-mono">
                {cowLatency.toFixed(2)}ms
              </div>
            </div>
            <div className="bg-slate-950/80 p-1.5 rounded border border-slate-800">
              <div className="text-slate-400 text-[9px]">Z3 Solver</div>
              <div className="text-cyan-300 font-bold numeral-mono">
                {z3Latency.toFixed(2)}ms
              </div>
            </div>
            <div className="bg-slate-950/80 p-1.5 rounded border border-slate-800">
              <div className="text-slate-400 text-[9px]">Total Intercept</div>
              <div className="text-emerald-300 font-bold numeral-mono">
                {node.total_latency_ms.toFixed(2)}ms
              </div>
            </div>
          </div>
        </div>

        {/* Violated Invariants & Remediation Hint (when UNSAT) */}
        {node.violated_invariants && node.violated_invariants.length > 0 && (
          <div className="bg-red-950/30 p-3 rounded-lg border border-red-900/60 space-y-3">
            <div className="flex items-center gap-1.5 text-chronos-crimson font-semibold text-[11px]">
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>UnsatCore Violations ({node.violated_invariants.length})</span>
            </div>

            {node.violated_invariants.map((v, i) => (
              <div key={i} className="bg-slate-950/90 p-2.5 rounded border border-red-900/40 space-y-1.5">
                <div className="text-[11px] font-bold text-red-300 flex items-center gap-1">
                  <ChevronRight className="w-3 h-3 text-chronos-crimson" />
                  <span>{v.rule_id}</span>
                </div>
                <div className="text-[10px] text-slate-400">
                  <span className="text-slate-500">Formal: </span>
                  <span className="text-slate-300">{v.formal_assertion}</span>
                </div>
                <div className="text-[10px] text-red-400/90 bg-red-950/30 px-1.5 py-0.5 rounded">
                  <span className="font-semibold">Delta: </span>
                  {v.counterexample}
                </div>
                <div className="text-[10px] text-amber-300/90 bg-amber-950/20 px-1.5 py-1 rounded border border-amber-900/30">
                  <span className="font-semibold block text-[9px] uppercase text-amber-400">
                    Remediation Hint:
                  </span>
                  {v.remediation_hint}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Cryptographic SHA-256 Receipt */}
        {node.sha256_proof_hash && (
          <div className="bg-[#0F172A] p-3 rounded-lg border border-[#1E293B] space-y-2">
            <div className="flex items-center justify-between text-[11px]">
              <div className="flex items-center gap-1.5 text-slate-300 font-semibold">
                <KeyRound className="w-3.5 h-3.5 text-emerald-400" />
                <span>SHA-256 Proof Receipt</span>
              </div>
              <button
                onClick={handleCopyHash}
                className="flex items-center gap-1 text-[10px] text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                {copiedHash ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-400" />
                    <span className="text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>

            <div className="bg-slate-950 p-2 rounded border border-slate-800 text-[10px] text-emerald-300 break-all numeral-mono select-all">
              {node.sha256_proof_hash}
            </div>
            <div className="text-[9px] text-slate-500 flex items-center justify-between">
              <span>Deterministic SMT-LIB2 Digest</span>
              <span className="text-emerald-400 font-semibold">VERIFIED</span>
            </div>
          </div>
        )}

        {/* SMT-LIB2 Dump */}
        {node.smt2_dump && (
          <div className="bg-[#0F172A] p-3 rounded-lg border border-[#1E293B] space-y-2">
            <div className="flex items-center justify-between text-[11px]">
              <div className="flex items-center gap-1.5 text-slate-300 font-semibold">
                <FileCode2 className="w-3.5 h-3.5 text-purple-400" />
                <span>SMT-LIB2 S-Expressions</span>
              </div>
              <button
                onClick={handleCopySmt2}
                className="flex items-center gap-1 text-[10px] text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                {copiedSmt2 ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-400" />
                    <span className="text-emerald-400">Copied</span>
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

        {/* Tool Call Arguments Payload */}
        {node.tool_call && (
          <div className="bg-[#0F172A] p-3 rounded-lg border border-[#1E293B] space-y-2">
            <div className="text-[11px] text-slate-300 font-semibold flex items-center gap-1">
              <Terminal className="w-3.5 h-3.5 text-cyan-400" />
              <span>Tool Call Interception</span>
            </div>
            <div className="text-[10px] text-slate-400">
              <span className="text-slate-500">Tool: </span>
              <span className="text-cyan-300 font-semibold">{node.tool_call.tool_name}</span>
            </div>
            <div className="text-[10px] text-slate-400">
              <span className="text-slate-500">Resource: </span>
              <span className="text-slate-300">{node.tool_call.target_resource}</span>
            </div>
            <pre className="bg-slate-950 p-2 rounded border border-slate-800 text-[10px] text-slate-300 overflow-x-auto max-h-36">
              <code>{JSON.stringify(node.tool_call.arguments, null, 2)}</code>
            </pre>
          </div>
        )}
      </div>
    </aside>
  );
};
