"use client";

import React, { useRef, useState } from "react";
import {
  Code2,
  Sparkles,
  CheckCircle2,
  Sliders,
  ChevronUp,
  ChevronDown,
  Copy,
  Check,
  ShieldCheck,
  Cpu,
  AlertTriangle,
} from "lucide-react";
import { CartridgeId, PolicyCompileResponse } from "../types/contracts";
import type { ActivePolicy } from "../hooks/useChronosWS";

interface LivePolicyStudioProps {
  activeCartridge: CartridgeId;
  activePolicy: ActivePolicy | null;
  onPolicyCompiled: (policy: ActivePolicy) => void;
}

interface CompiledRuleOutput {
  ruleId: string;
  cartridge: CartridgeId;
  nl: string;
  pythonZ3: string;
  smt2: string;
  remediationHint: string;
  compileLatencyMs: number | null;
}

// E3's judge policies (services/cartridges/scenarios/judge_policies.py): each is pre-recorded in
// the offline replay cache and compiles on the verifier's deterministic (no-LLM) path.
const JUDGE_PRESETS: { label: string; nl: string; cartridge: CartridgeId }[] = [
  { label: "Wire cap $500", nl: "No single wire transfer may exceed $500.", cartridge: "FINTECH_ESCROW" },
  { label: "SLA < 100 ms", nl: "Only pay vendors whose SLA latency is under 100 ms.", cartridge: "FINTECH_ESCROW" },
  { label: "Metformin eGFR < 45", nl: "Never prescribe Metformin to a patient with eGFR below 45.", cartridge: "HEALTHCARE_FHIR" },
  { label: "No DROP / TRUNCATE", nl: "Never drop or truncate a production table.", cartridge: "CLOUD_DEVOPS" },
  { label: "No public SSH", nl: "SSH port 22 must never be open to the internet.", cartridge: "CLOUD_DEVOPS" },
];

const CARTRIDGE_TAG: Record<CartridgeId, string> = {
  HEALTHCARE_FHIR: "MED",
  FINTECH_ESCROW: "FIN",
  CLOUD_DEVOPS: "OPS",
};

export const LivePolicyStudio: React.FC<LivePolicyStudioProps> = ({
  activeCartridge,
  activePolicy,
  onPolicyCompiled,
}) => {
  // Keep the main DAG presentation calm by default; the full compiler remains
  // one click away for the policy portion of the pitch.
  const [isExpanded, setIsExpanded] = useState(false);
  const [customRule, setCustomRule] = useState("");
  const [activeTab, setActiveTab] = useState<"PYTHON_Z3" | "SMT2" | "HINT">("PYTHON_Z3");
  const [isCompiling, setIsCompiling] = useState(false);
  const [compiledResult, setCompiledResult] = useState<CompiledRuleOutput | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const counterRef = useRef(0);

  /** POST /v1/z3/compile-policy: AST sandbox, SAT/UNSAT synthetic vectors, then hot-load. */
  const compile = async (text: string, cartridge: CartridgeId) => {
    const nl = text.trim();
    if (!nl || isCompiling) return;
    counterRef.current = (counterRef.current % 99) + 1;
    // Contract 3 rule_id pattern: ^INV_[A-Z]+_[0-9]{2}_[A-Z0-9_]+$
    const ruleId = `INV_POL_${String(counterRef.current).padStart(2, "0")}_${CARTRIDGE_TAG[cartridge]}`;
    setIsCompiling(true);
    setError(null);
    try {
      const res = await fetch("/v1/z3/compile-policy", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ cartridge_id: cartridge, rule_id: ruleId, natural_language_rule: nl }),
        signal: AbortSignal.timeout(5000),
      });
      const data = (await res.json().catch(() => null)) as PolicyCompileResponse | null;
      if (!res.ok || !data) {
        throw new Error(`Z3 verifier returned HTTP ${res.status}`);
      }
      if (data.status !== "COMPILED") {
        throw new Error(data.message || "Policy could not be compiled");
      }
      const formal = data.compiled_code || data.formal_assertion;
      setCompiledResult({
        ruleId: data.rule_id,
        cartridge,
        nl,
        pythonZ3: `# ${nl}\n# Hot-loaded into the ${cartridge} prover registry (AST-sandboxed, tested on SAT + UNSAT vectors)\ns.set("timeout", 50)\ns.assert_and_track(\n    ${formal},\n    "${data.rule_id}"\n)`,
        smt2: data.smt2_dump || "",
        remediationHint: data.remediation_hint || "",
        compileLatencyMs: data.compilation_latency_ms ?? null,
      });
      onPolicyCompiled({ cartridge, ruleId: data.rule_id, text: nl });
    } catch (e) {
      const message = (e as Error).message;
      setError(
        message.includes("fetch") || message.includes("timed out") || message.includes("aborted")
          ? `Z3 verifier unreachable on :8001 (${message})`
          : message
      );
    } finally {
      setIsCompiling(false);
    }
  };

  const handleCopyCode = () => {
    if (!compiledResult) return;
    const textToCopy =
      activeTab === "PYTHON_Z3"
        ? compiledResult.pythonZ3
        : activeTab === "SMT2"
        ? compiledResult.smt2
        : compiledResult.remediationHint;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const presets = [
    ...JUDGE_PRESETS.filter((p) => p.cartridge === activeCartridge),
    ...JUDGE_PRESETS.filter((p) => p.cartridge !== activeCartridge),
  ];

  return (
    <footer className="w-full bg-[#0B1120] border-t border-[#24324A] select-none text-slate-300 font-mono shrink-0 shadow-[0_-12px_32px_rgba(0,0,0,0.16)]">
      {/* Studio Header bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#0F172A]/90 border-b border-[#1E293B]/70">
        <div className="flex items-center gap-2.5">
          <div className="p-1 rounded bg-cyan-950 border border-cyan-700/60 text-cyan-400">
            <Code2 className="w-4 h-4 text-cyan-400" />
          </div>
          <span className="text-xs font-bold uppercase tracking-wider text-slate-100">
            Live Policy Studio
          </span>
          <span className="text-[10px] text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
            Active Cartridge: {activeCartridge}
          </span>
          <span className="hidden sm:inline-flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-700/50">
            <CheckCircle2 className="w-3 h-3 text-[#10B981]" />
            POST /v1/z3/compile-policy
          </span>

          {activePolicy && (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 border border-emerald-500 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.35)]">
              <ShieldCheck className="w-3.5 h-3.5 text-[#10B981]" />
              ENFORCED ON NEXT {activePolicy.cartridge} RUN: {activePolicy.ruleId}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 transition-colors p-1"
          >
            <Sliders className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-[11px]">{isExpanded ? "Collapse" : "Expand"}</span>
            {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Expandable Studio Body */}
      {isExpanded && (
        <div className="p-3 bg-[#0B1120]/95 grid grid-cols-1 lg:grid-cols-12 gap-3 text-xs max-h-[31vh] overflow-y-auto">
          {/* Left Column: Natural Language Input & Judge Q&A Quick Chips */}
          <div className="lg:col-span-7 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase text-slate-400 font-semibold flex items-center gap-1.5">
                <Sparkles className="w-3 h-3 text-cyan-400" />
                Judge Q&amp;A Plain-English Presets:
              </span>
              <span className="text-[9px] text-slate-500">
                Click a preset (compiles for its cartridge) or type a rule for {activeCartridge}
              </span>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {presets.map((preset) => (
                <button
                  key={preset.nl}
                  onClick={() => {
                    setCustomRule(preset.nl);
                    compile(preset.nl, preset.cartridge);
                  }}
                  disabled={isCompiling}
                  title={`${preset.cartridge}: ${preset.nl}`}
                  className={`px-2.5 py-1 rounded border text-[10px] transition-all shadow-sm disabled:opacity-50 ${
                    preset.cartridge === activeCartridge
                      ? "bg-[#0F172A] hover:bg-[#1E293B] border-cyan-800/70 text-slate-200"
                      : "bg-[#0B1120] hover:bg-[#1E293B] border-[#1E293B] text-slate-500"
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>

            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type="text"
                  value={customRule}
                  onChange={(e) => setCustomRule(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") compile(customRule, activeCartridge);
                  }}
                  placeholder="Type a plain-English rule, e.g. Block any wire transfer exceeding $5,000 unless the IBAN is allowlisted"
                  className="w-full bg-slate-950 px-3 py-2 rounded-md border border-[#1E293B] text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 text-xs font-mono pr-8"
                />
                {customRule && (
                  <button
                    onClick={() => setCustomRule("")}
                    className="absolute right-2.5 top-2.5 text-slate-500 hover:text-slate-300 text-xs"
                  >
                    ×
                  </button>
                )}
              </div>

              <button
                onClick={() => compile(customRule, activeCartridge)}
                disabled={isCompiling || !customRule.trim()}
                className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-950 font-bold text-xs transition-colors shrink-0 shadow-sm"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{isCompiling ? "Compiling..." : "Compile to Z3 SMT"}</span>
              </button>
            </div>

            {isCompiling && (
              <div className="flex items-center gap-2 p-2 rounded bg-cyan-950/40 border border-cyan-800/60 text-cyan-300 text-[11px] animate-pulse">
                <Cpu className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
                <span className="font-semibold">
                  Compiling on the Z3 verifier: AST sandbox, contradiction/tautology check, SAT + UNSAT test vectors...
                </span>
              </div>
            )}
            {error && !isCompiling && (
              <div className="flex items-start gap-2 p-2 rounded bg-red-950/50 border border-red-800/70 text-red-300 text-[11px]">
                <AlertTriangle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
                <span className="font-semibold break-all">Not loaded: {error}</span>
              </div>
            )}
          </div>

          {/* Right Column: Code Output, Tabs, and Status */}
          <div className="lg:col-span-5 bg-slate-950 p-2.5 rounded-lg border border-[#1E293B] space-y-2 flex flex-col justify-between">
            <div className="flex items-center justify-between pb-1.5 border-b border-slate-900 text-[10px]">
              <div className="flex items-center gap-1">
                {(
                  [
                    ["PYTHON_Z3", "Python Z3"],
                    ["SMT2", "SMT-LIB2"],
                    ["HINT", "Agent Hint"],
                  ] as const
                ).map(([tab, label]) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-2 py-0.5 rounded transition-colors font-semibold ${
                      activeTab === tab
                        ? "bg-cyan-950 text-cyan-300 border border-cyan-700/60"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                {compiledResult?.compileLatencyMs != null && (
                  <span className="text-[9px] text-emerald-400 font-mono">
                    {compiledResult.compileLatencyMs}ms
                  </span>
                )}
                <button
                  onClick={handleCopyCode}
                  className="flex items-center gap-1 text-[9px] text-slate-400 hover:text-slate-200 transition-colors"
                >
                  {copied ? (
                    <>
                      <Check className="w-2.5 h-2.5 text-[#10B981]" />
                      <span className="text-[#10B981]">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-2.5 h-2.5" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            <pre className="text-[10px] text-slate-300 overflow-x-auto max-h-24 leading-relaxed font-mono select-all bg-slate-900/60 p-2 rounded border border-slate-900">
              <code>
                {compiledResult
                  ? activeTab === "PYTHON_Z3"
                    ? compiledResult.pythonZ3
                    : activeTab === "SMT2"
                    ? compiledResult.smt2
                    : compiledResult.remediationHint
                  : `# Pick a preset or type a rule. The Z3 verifier compiles it into\n# s.assert_and_track(<expr>, "INV_POL_NN_...") and enforces it on the next run.`}
              </code>
            </pre>

            {compiledResult ? (
              <div className="flex items-center justify-between pt-1 border-t border-slate-900 text-[10px]">
                <span className="text-emerald-400 flex items-center gap-1 font-semibold">
                  <CheckCircle2 className="w-3 h-3 text-[#10B981]" />
                  LOADED: {compiledResult.ruleId} ({compiledResult.cartridge})
                </span>
                <span className="text-slate-500 font-mono">
                  {compiledResult.compileLatencyMs != null
                    ? `Compiled in ${compiledResult.compileLatencyMs}ms on the verifier`
                    : "Compiled on the verifier"}
                </span>
              </div>
            ) : (
              <div className="text-[9px] text-slate-600 flex items-center justify-between">
                <span>Compiler: Z3 verifier :8001</span>
                <span>Run the cartridge after compiling to see it enforced</span>
              </div>
            )}
          </div>
        </div>
      )}
    </footer>
  );
};
