"""
ThreatTron AI — Pydantic Schemas (Request / Response)
======================================================
"""

from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


# ── Request Bodies ───────────────────────────────────────────────────────────
class SessionCreate(BaseModel):
    session_id: str
    agent_id: str | None = None
    hostname: str | None = None


class EventPayload(BaseModel):
    session_id: str
    account_type: str | None = None
    occupation: str | None = None
    segment: str | None = None
    area: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)


class BatchPayload(BaseModel):
    session: SessionCreate | None = None
    events: list[EventPayload]


class PredictRequest(BaseModel):
    features: dict[str, Any] = Field(default_factory=dict)


class SampleRequest(BaseModel):
    index: int = 0


# ── Response Bodies ──────────────────────────────────────────────────────────
class RiskResponse(BaseModel):
    risk_score: float
    risk_level: str
    prediction: int
    top_factors: list[dict[str, Any]] = Field(default_factory=list)


class EventResponse(BaseModel):
    id: int
    session_id: str
    timestamp: datetime | None = None
    account_type: str | None = None
    occupation: str | None = None
    segment: str | None = None
    area: str | None = None
    risk_score: float | None = None
    prediction: int | None = None
    risk_level: str | None = None

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_events: int
    high_risk_events: int
    normal_events: int
    medium_risk_events: int
    avg_risk_score: float


class TimelinePoint(BaseModel):
    timestamp: str
    risk_score: float
    prediction: int
    risk_level: str


class FeatureImportance(BaseModel):
    feature: str
    importance: float


class ShapExplanation(BaseModel):
    base_value: float
    shap_values: list[dict[str, Any]]


# ── Case Investigation Schemas ────────────────────────────────────────────────

class CaseEvidenceResponse(BaseModel):
    id: int
    case_id: int
    source: str
    description: str
    severity: str

    class Config:
        from_attributes = True


class AgentExecutionLogResponse(BaseModel):
    id: int
    case_id: int
    step_number: int
    thought: str | None = None
    action: str | None = None
    action_input: str | None = None
    observation: str | None = None
    timestamp: datetime

    class Config:
        from_attributes = True


class MitigationActionResponse(BaseModel):
    id: int
    case_id: int
    action_type: str
    status: str
    executed_by: str
    updated_at: datetime

    class Config:
        from_attributes = True


class CaseResponse(BaseModel):
    id: int
    trigger_event_id: int
    status: str
    risk_score: float
    summary: str | None = None
    recommended_action: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class CaseDetailResponse(CaseResponse):
    evidence: list[CaseEvidenceResponse] = Field(default_factory=list)
    logs: list[AgentExecutionLogResponse] = Field(default_factory=list)
    actions: list[MitigationActionResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class InvestigateResponse(BaseModel):
    case_id: int
    status: str
    risk_score: float
    recommended_action: str
    summary: str
    evidence_count: int
    logs_count: int

