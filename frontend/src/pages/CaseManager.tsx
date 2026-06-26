/**
 * ThreatTron AI — Case Manager Page
 * Lists all investigation cases with filtering, search, and status badges.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchCases, type Case } from "../api";

const STATUS_COLORS: Record<string, string> = {
  OPEN: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  INVESTIGATING: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  CLOSED: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
};

const ACTION_COLORS: Record<string, string> = {
  BLOCK_ACCOUNT: "text-red-400",
  MFA_CHALLENGE: "text-yellow-400",
  APPROVE: "text-emerald-400",
  PENDING: "text-white/30",
};

const SEVERITY_GRADIENT: Record<string, string> = {
  HIGH: "from-red-500/20 border-red-500/30",
  MEDIUM: "from-yellow-500/20 border-yellow-500/30",
  LOW: "from-emerald-500/20 border-emerald-500/30",
};

function riskColor(score: number) {
  if (score >= 0.8) return "text-red-400";
  if (score >= 0.45) return "text-yellow-400";
  return "text-emerald-400";
}

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] ?? "bg-white/10 text-white/50 border-white/10";
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${cls}`}>
      {status}
    </span>
  );
}

export default function CaseManager() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const cases = useQuery({
    queryKey: ["cases", statusFilter],
    queryFn: () =>
      fetchCases(200, 0, statusFilter === "ALL" ? undefined : statusFilter),
    refetchInterval: 8000,
  });

  const filtered = (cases.data ?? []).filter((c) => {
    if (!search.trim()) return true;
    const term = search.toLowerCase();
    return (
      String(c.id).includes(term) ||
      (c.summary ?? "").toLowerCase().includes(term) ||
      (c.recommended_action ?? "").toLowerCase().includes(term) ||
      c.status.toLowerCase().includes(term)
    );
  });

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">Case Manager</h2>
        <p className="text-sm text-white/40 mt-1">
          Autonomous fraud investigation cases · High-risk event forensics
        </p>
      </div>

      {/* Controls */}
      <div className="glass-card flex flex-wrap items-center gap-4">
        {/* Search */}
        <input
          id="case-search"
          type="text"
          placeholder="Search cases…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-48 px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder-white/30 focus:outline-none focus:border-cyan-500/50 transition"
        />

        {/* Status filter */}
        <div className="flex gap-2">
          {["ALL", "OPEN", "INVESTIGATING", "CLOSED"].map((s) => (
            <button
              key={s}
              id={`filter-${s.toLowerCase()}`}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                statusFilter === s
                  ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                  : "bg-white/5 text-white/40 border border-white/10 hover:text-white/70"
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Count */}
        <span className="text-xs text-white/30 ml-auto">
          {filtered.length} case{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Cases Table */}
      <div className="glass-card overflow-x-auto">
        {cases.isLoading ? (
          <div className="py-16 text-center text-white/30 text-sm">
            Loading cases…
          </div>
        ) : cases.isError ? (
          <div className="py-16 text-center text-white/30 text-sm">
            <p className="text-4xl mb-3">⚠️</p>
            <p>Unable to load cases. Check backend connectivity.</p>
            <p className="mt-1 text-xs text-white/15">
              {String(cases.error)}
            </p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center text-white/20 text-sm">
            <p className="text-4xl mb-3">🕵️</p>
            <p>No cases found. High-risk events will appear here automatically.</p>
            <p className="mt-1 text-xs text-white/15">
              Run simulate_threat.py to generate test cases.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-white/30 text-xs uppercase tracking-wider border-b border-white/5">
                <th className="pb-3 pr-4">Case #</th>
                <th className="pb-3 pr-4">Status</th>
                <th className="pb-3 pr-4">Risk Score</th>
                <th className="pb-3 pr-4">Recommended Action</th>
                <th className="pb-3 pr-4">Created</th>
                <th className="pb-3">Summary</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c: Case) => (
                <tr
                  key={c.id}
                  id={`case-row-${c.id}`}
                  onClick={() => navigate(`/cases/${c.id}`)}
                  className="border-b border-white/[0.03] hover:bg-white/[0.03] transition cursor-pointer group"
                >
                  {/* ID */}
                  <td className="py-3 pr-4 font-mono text-xs text-white/50">
                    #{c.id}
                  </td>

                  {/* Status */}
                  <td className="py-3 pr-4">
                    <StatusBadge status={c.status} />
                  </td>

                  {/* Risk Score */}
                  <td className={`py-3 pr-4 font-mono font-bold ${riskColor(c.risk_score)}`}>
                    {(c.risk_score * 100).toFixed(1)}%
                  </td>

                  {/* Recommended Action */}
                  <td className={`py-3 pr-4 text-xs font-semibold ${ACTION_COLORS[c.recommended_action ?? "PENDING"] ?? "text-white/40"}`}>
                    {c.recommended_action ?? "—"}
                  </td>

                  {/* Created At */}
                  <td className="py-3 pr-4 text-xs text-white/40">
                    {new Date(c.created_at).toLocaleString()}
                  </td>

                  {/* Summary */}
                  <td className="py-3 text-xs text-white/50 max-w-xs truncate group-hover:text-white/70">
                    {c.summary ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
