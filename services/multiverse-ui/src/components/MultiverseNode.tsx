"use client";

import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  GitBranch,
  Clock,
  KeyRound,
  FileCode2,
} from "lucide-react";
import { TelemetryNode } from "../types/contracts";

interface MultiverseNodeProps {
  data: TelemetryNode;
  selected?: boolean;
}

export const MultiverseNode = memo(function MultiverseNode({
  data,
  selected,
}: MultiverseNodeProps) {
  const isRejected = data.branch_type === "SHADOW_REJECTED";
  const isSafe = data.branch_type === "COMMITTED_SAFE";
  const isCorrupted = data.branch_type === "BYPASS_CORRUPTED";
  const isRoot = data.branch_type === "ROOT";

  // Border & Glow styling
  let containerClasses =
    "relative min-w-[260px] max-w-[320px] rounded-lg p-3 transition-all duration-200 cursor-pointer text-left ";
  if (isRejected) {
    containerClasses +=
      "bg-[#0F172A]/90 border-2 border-chronos-crimson/80 shadow-[0_0_15px_rgba(239,68,68,0.25)] hover:border-chronos-crimson";
  } else if (isSafe) {
    containerClasses +=
      "bg-[#0F172A]/90 border-2 border-chronos-emerald/80 shadow-[0_0_15px_rgba(16,185,129,0.25)] hover:border-chronos-emerald";
  } else if (isCorrupted) {
    containerClasses +=
      "bg-[#0F172A]/90 border-2 border-amber-500 shadow-[0_0_20px_rgba(245,158,11,0.35)] animate-pulse hover:border-amber-400";
  } else {
    containerClasses +=
      "bg-[#0F172A]/80 border border-slate-700 shadow-[0_0_10px_rgba(30,41,59,0.5)] hover:border-slate-500";
  }

  if (selected) {
    containerClasses += " ring-2 ring-cyan-400 ring-offset-2 ring-offset-[#090D16]";
  }

  return (
    <div className={containerClasses}>
      {/* Target Handle (Left) */}
      {!isRoot && (
        <Handle
          type="target"
          position={Position.Left}
          className="!w-2.5 !h-2.5 !bg-slate-400 !border-2 !border-[#090D16]"
        />
      )}

      {/* Header Row: Branch Type Badge & Latency */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          {isRejected && <ShieldAlert className="w-4 h-4 text-chronos-crimson" />}
          {isSafe && <ShieldCheck className="w-4 h-4 text-chronos-emerald" />}
          {isCorrupted && <AlertTriangle className="w-4 h-4 text-amber-500" />}
          {isRoot && <GitBranch className="w-4 h-4 text-slate-400" />}

          <span
            className={`text-xs font-semibold uppercase tracking-wider ${
              isRejected
                ? "text-chronos-crimson"
                : isSafe
                ? "text-chronos-emerald"
                : isCorrupted
                ? "text-amber-400"
                : "text-slate-400"
            }`}
          >
            {isRejected
              ? "UNSAT // ROLLED BACK"
              : isSafe
              ? "SAT // COMMITTED"
              : isCorrupted
              ? "BYPASS // CORRUPTED"
              : "ORIGIN ROOT"}
          </span>
        </div>

        {/* Latency numeral */}
        <div className="flex items-center gap-1 text-[11px] font-mono text-slate-400 bg-slate-900/80 px-1.5 py-0.5 rounded border border-slate-800">
          <Clock className="w-3 h-3 text-cyan-400" />
          <span className="numeral-mono">{data.total_latency_ms.toFixed(2)}ms</span>
        </div>
      </div>

      {/* Action / Tool Label */}
      <div className="text-xs font-mono font-medium text-slate-200 line-clamp-2 bg-slate-950/60 p-1.5 rounded border border-slate-800/80 mb-2 break-all">
        {data.action_label}
      </div>

      {/* Badges Footer */}
      <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
        {/* UNSAT Core badges */}
        {data.violated_rules && data.violated_rules.length > 0 && (
          <div className="flex items-center gap-1 bg-red-950/50 text-red-300 border border-red-800/60 px-1.5 py-0.5 rounded">
            <span className="font-semibold">UnsatCore:</span>
            <span className="font-mono">
              {data.violated_rules.length === 1
                ? data.violated_rules[0]
                : `${data.violated_rules.length} rules`}
            </span>
          </div>
        )}

        {/* SHA-256 Receipt badge for SAT */}
        {isSafe && data.sha256_proof_hash && (
          <div className="flex items-center gap-1 bg-emerald-950/50 text-emerald-300 border border-emerald-800/60 px-1.5 py-0.5 rounded font-mono">
            <KeyRound className="w-2.5 h-2.5" />
            <span>SHA-256: {data.sha256_proof_hash.slice(0, 8)}...</span>
          </div>
        )}

        {/* Loss or Hazard prevention flags */}
        {data.financial_loss_prevented_usd > 0 && (
          <span className="bg-amber-950/50 text-amber-300 border border-amber-800/60 px-1.5 py-0.5 rounded font-mono font-medium">
            Saved ${(data.financial_loss_prevented_usd / 1000).toFixed(0)}k
          </span>
        )}
        {data.clinical_hazard_prevented && (
          <span className="bg-purple-950/50 text-purple-300 border border-purple-800/60 px-1.5 py-0.5 rounded font-medium">
            Hazard Blocked
          </span>
        )}

        {data.smt2_dump && (
          <span className="text-slate-500 flex items-center gap-0.5 ml-auto text-[9px] font-mono">
            <FileCode2 className="w-2.5 h-2.5" />
            SMT2
          </span>
        )}
      </div>

      {/* Source Handle (Right) */}
      <Handle
        type="source"
        position={Position.Right}
        className="!w-2.5 !h-2.5 !bg-slate-400 !border-2 !border-[#090D16]"
      />
    </div>
  );
});
