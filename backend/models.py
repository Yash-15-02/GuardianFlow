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
