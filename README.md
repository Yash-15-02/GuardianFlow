# 🛡️ ThreatTron AI — Behavioral Fraud Detection Platform

A production-ready banking anomaly detection system combining LightGBM machine learning, real-time telemetry streaming, and an interactive React dashboard.

---

## 🏗️ Architecture

```
DataSet.csv
    │
    ├─► Agent Simulator ─────► FastAPI Backend ─────► SQLite / MySQL
    │                               │
    │                          ML Risk Engine
    │                          (LightGBM + SHAP)
    │                               │
    └─► Threat Simulator ─────►    │
                                    ▼
                            React Dashboard
                         (Risk Gauge · Analytics · Sandbox)
```

## 📁 Project Structure

```
ThreatTron_ITD/
├── DataSet.csv                    # Banking anomaly dataset (9082 × 3925)
├── Behavioural-model/             # ML Pipeline
│   ├── config.yaml                # Hyperparameters & thresholds
│   ├── preprocess.py              # Data cleaning & encoding
│   ├── train.py                   # LightGBM training with K-Fold CV
│   ├── evaluate.py                # Metrics, ROC, confusion matrix
│   ├── model_service.py           # Inference + SHAP explanations
│   ├── requirements.txt
│   ├── models/                    # Saved model artifacts
│   └── processed/                 # Processed data
├── backend/                       # FastAPI Backend
│   ├── main.py                    # API endpoints
│   ├── models.py                  # SQLAlchemy ORM
│   ├── schemas.py                 # Pydantic request/response
│   ├── crud.py                    # DB operations
│   ├── database.py                # Engine (SQLite / MySQL)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── agent/                         # Streaming Agent
│   ├── requirements.txt
│   └── src/
│       ├── main.py                # Row-by-row CSV streamer
│       └── sender/sender.py       # HTTP batch client
├── frontend/                      # React Dashboard
│   ├── src/
│   │   ├── App.tsx                # Router + layout
│   │   ├── api.ts                 # Typed API client
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx      # Stats + Gauge + Timeline + Table
│   │   │   ├── Analytics.tsx      # Metrics + Feature Importance + ROC
│   │   │   └── Sandbox.tsx        # Interactive ML testing
│   │   └── components/
│   │       ├── RiskGauge.tsx       # SVG radial gauge
│   │       ├── StatCard.tsx        # Glassmorphism stat card
│   │       └── Sidebar.tsx         # Navigation
│   ├── Dockerfile
│   ├── nginx.conf
│   └── .env.example
├── simulate_threat.py             # Anomaly row streamer (demo tool)
├── docker-compose.yml
└── README.md
```

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm 9+

### Step 1: Install Python Dependencies

```bash
pip install -r Behavioural-model/requirements.txt
pip install -r backend/requirements.txt
```

### Step 2: Train the ML Model

```bash
cd Behavioural-model
python preprocess.py
python train.py
python evaluate.py
cd ..
```

This creates `models/model.pkl`, `models/feature_columns.pkl`, and `models/encoders.pkl`.

### Step 3: Start the Backend

```bash
uvicorn backend.main:app --reload --port 8000
```

The API is now live at `http://localhost:8000`.
View API docs at `http://localhost:8000/docs`.

### Step 4: Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard is now live at `http://localhost:5173`.

### Step 5: Stream Data

**Normal agent (all rows):**
```bash
python -m agent.src.main --delay 2 --batch 5 --rows 100
```

**Threat simulator (anomalies only):**
```bash
python simulate_threat.py --delay 0.5 --batch 3
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/events/batch` | Ingest telemetry events |
| `GET` | `/api/events` | List events (paginated) |
| `GET` | `/api/dashboard/stats` | Dashboard statistics |
| `GET` | `/api/dashboard/high-risk` | High-risk events |
| `GET` | `/api/risk/timeline` | Risk timeline data |
| `POST` | `/api/predict` | Direct ML prediction |
| `POST` | `/api/explain` | SHAP explanation |
| `GET` | `/api/feature-importance` | Feature importance |
| `POST` | `/api/sample` | Load sample row |
| `GET` | `/api/model/evaluation` | Model evaluation report |
| `GET` | `/api/dataset/stats` | Dataset metadata |

### Sample curl Commands

**Predict risk:**
```bash
curl -X POST http://localhost:8000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"features": {"F3912": 1, "F2506": 1, "F2507": 1, "F515": 5.96}}'
```

**Get dashboard stats:**
```bash
curl http://localhost:8000/api/dashboard/stats
```

**Get feature importance:**
```bash
curl http://localhost:8000/api/feature-importance?top_n=10
```

**Ingest a batch:**
```bash
curl -X POST http://localhost:8000/events/batch \
  -H "Content-Type: application/json" \
  -d '{
    "session": {"session_id": "test-001", "agent_id": "demo"},
    "events": [{
      "session_id": "test-001",
      "account_type": "Savings",
      "occupation": "salaried",
      "segment": "RETAIL",
      "area": "R",
      "features": {"F3912": 0, "F2506": 0.5, "F515": 0.7}
    }]
  }'
```

---

## 🗄️ Database Schema

### `agent_sessions`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| session_id | VARCHAR(64) | Unique session identifier |
| agent_id | VARCHAR(128) | Machine identifier |
| hostname | VARCHAR(256) | Hostname |
| started_at | DATETIME | Session start time |

### `telemetry_events`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| session_id | VARCHAR(64) FK | References agent_sessions |
| timestamp | DATETIME | Event time |
| account_type | VARCHAR(64) | Account type category |
| occupation | VARCHAR(64) | Customer occupation |
| segment | VARCHAR(32) | RETAIL / CORPORATE |
| area | VARCHAR(16) | R / SU / M / U |
| risk_score | FLOAT | ML-computed risk (0–1) |
| prediction | INTEGER | 0=Normal, 1=Anomaly |
| risk_level | VARCHAR(16) | LOW / MEDIUM / HIGH |
| features_json | TEXT | Full feature vector as JSON |

---

## 🐳 Docker Deployment

```bash
# Build and run
docker-compose up --build

# Frontend: http://localhost:80
# Backend:  http://localhost:8000
```

---

## ☁️ Render Deployment

### Backend
- **Root Directory**: `.` (project root)
- **Build Command**: `pip install -r backend/requirements.txt`
- **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Environment**: Set `DATABASE_URL` for MySQL, `ALLOWED_ORIGINS` for CORS

### Frontend
- **Root Directory**: `frontend`
- **Build Command**: `npm install && npm run build`
- **Publish Directory**: `dist`

---

## 🧠 ML Model Details

- **Algorithm**: LightGBM (Gradient Boosted Decision Trees)
- **Dataset**: 9,082 rows × 3,861 features (after preprocessing)
- **Target**: F3924 (0=Normal, 1=Anomaly)
- **Class Balance**: 9,001 normal : 81 anomaly (111:1 ratio)
- **Imbalance Handling**: `scale_pos_weight=111`, `class_weight="balanced"`
- **Explainability**: SHAP TreeExplainer for per-prediction explanations

---

## 📜 License

MIT License — Built for hackathon demonstration and educational purposes.
