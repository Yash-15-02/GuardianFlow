"""
ThreatTron AI — SQLAlchemy ORM Models
======================================
AgentSession : tracks each agent connection lifetime.
TelemetryEvent : individual event/row ingested from the agent.
"""

import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, Index,
)
from sqlalchemy.orm import relationship
from backend.database import Base


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    agent_id = Column(String(128), nullable=True, index=True)
    hostname = Column(String(256), nullable=True)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)

    events = relationship(
        "TelemetryEvent",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AgentSession session_id={self.session_id}>"


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String(64),
        ForeignKey("agent_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    account_type = Column(String(64), nullable=True)
    occupation = Column(String(64), nullable=True)
    segment = Column(String(32), nullable=True)
    area = Column(String(16), nullable=True)
    risk_score = Column(Float, nullable=True)
    prediction = Column(Integer, nullable=True)
    risk_level = Column(String(16), nullable=True)
    features_json = Column(Text, nullable=True)

    session = relationship("AgentSession", back_populates="events")

    __table_args__ = (
        Index("ix_telemetry_risk", "risk_score"),
        Index("ix_telemetry_prediction", "prediction"),
    )

    def __repr__(self) -> str:
        return f"<TelemetryEvent id={self.id} risk={self.risk_score}>"


# ── Case Investigation Models ─────────────────────────────────────────────────

class Case(Base):
    """Top-level investigation case created for every high-risk event."""
    __tablename__ = "investigation_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trigger_event_id = Column(
        Integer,
        ForeignKey("telemetry_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(String(32), default="OPEN", nullable=False, index=True)
    risk_score = Column(Float, nullable=False)
    summary = Column(Text, nullable=True)
    recommended_action = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    trigger_event = relationship("TelemetryEvent", foreign_keys=[trigger_event_id])
    evidence = relationship(
        "CaseEvidence",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    logs = relationship(
        "AgentExecutionLog",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    actions = relationship(
        "MitigationAction",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Case id={self.id} status={self.status}>"


class CaseEvidence(Base):
    """A single piece of evidence attached to an investigation case."""
    __tablename__ = "case_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(
        Integer,
        ForeignKey("investigation_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source = Column(String(128), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(16), nullable=False, default="MEDIUM")

    case = relationship("Case", back_populates="evidence")

    def __repr__(self) -> str:
        return f"<CaseEvidence id={self.id} source={self.source}>"


class AgentExecutionLog(Base):
    """One step of the autonomous investigation agent's ReAct loop."""
    __tablename__ = "agent_execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(
        Integer,
        ForeignKey("investigation_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_number = Column(Integer, nullable=False)
    thought = Column(Text, nullable=True)
    action = Column(String(256), nullable=True)
    action_input = Column(Text, nullable=True)
    observation = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    case = relationship("Case", back_populates="logs")

    def __repr__(self) -> str:
        return f"<AgentExecutionLog id={self.id} step={self.step_number}>"


class MitigationAction(Base):
    """A recommended or executed mitigation action for a case."""
    __tablename__ = "mitigation_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(
        Integer,
        ForeignKey("investigation_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="PENDING_APPROVAL")
    executed_by = Column(String(64), nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

    case = relationship("Case", back_populates="actions")

    def __repr__(self) -> str:
        return f"<MitigationAction id={self.id} type={self.action_type}>"

