/**
 * ThreatTron AI — Case Details Page
 * Full investigation view: summary, evidence, agent logs, mitigation actions,
 * Reasoning Panel, and Decision Panel.
 */

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchCaseById,
  reInvestigateCase,
  triggerReasoning,
  fetchReasoning,
  fetchDecision,
  type CaseDetail,
  type CaseEvidence,
  type AgentExecutionLog,
  type ReasoningResult,
  type DecisionResult,
} from "../api";

/* ── Style Maps ──────────────────────────────────────────────────────────── */
const SEVERITY_CLASSES: Record<string, string> = {
  CRITICAL: "bg-red-600/20 text-red-300 border-red-600/30",
  HIGH:     "bg-red-500/20 text-red-400 border-red-500/30",
  MEDIUM:   "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  LOW:      "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
};
const STATUS_CLASSES: Record<string, string> = {
  OPEN:          "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  INVESTIGATING: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  CLOSED:        "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
};
const ACTION_CLASSES: Record<string, string> = {
  BLOCK_ACCOUNT: "bg-red-500/20 text-red-400 border-red-500/30",
  MFA_CHALLENGE: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  APPROVE:       "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  DISMISS:       "bg-white/10 text-white/40 border-white/10",
  PENDING:       "bg-white/5 text-white/30 border-white/5",
};
const DECISION_CLASSES: Record<string, string> = {
  BLOCK_ACCOUNT: "bg-red-600/25 text-red-300 border-red-500/40",
  MANUAL_REVIEW: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
  MFA_CHALLENGE: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  APPROVE:       "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
};
const DECISION_ICON: Record<string, string> = {
  BLOCK_ACCOUNT: "🔴",
  MANUAL_REVIEW: "🟡",
  MFA_CHALLENGE: "🟣",
  APPROVE:       "🟢",
};

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function Badge({ label, colorClass }: { label: string; colorClass: string }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${colorClass}`}>
      {label}
    </span>
  );
}
function riskBarColor(s: number) {
  return s >= 0.8 ? "bg-red-500" : s >= 0.45 ? "bg-yellow-500" : "bg-emerald-500";
}
function riskTextColor(s: number) {
  return s >= 0.8 ? "text-red-400" : s >= 0.45 ? "text-yellow-400" : "text-emerald-400";
}
function ConfidenceBar({ value, color = "cyan" }: { value: number; color?: string }) {
  const pct = Math.round(value * 100);
  const barMap: Record<string, string> = {
    cyan:   "bg-cyan-400",
    purple: "bg-purple-400",
    red:    "bg-red-400",
    green:  "bg-emerald-400",
    yellow: "bg-yellow-400",
  };
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${barMap[color] ?? "bg-cyan-400"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs font-bold ${color === "cyan" ? "text-cyan-400" : color === "purple" ? "text-purple-400" : "text-white/60"}`}>
        {pct}%
      </span>
    </div>
  );
}

/* ── Evidence Row ────────────────────────────────────────────────────────── */
function EvidenceRow({ ev, idx }: { ev: CaseEvidence; idx: number }) {
  return (
    <tr id={`evidence-row-${ev.id}`} className="border-b border-white/[0.04] hover:bg-white/[0.02] transition">
      <td className="py-3 pr-4 text-white/30 text-xs font-mono">{idx + 1}</td>
      <td className="py-3 pr-4 text-white/70 text-xs font-semibold">{ev.source}</td>
      <td className="py-3 pr-4 text-white/50 text-xs leading-relaxed">{ev.description}</td>
      <td className="py-3">
        <Badge label={ev.severity} colorClass={SEVERITY_CLASSES[ev.severity] ?? "bg-white/10 text-white/30 border-white/10"} />
      </td>
    </tr>
  );
}

/* ── Agent Log Step ──────────────────────────────────────────────────────── */
function AgentLogStep({ log }: { log: AgentExecutionLog }) {
  const [expanded, setExpanded] = useState(false);
  let observationParsed: Record<string, unknown> | null = null;
  try {
    if (log.observation) observationParsed = JSON.parse(log.observation);
  } catch { /* plain text */ }

  return (
    <div id={`log-step-${log.id}`} className="border border-white/5 rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-start gap-4 p-4 text-left hover:bg-white/[0.02] transition"
      >
        <span className="flex-shrink-0 w-6 h-6 rounded-full bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 text-xs flex items-center justify-center font-bold">
          {log.step_number}
        </span>
        <div className="flex-1 min-w-0">
          {log.thought && <p className="text-xs text-white/60 italic mb-1 leading-relaxed">💭 {log.thought}</p>}
          {log.action && (
            <p className="text-xs font-mono text-purple-400">
              ⚡ {log.action}
              {log.action_input ? <span className="text-white/30 ml-1">({log.action_input})</span> : null}
            </p>
          )}
        </div>
        <span className="flex-shrink-0 text-white/20 text-xs">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && log.observation && (
        <div className="border-t border-white/5 p-4 bg-black/20">
          <p className="text-[10px] text-white/30 uppercase tracking-wider mb-2">Observation</p>
          {observationParsed ? (
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(observationParsed).map(([k, v]) => (
                <div key={k} className="text-xs">
                  <span className="text-white/30">{k}: </span>
                  <span className="text-white/60 font-mono">{String(v)}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-white/50 font-mono">{log.observation}</p>
          )}
          <p className="text-[10px] text-white/20 mt-3">{new Date(log.timestamp).toLocaleString()}</p>
        </div>
      )}
    </div>
  );
}

/* ── Reasoning Panel ─────────────────────────────────────────────────────── */
function ReasoningPanel({ caseId, initialReasoning }: { caseId: number; initialReasoning: ReasoningResult | null | undefined }) {
  const qc = useQueryClient();

  const { data: reasoning } = useQuery<ReasoningResult>({
    queryKey: ["reasoning", caseId],
    queryFn: () => fetchReasoning(caseId),
    initialData: initialReasoning ?? undefined,
    enabled: !!initialReasoning,
    retry: false,
  });

  const trigger = useMutation({
    mutationFn: () => triggerReasoning(caseId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reasoning", caseId] });
      qc.invalidateQueries({ queryKey: ["decision", caseId] });
      qc.invalidateQueries({ queryKey: ["case", caseId] });
    },
  });

  if (!reasoning && !trigger.isPending) {
    return (
      <div className="glass-card border border-purple-500/10">
        <div className="flex items-center justify-between mb-4">
          <p className="text-xs text-white/40 uppercase tracking-widest">🧠 AI Reasoning Report</p>
          <button
            id="btn-run-reasoning"
            onClick={() => trigger.mutate()}
            disabled={trigger.isPending}
            className="px-4 py-2 bg-purple-500/20 border border-purple-500/30 text-purple-400 rounded-lg text-sm font-medium hover:bg-purple-500/30 transition disabled:opacity-50"
          >
            Generate AI Report
          </button>
        </div>
        <p className="text-white/25 text-sm text-center py-8">
          No reasoning report yet. Click "Generate AI Report" to run the Reasoning Agent + Decision Engine.
        </p>
      </div>
    );
  }

  if (trigger.isPending) {
    return (
      <div className="glass-card border border-purple-500/10">
        <p className="text-xs text-white/40 uppercase tracking-widest mb-4">🧠 AI Reasoning Report</p>
        <div className="flex items-center gap-3 py-8 justify-center">
          <div className="w-5 h-5 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
          <p className="text-white/40 text-sm">Reasoning Agent is analysing the case…</p>
        </div>
      </div>
    );
  }

  if (!reasoning) return null;

  return (
    <div className="glass-card border border-purple-500/10 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-white/40 uppercase tracking-widest">🧠 AI Reasoning Report</p>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-white/25 font-mono">provider: {reasoning.provider}</span>
          <button
            id="btn-re-reason"
            onClick={() => trigger.mutate()}
            disabled={trigger.isPending}
            className="px-3 py-1.5 bg-purple-500/10 border border-purple-500/20 text-purple-400 rounded-lg text-xs hover:bg-purple-500/20 transition"
          >
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Executive Summary */}
      <div className="p-4 bg-purple-500/[0.06] border border-purple-500/15 rounded-xl">
        <p className="text-[10px] text-purple-400/70 uppercase tracking-wider mb-2">Executive Summary</p>
        <p className="text-sm text-white/80 leading-relaxed">{reasoning.executive_summary}</p>
      </div>

      {/* Confidence */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <p className="text-[10px] text-white/40 uppercase tracking-wider">Reasoning Confidence</p>
          <span className={`text-xs font-bold ${reasoning.confidence >= 0.75 ? "text-cyan-400" : reasoning.confidence >= 0.50 ? "text-yellow-400" : "text-white/40"}`}>
            {reasoning.confidence >= 0.75 ? "HIGH" : reasoning.confidence >= 0.50 ? "MODERATE" : "LOW"}
          </span>
        </div>
        <ConfidenceBar value={reasoning.confidence} color="purple" />
      </div>

      {/* Findings */}
      {reasoning.findings.length > 0 && (
        <div>
          <p className="text-[10px] text-white/40 uppercase tracking-wider mb-3">
            Analytical Findings ({reasoning.findings.length})
          </p>
          <div className="space-y-2">
            {reasoning.findings.map((f, i) => (
              <div key={i} className="flex gap-3 p-3 bg-white/[0.025] border border-white/[0.04] rounded-lg">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-purple-500/20 text-purple-400 text-[10px] flex items-center justify-center font-bold">
                  {i + 1}
                </span>
                <p className="text-xs text-white/65 leading-relaxed">{f}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Rationale */}
      {reasoning.rationale && (
        <div className="p-3 bg-white/[0.02] border border-white/[0.04] rounded-xl">
          <p className="text-[10px] text-white/30 uppercase tracking-wider mb-1">Recommendation Rationale</p>
          <p className="text-xs text-white/55 leading-relaxed">{reasoning.rationale}</p>
        </div>
      )}

      <p className="text-[10px] text-white/20">
        Generated {new Date(reasoning.created_at).toLocaleString()}
      </p>
    </div>
  );
}

/* ── Decision Panel ──────────────────────────────────────────────────────── */
function DecisionPanel({ caseId, initialDecision }: { caseId: number; initialDecision: DecisionResult | null | undefined }) {
  const [traceOpen, setTraceOpen] = useState(false);

  const { data: decision } = useQuery<DecisionResult>({
    queryKey: ["decision", caseId],
    queryFn: () => fetchDecision(caseId),
    initialData: initialDecision ?? undefined,
    enabled: !!initialDecision,
    retry: false,
  });

  if (!decision) return null;

  const icon  = DECISION_ICON[decision.decision]  ?? "⚪";
  const cls   = DECISION_CLASSES[decision.decision] ?? "bg-white/10 text-white/30 border-white/10";
  const decPct = Math.round(decision.decision_confidence * 100);
  const traceFactors = (decision.decision_trace?.factors as string[] | undefined) ?? [];
  const evCounts     = decision.decision_trace?.evidence_counts as Record<string, number> | undefined;

  return (
    <div className="glass-card border border-cyan-500/10 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-white/40 uppercase tracking-widest">⚖️ Autonomous Decision</p>
        <span className="text-[10px] text-white/25 font-mono">Rule-Based Engine</span>
      </div>

      {/* Decision Badge + Confidence */}
      <div className="flex items-center gap-4 p-4 bg-white/[0.03] border border-white/[0.05] rounded-xl">
        <span className="text-4xl">{icon}</span>
        <div className="flex-1">
          <p className={`text-xl font-bold mb-1 ${cls.split(" ")[1]}`}>{decision.decision}</p>
          <ConfidenceBar value={decision.decision_confidence} color={decision.decision === "APPROVE" ? "green" : decision.decision === "BLOCK_ACCOUNT" ? "red" : decision.decision === "MFA_CHALLENGE" ? "purple" : "yellow"} />
        </div>
        <div className="text-right">
          <p className="text-[10px] text-white/30 mb-1">Confidence</p>
          <p className="text-2xl font-bold text-white/70">{decPct}%</p>
        </div>
      </div>

      {/* Rationale */}
      {decision.decision_rationale && (
        <div className="p-4 bg-white/[0.025] border border-white/[0.04] rounded-xl">
          <p className="text-[10px] text-white/30 uppercase tracking-wider mb-2">Decision Rationale</p>
          <p className="text-xs text-white/65 leading-relaxed">{decision.decision_rationale}</p>
        </div>
      )}

      {/* Factor Pills */}
      {traceFactors.length > 0 && (
        <div>
          <p className="text-[10px] text-white/30 uppercase tracking-wider mb-2">Contributing Factors</p>
          <div className="flex flex-wrap gap-2">
            {traceFactors.map((f) => (
              <span key={f} className="px-2 py-1 rounded-full bg-white/[0.04] border border-white/[0.06] text-[10px] text-white/50 font-mono">
                {f}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Evidence Count Summary */}
      {evCounts && (
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Critical", key: "critical", color: "text-red-400" },
            { label: "High",     key: "high",     color: "text-orange-400" },
            { label: "Medium",   key: "medium",   color: "text-yellow-400" },
            { label: "Total",    key: "total",    color: "text-white/50" },
          ].map(({ label, key, color }) => (
            <div key={key} className="text-center p-2 bg-white/[0.02] border border-white/[0.04] rounded-lg">
              <p className={`text-lg font-bold ${color}`}>{evCounts[key] ?? 0}</p>
              <p className="text-[9px] text-white/25 uppercase">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Machine-Readable Trace (collapsible) */}
      <div>
        <button
          id="btn-toggle-trace"
          onClick={() => setTraceOpen((v) => !v)}
          className="flex items-center gap-2 text-[10px] text-white/25 hover:text-white/50 transition"
        >
          <span>{traceOpen ? "▼" : "▶"}</span>
          <span>Machine-Readable Decision Trace (Compliance)</span>
        </button>
        {traceOpen && (
          <pre className="mt-3 p-4 bg-black/30 border border-white/[0.04] rounded-xl text-[10px] text-white/40 font-mono overflow-x-auto leading-relaxed">
            {JSON.stringify(decision.decision_trace, null, 2)}
          </pre>
        )}
      </div>

      <p className="text-[10px] text-white/20">
        Decided {new Date(decision.created_at).toLocaleString()}
      </p>
    </div>
  );
}

/* ── Main Page ───────────────────────────────────────────────────────────── */
export default function CaseDetails() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const id = parseInt(caseId ?? "0", 10);

  const { data: caseData, isLoading } = useQuery<CaseDetail>({
    queryKey: ["case", id],
    queryFn:  () => fetchCaseById(id),
    enabled:  id > 0,
    refetchInterval: 15000,
  });

  const investigate = useMutation({
    mutationFn: () => reInvestigateCase(id),
    onSuccess:  () => qc.invalidateQueries({ queryKey: ["case", id] }),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-white/30 text-sm">
        Loading case…
      </div>
    );
  }
  if (!caseData) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-white/30">
        <p className="text-4xl">🚫</p>
        <p>Case not found.</p>
        <button
          onClick={() => navigate("/cases")}
          className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white/50 hover:text-white/80 transition"
        >
          Back to Cases
        </button>
      </div>
    );
  }

  const riskPct = Math.round(caseData.risk_score * 100);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Breadcrumb + Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <button
            onClick={() => navigate("/cases")}
            className="text-xs text-white/30 hover:text-cyan-400 transition mb-1"
          >
            ← Case Manager
          </button>
          <h2 className="text-2xl font-bold text-white">Case #{caseData.id}</h2>
          <p className="text-sm text-white/40 mt-1">
            Trigger event #{caseData.trigger_event_id} · Created{" "}
            {new Date(caseData.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge
            label={caseData.status}
            colorClass={STATUS_CLASSES[caseData.status] ?? "bg-white/10 text-white/30 border-white/10"}
          />
          <button
            id="btn-re-investigate"
            onClick={() => investigate.mutate()}
            disabled={investigate.isPending}
            className="px-4 py-2 bg-purple-500/20 border border-purple-500/30 text-purple-400 rounded-lg text-sm font-medium hover:bg-purple-500/30 transition disabled:opacity-50"
          >
            {investigate.isPending ? "Investigating…" : "🔍 Re-Investigate"}
          </button>
        </div>
      </div>

      {/* Risk Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Risk Score */}
        <div className="glass-card">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-3">Risk Score</p>
          <p className={`text-4xl font-bold ${riskTextColor(caseData.risk_score)}`}>{riskPct}%</p>
          <div className="mt-3 h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${riskBarColor(caseData.risk_score)}`}
              style={{ width: `${riskPct}%` }}
            />
          </div>
        </div>

        {/* Recommended Action */}
        <div className="glass-card">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-3">Recommended Action</p>
          <Badge
            label={caseData.recommended_action ?? "PENDING"}
            colorClass={ACTION_CLASSES[caseData.recommended_action ?? "PENDING"] ?? "bg-white/10 text-white/30 border-white/10"}
          />
          <p className="text-xs text-white/30 mt-3">
            {caseData.actions.length > 0
              ? `${caseData.actions.length} mitigation action(s) logged`
              : "Awaiting agent recommendation"}
          </p>
        </div>

        {/* Investigation Stats */}
        <div className="glass-card">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-3">Investigation Stats</p>
          <div className="space-y-2">
            {[
              { label: "Evidence Items", val: caseData.evidence.length,  color: "text-cyan-400"   },
              { label: "Agent Steps",    val: caseData.logs.length,       color: "text-purple-400" },
              { label: "Actions",        val: caseData.actions.length,    color: "text-yellow-400" },
            ].map(({ label, val, color }) => (
              <div key={label} className="flex justify-between text-sm">
                <span className="text-white/50">{label}</span>
                <span className={`font-bold ${color}`}>{val}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Investigation Summary */}
      {caseData.summary && (
        <div className="glass-card border border-cyan-500/10">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-3">Investigation Summary</p>
          <p className="text-sm text-white/70 leading-relaxed">{caseData.summary}</p>
        </div>
      )}

      {/* Evidence + Mitigation grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Evidence Table */}
        <div className="glass-card">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
            Evidence ({caseData.evidence.length})
          </p>
          {caseData.evidence.length === 0 ? (
            <p className="text-white/20 text-sm py-8 text-center">No evidence collected yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-white/25 text-[10px] uppercase tracking-wider border-b border-white/5">
                    <th className="pb-2 pr-3 text-left">#</th>
                    <th className="pb-2 pr-3 text-left">Source</th>
                    <th className="pb-2 pr-3 text-left">Description</th>
                    <th className="pb-2 text-left">Severity</th>
                  </tr>
                </thead>
                <tbody>
                  {caseData.evidence.map((ev, i) => (
                    <EvidenceRow key={ev.id} ev={ev} idx={i} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Mitigation Actions */}
        <div className="glass-card">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-4">Mitigation Actions</p>
          {caseData.actions.length === 0 ? (
            <p className="text-white/20 text-sm py-8 text-center">No actions created yet.</p>
          ) : (
            <div className="space-y-3">
              {caseData.actions.map((a) => (
                <div
                  key={a.id}
                  id={`action-item-${a.id}`}
                  className="flex items-center justify-between px-4 py-3 bg-white/[0.02] border border-white/5 rounded-xl"
                >
                  <div>
                    <Badge label={a.action_type} colorClass={ACTION_CLASSES[a.action_type] ?? "bg-white/10 text-white/30 border-white/10"} />
                    <p className="text-[10px] text-white/25 mt-1">
                      by {a.executed_by} · {new Date(a.updated_at).toLocaleString()}
                    </p>
                  </div>
                  <Badge
                    label={a.status}
                    colorClass={
                      a.status === "EXECUTED"
                        ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                        : a.status === "DENIED"
                        ? "bg-red-500/20 text-red-400 border-red-500/30"
                        : "bg-white/5 text-white/30 border-white/10"
                    }
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Reasoning Panel ─────────────────────────────────────────────── */}
      <ReasoningPanel
        caseId={id}
        initialReasoning={(caseData as CaseDetail & { reasoning?: ReasoningResult }).reasoning}
      />

      {/* ── Decision Panel ───────────────────────────────────────────────── */}
      {(caseData as CaseDetail & { decision?: DecisionResult }).decision && (
        <DecisionPanel
          caseId={id}
          initialDecision={(caseData as CaseDetail & { decision?: DecisionResult }).decision}
        />
      )}

      {/* Agent Execution Logs */}
      <div className="glass-card">
        <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
          Agent Execution Log ({caseData.logs.length} steps)
        </p>
        {caseData.logs.length === 0 ? (
          <p className="text-white/20 text-sm py-8 text-center">No agent steps recorded.</p>
        ) : (
          <div className="space-y-3">
            {[...caseData.logs]
              .sort((a, b) => a.step_number - b.step_number)
              .map((log) => (
                <AgentLogStep key={log.id} log={log} />
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
