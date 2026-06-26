"""
ThreatTron AI — Investigation Service
=======================================
Stateless service that analyses a TelemetryEvent and produces structured
evidence records and a recommended mitigation action for a given Case.
"""

from __future__ import annotations

import json
import datetime
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.models import TelemetryEvent, Case, CaseEvidence
from backend import crud

# Thresholds
AMOUNT_SPIKE_MULTIPLIER = 2.0          # flag if current > mean * this
GEO_RISK_AREAS = {"INTERNATIONAL", "FOREIGN", "OVERSEAS"}
HIGH_FREQ_THRESHOLD = 3                # prior high-risk events in session


class InvestigationService:
    """
    Static-method service that:
    1. Queries historical events for the triggering event's session.
    2. Detects amount spikes, geo-anomalies, and high-frequency fraud patterns.
    3. Writes CaseEvidence rows.
    4. Returns a findings dict including recommended_action.
    """

    @staticmethod
    def analyze_event(db: Session, event_id: int, case_id: int) -> dict[str, Any]:
        """
        Main analysis entry point.

        Parameters
        ----------
        db        : SQLAlchemy session
        event_id  : ID of the triggering TelemetryEvent
        case_id   : ID of the parent Case (for attaching evidence)

        Returns
        -------
        dict with keys:
          session_id, current_amount, average_amount, previous_alerts,
          risk_factors (list[str]), recommended_action
        """
        event = db.query(TelemetryEvent).filter(TelemetryEvent.id == event_id).first()
        if not event:
            return {
                "session_id": "UNKNOWN",
                "current_amount": 0,
                "average_amount": 0,
                "previous_alerts": 0,
                "risk_factors": ["Event record not found"],
                "recommended_action": "MANUAL_REVIEW",
            }

        features: dict[str, Any] = {}
        if event.features_json:
            try:
                features = json.loads(event.features_json)
            except Exception:
                pass

        session_id = event.session_id
        current_amount = float(features.get("TRANSACTION_AMOUNT", 0))
        current_area = str(features.get("AREA", "")).upper()

        # ── Historical context ────────────────────────────────────────────────
        session_events = (
            db.query(TelemetryEvent)
            .filter(
                TelemetryEvent.session_id == session_id,
                TelemetryEvent.id != event_id,
            )
            .order_by(desc(TelemetryEvent.timestamp))
            .limit(50)
            .all()
        )

        amounts = []
        prev_high_risk = 0
        for e in session_events:
            f: dict[str, Any] = {}
            if e.features_json:
                try:
                    f = json.loads(e.features_json)
                except Exception:
                    pass
            amt = float(f.get("TRANSACTION_AMOUNT", 0))
            if amt > 0:
                amounts.append(amt)
            if (e.risk_score or 0) >= 0.80:
                prev_high_risk += 1

        average_amount = sum(amounts) / len(amounts) if amounts else 0.0

        # ── Risk factor detection ─────────────────────────────────────────────
        risk_factors: list[str] = []
        evidence_items: list[dict[str, str]] = []

        # 1. Amount spike
        if average_amount > 0 and current_amount >= average_amount * AMOUNT_SPIKE_MULTIPLIER:
            factor = (
                f"Transaction amount {current_amount:.2f} is "
                f"{current_amount / average_amount:.1f}x above session average "
                f"{average_amount:.2f}"
            )
            risk_factors.append(factor)
            evidence_items.append({
                "source": "AMOUNT_ANALYSIS",
                "description": factor,
                "severity": "HIGH",
            })

        # 2. Geo / area anomaly
        if current_area in GEO_RISK_AREAS:
            factor = f"Transaction originated from high-risk area: {current_area}"
            risk_factors.append(factor)
            evidence_items.append({
                "source": "GEO_ANALYSIS",
                "description": factor,
                "severity": "HIGH",
            })

        # 3. Repeated high-risk events in same session
        if prev_high_risk >= HIGH_FREQ_THRESHOLD:
            factor = (
                f"Session {session_id} has {prev_high_risk} prior high-risk "
                f"events — possible sustained attack pattern"
            )
            risk_factors.append(factor)
            evidence_items.append({
                "source": "SESSION_FREQUENCY",
                "description": factor,
                "severity": "CRITICAL",
            })

        # 4. ML model flag alone (always add as baseline evidence)
        evidence_items.append({
            "source": "ML_MODEL",
            "description": (
                f"LightGBM model flagged this event with risk score "
                f"{event.risk_score:.4f} (threshold: 0.80)"
            ),
            "severity": "HIGH" if (event.risk_score or 0) >= 0.90 else "MEDIUM",
        })

        # ── Write evidence to DB ──────────────────────────────────────────────
        for item in evidence_items:
            crud.create_evidence(
                db=db,
                case_id=case_id,
                source=item["source"],
                description=item["description"],
                severity=item["severity"],
            )

        # ── Recommended action ────────────────────────────────────────────────
        if prev_high_risk >= HIGH_FREQ_THRESHOLD or current_area in GEO_RISK_AREAS:
            recommended_action = "BLOCK_ACCOUNT"
        elif current_amount >= (average_amount * AMOUNT_SPIKE_MULTIPLIER if average_amount > 0 else 1):
            recommended_action = "MFA_CHALLENGE"
        else:
            recommended_action = "MFA_CHALLENGE"

        return {
            "session_id": session_id,
            "current_amount": current_amount,
            "average_amount": round(average_amount, 2),
            "previous_alerts": prev_high_risk,
            "risk_factors": risk_factors,
            "recommended_action": recommended_action,
        }
