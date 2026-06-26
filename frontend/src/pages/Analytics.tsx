/**
 * ThreatTron AI — Analytics Page
 * Feature importance chart, risk distribution, and model evaluation metrics.
 */

import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
} from "recharts";
import {
  fetchFeatureImportance,
  fetchDashboardStats,
  fetchEvaluationReport,
} from "../api";

const PIE_COLORS = ["#22c55e", "#eab308", "#ef4444"];

export default function Analytics() {
  const importance = useQuery({
    queryKey: ["feature-importance"],
    queryFn: () => fetchFeatureImportance(20),
  });

  const stats = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: fetchDashboardStats,
  });

  const evaluation = useQuery({
    queryKey: ["evaluation"],
    queryFn: fetchEvaluationReport,
  });

  const pieData = stats.data
    ? [
        { name: "Normal", value: stats.data.normal_events },
        { name: "Medium", value: stats.data.medium_risk_events },
        { name: "High Risk", value: stats.data.high_risk_events },
      ]
    : [];

  const rocData =
    evaluation.data?.roc_curve
      ? evaluation.data.roc_curve.fpr.map((fpr: number, i: number) => ({
          fpr: parseFloat(fpr.toFixed(3)),
          tpr: parseFloat(evaluation.data!.roc_curve.tpr[i].toFixed(3)),
        }))
      : [];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">Analytics</h2>
        <p className="text-sm text-white/40 mt-1">
          Model performance & feature insights
        </p>
      </div>

      {/* Model Metrics Cards */}
      {evaluation.data && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {[
            {
              label: "Accuracy",
              val: evaluation.data.accuracy,
              color: "text-cyan-400",
            },
            {
              label: "Precision",
              val: evaluation.data.precision,
              color: "text-purple-400",
            },
            {
              label: "Recall",
              val: evaluation.data.recall,
              color: "text-emerald-400",
            },
            {
              label: "F1 Score",
              val: evaluation.data.f1_score,
              color: "text-yellow-400",
            },
            {
              label: "ROC AUC",
              val: evaluation.data.roc_auc,
              color: "text-red-400",
            },
          ].map((m) => (
            <div key={m.label} className="glass-card text-center">
              <p className="text-xs text-white/40 uppercase tracking-wider mb-2">
                {m.label}
              </p>
              <p className={`text-2xl font-bold ${m.color}`}>
                {(m.val * 100).toFixed(1)}%
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Feature Importance */}
        <div className="glass-card">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
            Top Feature Importance
          </p>
          {importance.data && importance.data.length > 0 ? (
            <ResponsiveContainer width="100%" height={400}>
              <BarChart
                data={importance.data.slice(0, 15)}
                layout="vertical"
                margin={{ left: 60 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.04)"
                />
                <XAxis
                  type="number"
                  tick={{ fontSize: 10, fill: "rgba(255,255,255,0.3)" }}
                />
                <YAxis
                  dataKey="feature"
                  type="category"
                  tick={{ fontSize: 11, fill: "rgba(255,255,255,0.5)" }}
                  width={55}
                />
                <Tooltip
                  contentStyle={{
                    background: "rgba(13,18,36,0.95)",
                    border: "1px solid rgba(168,85,247,0.3)",
                    borderRadius: 12,
                    fontSize: 12,
                  }}
                />
                <Bar
                  dataKey="importance"
                  fill="#a855f7"
                  radius={[0, 6, 6, 0]}
                  barSize={16}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-96 flex items-center justify-center text-white/20 text-sm">
              Train the model first to see feature importance.
            </div>
          )}
        </div>

        {/* Risk Distribution Pie + ROC */}
        <div className="space-y-6">
          {/* Pie */}
          <div className="glass-card">
            <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
              Risk Distribution
            </p>
            {pieData.length > 0 &&
            pieData.some((d) => d.value > 0) ? (
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={4}
                    dataKey="value"
                    stroke="none"
                  >
                    {pieData.map((_, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={PIE_COLORS[index % PIE_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: "rgba(13,18,36,0.95)",
                      border: "1px solid rgba(34,211,238,0.2)",
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-48 flex items-center justify-center text-white/20 text-sm">
                No data
              </div>
            )}
            <div className="flex justify-center gap-6 mt-2">
              {pieData.map((d, i) => (
                <div key={d.name} className="flex items-center gap-2 text-xs">
                  <span
                    className="w-3 h-3 rounded-full"
                    style={{ background: PIE_COLORS[i] }}
                  />
                  <span className="text-white/50">
                    {d.name}: {d.value}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* ROC Curve */}
          <div className="glass-card">
            <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
              ROC Curve
            </p>
            {rocData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={rocData}>
                  <defs>
                    <linearGradient id="rocGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="0%"
                        stopColor="#a855f7"
                        stopOpacity={0.3}
                      />
                      <stop
                        offset="100%"
                        stopColor="#a855f7"
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.04)"
                  />
                  <XAxis
                    dataKey="fpr"
                    tick={{ fontSize: 10, fill: "rgba(255,255,255,0.3)" }}
                    label={{
                      value: "FPR",
                      position: "bottom",
                      fill: "rgba(255,255,255,0.3)",
                      fontSize: 10,
                    }}
                  />
                  <YAxis
                    dataKey="tpr"
                    tick={{ fontSize: 10, fill: "rgba(255,255,255,0.3)" }}
                    label={{
                      value: "TPR",
                      angle: -90,
                      position: "insideLeft",
                      fill: "rgba(255,255,255,0.3)",
                      fontSize: 10,
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "rgba(13,18,36,0.95)",
                      border: "1px solid rgba(168,85,247,0.3)",
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="tpr"
                    stroke="#a855f7"
                    fill="url(#rocGrad)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-48 flex items-center justify-center text-white/20 text-sm">
                Run evaluate.py to generate ROC data.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Confusion Matrix */}
      {evaluation.data?.confusion_matrix && (
        <div className="glass-card max-w-md">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
            Confusion Matrix
          </p>
          <div className="grid grid-cols-3 gap-1 text-center text-xs">
            <div />
            <div className="text-white/40 py-2">Pred Normal</div>
            <div className="text-white/40 py-2">Pred Anomaly</div>
            <div className="text-white/40 py-2">Actual Normal</div>
            <div className="py-3 rounded-lg bg-emerald-500/10 text-emerald-400 font-bold text-lg">
              {evaluation.data.confusion_matrix.true_negative}
            </div>
            <div className="py-3 rounded-lg bg-red-500/10 text-red-400 font-bold text-lg">
              {evaluation.data.confusion_matrix.false_positive}
            </div>
            <div className="text-white/40 py-2">Actual Anomaly</div>
            <div className="py-3 rounded-lg bg-yellow-500/10 text-yellow-400 font-bold text-lg">
              {evaluation.data.confusion_matrix.false_negative}
            </div>
            <div className="py-3 rounded-lg bg-cyan-500/10 text-cyan-400 font-bold text-lg">
              {evaluation.data.confusion_matrix.true_positive}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
