"use client";

import React from "react";
import {
  ShieldCheck,
  Zap,
  Activity,
  DollarSign,
  AlertOctagon,
  RefreshCw,
  Play,
  RotateCcw,
  Wifi,
  WifiOff,
} from "lucide-react";
import { CartridgeId } from "../types/contracts";
import { TelemetryMetrics, WSConnectionStatus } from "../hooks/useChronosWS";

interface TopTelemetryBarProps {
  status: WSConnectionStatus;
  metrics: TelemetryMetrics;
  activeCartridge: CartridgeId;
  setActiveCartridge: (cartridge: CartridgeId) => void;
  isSimulating: boolean;
  onSimulate: (cartridge: CartridgeId) => void;
  onSimulateBypass: () => void;
  onReset: () => void;
}

export const TopTelemetryBar: React.FC<TopTelemetryBarProps> = ({
  status,
  metrics,
  activeCartridge,
  setActiveCartridge,
  isSimulating,
  onSimulate,
  onSimulateBypass,
  onReset,
}) => {
  const cartridges: { id: CartridgeId; label: string }[] = [
    { id: "FINTECH_ESCROW", label: "FinTech Escrow" },
    { id: "HEALTHCARE_FHIR", label: "Healthcare FHIR" },
    { id: "CLOUD_DEVOPS", label: "Cloud DevOps" },
  ];

  return (
    <header className="w-full bg-[#090D16] border-b border-[#1E293B] px-4 py-2.5 select-none">
      {/* Top row: Brand, Connection, Mode, Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-2.5">
        {/* Brand & Subtitle */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="relative flex items-center justify-center w-7 h-7 rounded bg-cyan-950/60 border border-cyan-500/40 text-cyan-400">
              <Zap className="w-4 h-4 fill-cyan-400/20" />
              <span className="absolute -top-1 -right-1 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
              </span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold tracking-wider text-sm text-slate-100">
                  CHRONOS-ZERO
                </span>
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.2 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800/80">
                  v0.4.0 Kernel
                </span>
              </div>
              <p className="text-[10px] text-slate-400 font-mono">
                Speculative CoW & Formal Z3 SMT Mission Control
              </p>
            </div>
          </div>

          <div className="h-6 w-px bg-[#1E293B]" />

          {/* Connection status indicator */}
          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-[#0F172A] border border-[#1E293B] text-xs font-mono">
            {status === "CONNECTED" ? (
              <>
                <Wifi className="w-3.5 h-3.5 text-chronos-emerald animate-pulse" />
                <span className="text-chronos-emerald font-medium">WS: CONNECTED</span>
              </>
            ) : status === "RECONNECTING" ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 text-amber-400 animate-spin" />
                <span className="text-amber-400 font-medium">WS: RECONNECTING</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3.5 h-3.5 text-slate-400" />
                <span className="text-slate-400 font-medium">WS: LOCAL STANDALONE</span>
              </>
            )}
          </div>

          {/* Guarded Mode Badge */}
          <div className="hidden md:flex items-center gap-1.5 px-2 py-1 rounded bg-emerald-950/40 border border-emerald-800/60 text-xs font-mono text-emerald-300">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>ACTIVE // CoW+Z3 Guarded</span>
          </div>
        </div>

        {/* Cartridge Selector Tabs */}
        <div className="flex items-center rounded-lg bg-[#0F172A] p-0.5 border border-[#1E293B]">
          {cartridges.map((c) => (
            <button
              key={c.id}
              onClick={() => setActiveCartridge(c.id)}
              className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                activeCartridge === c.id
                  ? "bg-cyan-950/80 text-cyan-300 border border-cyan-700/60 font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => onSimulate(activeCartridge)}
            disabled={isSimulating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-950 font-mono font-semibold text-xs transition-colors shadow-sm"
          >
            <Play className="w-3 h-3 fill-current" />
            <span>Simulate Mock Telemetry</span>
          </button>

          <button
            onClick={onSimulateBypass}
            disabled={isSimulating}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-amber-950/60 hover:bg-amber-900/60 border border-amber-600/60 text-amber-300 font-mono text-xs transition-colors"
            title="Demonstrate catastrophic state corruption when Chronos interception is bypassed"
          >
            <AlertOctagon className="w-3 h-3 text-amber-400" />
            <span>Simulate Bypass Attack</span>
          </button>

          <button
            onClick={onReset}
            className="flex items-center gap-1 px-2 py-1.5 rounded bg-slate-900 hover:bg-slate-800 border border-[#1E293B] text-slate-300 font-mono text-xs transition-colors"
            title="Clear DAG canvas and reset metrics"
          >
            <RotateCcw className="w-3 h-3" />
            <span className="hidden sm:inline">Reset</span>
          </button>
        </div>
      </div>

      {/* Bottom row: High-density monospace telemetry numerals */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 pt-1 border-t border-[#1E293B]/60 text-xs font-mono">
        {/* Metric 1: Total Branches */}
        <div className="bg-[#0F172A]/70 px-2.5 py-1.5 rounded border border-[#1E293B]">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1">
            <Activity className="w-3 h-3 text-cyan-400" />
            <span>Total Branches</span>
          </div>
          <div className="text-base font-bold text-slate-100 numeral-mono">
            {metrics.totalBranches.toString().padStart(3, "0")}
          </div>
        </div>

        {/* Metric 2: UNSAT Rollbacks */}
        <div className="bg-[#0F172A]/70 px-2.5 py-1.5 rounded border border-[#1E293B]">
          <div className="text-[10px] text-chronos-crimson uppercase tracking-wider flex items-center gap-1">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-chronos-crimson"></span>
            <span>UNSAT Prevented</span>
          </div>
          <div className="text-base font-bold text-chronos-crimson numeral-mono">
            {metrics.unsatRollbacks.toString().padStart(2, "0")}
          </div>
        </div>

        {/* Metric 3: SAT Committed */}
        <div className="bg-[#0F172A]/70 px-2.5 py-1.5 rounded border border-[#1E293B]">
          <div className="text-[10px] text-chronos-emerald uppercase tracking-wider flex items-center gap-1">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-chronos-emerald"></span>
            <span>SAT Committed</span>
          </div>
          <div className="text-base font-bold text-chronos-emerald numeral-mono">
            {metrics.satCommitted.toString().padStart(2, "0")}
          </div>
        </div>

        {/* Metric 4: Financial Loss Prevented */}
        <div className="bg-[#0F172A]/70 px-2.5 py-1.5 rounded border border-[#1E293B]">
          <div className="text-[10px] text-amber-400 uppercase tracking-wider flex items-center gap-1">
            <DollarSign className="w-3 h-3 text-amber-400" />
            <span>Loss Prevented</span>
          </div>
          <div className="text-base font-bold text-amber-300 numeral-mono">
            ${metrics.financialLossPreventedUsd.toLocaleString()}
          </div>
        </div>

        {/* Metric 5: Clinical Hazards */}
        <div className="bg-[#0F172A]/70 px-2.5 py-1.5 rounded border border-[#1E293B]">
          <div className="text-[10px] text-purple-400 uppercase tracking-wider flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 text-purple-400" />
            <span>Hazards Blocked</span>
          </div>
          <div className="text-base font-bold text-purple-300 numeral-mono">
            {metrics.clinicalHazardsPrevented.toString().padStart(2, "0")}
          </div>
        </div>

        {/* Metric 6: P50 Avg Latency */}
        <div className="bg-[#0F172A]/70 px-2.5 py-1.5 rounded border border-[#1E293B]">
          <div className="text-[10px] text-cyan-400 uppercase tracking-wider flex items-center gap-1">
            <Zap className="w-3 h-3 text-cyan-400" />
            <span>Avg Latency (P50)</span>
          </div>
          <div className="text-base font-bold text-cyan-300 numeral-mono">
            {metrics.avgTotalLatencyMs > 0
              ? `${metrics.avgTotalLatencyMs.toFixed(2)}ms`
              : "--"}
          </div>
        </div>
      </div>
    </header>
  );
};
