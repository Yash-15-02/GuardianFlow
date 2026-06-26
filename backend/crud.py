"""
ThreatTron AI — CRUD Operations
================================
Database read/write helpers used by the API routes.
"""

import json
import datetime
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from backend.models import (
    AgentSession,
    TelemetryEvent,
    Case,
    CaseEvidence,
    AgentExecutionLog,
    MitigationAction,
    CaseReasoning,
    CaseDecision,
)



# ── Sessions ─────────────────────────────────────────────────────────────────
def get_or_create_session(
    db: Session,
    session_id: str,
    agent_id: str | None = None,
    hostname: str | None = None,
) -> AgentSession:
    existing = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
    if existing:
        return existing
    new_session = AgentSession(
        session_id=session_id,
        agent_id=agent_id,
        hostname=hostname,
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


# ── Events ───────────────────────────────────────────────────────────────────
def create_event(
    db: Session,
    session_id: str,
    account_type: str | None,
    occupation: str | None,
    segment: str | None,
    area: str | None,
    risk_score: float | None,
    prediction: int | None,
    risk_level: str | None,
    features: dict[str, Any],
) -> TelemetryEvent:
    event = TelemetryEvent(
        session_id=session_id,
        timestamp=datetime.datetime.utcnow(),
        account_type=account_type,
        occupation=occupation,
        segment=segment,
        area=area,
        risk_score=risk_score,
        prediction=prediction,
        risk_level=risk_level,
        features_json=json.dumps(features),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_events(
    db: Session,
    limit: int = 100,
    offset: int = 0,
    risk_level: str | None = None,
) -> list[TelemetryEvent]:
    q = db.query(TelemetryEvent).order_by(desc(TelemetryEvent.timestamp))
    if risk_level:
        q = q.filter(TelemetryEvent.risk_level == risk_level.upper())
    return q.offset(offset).limit(limit).all()


def get_events_count(db: Session) -> int:
    return db.query(func.count(TelemetryEvent.id)).scalar() or 0


def get_high_risk_events(db: Session, threshold: float = 0.80, limit: int = 50) -> list[TelemetryEvent]:
    return (
        db.query(TelemetryEvent)
        .filter(TelemetryEvent.risk_score >= threshold)
        .order_by(desc(TelemetryEvent.timestamp))
        .limit(limit)
        .all()
    )


def get_dashboard_stats(db: Session) -> dict:
    total = db.query(func.count(TelemetryEvent.id)).scalar() or 0
    high = db.query(func.count(TelemetryEvent.id)).filter(TelemetryEvent.risk_level == "HIGH").scalar() or 0
    medium = db.query(func.count(TelemetryEvent.id)).filter(TelemetryEvent.risk_level == "MEDIUM").scalar() or 0
    normal = db.query(func.count(TelemetryEvent.id)).filter(TelemetryEvent.risk_level == "LOW").scalar() or 0
    avg_risk = db.query(func.avg(TelemetryEvent.risk_score)).scalar() or 0.0
    return {
        "total_events": total,
        "high_risk_events": high,
        "medium_risk_events": medium,
        "normal_events": normal,
        "avg_risk_score": round(float(avg_risk), 4),
    }


def get_risk_timeline(db: Session, limit: int = 100) -> list[dict]:
    events = (
        db.query(TelemetryEvent)
        .order_by(desc(TelemetryEvent.timestamp))
        .limit(limit)
        .all()
    )
    timeline = []
    for e in reversed(events):
        timeline.append({
            "timestamp": e.timestamp.isoformat() if e.timestamp else "",
            "risk_score": float(e.risk_score) if e.risk_score is not None else 0.0,
            "prediction": int(e.prediction) if e.prediction is not None else 0,
            "risk_level": e.risk_level or "LOW",
        })
    return timeline


# ── Case Investigation CRUD ───────────────────────────────────────────────────

def create_case(
    db: Session,
    trigger_event_id: int,
    risk_score: float,
    summary: str = "",
    recommended_action: str = "PENDING",
) -> Case:
    case = Case(
        trigger_event_id=trigger_event_id,
        status="OPEN",
        risk_score=risk_score,
        summary=summary,
        recommended_action=recommended_action,
        created_at=datetime.datetime.utcnow(),
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def get_cases(
    db: Session,
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
) -> list[Case]:
    q = db.query(Case)
    if status:
        q = q.filter(Case.status == status)
    return q.order_by(desc(Case.created_at)).offset(offset).limit(limit).all()


def get_case_by_id(db: Session, case_id: int) -> Case | None:
    return db.query(Case).filter(Case.id == case_id).first()


def update_case_status(
    db: Session,
    case_id: int,
    status: str,
    summary: str | None = None,
    recommended_action: str | None = None,
) -> Case | None:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return None
    case.status = status
    if summary is not None:
        case.summary = summary
    if recommended_action is not None:
        case.recommended_action = recommended_action
    db.commit()
    db.refresh(case)
    return case


def create_evidence(
    db: Session,
    case_id: int,
    source: str,
    description: str,
    severity: str = "MEDIUM",
) -> CaseEvidence:
    ev = CaseEvidence(
        case_id=case_id,
        source=source,
        description=description,
        severity=severity,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def get_case_evidence(db: Session, case_id: int) -> list[CaseEvidence]:
    return (
        db.query(CaseEvidence)
        .filter(CaseEvidence.case_id == case_id)
        .order_by(CaseEvidence.id)
        .all()
    )


def create_agent_log(
    db: Session,
    case_id: int,
    step_number: int,
    thought: str | None = None,
    action: str | None = None,
    action_input: str | None = None,
    observation: str | None = None,
) -> AgentExecutionLog:
    log = AgentExecutionLog(
        case_id=case_id,
        step_number=step_number,
        thought=thought,
        action=action,
        action_input=action_input,
        observation=observation,
        timestamp=datetime.datetime.utcnow(),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def create_mitigation_action(
    db: Session,
    case_id: int,
    action_type: str,
    status: str = "PENDING_APPROVAL",
    executed_by: str = "AGENT_AUTO",
) -> MitigationAction:
    action = MitigationAction(
        case_id=case_id,
        action_type=action_type,
        status=status,
        executed_by=executed_by,
        updated_at=datetime.datetime.utcnow(),
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


# ── Reasoning CRUD ────────────────────────────────────────────────────────────

def upsert_reasoning(
    db: Session,
    case_id: int,
    result: Any,  # ReasoningResult from reasoning_service
) -> CaseReasoning:
    """Insert or replace the reasoning record for a case."""
    import json
    row = db.query(CaseReasoning).filter(CaseReasoning.case_id == case_id).first()
    if row:
        db.delete(row)
        db.commit()
    row = CaseReasoning(
        case_id=case_id,
        executive_summary=result.executive_summary,
        findings_json=json.dumps(result.findings),
        confidence=result.confidence,
        rationale=result.rationale,
        reasoning_trace_json=json.dumps(result.reasoning_trace),
        provider=result.provider,
        created_at=datetime.datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_reasoning_by_case(db: Session, case_id: int) -> CaseReasoning | None:
    return db.query(CaseReasoning).filter(CaseReasoning.case_id == case_id).first()


# ── Decision CRUD ─────────────────────────────────────────────────────────────

def upsert_decision(
    db: Session,
    case_id: int,
    result: Any,  # DecisionResult from decision_engine
) -> CaseDecision:
    """Insert or replace the decision record for a case."""
    import json
    row = db.query(CaseDecision).filter(CaseDecision.case_id == case_id).first()
    if row:
        db.delete(row)
        db.commit()
    row = CaseDecision(
        case_id=case_id,
        decision=result.decision,
        decision_confidence=result.decision_confidence,
        decision_rationale=result.decision_rationale,
        decision_trace_json=json.dumps(result.decision_trace),
        created_at=datetime.datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_decision_by_case(db: Session, case_id: int) -> CaseDecision | None:
    return db.query(CaseDecision).filter(CaseDecision.case_id == case_id).first()
