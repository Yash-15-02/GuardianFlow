/**
 * ThreatTron AI — ML Sandbox Page
 * Load sample customers, edit features, predict risk, view SHAP explanations.
 */

import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";
import RiskGauge from "../components/RiskGauge";
import {
  fetchSampleRow,
  predict,
  explain,
  type RiskResponse,
  type ShapExplanation,
} from "../api";

/** The most important features the user can adjust via sliders. */
const KEY_FEATURES = [
  "F3912",
  "F2506",
  "F2507",
  "F2408",
  "F2409",
  "F515",
  "F518",
  "F2578",
  "F82",
  "F81",
];

export default function Sandbox() {
  const [sampleIndex, setSampleIndex] = useState(0);
  const [features, setFeatures] = useState<Record<string, number>>({});
  const [result, setResult] = useState<RiskResponse | null>(null);
  const [shapData, setShapData] = useState<ShapExplanation | null>(null);
  const [loading, setLoading] = useState(false);

  const loadSample = async () => {
    setLoading(true);
    try {
      const data = await fetchSampleRow(sampleIndex);
      setFeatures(data.features);
      setResult(null);
      setShapData(null);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const runPrediction = async () => {
    setLoading(true);
    try {
      const [pred, shap] = await Promise.all([
        predict(features),
        explain(features),
      ]);
      setResult(pred);
      setShapData(shap);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const updateFeature = (name: string, value: number) => {
    setFeatures((prev) => ({ ...prev, [name]: value }));
  };

  const shapBars = shapData
    ? shapData.shap_values.slice(0, 15).map((sv) => ({
        feature: sv.feature,
        shap: parseFloat(sv.shap.toFixed(4)),
        fill: sv.shap >= 0 ? "#ef4444" : "#22c55e",
      }))
    : [];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">ML Sandbox</h2>
        <p className="text-sm text-white/40 mt-1">
          Load a customer, adjust features, and observe live risk predictions
        </p>
      </div>

      {/* Controls */}
      <div className="glass-card">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-xs text-white/40 mb-1">
              Sample Row Index
            </label>
            <input
              type="number"
              min={0}
              max={9081}
              value={sampleIndex}
              onChange={(e) => setSampleIndex(parseInt(e.target.value) || 0)}
              className="w-28 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500/50"
            />
          </div>
          <button
            onClick={loadSample}
            disabled={loading}
            className="px-5 py-2 bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 rounded-lg text-sm font-medium hover:bg-cyan-500/30 transition disabled:opacity-50"
          >
            {loading ? "Loading…" : "Load Sample"}
          </button>
          <button
            onClick={runPrediction}
            disabled={loading || Object.keys(features).length === 0}
            className="px-5 py-2 bg-purple-500/20 border border-purple-500/30 text-purple-400 rounded-lg text-sm font-medium hover:bg-purple-500/30 transition disabled:opacity-50"
          >
            {loading ? "Predicting…" : "🚀 Run Prediction"}
          </button>
        </div>
      </div>

      {/* Feature Sliders + Result */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sliders */}
        <div className="lg:col-span-2 glass-card">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
            Key Feature Controls
          </p>
          {Object.keys(features).length === 0 ? (
            <div className="py-16 text-center text-white/20 text-sm">
              Load a sample to see feature controls.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-4">
              {KEY_FEATURES.filter((f) => f in features).map((feat) => (
                <div key={feat}>
                  <div className="flex justify-between mb-1">
                    <label className="text-xs text-white/50 font-mono">
                      {feat}
                    </label>
                    <span className="text-xs text-cyan-400 font-mono">
                      {features[feat]?.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={Math.max(2, features[feat] * 2 || 1)}
                    step={0.01}
                    value={features[feat] ?? 0}
                    onChange={(e) =>
                      updateFeature(feat, parseFloat(e.target.value))
                    }
                    className="w-full h-1.5 bg-white/10 rounded-full appearance-none cursor-pointer accent-cyan-500"
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Result Gauge */}
        <div className="glass-card flex flex-col items-center justify-center">
          {result ? (
            <>
              <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
                Prediction Result
              </p>
              <RiskGauge score={result.risk_score} size={200} />
              <div className="mt-4 text-center">
                <p className="text-sm text-white/60">
                  Prediction:{" "}
                  <span
                    className={`font-bold ${result.prediction === 1 ? "text-red-400" : "text-emerald-400"}`}
                  >
                    {result.prediction === 1 ? "ANOMALY" : "NORMAL"}
                  </span>
                </p>
                <p className="text-xs text-white/40 mt-1">
                  Score: {result.risk_score.toFixed(4)}
                </p>
              </div>

              {/* Top Factors */}
              {result.top_factors.length > 0 && (
                <div className="mt-4 w-full">
                  <p className="text-xs text-white/30 mb-2">
                    Top Contributing Factors:
                  </p>
                  <div className="space-y-1">
                    {result.top_factors.slice(0, 5).map((f) => (
                      <div
                        key={f.feature}
                        className="flex justify-between text-xs"
                      >
                        <span className="text-white/50 font-mono">
                          {f.feature}
                        </span>
                        <span className="text-purple-400">
                          {f.importance.toFixed(0)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-center text-white/20 text-sm py-8">
              <p className="text-4xl mb-3">🧪</p>
              <p>Load a sample and run prediction</p>
            </div>
          )}
        </div>
      </div>

      {/* SHAP Explanation Chart */}
      {shapBars.length > 0 && (
        <div className="glass-card">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-4">
            SHAP Feature Explanation
          </p>
          <p className="text-xs text-white/30 mb-3">
            Red = pushes toward anomaly · Green = pushes toward normal · Base
            value: {shapData?.base_value.toFixed(4)}
          </p>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart
              data={shapBars}
              layout="vertical"
              margin={{ left: 70, right: 20 }}
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
                width={65}
              />
              <Tooltip
                contentStyle={{
                  background: "rgba(13,18,36,0.95)",
                  border: "1px solid rgba(168,85,247,0.3)",
                  borderRadius: 12,
                  fontSize: 12,
                }}
              />
              <ReferenceLine x={0} stroke="rgba(255,255,255,0.15)" />
              <Bar dataKey="shap" radius={[0, 4, 4, 0]} barSize={14}>
                {shapBars.map((entry, idx) => (
                  <Cell key={idx} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
