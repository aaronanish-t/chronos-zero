"use client";

import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";
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

  const latency = (data.total_latency_ms ?? 0).toFixed(2);

  if (isRoot) {
    return (
      <div
        className={`relative min-w-[200px] max-w-[240px] bg-surface-container rounded-DEFAULT p-3 shadow-xl backdrop-blur-md transition-all hover:bg-surface-container-high border border-white/5 select-none text-left cursor-pointer ${
          selected ? "ring-1 ring-secondary" : ""
        }`}
      >
        <div className="flex items-center justify-between pb-1.5 mb-2 bg-surface-container-high -mx-3 -mt-3 p-2 rounded-t-DEFAULT">
          <span className="font-label-sm text-label-sm font-semibold text-on-surface">
            PRISTINE ORIGIN
          </span>
          <span className="font-label-sm text-label-sm text-secondary bg-surface-container-lowest px-1.5 py-0.5 rounded-DEFAULT font-mono">
            {latency}ms
          </span>
        </div>
        <div className="space-y-1">
          <div className="font-label-md text-label-md font-bold text-on-surface flex items-center gap-1">
            <span className="material-symbols-outlined text-xs text-primary">
              database
            </span>
            <span className="font-mono">block_#04920</span>
          </div>
          <p className="font-label-sm text-label-sm text-outline truncate font-mono">
            {data.action_label || "db: prod_cluster_primary"}
          </p>
          <div className="pt-1 flex items-center justify-between font-label-sm text-label-sm text-on-surface-variant">
            <span>CoW State</span>
            <span className="text-primary font-medium font-mono">CLEAN</span>
          </div>
        </div>
        <Handle
          type="source"
          position={Position.Right}
          className="!w-2.5 !h-2.5 !bg-secondary !border-2 !border-surface-container-lowest"
        />
      </div>
    );
  }

  if (isSafe) {
    const hash = data.sha256_proof_hash
      ? `${data.sha256_proof_hash.slice(0, 8)}...${data.sha256_proof_hash.slice(-4)}`
      : "0x4e9c1...a109";

    return (
      <div
        className={`relative min-w-[280px] max-w-[340px] bg-surface-container rounded-DEFAULT p-3.5 shadow-[0_4px_24px_rgba(16,185,129,0.15)] ring-1 ring-primary/40 backdrop-blur-md transition-all hover:bg-surface-container-high select-none text-left cursor-pointer ${
          selected ? "ring-2 ring-primary" : ""
        }`}
      >
        <Handle
          type="target"
          position={Position.Left}
          className="!w-2.5 !h-2.5 !bg-primary !border-2 !border-surface-container-lowest"
        />

        <div className="flex items-center justify-between pb-2 mb-2 bg-primary/10 -mx-3.5 -mt-3.5 p-2.5 rounded-t-DEFAULT">
          <div className="flex items-center gap-1.5 text-primary">
            <span
              className="material-symbols-outlined text-sm leading-none"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              check_circle
            </span>
            <span className="font-label-sm text-label-sm font-bold uppercase tracking-wider font-mono">
              Z3 PROVEN SAT ({latency}ms)
            </span>
          </div>
          <span className="font-label-sm text-label-sm font-mono text-primary bg-primary/20 px-1.5 py-0.5 rounded-DEFAULT">
            COMMITTED
          </span>
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between font-label-sm text-label-sm">
            <span className="text-outline">TX_COMMIT // ID</span>
            <span className="font-mono text-on-surface">{hash}</span>
          </div>

          <div className="bg-surface-container-lowest p-2 rounded-DEFAULT font-label-sm text-label-sm text-on-surface space-y-0.5">
            <div className="text-outline-variant font-mono text-[10px]">
              EXEC_ACTION:
            </div>
            <div className="font-mono text-primary font-semibold text-[11px] leading-tight break-all line-clamp-2">
              {data.action_label}
            </div>
          </div>

          <div className="flex items-center justify-between font-label-sm text-label-sm pt-1">
            <span className="font-mono text-outline truncate max-w-[150px]">
              Schema Migrated Cleanly
            </span>
            <span className="px-1.5 py-0.5 rounded-DEFAULT bg-primary/15 text-primary font-mono text-[10px] font-semibold">
              0.00% DATA LOSS
            </span>
          </div>
        </div>

        <Handle
          type="source"
          position={Position.Right}
          className="!w-2.5 !h-2.5 !bg-primary !border-2 !border-surface-container-lowest"
        />
      </div>
    );
  }

  if (isRejected) {
    const ruleId =
      data.violated_rules && data.violated_rules.length > 0
        ? data.violated_rules[0]
        : "INV_SAFETY_GUARD";

    return (
      <div
        className={`relative min-w-[300px] max-w-[360px] bg-surface-container-high rounded-DEFAULT p-3.5 shadow-[0_0_30px_rgba(239,68,68,0.25)] ring-1 ring-error/50 backdrop-blur-md transition-all hover:scale-[1.01] select-none text-left cursor-pointer ${
          selected ? "ring-2 ring-error" : ""
        }`}
      >
        <Handle
          type="target"
          position={Position.Left}
          className="!w-2.5 !h-2.5 !bg-error !border-2 !border-surface-container-lowest"
        />

        <div className="flex items-center justify-between pb-2 mb-2 bg-error/15 -mx-3.5 -mt-3.5 p-2.5 rounded-t-DEFAULT">
          <div className="flex items-center gap-1.5 text-error">
            <span
              className="material-symbols-outlined text-sm leading-none"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              cancel
            </span>
            <span className="font-label-sm text-label-sm font-bold uppercase tracking-wider font-mono">
              UNSAT — KILLED IN SHADOW
            </span>
          </div>
          <span className="font-label-sm text-label-sm font-mono text-error bg-error/25 px-1.5 py-0.5 rounded-DEFAULT">
            {latency}ms
          </span>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="px-2 py-0.5 rounded-DEFAULT bg-error/20 text-error font-label-sm text-label-sm font-semibold tracking-wide">
              0 BYTES PROD DAMAGE
            </span>
            {data.financial_loss_prevented_usd > 0 && (
              <span className="font-label-sm text-label-sm text-error font-bold font-mono">
                ${data.financial_loss_prevented_usd.toLocaleString()} SAVED
              </span>
            )}
            {data.clinical_hazard_prevented && (
              <span className="font-label-sm text-label-sm text-error font-bold font-mono">
                HAZARD PREVENTED
              </span>
            )}
            {!data.financial_loss_prevented_usd && !data.clinical_hazard_prevented && (
              <span className="font-label-sm text-label-sm text-error font-bold font-mono">
                15,420 ACCOUNTS SAVED
              </span>
            )}
          </div>

          <div className="bg-surface-container-lowest p-2 rounded-DEFAULT font-label-sm text-label-sm space-y-1">
            <span className="text-outline text-[10px] uppercase font-mono block">
              ATTEMPTED UNVERIFIED ACTION
            </span>
            <p className="font-mono text-error font-medium leading-tight break-all line-clamp-2">
              {data.action_label}
            </p>
          </div>

          <div className="bg-surface-container-low p-2 rounded-DEFAULT space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-label-sm text-label-sm text-outline">
                Violated Invariant:
              </span>
              <span className="font-label-sm text-label-sm text-error font-mono font-bold">
                [{ruleId}]
              </span>
            </div>
            <div className="font-mono text-[10px] text-tertiary bg-surface-container-lowest px-2 py-1 rounded-DEFAULT truncate">
              Destructive mutation aborted — Outage Prevented
            </div>
          </div>
        </div>

        <Handle
          type="source"
          position={Position.Right}
          className="!w-2.5 !h-2.5 !bg-error !border-2 !border-surface-container-lowest"
        />
      </div>
    );
  }

  // Corrupted / Bypass mode
  return (
    <div
      className={`relative min-w-[280px] max-w-[340px] bg-surface-container rounded-DEFAULT p-3.5 shadow-[0_0_25px_rgba(245,158,11,0.35)] ring-2 ring-error animate-pulse select-none text-left cursor-pointer ${
        selected ? "ring-4 ring-error" : ""
      }`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-2.5 !h-2.5 !bg-error !border-2 !border-surface-container-lowest"
      />

      <div className="flex items-center justify-between pb-2 mb-2 bg-error/20 -mx-3.5 -mt-3.5 p-2.5 rounded-t-DEFAULT">
        <div className="flex items-center gap-1.5 text-error">
          <span className="material-symbols-outlined text-sm leading-none">
            warning
          </span>
          <span className="font-label-sm text-label-sm font-bold uppercase tracking-wider font-mono">
            BYPASS // CORRUPTED
          </span>
        </div>
        <span className="font-label-sm text-label-sm font-mono text-error bg-error/30 px-1.5 py-0.5 rounded-DEFAULT">
          {latency}ms
        </span>
      </div>

      <div className="space-y-1.5">
        <div className="bg-surface-container-lowest p-2 rounded-DEFAULT font-label-sm text-label-sm text-error space-y-0.5">
          <div className="text-outline font-mono text-[10px]">
            UNVERIFIED DIRECT WRITE:
          </div>
          <div className="font-mono font-semibold text-[11px] leading-tight break-all">
            {data.action_label}
          </div>
        </div>
        <p className="text-[10px] font-mono text-error/90 pt-1">
          Zero verification guardrails. Unsafe mutation committed directly to
          database.
        </p>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="!w-2.5 !h-2.5 !bg-error !border-2 !border-surface-container-lowest"
      />
    </div>
  );
});
