"""
ThreatTron AI — FastAPI Backend (main.py)
==========================================
Central ingestion API, risk prediction endpoints, dashboard analytics,
and SHAP explanation routes.
"""

import os
import sys
import json
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# ── Make sibling packages importable ─────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import get_db, init_db
from backend import crud
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
)

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

    return results


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
