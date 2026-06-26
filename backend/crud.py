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

from backend.models import AgentSession, TelemetryEvent


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
