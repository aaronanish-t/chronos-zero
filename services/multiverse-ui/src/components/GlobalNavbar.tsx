"use client";

import React from "react";
import { WSConnectionStatus } from "../hooks/useChronosWS";

interface GlobalNavbarProps {
  currentView: "dag" | "architecture";
  onSelectView: (view: "dag" | "architecture") => void;
  status: WSConnectionStatus;
  latencyMs?: number;
  onOpenBenchmarks: () => void;
  onOpenDocs?: () => void;
  onOpenSMTProver?: () => void;
}

export const GlobalNavbar: React.FC<GlobalNavbarProps> = ({
  currentView,
  onSelectView,
  status,
  latencyMs = 0,
  onOpenBenchmarks,
  onOpenDocs,
  onOpenSMTProver,
}) => {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-surface-container-lowest/85 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.6)] border-b border-surface-container-high/40 select-none">
      <div className="h-16 w-full max-w-[1400px] mx-auto px-margin-mobile lg:px-6 flex items-center justify-between gap-space-md">
        {/* Brand & Version Badge */}
        <div className="flex items-center gap-space-lg">
          <button
            onClick={() => onSelectView("architecture")}
            className="flex items-center gap-space-sm group text-left cursor-pointer transition-transform hover:scale-[1.01]"
          >
            <div className="h-8 w-8 rounded-lg bg-surface-container-high flex items-center justify-center ring-1 ring-white/10 group-hover:ring-primary/40 transition-all shadow-inner">
              <span className="text-primary font-bold text-base leading-none">⚡</span>
            </div>
            <div className="flex items-center gap-space-xs">
              <span className="font-label-lg text-label-lg tracking-tight font-semibold text-on-surface group-hover:text-primary transition-colors">
                CHRONOS-ZERO
              </span>
              <span className="hidden sm:inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT bg-surface-container-high text-primary font-label-sm text-label-sm tracking-wide">
                v2.4 KERNEL (STABLE)
              </span>
            </div>
          </button>

          {/* Navigation Links (Matching Stitch Minimal Dark Design System) */}
          <nav className="hidden lg:flex items-center gap-space-xs">
            <button
              onClick={() => onSelectView("architecture")}
              className={`px-3 py-1.5 rounded-DEFAULT font-label-md text-label-md transition-colors ${
                currentView === "architecture"
                  ? "text-primary font-medium bg-surface-container-high shadow-sm"
                  : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low"
              }`}
            >
              Architecture
            </button>
            <button
              onClick={() => {
                if (onOpenSMTProver) onOpenSMTProver();
                else onSelectView("dag");
              }}
              className="px-3 py-1.5 rounded-DEFAULT font-label-md text-label-md text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low transition-colors"
            >
              SMT Prover
            </button>
            <button
              onClick={() => onSelectView("dag")}
              className={`px-3 py-1.5 rounded-DEFAULT font-label-md text-label-md transition-colors ${
                currentView === "dag"
                  ? "text-primary font-medium bg-surface-container-high shadow-sm"
                  : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low"
              }`}
            >
              Multiverse DAG
            </button>
            <button
              onClick={onOpenBenchmarks}
              className="px-3 py-1.5 rounded-DEFAULT font-label-md text-label-md text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low transition-colors"
            >
              Benchmarks
            </button>
            <button
              onClick={() => {
                if (onOpenDocs) onOpenDocs();
                else onSelectView("architecture");
              }}
              className="px-3 py-1.5 rounded-DEFAULT font-label-md text-label-md text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low transition-colors"
            >
              Docs
            </button>
          </nav>
        </div>

        {/* Live WS Status + Launch Sandbox CTA + Avatar */}
        <div className="flex items-center gap-space-md">
          {/* Live WS Latency Beacon */}
          <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-DEFAULT bg-surface-container-high shadow-inner">
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
              className={`font-label-sm text-label-sm font-medium ${
                status === "CONNECTED" ? "text-on-surface" : "text-error"
              }`}
            >
              {status === "CONNECTED"
                ? `Live WS${latencyMs > 0 ? ` · avg kernel ${latencyMs.toFixed(2)}ms` : ""}`
                : "Live WS: Offline"}
            </span>
          </div>

          {/* Launch Sandbox Action Pill */}
          <button
            onClick={() => onSelectView("dag")}
            className="inline-flex items-center justify-center px-3.5 py-1.5 rounded-DEFAULT bg-primary font-label-sm text-label-sm text-on-primary font-semibold hover:bg-primary-fixed transition-all shadow-[0_0_12px_rgba(16,185,129,0.25)] active:scale-[0.98]"
          >
            Launch Sandbox
          </button>

          {/* User Profile Avatar Ring */}
          <div className="flex items-center pl-space-xs">
            <div
              title="Verified Operator"
              className="w-8 h-8 rounded-full bg-surface-container-high ring-1 ring-surface-variant hover:ring-primary transition-all cursor-pointer flex items-center justify-center font-mono text-xs text-primary font-bold shadow-inner"
            >
              CZ
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
