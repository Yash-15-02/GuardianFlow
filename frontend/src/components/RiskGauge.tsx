/**
 * ThreatTron AI — Risk Gauge Component
 * Animated SVG radial gauge showing current risk score.
 */

interface RiskGaugeProps {
  score: number; // 0.0 – 1.0
  size?: number;
}

export default function RiskGauge({ score, size = 200 }: RiskGaugeProps) {
  const pct = Math.max(0, Math.min(score, 1));
  const radius = 80;
  const stroke = 12;
  const circumference = Math.PI * radius; // half-circle
  const offset = circumference - pct * circumference;

  const getColor = () => {
    if (pct >= 0.8) return "#ef4444";
    if (pct >= 0.45) return "#eab308";
    return "#22c55e";
  };

  const getLabel = () => {
    if (pct >= 0.8) return "CRITICAL";
    if (pct >= 0.45) return "MEDIUM";
    return "LOW";
  };

  const color = getColor();
  const isHigh = pct >= 0.8;

  return (
    <div
      className={`flex flex-col items-center ${isHigh ? "pulse-alert" : ""}`}
    >
      <svg
        width={size}
        height={size * 0.6}
        viewBox="0 0 200 120"
        className="gauge-glow"
      >
        {/* Background arc */}
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={stroke}
          strokeLinecap="round"
        />
        {/* Value arc */}
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{
            transition: "stroke-dashoffset 0.8s ease, stroke 0.5s ease",
            filter: `drop-shadow(0 0 8px ${color}80)`,
          }}
        />
        {/* Score text */}
        <text
          x="100"
          y="85"
          textAnchor="middle"
          fill={color}
          fontSize="32"
          fontWeight="700"
          fontFamily="Inter, system-ui"
        >
          {(pct * 100).toFixed(0)}
        </text>
        <text
          x="100"
          y="105"
          textAnchor="middle"
          fill="rgba(255,255,255,0.5)"
          fontSize="11"
          fontWeight="500"
          fontFamily="Inter, system-ui"
          letterSpacing="2"
        >
          {getLabel()}
        </text>
      </svg>
      {isHigh && (
        <div className="mt-2 px-4 py-1.5 rounded-full bg-red-500/20 border border-red-500/40 text-red-400 text-xs font-semibold tracking-wider animate-pulse">
          🔴 HIGH RISK ALERT
        </div>
      )}
    </div>
  );
}
