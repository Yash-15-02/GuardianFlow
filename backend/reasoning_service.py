"""
ThreatTron AI — Reasoning Service
===================================
Transforms structured investigation evidence into a natural-language
fraud investigation report grounded strictly in DataSet.csv features.

Architecture:
  ReasoningService (orchestrator)
    └── ReasoningProvider (abstract)
          ├── LocalReasoningProvider   ← production-ready, dataset-grounded
          └── CortexReasoningProvider  ← future Snowflake Cortex stub

Anti-hallucination rules enforced here:
  - Never mention IP addresses, countries, devices, beneficiaries, or sessions
  - All statements derive from evidence rows, interpretable F-features, or
    account metadata stored in TelemetryEvent
"""

from __future__ import annotations

import json
import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from backend.models import Case, TelemetryEvent, CaseEvidence, CaseReasoning

# ── Semantic feature map — only columns confirmed in DataSet.csv ──────────────
FEATURE_LABELS: dict[str, str] = {
    "F3796": "total transaction count (all periods)",
    "F3797": "credit transaction count (all periods)",
    "F3798": "debit transaction count (all periods)",
    "F3799": "total transaction volume",
    "F3800": "total credit volume",
    "F3801": "total debit volume",
    "F3802": "transaction count (short window)",
    "F3803": "credit count (short window)",
    "F3804": "debit count (short window)",
    "F3805": "transaction volume (short window)",
    "F3806": "credit volume (short window)",
    "F3807": "debit volume (short window)",
    "F3808": "transaction count (medium window)",
    "F3809": "credit count (medium window)",
    "F3810": "debit count (medium window)",
    "F3811": "transaction volume (medium window)",
    "F3812": "credit volume (medium window)",
    "F3813": "debit volume (medium window)",
    "F3814": "credit-to-total ratio",
    "F3815": "debit-to-credit ratio (short window)",
    "F3816": "debit-to-credit ratio (medium window)",
    "F3894": "customer age",
    "F3895": "credit score (bureau 1)",
    "F3896": "credit score (bureau 2)",
}

# F3889 — relationship duration category
TENURE_LABELS: dict[str, str] = {
    "L31D":  "less than 31 days",
    "L90D":  "less than 90 days",
    "L180D": "less than 180 days",
    "L365D": "less than 365 days",
    "G365D": "greater than 365 days",
}
SHORT_TENURE  = {"L31D", "L90D"}
MEDIUM_TENURE = {"L180D"}

# F3890 — geographic area type
AREA_LABELS: dict[str, str] = {
    "R":  "Rural",
    "SU": "Semi-Urban",
    "M":  "Metropolitan",
    "U":  "Urban",
}

LOW_CREDIT_THRESHOLD: int   = 550
HIGH_VOLUME_FLAG:     float = 5_000_000.0   # flag when total vol > ₹5M


@dataclass
class ReasoningResult:
    """Structured output produced by any ReasoningProvider."""
    executive_summary: str
    findings: list[str]
    confidence: float
    rationale: str
    reasoning_trace: dict[str, Any]
    provider: str = "LOCAL"


class ReasoningProvider(ABC):
    """Abstract interface — every provider must implement `reason()`."""

    @abstractmethod
    def reason(
        self,
        case: "Case",
        event: "TelemetryEvent | None",
        evidence: "list[CaseEvidence]",
    ) -> ReasoningResult: ...


# ─────────────────────────────────────────────────────────────────────────────
class LocalReasoningProvider(ReasoningProvider):
    """
    Dataset-grounded, template-based reasoning.

    Signal sources (strictly):
      1. ML risk score (stored on Case)
      2. Account metadata: occupation, area, account_type, segment (TelemetryEvent)
      3. Tenure category F3889, credit scores F3895/F3896,
         transaction aggregates F3796–F3813, behavioral flags F3900–F3923
         — all read from TelemetryEvent.features_json
      4. Existing CaseEvidence rows (already computed by InvestigationService)
    """

    def reason(
        self,
        case: "Case",
        event: "TelemetryEvent | None",
        evidence: "list[CaseEvidence]",
    ) -> ReasoningResult:
        features: dict[str, Any] = {}
        if event and event.features_json:
            try:
                features = json.loads(event.features_json)
            except Exception:
                pass

        findings: list[str] = []
        trace_factors: list[str] = []
        signal_weights: list[float] = []

        risk_score = float(case.risk_score or 0.0)
        risk_pct   = round(risk_score * 100, 1)
        risk_label = "HIGH" if risk_score >= 0.80 else "MODERATE" if risk_score >= 0.45 else "LOW"

        # ── 1. ML Risk Score ──────────────────────────────────────────────────
        findings.append(
            f"The LightGBM fraud detection model assigned a risk score of "
            f"{risk_pct}%, indicating a {risk_label.lower()} probability of "
            f"anomalous behaviour."
        )
        if risk_score >= 0.80:
            trace_factors.append("high_ml_risk_score")
            signal_weights.append(0.35)
        elif risk_score >= 0.45:
            trace_factors.append("moderate_ml_risk_score")
            signal_weights.append(0.15)

        # ── 2. Account Profile ────────────────────────────────────────────────
        if event:
            profile_parts: list[str] = []
            if event.account_type:
                profile_parts.append(f"account type: {event.account_type}")
            if event.occupation:
                profile_parts.append(f"occupation: {event.occupation}")
            if event.segment:
                profile_parts.append(f"segment: {event.segment}")
            if event.area:
                profile_parts.append(
                    f"area: {AREA_LABELS.get(event.area.upper(), event.area)}"
                )
            if profile_parts:
                findings.append(
                    f"Account profile — {'; '.join(profile_parts)}."
                )

        # ── 3. Account Tenure ─────────────────────────────────────────────────
        tenure_raw = str(features.get("F3889", "")).strip().upper()
        if tenure_raw in SHORT_TENURE:
            findings.append(
                f"Account relationship duration is {TENURE_LABELS[tenure_raw]}, "
                f"placing this account in the high-risk new-account category. "
                f"Short-tenure accounts carry significantly elevated fraud probability."
            )
            trace_factors.append("short_account_tenure")
            signal_weights.append(0.20)
        elif tenure_raw in MEDIUM_TENURE:
            findings.append(
                f"Account relationship duration is {TENURE_LABELS[tenure_raw]}, "
                f"a medium-tenure profile with moderate baseline risk."
            )
            trace_factors.append("medium_account_tenure")
            signal_weights.append(0.08)

        # ── 4. Credit Profile ─────────────────────────────────────────────────
        for credit_col, label in [("F3895", "bureau 1"), ("F3896", "bureau 2")]:
            raw = features.get(credit_col)
            if raw is None:
                continue
            try:
                score = float(raw)
                if score <= 0:
                    continue
                if score < LOW_CREDIT_THRESHOLD:
                    findings.append(
                        f"Credit score ({label}) is {int(score)}, below the "
                        f"risk threshold of {LOW_CREDIT_THRESHOLD}. "
                        f"Low credit scores are correlated with elevated fraud risk."
                    )
                    if "low_credit_score" not in trace_factors:
                        trace_factors.append("low_credit_score")
                        signal_weights.append(0.15)
                else:
                    findings.append(
                        f"Credit score ({label}) is {int(score)}, within normal range."
                    )
            except (ValueError, TypeError):
                pass

        # ── 5. Transaction Volume & Velocity ──────────────────────────────────
        total_vol  = self._safe_float(features.get("F3799"))
        debit_vol  = self._safe_float(features.get("F3801"))
        credit_vol = self._safe_float(features.get("F3800"))
        total_cnt  = self._safe_float(features.get("F3796"))
        short_cnt  = self._safe_float(features.get("F3802"))
        short_vol  = self._safe_float(features.get("F3805"))

        if total_vol is not None and total_vol > HIGH_VOLUME_FLAG:
            findings.append(
                f"Total transaction volume over the observation period is "
                f"₹{total_vol:,.2f}, significantly exceeding typical thresholds "
                f"for this account profile."
            )
            trace_factors.append("high_total_transaction_volume")
            signal_weights.append(0.20)

        if debit_vol is not None and credit_vol is not None and credit_vol > 0:
            ratio = debit_vol / credit_vol
            if ratio > 1.5:
                findings.append(
                    f"Debit-to-credit volume ratio is {ratio:.2f}x, indicating "
                    f"significant net outward cash flow — consistent with account "
                    f"draining or structuring behaviour."
                )
                trace_factors.append("high_debit_credit_ratio")
                signal_weights.append(0.18)

        if short_cnt is not None and total_cnt is not None and total_cnt > 0:
            velocity_ratio = short_cnt / total_cnt
            if velocity_ratio > 0.60:
                findings.append(
                    f"Short-window transaction count is {velocity_ratio * 100:.1f}% "
                    f"of the total historical count, indicating a concentrated "
                    f"burst of activity — a velocity spike pattern."
                )
                trace_factors.append("velocity_spike_short_window")
                signal_weights.append(0.18)

        if short_vol is not None and total_vol is not None and total_vol > 0:
            vol_ratio = short_vol / total_vol
            if vol_ratio > 0.55:
                findings.append(
                    f"Short-window transaction volume represents {vol_ratio * 100:.1f}% "
                    f"of total period volume, suggesting a recent surge in activity."
                )
                if "volume_surge" not in trace_factors:
                    trace_factors.append("volume_surge")
                    signal_weights.append(0.12)

        # ── 6. Evidence Analysis ──────────────────────────────────────────────
        crit_cnt   = sum(1 for e in evidence if e.severity == "CRITICAL")
        high_cnt   = sum(1 for e in evidence if e.severity == "HIGH")
        medium_cnt = sum(1 for e in evidence if e.severity == "MEDIUM")

        if evidence:
            sev_parts = []
            if crit_cnt:
                sev_parts.append(f"{crit_cnt} CRITICAL")
                trace_factors.append("critical_evidence")
                signal_weights.append(0.30)
            if high_cnt:
                sev_parts.append(f"{high_cnt} HIGH")
                if "high_evidence" not in trace_factors:
                    trace_factors.append("high_evidence")
                    signal_weights.append(0.20)
            if medium_cnt:
                sev_parts.append(f"{medium_cnt} MEDIUM")

            sources = ", ".join(sorted({e.source for e in evidence}))
            findings.append(
                f"Investigation produced {len(evidence)} evidence item(s) "
                f"({'|'.join(sev_parts) if sev_parts else 'MEDIUM'} severity). "
                f"Evidence sources: {sources}."
            )
            for ev in evidence[:4]:           # cite top 4 items
                findings.append(f"[{ev.severity}] {ev.description}")

        # ── 7. Behavioral Flags ───────────────────────────────────────────────
        active_flags = [
            f"F{n}" for n in range(3900, 3924)
            if self._safe_float(features.get(f"F{n}")) == 1.0
        ]
        if active_flags:
            findings.append(
                f"{len(active_flags)} behavioral flag(s) are active "
                f"({', '.join(active_flags[:6])}"
                f"{'…' if len(active_flags) > 6 else ''}). "
                f"Behavioral flags capture account-state changes and product activations."
            )
            if len(active_flags) >= 5:
                trace_factors.append("multiple_behavioral_flags")
                signal_weights.append(0.10)

        # ── 8. Age Cohort ─────────────────────────────────────────────────────
        age = self._safe_float(features.get("F3894"))
        if age is not None and 18 <= age <= 25:
            findings.append(
                f"Customer age is {int(age)}, within the 18–25 cohort that "
                f"statistically exhibits higher first-party fraud incidence."
            )
            trace_factors.append("young_age_cohort")
            signal_weights.append(0.05)

        # ── Compute Confidence ────────────────────────────────────────────────
        raw_conf   = min(sum(signal_weights), 1.0) if signal_weights else 0.0
        confidence = round(
            0.55 * raw_conf + 0.45 * risk_score, 4
        )

        # ── Executive Summary ─────────────────────────────────────────────────
        conf_label = (
            "HIGH" if confidence >= 0.75
            else "MODERATE" if confidence >= 0.50
            else "LOW"
        )
        executive_summary = (
            f"Case #{case.id} reviewed by the ThreatTron Reasoning Agent. "
            f"The ML model assigned a {risk_label} risk score of {risk_pct}%. "
            f"{len(findings)} analytical findings were generated across account "
            f"profile, transaction behaviour, and investigation evidence. "
            f"Overall reasoning confidence: {conf_label} ({round(confidence * 100, 1)}%)."
        )

        # ── Recommendation Rationale ──────────────────────────────────────────
        action = case.recommended_action or "MANUAL_REVIEW"
        rationale = (
            f"Recommended action '{action}': risk score {risk_pct}% ({risk_label}), "
            f"reasoning confidence {round(confidence * 100, 1)}% ({conf_label}), "
            f"{len(evidence)} evidence item(s) "
            f"({crit_cnt} critical, {high_cnt} high). "
            f"Primary signals — {', '.join(trace_factors) if trace_factors else 'ML model output'}."
        )

        # ── Reasoning Trace ───────────────────────────────────────────────────
        reasoning_trace: dict[str, Any] = {
            "case_id":          case.id,
            "risk_score_pct":   risk_pct,
            "confidence":       confidence,
            "factors":          trace_factors,
            "signal_weights":   dict(zip(trace_factors, signal_weights)),
            "evidence_count":   len(evidence),
            "critical_count":   crit_cnt,
            "high_count":       high_cnt,
            "findings_count":   len(findings),
            "tenure_code":      tenure_raw or None,
            "active_flags":     len(active_flags),
            "provider":         "LOCAL",
            "generated_at":     datetime.datetime.utcnow().isoformat(),
        }

        return ReasoningResult(
            executive_summary=executive_summary,
            findings=findings,
            confidence=confidence,
            rationale=rationale,
            reasoning_trace=reasoning_trace,
            provider="LOCAL",
        )

    @staticmethod
    def _safe_float(val: Any) -> float | None:
        if val is None:
            return None
        try:
            f = float(val)
            return f if f > -999 else None  # -1 sentinel means "not applicable"
        except (ValueError, TypeError):
            return None


# ─────────────────────────────────────────────────────────────────────────────
class CortexReasoningProvider(ReasoningProvider):
    """
    Future Snowflake Cortex integration stub.

    When ready, replace this body with:
      snowflake.snowpark.Session + SNOWFLAKE.CORTEX.COMPLETE(llama3-70b)
    Environment variables required (not set in local dev):
      SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
      SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA
    """

    def reason(
        self,
        case: "Case",
        event: "TelemetryEvent | None",
        evidence: "list[CaseEvidence]",
    ) -> ReasoningResult:
        raise NotImplementedError(
            "CortexReasoningProvider requires Snowflake Cortex credentials. "
            "Set REASONING_PROVIDER=cortex and configure SNOWFLAKE_* env vars."
        )


# ─────────────────────────────────────────────────────────────────────────────
class ReasoningService:
    """
    Orchestrator: picks provider from env/config, runs reasoning, persists result.
    Usage:
        svc = ReasoningService()
        reasoning_row = svc.run(db, case_id=42)
    """

    def __init__(self, provider: str = "local") -> None:
        if provider.lower() == "cortex":
            self._provider: ReasoningProvider = CortexReasoningProvider()
        else:
            self._provider = LocalReasoningProvider()

    def run(self, db: Session, case_id: int) -> "CaseReasoning":
        from backend.models import Case, TelemetryEvent, CaseReasoning
        from backend import crud

        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case {case_id} not found")

        event: TelemetryEvent | None = None
        if case.trigger_event_id:
            event = db.query(TelemetryEvent).filter(
                TelemetryEvent.id == case.trigger_event_id
            ).first()

        evidence = crud.get_case_evidence(db, case_id)
        result   = self._provider.reason(case, event, evidence)
        return crud.upsert_reasoning(db, case_id, result)
