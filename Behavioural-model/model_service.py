"""
ThreatTron AI — Model Service (Inference Layer)
=================================================
Loads the trained LightGBM model once and exposes:
  • predict_risk()          — predict + risk level + top factors
  • get_feature_importance() — global feature importance list
  • explain_prediction()    — SHAP-based local explanation for a single sample
"""

import json
import pickle
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.yaml"


def _load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


class ModelService:
    """Singleton-style service wrapping the trained LightGBM artefacts."""

    def __init__(self) -> None:
        self.cfg = _load_config()
        models_dir = BASE_DIR / self.cfg["paths"]["models_dir"]

        # Model
        with open(str(models_dir / "model.pkl"), "rb") as f:
            self.model = pickle.load(f)

        # Feature columns (ordered list the model was trained on)
        with open(str(models_dir / "feature_columns.pkl"), "rb") as f:
            self.feature_columns: list[str] = pickle.load(f)

        # Label encoders for categoricals
        with open(str(models_dir / "encoders.pkl"), "rb") as f:
            self.encoders: dict = pickle.load(f)

        # Pre-sorted feature importance
        imp = self.model.feature_importances_
        self._importance_df = (
            pd.DataFrame({"feature": self.feature_columns, "importance": imp.astype(float)})
            .sort_values("importance", ascending=False)
        )

        # Lazy SHAP explainer (created on first call)
        self._shap_explainer = None

        # Thresholds
        self._thresh = self.cfg["thresholds"]

    # ── helpers ──────────────────────────────────────────────────────────────
    def _risk_level(self, score: float) -> str:
        if score >= self._thresh["risk_high"]:
            return "HIGH"
        if score >= self._thresh["risk_medium"]:
            return "MEDIUM"
        return "LOW"

    def _prepare_input(self, features: dict) -> pd.DataFrame:
        """Build a single-row DataFrame aligned with training columns."""
        row: dict[str, Any] = {}
        cat_cols = set(self.cfg["categorical_columns"])

        for col in self.feature_columns:
            val = features.get(col, 0)
            if col in cat_cols and col in self.encoders:
                le = self.encoders[col]
                str_val = str(val) if val is not None else "MISSING"
                if str_val in le.classes_:
                    val = int(le.transform([str_val])[0])
                else:
                    val = int(le.transform(["MISSING"])[0]) if "MISSING" in le.classes_ else 0
            row[col] = val

        return pd.DataFrame([row], columns=self.feature_columns)

    def _ensure_shap(self):
        if self._shap_explainer is None:
            import shap
            self._shap_explainer = shap.TreeExplainer(self.model)

    # ── public API ───────────────────────────────────────────────────────────
    def predict_risk(self, features: dict) -> dict:
        """
        Predict risk for a single customer/event.

        Returns
        -------
        {
            "risk_score": float,
            "risk_level": "LOW" | "MEDIUM" | "HIGH",
            "prediction": 0 | 1,
            "top_factors": [{"feature": str, "importance": float}, ...],
        }
        """
        df = self._prepare_input(features)
        proba = float(self.model.predict_proba(df)[0, 1])
        pred = int(self.model.predict(df)[0])
        level = self._risk_level(proba)

        # Per-sample top factors from model feature importance
        top = self._importance_df.head(10).to_dict("records")

        return {
            "risk_score": round(proba, 4),
            "risk_level": level,
            "prediction": pred,
            "top_factors": top,
        }

    def get_feature_importance(self, top_n: int = 20) -> list[dict]:
        """Global feature importance list."""
        return self._importance_df.head(top_n).to_dict("records")

    def explain_prediction(self, features: dict) -> dict:
        """
        SHAP-based local explanation for a single sample.

        Returns
        -------
        {
            "base_value": float,
            "shap_values": [{"feature": str, "value": float, "shap": float}, ...],
        }
        """
        self._ensure_shap()
        df = self._prepare_input(features)
        shap_vals = self._shap_explainer.shap_values(df)

        # For binary classification shap_values can be a list of two arrays
        if isinstance(shap_vals, list):
            sv = shap_vals[1][0]  # class-1 explanations
        else:
            sv = shap_vals[0]

        base = float(self._shap_explainer.expected_value[1]) if isinstance(
            self._shap_explainer.expected_value, (list, np.ndarray)
        ) else float(self._shap_explainer.expected_value)

        explanations = []
        for feat, val, s in zip(self.feature_columns, df.iloc[0].values, sv):
            explanations.append({
                "feature": feat,
                "value": round(float(val), 4),
                "shap": round(float(s), 6),
            })

        # Sort by absolute SHAP magnitude descending
        explanations.sort(key=lambda x: abs(x["shap"]), reverse=True)

        return {
            "base_value": round(base, 4),
            "shap_values": explanations[:30],  # top-30 for readability
        }

    def get_sample_row(self, index: int = 0) -> dict:
        """Load a specific row from the processed dataset for sandbox use."""
        processed_dir = BASE_DIR / self.cfg["paths"]["processed_dir"]
        X = pd.read_csv(str(processed_dir / "X_processed.csv"), skiprows=range(1, index + 1), nrows=1)
        if X.empty:
            X = pd.read_csv(str(processed_dir / "X_processed.csv"), nrows=1)
        return X.iloc[0].to_dict()

    def get_dataset_stats(self) -> dict:
        """Return lightweight metadata about the processed dataset."""
        processed_dir = BASE_DIR / self.cfg["paths"]["processed_dir"]
        meta_path = processed_dir / "preprocessing_meta.json"
        if meta_path.exists():
            with open(str(meta_path), "r") as f:
                return json.load(f)
        return {}


# ── Singleton ────────────────────────────────────────────────────────────────
_instance: ModelService | None = None


def get_model_service() -> ModelService:
    global _instance
    if _instance is None:
        _instance = ModelService()
    return _instance
