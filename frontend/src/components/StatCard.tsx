/**
 * ThreatTron AI — Stat Card Component
 */

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: string;
  color: "cyan" | "red" | "green" | "yellow" | "purple";
}

const colorMap: Record<string, string> = {
  cyan: "from-cyan-500/20 to-cyan-600/5 border-cyan-500/20 text-cyan-400",
  red: "from-red-500/20 to-red-600/5 border-red-500/20 text-red-400",
  green:
    "from-emerald-500/20 to-emerald-600/5 border-emerald-500/20 text-emerald-400",
  yellow:
    "from-yellow-500/20 to-yellow-600/5 border-yellow-500/20 text-yellow-400",
  purple:
    "from-purple-500/20 to-purple-600/5 border-purple-500/20 text-purple-400",
};

export default function StatCard({
  title,
  value,
  subtitle,
  icon,
  color,
}: StatCardProps) {
  return (
    <div
      className={`glass-card bg-gradient-to-br ${colorMap[color]} animate-fade-in`}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-2xl">{icon}</span>
        <span
          className={`text-xs font-semibold uppercase tracking-wider opacity-60`}
        >
          {title}
        </span>
      </div>
      <div className="text-3xl font-bold text-white mb-1">{value}</div>
      {subtitle && (
        <div className="text-xs text-white/40">{subtitle}</div>
      )}
    </div>
  );
}
