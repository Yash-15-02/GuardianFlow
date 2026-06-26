"""
ThreatTron AI — Decision Engine
=================================
Autonomous multi-factor fraud response determination.

Architecture:
  DecisionService (orchestrator)
    └── DecisionProvider (abstract)
          ├── RuleBasedDecisionProvider  ← production-ready, configurable
          └── CortexDecisionProvider     ← future Snowflake Cortex stub

Decisions:
  APPROVE       — risk < 0.70, no high/critical evidence
  MFA_CHALLENGE — risk 0.70–0.85, limited high evidence
  MANUAL_REVIEW — risk 0.85–0.95, OR ≥2 high / any critical evidence
  BLOCK_ACCOUNT — risk ≥ 0.95 AND reasoning_confidence ≥ 0.85 AND critical evidence
"""

from __future__ import annotations

import json
import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from backend.models import Case, CaseEvidence, CaseReasoning, CaseDecision

# ── Configurable decision thresholds ─────────────────────────────────────────
THRESHOLDS: dict[str, float | int] = {
    "approve_max":             0.70,
    "mfa_max":                 0.85,
    "manual_max":              0.95,
    "block_confidence_min":    0.85,
    "high_ev_escalation":      2,     # ≥ N HIGH evidence items → escalate
    "critical_ev_escalation":  1,     # ≥ N CRITICAL evidence  → at least MANUAL_REVIEW
}

VALID_DECISIONS = frozenset({"APPROVE", "MFA_CHALLENGE", "MANUAL_REVIEW", "BLOCK_ACCOUNT"})


@dataclass
class DecisionResult:
    """Structured output produced by any DecisionProvider."""
    decision:             str
    decision_confidence:  float
    decision_rationale:   str
    decision_trace:       dict[str, Any]

    def __post_init__(self) -> None:
        assert self.decision in VALID_DECISIONS, f"Invalid decision: {self.decision}"


class DecisionProvider(ABC):
    """Abstract interface — every provider must implement `decide()`."""

    @abstractmethod
    def decide(
        self,
        case:      "Case",
        evidence:  "list[CaseEvidence]",
        reasoning: "CaseReasoning | None",
    ) -> DecisionResult: ...


# ─────────────────────────────────────────────────────────────────────────────
class RuleBasedDecisionProvider(DecisionProvider):
    """
    Multi-factor, threshold-configurable decision logic.

    Factor weights:
      - ML risk score      → 45%
      - Reasoning agent    → 35%
      - Evidence severity  → 20%
    """

    def decide(
        self,
        case:      "Case",
        evidence:  "list[CaseEvidence]",
        reasoning: "CaseReasoning | None",
    ) -> DecisionResult:
        risk       = float(case.risk_score or 0.0)
        confidence = float(reasoning.confidence if reasoning else 0.0)

        crit_cnt   = sum(1 for e in evidence if e.severity == "CRITICAL")
        high_cnt   = sum(1 for e in evidence if e.severity == "HIGH")
        medium_cnt = sum(1 for e in evidence if e.severity == "MEDIUM")

        trace_factors: list[str] = [f"risk_score_{int(risk * 100)}"]

        # ── Primary decision rule ─────────────────────────────────────────────
        decision: str

        if (
            risk >= THRESHOLDS["manual_max"]
            and confidence >= THRESHOLDS["block_confidence_min"]
            and crit_cnt >= THRESHOLDS["critical_ev_escalation"]
        ):
            decision = "BLOCK_ACCOUNT"
            trace_factors += ["extreme_risk", "high_reasoning_confidence", f"critical_evidence_{crit_cnt}"]

        elif (
            risk >= THRESHOLDS["mfa_max"]
            or crit_cnt >= THRESHOLDS["critical_ev_escalation"]
            or high_cnt >= THRESHOLDS["high_ev_escalation"]
        ):
            decision = "MANUAL_REVIEW"
            trace_factors.append("multiple_risk_signals")
            if crit_cnt:
                trace_factors.append(f"critical_evidence_{crit_cnt}")
            if high_cnt:
                trace_factors.append(f"high_evidence_{high_cnt}")

        elif (
            risk >= THRESHOLDS["approve_max"]
            and crit_cnt == 0
            and high_cnt < THRESHOLDS["high_ev_escalation"]
        ):
            decision = "MFA_CHALLENGE"
            trace_factors.append("moderate_risk_range")
            if high_cnt:
                trace_factors.append(f"high_evidence_{high_cnt}")

        else:
            decision = "APPROVE"
            trace_factors.append("risk_below_threshold")

        # ── Decision confidence ───────────────────────────────────────────────
        ev_signal = min(
            crit_cnt * 0.30 + high_cnt * 0.15 + medium_cnt * 0.05,
            0.40,
        )
        decision_confidence = round(
            min(max(0.45 * risk + 0.35 * confidence + 0.20 * ev_signal, 0.0), 1.0),
            4,
        )

        # ── Rationale ─────────────────────────────────────────────────────────
        rationale = self._compose_rationale(
            decision, risk, confidence, decision_confidence,
            crit_cnt, high_cnt, medium_cnt, trace_factors,
        )

        # ── Machine-readable trace ────────────────────────────────────────────
        decision_trace: dict[str, Any] = {
            "risk_score":            round(risk, 4),
            "risk_pct":              round(risk * 100, 1),
            "reasoning_confidence":  confidence,
            "decision_confidence":   decision_confidence,
            "evidence_counts": {
                "critical": crit_cnt,
                "high":     high_cnt,
                "medium":   medium_cnt,
                "total":    len(evidence),
            },
            "factors":    trace_factors,
            "thresholds": {k: float(v) for k, v in THRESHOLDS.items()},
            "provider":   "RULE_BASED",
            "decided_at": datetime.datetime.utcnow().isoformat(),
        }

        return DecisionResult(
            decision=decision,
            decision_confidence=decision_confidence,
            decision_rationale=rationale,
            decision_trace=decision_trace,
        )

    @staticmethod
    def _compose_rationale(
        decision: str,
        risk: float,
        confidence: float,
        dec_conf: float,
        crit_cnt: int,
        high_cnt: int,
        medium_cnt: int,
        factors: list[str],
    ) -> str:
        risk_pct = round(risk * 100, 1)
        conf_pct = round(confidence * 100, 1)
        dec_pct  = round(dec_conf * 100, 1)

        lines: list[str] = [
            f"Decision: {decision} (confidence {dec_pct}%).",
            f"ML fraud risk score: {risk_pct}%.",
        ]
        if confidence > 0:
            lines.append(f"Reasoning agent confidence: {conf_pct}%.")
        if crit_cnt:
            lines.append(
                f"{crit_cnt} CRITICAL evidence item(s) detected — "
                f"immediate escalation warranted."
            )
        if high_cnt:
            lines.append(
                f"{high_cnt} HIGH severity evidence item(s) support the elevated response."
            )
        if medium_cnt:
            lines.append(f"{medium_cnt} MEDIUM severity evidence item(s) noted.")

        action_explain = {
            "APPROVE":       "No significant risk signals; behaviour is within expected norms.",
            "MFA_CHALLENGE": "Moderate risk detected; additional authentication required.",
            "MANUAL_REVIEW": "Multiple risk indicators require human analyst review before action.",
            "BLOCK_ACCOUNT": "Extreme risk with high confidence — immediate account suspension recommended.",
        }
        lines.append(action_explain.get(decision, ""))
        return " ".join(ln for ln in lines if ln)


# ─────────────────────────────────────────────────────────────────────────────
class CortexDecisionProvider(DecisionProvider):
    """
    Future Snowflake Cortex integration stub.
    Replace with SNOWFLAKE.CORTEX.COMPLETE calls when credentials are available.
    """

    def decide(
        self,
        case:      "Case",
        evidence:  "list[CaseEvidence]",
        reasoning: "CaseReasoning | None",
    ) -> DecisionResult:
        raise NotImplementedError(
            "CortexDecisionProvider requires Snowflake Cortex credentials. "
            "Set DECISION_PROVIDER=cortex and configure SNOWFLAKE_* env vars."
        )


# ─────────────────────────────────────────────────────────────────────────────
class DecisionService:
    """
    Orchestrator: picks provider, runs decision logic, persists result.
    Usage:
        svc = DecisionService()
        decision_row = svc.run(db, case_id=42)
    """

    def __init__(self, provider: str = "rule_based") -> None:
        if provider.lower() == "cortex":
            self._provider: DecisionProvider = CortexDecisionProvider()
        else:
            self._provider = RuleBasedDecisionProvider()

    def run(self, db: Session, case_id: int) -> "CaseDecision":
        from backend.models import Case
        from backend import crud

        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case {case_id} not found")

        evidence  = crud.get_case_evidence(db, case_id)
        reasoning = crud.get_reasoning_by_case(db, case_id)
        result    = self._provider.decide(case, evidence, reasoning)
        return crud.upsert_decision(db, case_id, result)
