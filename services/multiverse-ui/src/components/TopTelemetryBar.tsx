"use client";

import React, { useEffect } from "react";
import { motion, useSpring, useTransform } from "framer-motion";
import {
  ShieldCheck,
  Zap,
  Activity,
  DollarSign,
  AlertTriangle,
  RefreshCw,
  Play,
  RotateCcw,
  Wifi,
  WifiOff,
  Stethoscope,
  Coins,
  Server,
  ToggleLeft,
  ToggleRight,
  ShieldAlert,
} from "lucide-react";
import { CartridgeId, ChronosMode } from "../types/contracts";
import { TelemetryMetrics, WSConnectionStatus } from "../hooks/useChronosWS";

/**
 * Animated Integer Counter using Framer Motion
 */
function AnimatedCounter({
  value,
  prefix = "",
  suffix = "",
}: {
  value: number;
  prefix?: string;
  suffix?: string;
}) {
  const spring = useSpring(value, { mass: 0.8, stiffness: 75, damping: 15 });
  const display = useTransform(
    spring,
    (current) => `${prefix}${Math.round(current).toLocaleString()}${suffix}`
  );

  useEffect(() => {
    spring.set(value);
  }, [spring, value]);

  return <motion.span className="numeral-mono">{display}</motion.span>;
}

/**
 * Animated Decimal Counter using Framer Motion (for latencies)
 */
function AnimatedDecimal({
  value,
  suffix = "ms",
}: {
  value: number;
  suffix?: string;
}) {
  const spring = useSpring(value, { mass: 0.8, stiffness: 75, damping: 15 });
  const display = useTransform(
    spring,
    (current) => (current > 0 ? `${current.toFixed(2)}${suffix}` : "--")
  );

  useEffect(() => {
    spring.set(value);
  }, [spring, value]);

  return <motion.span className="numeral-mono">{display}</motion.span>;
}

interface TopTelemetryBarProps {
  status: WSConnectionStatus;
  metrics: TelemetryMetrics;
  activeCartridge: CartridgeId;
  setActiveCartridge: (cartridge: CartridgeId) => void;
  chronosMode?: ChronosMode;
  onToggleChronosMode?: () => void;
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
  chronosMode = "ACTIVE",
  onToggleChronosMode,
  isSimulating,
  onSimulate,
  onSimulateBypass,
  onReset,
}) => {
  // 1-Click Cartridge Switcher configuration
  const cartridges: {
    id: CartridgeId;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
  }[] = [
    { id: "HEALTHCARE_FHIR", label: "Healthcare FHIR", icon: Stethoscope },
    { id: "FINTECH_ESCROW", label: "FinTech Escrow", icon: Coins },
    { id: "CLOUD_DEVOPS", label: "Cloud DevOps", icon: Server },
  ];

  const isBypass = chronosMode === "BYPASS";

  return (
    <header className="w-full bg-[#090D16] border-b border-[#1E293B] px-4 py-2.5 select-none text-slate-100">
      {/* Top Row: System Identity, Connection, Master Switch, Cartridge Switcher, and Simulation Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-2.5">
        {/* Brand & Connection Badge */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="relative flex items-center justify-center w-7 h-7 rounded bg-cyan-950/80 border border-cyan-500/50 text-cyan-400">
              <Zap className="w-4 h-4 fill-cyan-400/20" />
              <span className="absolute -top-1 -right-1 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500" />
              </span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold tracking-wider text-sm text-slate-100">
                  CHRONOS-ZERO
                </span>
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.2 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800/80">
                  Mission Control
                </span>
              </div>
              <p className="text-[10px] text-slate-400 font-mono">
                Speculative CoW & Formal Z3 Verification Kernel
              </p>
            </div>
          </div>

          <div className="h-6 w-px bg-[#1E293B]" />

          {/* Connection Status Indicator */}
          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-[#0F172A] border border-[#1E293B] text-xs font-mono">
            {status === "CONNECTED" ? (
              <>
                <Wifi className="w-3.5 h-3.5 text-[#10B981] animate-pulse" />
                <span className="text-[#10B981] font-medium">WS: CONNECTED</span>
              </>
            ) : status === "RECONNECTING" ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 text-[#F59E0B] animate-spin" />
                <span className="text-[#F59E0B] font-medium">
                  WS: RECONNECTING
                </span>
              </>
            ) : (
              <>
                <WifiOff className="w-3.5 h-3.5 text-slate-400" />
                <span className="text-slate-400 font-medium">
                  WS: STANDALONE (MOCK)
                </span>
              </>
            )}
          </div>
        </div>

        {/* 2. Master Kernel Switch: CHRONOS: BYPASS [UNSAFE] vs CHRONOS: ACTIVE [Z3 PROTECTED] */}
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleChronosMode}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-mono text-xs font-bold transition-all border ${
              !isBypass
                ? "bg-emerald-950/80 border-[#10B981] text-emerald-300 shadow-[0_0_15px_rgba(16,185,129,0.25)] hover:bg-emerald-900/80"
                : "bg-red-950/90 border-[#EF4444] text-red-300 shadow-[0_0_18px_rgba(239,68,68,0.45)] animate-pulse hover:bg-red-900/90"
            }`}
            title="Toggle between CoW+Z3 Active Formal Verification and Raw Unverified Bypass"
          >
            {!isBypass ? (
              <>
                <ShieldCheck className="w-4 h-4 text-[#10B981]" />
                <span>CHRONOS: ACTIVE [Z3 PROTECTED]</span>
                <ToggleRight className="w-4 h-4 text-[#10B981]" />
              </>
            ) : (
              <>
                <ShieldAlert className="w-4 h-4 text-[#EF4444]" />
                <span>CHRONOS: BYPASS [UNSAFE]</span>
                <ToggleLeft className="w-4 h-4 text-[#EF4444]" />
              </>
            )}
          </button>
        </div>

        {/* 1. 1-Click Cartridge Switcher (HEALTHCARE_FHIR | FINTECH_ESCROW | CLOUD_DEVOPS) */}
        <div className="flex items-center rounded-lg bg-[#0F172A] p-0.5 border border-[#1E293B]">
          {cartridges.map((c) => {
            const Icon = c.icon;
            const isSelected = activeCartridge === c.id;
            return (
              <button
                key={c.id}
                onClick={() => setActiveCartridge(c.id)}
                className={`flex items-center gap-1.5 px-3 py-1 text-xs font-mono rounded transition-colors ${
                  isSelected
                    ? "bg-cyan-950/90 text-cyan-300 border border-cyan-700/70 font-semibold shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isSelected ? "text-cyan-400" : "text-slate-500"}`} />
                <span>{c.label}</span>
              </button>
            );
          })}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => onSimulate(activeCartridge)}
            disabled={isSimulating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-950 font-mono font-semibold text-xs transition-colors shadow-sm"
          >
            <Play className="w-3 h-3 fill-current" />
            <span>Simulate Mock Telemetry</span>
          </button>

          <button
            onClick={onSimulateBypass}
            disabled={isSimulating}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-amber-950/60 hover:bg-amber-900/60 border border-amber-600/60 text-amber-300 font-mono text-xs transition-colors"
            title="Demonstrate catastrophic state corruption in BYPASS mode"
          >
            <AlertTriangle className="w-3 h-3 text-amber-400" />
            <span>Bypass Attack</span>
          </button>

          <button
            onClick={onReset}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-slate-900 hover:bg-slate-800 border border-[#1E293B] text-slate-300 font-mono text-xs transition-colors"
            title="Clear DAG canvas"
          >
            <RotateCcw className="w-3 h-3" />
            <span className="hidden sm:inline">Reset</span>
          </button>
        </div>
      </div>

      {/* 3. Animated Telemetry Counters Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 pt-1 border-t border-[#1E293B]/60 text-xs font-mono">
        {/* Counter 1: Total Capital Protected ($) */}
        <div className="bg-[#0F172A]/80 px-2.5 py-1.5 rounded border border-[#1E293B]">
          <div className="text-[10px] text-amber-400 uppercase tracking-wider flex items-center gap-1">
            <DollarSign className="w-3 h-3 text-amber-400" />
            <span>Capital Protected ($)</span>
          </div>
          <div className="text-base font-bold text-amber-300 numeral-mono">
            <AnimatedCounter
              value={metrics.financialLossPreventedUsd}
              prefix="$"
            />
          </div>
        </div>

        {/* Counter 2: Clinical Hazards Blocked */}
        <div className="bg-[#0F172A]/80 px-2.5 py-1.5 rounded border border-[#1E293B]">
          <div className="text-[10px] text-purple-400 uppercase tracking-wider flex items-center gap-1">
            <Stethoscope className="w-3 h-3 text-purple-400" />
            <span>Hazards Blocked</span>
          </div>
          <div className="text-base font-bold text-purple-300 numeral-mono">
            <AnimatedCounter value={metrics.clinicalHazardsPrevented} />
          </div>
        </div>

        {/* Counter 3: P50 Proof Latency (ms) */}
        <div className="bg-[#0F172A]/80 px-2.5 py-1.5 rounded border border-[#1E293B]">
          <div className="text-[10px] text-cyan-400 uppercase tracking-wider flex items-center gap-1">
            <Zap className="w-3 h-3 text-cyan-400" />
            <span>P50 Proof Latency</span>
          </div>
          <div className="text-base font-bold text-cyan-300 numeral-mono">
            <AnimatedDecimal value={metrics.avgTotalLatencyMs} suffix=" ms" />
          </div>
        </div>

        {/* Counter 4: Total Branches */}
        <div className="bg-[#0F172A]/80 px-2.5 py-1.5 rounded border border-[#1E293B]">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1">
            <Activity className="w-3 h-3 text-cyan-400" />
            <span>Total Branches</span>
          </div>
          <div className="text-base font-bold text-slate-100 numeral-mono">
            <AnimatedCounter value={metrics.totalBranches} />
          </div>
        </div>

        {/* Counter 5: UNSAT Prevented */}
        <div className="bg-[#0F172A]/80 px-2.5 py-1.5 rounded border border-[#1E293B]">
          <div className="text-[10px] text-[#EF4444] uppercase tracking-wider flex items-center gap-1">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#EF4444]" />
            <span>UNSAT Prevented</span>
          </div>
          <div className="text-base font-bold text-[#EF4444] numeral-mono">
            <AnimatedCounter value={metrics.unsatRollbacks} />
          </div>
        </div>

        {/* Counter 6: SAT Committed */}
        <div className="bg-[#0F172A]/80 px-2.5 py-1.5 rounded border border-[#1E293B]">
          <div className="text-[10px] text-[#10B981] uppercase tracking-wider flex items-center gap-1">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#10B981]" />
            <span>SAT Committed</span>
          </div>
          <div className="text-base font-bold text-[#10B981] numeral-mono">
            <AnimatedCounter value={metrics.satCommitted} />
          </div>
        </div>
      </div>
    </header>
  );
};
