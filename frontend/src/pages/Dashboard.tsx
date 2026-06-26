/**
 * ThreatTron AI — Dashboard Page
 * Shows stats cards, live risk gauge, recent events table, and risk timeline.
 */

import { useQuery } from "@tanstack/react-query";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts";
import StatCard from "../components/StatCard";
import RiskGauge from "../components/RiskGauge";
import {
  fetchDashboardStats,
  fetchEvents,
  fetchTimeline,
  type TelemetryEvent,
} from "../api";

function riskBadge(level: string | null) {
  if (level === "HIGH")
    return (
      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-500/20 text-red-400 border border-red-500/30">
        HIGH
      </span>
    );
  if (level === "MEDIUM")
    return (
      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
        MEDIUM
      </span>
    );
  return (
    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
      LOW
    </span>
  );
}

export default function Dashboard() {
  const stats = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: fetchDashboardStats,
    refetchInterval: 5000,
  });

  const events = useQuery({
    queryKey: ["events"],
    queryFn: () => fetchEvents(20),
    refetchInterval: 5000,
  });

  const timeline = useQuery({
    queryKey: ["timeline"],
    queryFn: () => fetchTimeline(50),
    refetchInterval: 5000,
  });

  const latestRisk =
    events.data && events.data.length > 0
      ? events.data[0].risk_score ?? 0
      : 0;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">Dashboard</h2>
        <p className="text-sm text-white/40 mt-1">
          Real-time fraud detection overview
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Events"
          value={stats.data?.total_events ?? "—"}
          icon="📦"
          color="cyan"
          subtitle="All ingested events"
        />
        <StatCard
          title="High Risk"
          value={stats.data?.high_risk_events ?? "—"}
          icon="🔴"
          color="red"
          subtitle="Score ≥ 0.80"
        />
        <StatCard
          title="Medium Risk"
          value={stats.data?.medium_risk_events ?? "—"}
          icon="🟡"
          color="yellow"
          subtitle="Score 0.45 – 0.79"
        />
        <StatCard
          title="Normal"
          value={stats.data?.normal_events ?? "—"}
          icon="🟢"
          color="green"
          subtitle="Score < 0.45"
        />
      </div>

      {/* Gauge + Timeline Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live Gauge */}
        <div className="glass-card flex flex-col items-center justify-center">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
            Latest Risk Score
          </p>
          <RiskGauge score={latestRisk} size={240} />
          <p className="mt-4 text-sm text-white/50">
            Avg:{" "}
            <span className="text-cyan-400 font-semibold">
              {(stats.data?.avg_risk_score ?? 0).toFixed(3)}
            </span>
          </p>
        </div>

        {/* Risk Timeline Chart */}
        <div className="glass-card lg:col-span-2">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
            Risk Timeline
          </p>
          {timeline.data && timeline.data.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={timeline.data}>
                <defs>
                  <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.04)"
                />
                <XAxis
                  dataKey="timestamp"
                  tick={{ fontSize: 9, fill: "rgba(255,255,255,0.3)" }}
                  tickFormatter={(v: string) =>
                    v ? new Date(v).toLocaleTimeString() : ""
                  }
                />
                <YAxis
                  domain={[0, 1]}
                  tick={{ fontSize: 10, fill: "rgba(255,255,255,0.3)" }}
                />
                <Tooltip
                  contentStyle={{
                    background: "rgba(13,18,36,0.95)",
                    border: "1px solid rgba(34,211,238,0.2)",
                    borderRadius: 12,
                    fontSize: 12,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="risk_score"
                  stroke="#22d3ee"
                  fill="url(#riskGrad)"
                  strokeWidth={2}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-white/20 text-sm">
              No timeline data yet — start the agent to stream events.
            </div>
          )}
        </div>
      </div>

      {/* Recent Events Table */}
      <div className="glass-card">
        <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
          Recent Events
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-white/30 text-xs uppercase tracking-wider border-b border-white/5">
                <th className="pb-3 pr-4">ID</th>
                <th className="pb-3 pr-4">Time</th>
                <th className="pb-3 pr-4">Account</th>
                <th className="pb-3 pr-4">Occupation</th>
                <th className="pb-3 pr-4">Segment</th>
                <th className="pb-3 pr-4">Risk</th>
                <th className="pb-3">Level</th>
              </tr>
            </thead>
            <tbody>
              {events.data && events.data.length > 0 ? (
                events.data.map((ev: TelemetryEvent) => (
                  <tr
                    key={ev.id}
                    className="border-b border-white/[0.03] hover:bg-white/[0.02] transition"
                  >
                    <td className="py-3 pr-4 text-white/50 font-mono text-xs">
                      {ev.id}
                    </td>
                    <td className="py-3 pr-4 text-white/60 text-xs">
                      {ev.timestamp
                        ? new Date(ev.timestamp).toLocaleString()
                        : "—"}
                    </td>
                    <td className="py-3 pr-4 text-white/70">
                      {ev.account_type ?? "—"}
                    </td>
                    <td className="py-3 pr-4 text-white/70">
                      {ev.occupation ?? "—"}
                    </td>
                    <td className="py-3 pr-4 text-white/70">
                      {ev.segment ?? "—"}
                    </td>
                    <td className="py-3 pr-4 text-cyan-400 font-mono font-semibold">
                      {ev.risk_score != null ? ev.risk_score.toFixed(3) : "—"}
                    </td>
                    <td className="py-3">{riskBadge(ev.risk_level)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={7}
                    className="py-12 text-center text-white/20 text-sm"
                  >
                    No events yet — start the agent or threat simulator.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
