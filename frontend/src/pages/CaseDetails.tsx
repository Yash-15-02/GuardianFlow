/**
 * ThreatTron AI — Case Details Page
 * Full investigation view: summary, evidence table, agent logs, mitigation actions.
 */

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchCaseById,
  reInvestigateCase,
  type CaseDetail,
  type CaseEvidence,
  type AgentExecutionLog,
} from "../api";

/* ── Helpers ─────────────────────────────────────────────────────────────── */

const SEVERITY_CLASSES: Record<string, string> = {
  CRITICAL: "bg-red-600/20 text-red-300 border-red-600/30",
  HIGH: "bg-red-500/20 text-red-400 border-red-500/30",
  MEDIUM: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  LOW: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
};

const STATUS_CLASSES: Record<string, string> = {
  OPEN: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  INVESTIGATING: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  CLOSED: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
};

const ACTION_CLASSES: Record<string, string> = {
  BLOCK_ACCOUNT: "bg-red-500/20 text-red-400 border-red-500/30",
  MFA_CHALLENGE: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  APPROVE: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  DISMISS: "bg-white/10 text-white/40 border-white/10",
  PENDING: "bg-white/5 text-white/30 border-white/5",
};

function Badge({
  label,
  colorClass,
}: {
  label: string;
  colorClass: string;
}) {
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${colorClass}`}
    >
      {label}
    </span>
  );
}

function riskBarColor(score: number) {
  if (score >= 0.8) return "bg-red-500";
  if (score >= 0.45) return "bg-yellow-500";
  return "bg-emerald-500";
}

function riskTextColor(score: number) {
  if (score >= 0.8) return "text-red-400";
  if (score >= 0.45) return "text-yellow-400";
  return "text-emerald-400";
}

/* ── Evidence Row ─────────────────────────────────────────────────────────── */
function EvidenceRow({ ev, idx }: { ev: CaseEvidence; idx: number }) {
  return (
    <tr
      id={`evidence-row-${ev.id}`}
      className="border-b border-white/[0.04] hover:bg-white/[0.02] transition"
    >
      <td className="py-3 pr-4 text-white/30 text-xs font-mono">{idx + 1}</td>
      <td className="py-3 pr-4 text-white/70 text-xs font-semibold">
        {ev.source}
      </td>
      <td className="py-3 pr-4 text-white/50 text-xs leading-relaxed">
        {ev.description}
      </td>
      <td className="py-3">
        <Badge
          label={ev.severity}
          colorClass={SEVERITY_CLASSES[ev.severity] ?? "bg-white/10 text-white/30 border-white/10"}
        />
      </td>
    </tr>
  );
}

/* ── Agent Log Step ─────────────────────────────────────────────────────── */
function AgentLogStep({ log }: { log: AgentExecutionLog }) {
  const [expanded, setExpanded] = useState(false);
  let observationParsed: Record<string, unknown> | null = null;
  try {
    if (log.observation) observationParsed = JSON.parse(log.observation);
  } catch {
    /* plain text observation */
  }

  return (
    <div
      id={`log-step-${log.id}`}
      className="border border-white/5 rounded-xl overflow-hidden"
    >
      {/* Step header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-start gap-4 p-4 text-left hover:bg-white/[0.02] transition"
      >
        <span className="flex-shrink-0 w-6 h-6 rounded-full bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 text-xs flex items-center justify-center font-bold">
          {log.step_number}
        </span>
        <div className="flex-1 min-w-0">
          {log.thought && (
            <p className="text-xs text-white/60 italic mb-1 leading-relaxed">
              💭 {log.thought}
            </p>
          )}
          {log.action && (
            <p className="text-xs font-mono text-purple-400">
              ⚡ {log.action}
              {log.action_input ? (
                <span className="text-white/30 ml-1">({log.action_input})</span>
              ) : null}
            </p>
          )}
        </div>
        <span className="flex-shrink-0 text-white/20 text-xs">
          {expanded ? "▲" : "▼"}
        </span>
      </button>

      {/* Expanded observation */}
      {expanded && log.observation && (
        <div className="border-t border-white/5 p-4 bg-black/20">
          <p className="text-[10px] text-white/30 uppercase tracking-wider mb-2">
            Observation
          </p>
          {observationParsed ? (
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(observationParsed).map(([k, v]) => (
                <div key={k} className="text-xs">
                  <span className="text-white/30">{k}: </span>
                  <span className="text-white/60 font-mono">
                    {String(v)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-white/50 font-mono">{log.observation}</p>
          )}
          <p className="text-[10px] text-white/20 mt-3">
            {new Date(log.timestamp).toLocaleString()}
          </p>
        </div>
      )}
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
    queryFn: () => fetchCaseById(id),
    enabled: id > 0,
    refetchInterval: 10000,
  });

  const investigate = useMutation({
    mutationFn: () => reInvestigateCase(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case", id] }),
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
          <h2 className="text-2xl font-bold text-white">
            Case #{caseData.id}
          </h2>
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
        {/* Risk Score Card */}
        <div className="glass-card">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-3">
            Risk Score
          </p>
          <p className={`text-4xl font-bold ${riskTextColor(caseData.risk_score)}`}>
            {riskPct}%
          </p>
          <div className="mt-3 h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${riskBarColor(caseData.risk_score)}`}
              style={{ width: `${riskPct}%` }}
            />
          </div>
        </div>

        {/* Recommended Action */}
        <div className="glass-card">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-3">
            Recommended Action
          </p>
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

        {/* Evidence & Logs count */}
        <div className="glass-card">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-3">
            Investigation Stats
          </p>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-white/50">Evidence Items</span>
              <span className="text-cyan-400 font-bold">
                {caseData.evidence.length}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-white/50">Agent Steps</span>
              <span className="text-purple-400 font-bold">
                {caseData.logs.length}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-white/50">Actions</span>
              <span className="text-yellow-400 font-bold">
                {caseData.actions.length}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Investigation Summary */}
      {caseData.summary && (
        <div className="glass-card border border-cyan-500/10">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-3">
            Investigation Summary
          </p>
          <p className="text-sm text-white/70 leading-relaxed">
            {caseData.summary}
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Evidence Table */}
        <div className="glass-card">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
            Evidence ({caseData.evidence.length})
          </p>
          {caseData.evidence.length === 0 ? (
            <p className="text-white/20 text-sm py-8 text-center">
              No evidence collected yet.
            </p>
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
          <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
            Mitigation Actions
          </p>
          {caseData.actions.length === 0 ? (
            <p className="text-white/20 text-sm py-8 text-center">
              No actions created yet.
            </p>
          ) : (
            <div className="space-y-3">
              {caseData.actions.map((a) => (
                <div
                  key={a.id}
                  id={`action-item-${a.id}`}
                  className="flex items-center justify-between px-4 py-3 bg-white/[0.02] border border-white/5 rounded-xl"
                >
                  <div>
                    <Badge
                      label={a.action_type}
                      colorClass={ACTION_CLASSES[a.action_type] ?? "bg-white/10 text-white/30 border-white/10"}
                    />
                    <p className="text-[10px] text-white/25 mt-1">
                      by {a.executed_by} ·{" "}
                      {new Date(a.updated_at).toLocaleString()}
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

      {/* Agent Execution Logs */}
      <div className="glass-card">
        <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
          Agent Execution Log ({caseData.logs.length} steps)
        </p>
        {caseData.logs.length === 0 ? (
          <p className="text-white/20 text-sm py-8 text-center">
            No agent steps recorded.
          </p>
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
