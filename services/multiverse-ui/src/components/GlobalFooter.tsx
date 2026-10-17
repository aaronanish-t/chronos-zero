"use client";

import React from "react";

interface GlobalFooterProps {
  onOpenReceiptValidator?: () => void;
}

export const GlobalFooter: React.FC<GlobalFooterProps> = ({
  onOpenReceiptValidator,
}) => {
  return (
    <footer className="relative z-10 w-full bg-surface-container-lowest py-space-lg px-margin-mobile lg:px-margin border-t border-surface-container-high/40 shadow-[0_-1px_12px_rgba(0,0,0,0.5)] select-none">
      <div className="w-full max-w-[1400px] mx-auto flex flex-col md:flex-row items-center justify-between gap-space-lg text-xs">
        <div className="flex flex-wrap items-center gap-space-lg text-center md:text-left">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
            <span className="font-label-sm text-label-sm text-on-surface-variant">
              All Zero-Knowledge Rollup Nodes Operational
            </span>
          </div>
          <button
            onClick={onOpenReceiptValidator}
            className="font-label-sm text-label-sm text-secondary hover:text-secondary-fixed transition-colors flex items-center gap-1 cursor-pointer"
          >
            <span className="material-symbols-outlined text-sm leading-none">
              verified
            </span>
            Receipt Validator
          </button>
        </div>
        <div className="flex items-center gap-space-lg">
          <span className="font-label-sm text-label-sm text-on-surface-variant font-mono">
            POSTGRES 16 CoW • Z3 SMT
          </span>
          <span className="font-label-sm text-label-sm text-outline-variant font-mono">
            © 2025 CHRONOS FOUNDATION
          </span>
        </div>
      </div>
    </footer>
  );
};
