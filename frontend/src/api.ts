/**
 * ThreatTron AI — API Service Layer
 * Typed axios client for all backend endpoints.
 */

import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "";

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

/* ── Types ─────────────────────────────────────────────────────────────────── */

export interface DashboardStats {
  total_events: number;
  high_risk_events: number;
  normal_events: number;
  medium_risk_events: number;
  avg_risk_score: number;
}

export interface TelemetryEvent {
  id: number;
  session_id: string;
  timestamp: string;
  account_type: string | null;
  occupation: string | null;
  segment: string | null;
  area: string | null;
  risk_score: number | null;
  prediction: number | null;
  risk_level: string | null;
}

export interface TimelinePoint {
  timestamp: string;
  risk_score: number;
  prediction: number;
  risk_level: string;
}

export interface FeatureImportance {
  feature: string;
  importance: number;
}

export interface RiskResponse {
  risk_score: number;
  risk_level: string;
  prediction: number;
  top_factors: FeatureImportance[];
}

export interface ShapValue {
  feature: string;
  value: number;
  shap: number;
}

export interface ShapExplanation {
  base_value: number;
  shap_values: ShapValue[];
}

export interface EvaluationReport {
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  roc_auc: number;
  confusion_matrix: {
    true_negative: number;
    false_positive: number;
    false_negative: number;
    true_positive: number;
  };
  roc_curve: {
    fpr: number[];
    tpr: number[];
  };
  top_features: FeatureImportance[];
}

/* ── Endpoints ─────────────────────────────────────────────────────────────── */

export const fetchDashboardStats = () =>
  api.get<DashboardStats>("/api/dashboard/stats").then((r) => r.data);

export const fetchEvents = (limit = 100, offset = 0, riskLevel?: string) =>
  api
    .get<TelemetryEvent[]>("/api/events", {
      params: { limit, offset, risk_level: riskLevel },
    })
    .then((r) => r.data);

export const fetchHighRiskEvents = (limit = 50) =>
  api
    .get<TelemetryEvent[]>("/api/dashboard/high-risk", { params: { limit } })
    .then((r) => r.data);

export const fetchTimeline = (limit = 100) =>
  api
    .get<TimelinePoint[]>("/api/risk/timeline", { params: { limit } })
    .then((r) => r.data);

export const fetchFeatureImportance = (topN = 20) =>
  api
    .get<FeatureImportance[]>("/api/feature-importance", {
      params: { top_n: topN },
    })
    .then((r) => r.data);

export const predict = (features: Record<string, number>) =>
  api.post<RiskResponse>("/api/predict", { features }).then((r) => r.data);

export const explain = (features: Record<string, number>) =>
  api.post<ShapExplanation>("/api/explain", { features }).then((r) => r.data);

export const fetchSampleRow = (index: number) =>
  api
    .post<{ index: number; features: Record<string, number> }>("/api/sample", {
      index,
    })
    .then((r) => r.data);

export const fetchEvaluationReport = () =>
  api.get<EvaluationReport>("/api/model/evaluation").then((r) => r.data);

export default api;
