"use client";

import React, { useState, useEffect } from "react";
import { motion, useSpring, useTransform } from "framer-motion";
import { CartridgeId, ChronosMode } from "../types/contracts";
import { TelemetryMetrics, WSConnectionStatus } from "../hooks/useChronosWS";
import type { BenchmarkSummary } from "../app/api/benchmark/route";

function AnimatedCurrency({ value }: { value: number }) {
  const spring = useSpring(value, { mass: 0.8, stiffness: 75, damping: 15 });
  const display = useTransform(
    spring,
    (current) =>
      `$${Math.max(0, current).toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`
  );

  useEffect(() => {
    spring.set(value);
  }, [spring, value]);

  return <motion.span className="numeral-mono">{display}</motion.span>;
}

function AnimatedInteger({
  value,
  suffix = "",
}: {
  value: number;
  suffix?: string;
}) {
  const spring = useSpring(value, { mass: 0.8, stiffness: 75, damping: 15 });
  const display = useTransform(
    spring,
    (current) => `${Math.max(0, Math.round(current))}${suffix}`
  );

  useEffect(() => {
    spring.set(value);
  }, [spring, value]);

  return <motion.span className="numeral-mono">{display}</motion.span>;
}

function AnimatedDecimal({
  value,
  suffix = "ms",
}: {
  value: number;
  suffix?: string;
}) {
  const spring = useSpring(value, { mass: 0.8, stiffness: 75, damping: 15 });
  const display = useTransform(spring, (current) =>
    current > 0 ? `${current.toFixed(2)}${suffix}` : "--"
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
  isRunning: boolean;
  onRun: (cartridge: CartridgeId) => void;
  onRunBypass: (cartridge: CartridgeId) => void;
  onReset: () => void;
  onOpenSplitDemo?: () => void;
  currentView?: "dag" | "architecture";
  onSelectView?: (view: "dag" | "architecture") => void;
}

export const TopTelemetryBar: React.FC<TopTelemetryBarProps> = ({
  status,
  metrics,
  activeCartridge,
  setActiveCartridge,
  chronosMode = "ACTIVE",
  onToggleChronosMode,
  isRunning,
  onRun,
  onRunBypass,
  onReset,
  onOpenSplitDemo,
  currentView = "dag",
  onSelectView,
}) => {
  const [benchmark, setBenchmark] = useState<BenchmarkSummary | null>(null);

  useEffect(() => {
    fetch("/api/benchmark")
      .then((res) => res.json())
      .then((data: BenchmarkSummary) => setBenchmark(data))
      .catch(() => setBenchmark(null));
  }, []);

  const isBypass = chronosMode === "BYPASS";

  const cartridges: {
    id: CartridgeId;
    shortcut: string;
    label: string;
  }[] = [
    { id: "HEALTHCARE_FHIR", shortcut: "[1]", label: "Healthcare FHIR" },
    { id: "FINTECH_ESCROW", shortcut: "[2]", label: "FinTech Escrow" },
    { id: "CLOUD_DEVOPS", shortcut: "[3]", label: "Cloud DevOps" },
  ];

  return (
    <header className="w-full bg-surface-container-lowest/95 backdrop-blur-md px-margin-mobile lg:px-6 py-3 shadow-[0_4px_20px_rgba(0,0,0,0.6)] border-b border-surface-container-high/40 select-none">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Brand & Diagnostics Beacon */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-surface-container-high px-2.5 py-1 rounded-DEFAULT shadow-inner">
            <span className="text-primary font-bold text-sm leading-none flex items-center">
              ⚡
            </span>
            <span className="font-label-lg text-label-lg font-semibold tracking-tight text-on-surface">
              CHRONOS-ZERO
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-surface-variant" />
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-2 w-2">
                <span
                  className={`animate-ping absolute inline-flex h-full w-full rounded-full ${
                    status === "CONNECTED"
                      ? "bg-primary opacity-75"
                      : "bg-error opacity-75"
                  }`}
                />
                <span
                  className={`relative inline-flex rounded-full h-2 w-2 ${
                    status === "CONNECTED" ? "bg-primary" : "bg-error"
                  }`}
                />
              </span>
              <span
                className={`font-label-sm text-label-sm uppercase font-semibold ${
                  status === "CONNECTED" ? "text-primary" : "text-error"
                }`}
              >
                {status === "CONNECTED" ? "Live WS" : "WS Disconnected"}
              </span>
            </div>
          </div>

          <div className="hidden xl:flex items-center gap-1.5 bg-surface-container px-2.5 py-1 rounded-DEFAULT text-secondary">
            <span className="material-symbols-outlined text-sm leading-none">
              speed
            </span>
            <span className="font-label-sm text-label-sm font-semibold tracking-wider">
              {benchmark && benchmark.speedup_factor
                ? `${benchmark.speedup_factor.toFixed(0)}x VS LLM GUARDRAILS`
                : "BENCHMARK: RUN make bench"}
            </span>
          </div>

          {/* Navigation view tabs */}
          {onSelectView && (
            <nav className="hidden lg:flex items-center gap-1 bg-surface-container-low p-0.5 rounded-DEFAULT">
              <button
                onClick={() => onSelectView("dag")}
                className={`px-2.5 py-1 rounded-DEFAULT font-label-sm text-label-sm transition-all flex items-center gap-1 ${
                  currentView === "dag"
                    ? "bg-surface-container-high text-primary font-semibold shadow-sm"
                    : "text-on-surface-variant hover:text-on-surface"
                }`}
              >
                <span className="material-symbols-outlined text-xs leading-none">
                  account_tree
                </span>
                Multiverse DAG
              </button>
              <button
                onClick={() => onSelectView("architecture")}
                className={`px-2.5 py-1 rounded-DEFAULT font-label-sm text-label-sm transition-all flex items-center gap-1 ${
                  currentView === "architecture"
                    ? "bg-surface-container-high text-primary font-semibold shadow-sm"
                    : "text-on-surface-variant hover:text-on-surface"
                }`}
              >
                <span className="material-symbols-outlined text-xs leading-none">
                  terminal
                </span>
                Architecture & Proofs
              </button>
            </nav>
          )}
        </div>

        {/* Segmented Domain Cartridge Switcher */}
        <div
          className="flex items-center bg-surface-container-low p-1 rounded-DEFAULT gap-1 shadow-inner"
          id="cartridge-pills"
        >
          {cartridges.map((c) => {
            const isActive = activeCartridge === c.id;
            return (
              <button
                key={c.id}
                onClick={() => setActiveCartridge(c.id)}
                className={`cartridge-btn px-2.5 py-1 rounded-DEFAULT font-label-sm text-label-sm transition-all flex items-center gap-1.5 ${
                  isActive
                    ? "active text-on-surface bg-surface-container-highest shadow-sm text-primary ring-1 ring-primary/40"
                    : "text-on-surface-variant hover:text-on-surface"
                }`}
              >
                <span
                  className={
                    isActive ? "text-primary font-mono" : "text-outline font-mono"
                  }
                >
                  {c.shortcut}
                </span>
                <span>{c.label}</span>
                {isActive && (
                  <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                )}
              </button>
            );
          })}
        </div>

        {/* Execution Mode Toggle & Action Controls */}
        <div className="flex items-center gap-2">
          {/* Active / Bypass Segmented Toggle */}
          <div className="flex items-center bg-surface-container-low p-1 rounded-DEFAULT shadow-inner">
            <button
              onClick={() => {
                if (isBypass && onToggleChronosMode) onToggleChronosMode();
              }}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-DEFAULT font-label-sm text-label-sm font-semibold transition-all ${
                !isBypass
                  ? "bg-primary text-on-primary shadow-[0_0_12px_rgba(78,222,163,0.3)]"
                  : "text-on-surface-variant hover:text-primary"
              }`}
              id="mode-active-btn"
            >
              <span
                className="material-symbols-outlined text-sm leading-none"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                shield
              </span>
              <span>ACTIVE</span>
            </button>

            <button
              onClick={() => {
                if (!isBypass && onToggleChronosMode) onToggleChronosMode();
              }}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-DEFAULT font-label-sm text-label-sm font-medium transition-all ${
                isBypass
                  ? "bg-error text-on-error font-semibold shadow-[0_0_15px_rgba(239,68,68,0.4)]"
                  : "text-on-surface-variant hover:text-error"
              }`}
              id="mode-bypass-btn"
            >
              <span className="material-symbols-outlined text-sm leading-none">
                shield_with_heart
              </span>
              <span>BYPASS</span>
            </button>
          </div>

          {/* Action Buttons: Run, 50/50 Split, Reset */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() =>
                isBypass
                  ? onRunBypass(activeCartridge)
                  : onRun(activeCartridge)
              }
              disabled={isRunning}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-DEFAULT font-label-sm text-label-sm font-semibold transition-all ${
                isBypass
                  ? "bg-error text-on-error hover:bg-error-container shadow-[0_0_12px_rgba(239,68,68,0.35)]"
                  : "bg-primary text-on-primary hover:bg-primary-fixed shadow-[0_0_12px_rgba(78,222,163,0.35)]"
              } ${isRunning ? "opacity-50 cursor-not-allowed" : "active:scale-[0.98]"}`}
            >
              <span className="material-symbols-outlined text-sm leading-none font-bold">
                play_arrow
              </span>
              <span>Run</span>
              <span className="opacity-70 font-mono text-[9px]">(Space)</span>
            </button>

            {onOpenSplitDemo && (
              <button
                onClick={onOpenSplitDemo}
                className="hidden md:flex items-center gap-1 bg-surface-container-high px-2.5 py-1.5 rounded-DEFAULT text-primary font-label-sm text-label-sm ring-1 ring-primary/50 shadow-[0_0_12px_rgba(78,222,163,0.25)] hover:bg-surface-container-highest transition-all"
              >
                <span className="material-symbols-outlined text-sm leading-none text-primary">
                  splitscreen
                </span>
                <span className="font-semibold">50/50 Split [ACTIVE]</span>
              </button>
            )}

            <button
              onClick={onReset}
              disabled={isRunning}
              title="Reset State (R)"
              className="p-1.5 rounded-DEFAULT bg-surface-container-high text-on-surface-variant hover:text-on-surface hover:bg-surface-variant transition-all disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-sm leading-none">
                restart_alt
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Live Spring Metric Telemetry Ticker (5 Metrics) */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-3 pt-3 bg-surface-container-lowest/60">
        {/* Metric 1: Capital Protected */}
        <div className="flex flex-col bg-surface-container-low px-3 py-2 rounded-DEFAULT shadow-inner">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex items-center justify-between">
            Capital Protected
            <span className="material-symbols-outlined text-xs text-primary">
              lock
            </span>
          </span>
          <span
            className="font-label-lg text-label-lg font-bold text-primary tabular-nums tracking-tight mt-0.5"
            id="metric-capital"
          >
            <AnimatedCurrency value={metrics.financialLossPreventedUsd} />
          </span>
        </div>

        {/* Metric 2: Clinical Hazards */}
        <div className="flex flex-col bg-surface-container-low px-3 py-2 rounded-DEFAULT shadow-inner">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex items-center justify-between">
            Clinical Hazards
            <span className="material-symbols-outlined text-xs text-secondary">
              health_and_safety
            </span>
          </span>
          <span
            className="font-label-lg text-label-lg font-bold text-secondary tabular-nums tracking-tight mt-0.5"
            id="metric-hazards"
          >
            <AnimatedInteger
              value={metrics.clinicalHazardsPrevented}
              suffix=" PREVENTED"
            />
          </span>
        </div>

        {/* Metric 3: Infra Catastrophes */}
        <div className="flex flex-col bg-surface-container-low px-3 py-2 rounded-DEFAULT shadow-inner">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex items-center justify-between">
            Infra Catastrophes
            <span className="material-symbols-outlined text-xs text-error">
              database
            </span>
          </span>
          <span className="font-label-lg text-label-lg font-bold text-error tabular-nums tracking-tight mt-0.5">
            <AnimatedInteger
              value={metrics.unsatRollbacks}
              suffix=" BLOCKED"
            />
          </span>
        </div>

        {/* Metric 4: Kernel Latency */}
        <div className="flex flex-col bg-surface-container-low px-3 py-2 rounded-DEFAULT shadow-inner">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex items-center justify-between">
            Kernel Latency
            <span className="material-symbols-outlined text-xs text-secondary-fixed">
              bolt
            </span>
          </span>
          <span
            className="font-label-lg text-label-lg font-bold text-secondary-fixed tabular-nums tracking-tight mt-0.5"
            id="metric-latency"
          >
            <AnimatedDecimal value={metrics.avgTotalLatencyMs} />
          </span>
        </div>

        {/* Metric 5: UNSAT / SAT */}
        <div className="flex flex-col bg-surface-container-low px-3 py-2 rounded-DEFAULT shadow-inner">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex items-center justify-between">
            UNSAT / SAT
            <span className="material-symbols-outlined text-xs text-outline">
              swap_vert
            </span>
          </span>
          <span className="font-label-lg text-label-lg font-bold text-on-surface tabular-nums tracking-tight mt-0.5">
            <span className="text-error">{metrics.unsatRollbacks}</span> /{" "}
            <span className="text-primary">{metrics.satCommitted}</span>
          </span>
        </div>
      </div>
    </header>
  );
};
