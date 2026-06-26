"""
ThreatTron AI — FastAPI Backend (main.py)
==========================================
Central ingestion API, risk prediction endpoints, dashboard analytics,
SHAP explanation routes, and autonomous case investigation trigger.
"""

import os
import sys
import json
import threading
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# ── Make sibling packages importable ─────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import get_db, init_db, SessionLocal
from backend import crud
from backend.models import Case, TelemetryEvent
from backend.schemas import (
    BatchPayload,
    PredictRequest,
    SampleRequest,
    RiskResponse,
    EventResponse,
    DashboardStats,
    TimelinePoint,
    FeatureImportance,
    ShapExplanation,
    CaseResponse,
    CaseDetailResponse,
    CaseEvidenceResponse,
    InvestigateResponse,
)
from backend.investigation_service import InvestigationService

# ── Lazy model service (loaded once at startup) ─────────────────────────────
_model_svc = None


def _get_model():
    global _model_svc
    if _model_svc is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "model_service",
            str(ROOT / "Behavioural-model" / "model_service.py"),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _model_svc = module.get_model_service()
    return _model_svc


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        _backfill_cases_for_existing_high_risk_events()
        _get_model()
        print("✅  Model service loaded successfully.")
    except Exception as e:
        print(f"⚠️  Model not loaded (run training first): {e}")
    yield


# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ThreatTron AI — Backend API",
    description="Banking fraud detection & behavioral anomaly risk engine.",
    version="1.0.0",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "ThreatTron AI Backend"}


# ── Batch Ingestion ──────────────────────────────────────────────────────────
@app.post("/events/batch", response_model=list[EventResponse])
def ingest_batch(payload: BatchPayload, db: Session = Depends(get_db)):
    """
    Receive a batch of telemetry events from the agent.
    Each event is scored by the ML model and stored in the DB.
    """
    # Ensure session exists
    if payload.session:
        crud.get_or_create_session(
            db,
            session_id=payload.session.session_id,
            agent_id=payload.session.agent_id,
            hostname=payload.session.hostname,
        )

    results = []
    model = None
    try:
        model = _get_model()
    except Exception:
        pass

    for ev in payload.events:
        # Ensure session row exists even if session block wasn't provided
        crud.get_or_create_session(db, session_id=ev.session_id)

        risk_score = 0.0
        prediction = 0
        risk_level = "LOW"
        top_factors: list = []

        if model:
            try:
                result = model.predict_risk(ev.features)
                risk_score = result["risk_score"]
                prediction = result["prediction"]
                risk_level = result["risk_level"]
                top_factors = result["top_factors"]
            except Exception as exc:
                print(f"ML prediction error: {exc}")

        event_row = crud.create_event(
            db,
            session_id=ev.session_id,
            account_type=ev.account_type,
            occupation=ev.occupation,
            segment=ev.segment,
            area=ev.area,
            risk_score=risk_score,
            prediction=prediction,
            risk_level=risk_level,
            features=ev.features,
        )
        results.append(event_row)

        # ── Auto-trigger case investigation for high-risk events ──────────────
        if risk_score >= 0.80:
            _trigger_case_investigation(db, event_row.id, risk_score)

    return results


def _backfill_cases_for_existing_high_risk_events() -> None:
    """Create missing case records for high-risk telemetry events already in the DB."""
    db = SessionLocal()
    try:
        high_risk_events = (
            db.query(TelemetryEvent)
            .filter(TelemetryEvent.risk_score >= 0.80)
            .order_by(TelemetryEvent.id)
            .all()
        )
        for event in high_risk_events:
            existing = db.query(Case).filter(Case.trigger_event_id == event.id).first()
            if existing:
                continue
            _trigger_case_investigation(db, event.id, event.risk_score or 0.0)
    finally:
        db.close()


def _trigger_case_investigation(db: Session, event_id: int, risk_score: float) -> None:
    """
    Create a Case record and run the InvestigationService synchronously.
    Called in the same request context so the DB session is still valid.
    """
    try:
        existing = db.query(Case).filter(Case.trigger_event_id == event_id).first()
        if existing:
            return

        case = crud.create_case(
            db=db,
            trigger_event_id=event_id,
            risk_score=risk_score,
            summary="Investigation pending…",
            recommended_action="PENDING",
        )
        crud.update_case_status(db, case.id, status="INVESTIGATING")

        findings = InvestigationService.analyze_event(
            db=db,
            event_id=event_id,
            case_id=case.id,
        )

        # Build narrative summary from findings
        risk_factors_txt = "; ".join(findings.get("risk_factors", []))
        summary = (
            f"Session {findings.get('session_id', 'N/A')} flagged with risk score "
            f"{risk_score:.4f}. Detected: {risk_factors_txt or 'anomalous ML pattern'}. "
            f"Historical average amount: {findings.get('average_amount', 0)}, "
            f"current amount: {findings.get('current_amount', 0)}. "
            f"Previous alerts in session: {findings.get('previous_alerts', 0)}."
        )

        crud.update_case_status(
            db=db,
            case_id=case.id,
            status="OPEN",
            summary=summary,
            recommended_action=findings.get("recommended_action", "BLOCK_ACCOUNT"),
        )

        # Log the investigation as a single agent execution step
        crud.create_agent_log(
            db=db,
            case_id=case.id,
            step_number=1,
            thought="Analyzing high-risk event for behavioral anomalies and contextual signals.",
            action="InvestigationService.analyze_event",
            action_input=f"event_id={event_id}",
            observation=json.dumps({
                k: v for k, v in findings.items() if k != "risk_factors"
            }),
        )

        # Create recommended mitigation action
        crud.create_mitigation_action(
            db=db,
            case_id=case.id,
            action_type=findings.get("recommended_action", "BLOCK_ACCOUNT"),
            status="PENDING_APPROVAL",
            executed_by="AGENT_AUTO",
        )
    except Exception as exc:
        print(f"[case-trigger] Failed to create case for event {event_id}: {exc}")


# ── Query Events ─────────────────────────────────────────────────────────────
@app.get("/api/events", response_model=list[EventResponse])
def list_events(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    risk_level: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return crud.get_events(db, limit=limit, offset=offset, risk_level=risk_level)


# ── Dashboard Stats ──────────────────────────────────────────────────────────
@app.get("/api/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)):
    return crud.get_dashboard_stats(db)


# ── High-Risk Events ────────────────────────────────────────────────────────
@app.get("/api/dashboard/high-risk", response_model=list[EventResponse])
def high_risk_events(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return crud.get_high_risk_events(db, limit=limit)


# ── Risk Timeline ───────────────────────────────────────────────────────────
@app.get("/api/risk/timeline", response_model=list[TimelinePoint])
def risk_timeline(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return crud.get_risk_timeline(db, limit=limit)


# ── Direct Prediction ───────────────────────────────────────────────────────
@app.post("/api/predict", response_model=RiskResponse)
def predict(req: PredictRequest):
    try:
        model = _get_model()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Model not available: {e}")
    result = model.predict_risk(req.features)
    return result


# ── Feature Importance ───────────────────────────────────────────────────────
@app.get("/api/feature-importance", response_model=list[FeatureImportance])
def feature_importance(top_n: int = Query(20, ge=1, le=100)):
    try:
        model = _get_model()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Model not available: {e}")
    return model.get_feature_importance(top_n=top_n)


# ── SHAP Explanation ─────────────────────────────────────────────────────────
@app.post("/api/explain", response_model=ShapExplanation)
def explain(req: PredictRequest):
    try:
        model = _get_model()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Model not available: {e}")
    return model.explain_prediction(req.features)


# ── Sample Row (Sandbox) ────────────────────────────────────────────────────
@app.post("/api/sample")
def sample_row(req: SampleRequest):
    try:
        model = _get_model()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Model not available: {e}")
    row = model.get_sample_row(index=req.index)
    return {"index": req.index, "features": row}


# ── Dataset Metadata ────────────────────────────────────────────────────────
@app.get("/api/dataset/stats")
def dataset_stats():
    try:
        model = _get_model()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Model not available: {e}")
    return model.get_dataset_stats()


# ── Evaluation Report ───────────────────────────────────────────────────────
@app.get("/api/model/evaluation")
def model_evaluation():
    report_path = ROOT / "Behavioural-model" / "models" / "evaluation_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Evaluation report not found. Run evaluate.py first.")
    with open(str(report_path), "r") as f:
        return json.load(f)


# ══════════════════════════════════════════════════════════════════════════════
#  CASE INVESTIGATION ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

# ── List Cases ───────────────────────────────────────────────────────────────
@app.get("/api/cases", response_model=list[CaseResponse])
def list_cases(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None, description="Filter by status: OPEN, INVESTIGATING, CLOSED"),
    db: Session = Depends(get_db),
):
    """List all investigation cases, optionally filtered by status."""
    return crud.get_cases(db, limit=limit, offset=offset, status=status)


# ── Get Case Detail ───────────────────────────────────────────────────────────
@app.get("/api/cases/{case_id}", response_model=CaseDetailResponse)
def get_case(case_id: int, db: Session = Depends(get_db)):
    """Fetch a single case with evidence, execution logs, and actions."""
    case = crud.get_case_by_id(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    return case


# ── Get Case Evidence ────────────────────────────────────────────────────────
@app.get("/api/cases/{case_id}/evidence", response_model=list[CaseEvidenceResponse])
def get_case_evidence(case_id: int, db: Session = Depends(get_db)):
    """Fetch all evidence records attached to a specific case."""
    case = crud.get_case_by_id(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    return crud.get_case_evidence(db, case_id)


# ── Re-Run Investigation ─────────────────────────────────────────────────────
@app.post("/api/cases/{case_id}/investigate", response_model=InvestigateResponse)
def re_investigate_case(case_id: int, db: Session = Depends(get_db)):
    """
    Trigger or re-run the investigation service for an existing case.
    Useful when additional signals become available after initial creation.
    """
    case = crud.get_case_by_id(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    crud.update_case_status(db, case_id, status="INVESTIGATING")

    findings = InvestigationService.analyze_event(
        db=db,
        event_id=case.trigger_event_id,
        case_id=case_id,
    )

    risk_factors_txt = "; ".join(findings.get("risk_factors", []))
    summary = (
        f"Re-investigation of session {findings.get('session_id', 'N/A')}. "
        f"Detected: {risk_factors_txt or 'anomalous ML pattern'}. "
        f"Historical average: {findings.get('average_amount', 0)}, "
        f"current: {findings.get('current_amount', 0)}. "
        f"Previous alerts: {findings.get('previous_alerts', 0)}."
    )

    next_step = len(case.logs) + 1
    crud.create_agent_log(
        db=db,
        case_id=case_id,
        step_number=next_step,
        thought="Re-analyzing event with full historical context.",
        action="InvestigationService.analyze_event",
        action_input=f"event_id={case.trigger_event_id}",
        observation=json.dumps({
            k: v for k, v in findings.items() if k != "risk_factors"
        }),
    )

    recommended = findings.get("recommended_action", "BLOCK_ACCOUNT")
    updated = crud.update_case_status(
        db=db,
        case_id=case_id,
        status="OPEN",
        summary=summary,
        recommended_action=recommended,
    )

    evidence = crud.get_case_evidence(db, case_id)
    logs = updated.logs if updated else []

    return InvestigateResponse(
        case_id=case_id,
        status=updated.status if updated else "OPEN",
        risk_score=case.risk_score,
        recommended_action=recommended,
        summary=summary,
        evidence_count=len(evidence),
        logs_count=len(logs),
    )
