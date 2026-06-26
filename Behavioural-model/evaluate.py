"""
ThreatTron AI — Model Evaluation & Reporting
==============================================
Generates confusion matrix, classification report, ROC curve data,
and top-20 feature importance from the trained LightGBM model.
"""

import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    roc_curve,
    classification_report,
    confusion_matrix,
)

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def evaluate(cfg: dict) -> None:
    processed_dir = BASE_DIR / cfg["paths"]["processed_dir"]
    models_dir = BASE_DIR / cfg["paths"]["models_dir"]

    # ── Load model & test data ───────────────────────────────────────────────
    print("[1/4] Loading model and test data ...")
    with open(str(models_dir / "model.pkl"), "rb") as f:
        model = pickle.load(f)

    X_test = pd.read_csv(str(processed_dir / "X_test.csv"))
    y_test = pd.read_csv(str(processed_dir / "y_test.csv")).squeeze()
    print(f"      Test set: {X_test.shape[0]} samples")

    # ── Predict ──────────────────────────────────────────────────────────────
    print("[2/4] Running predictions ...")
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    # ── Metrics ──────────────────────────────────────────────────────────────
    print("[3/4] Computing metrics ...")
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    roc = roc_auc_score(y_test, y_proba)
    cm = confusion_matrix(y_test, y_pred)
    report = classification_report(y_test, y_pred, target_names=["Normal", "Anomaly"], output_dict=True)

    print(f"\n{'='*55}")
    print(f"  MODEL EVALUATION REPORT")
    print(f"{'='*55}")
    print(f"  Accuracy  : {acc:.4f}")
    print(f"  Precision : {prec:.4f}")
    print(f"  Recall    : {rec:.4f}")
    print(f"  F1-Score  : {f1:.4f}")
    print(f"  ROC-AUC   : {roc:.4f}")
    print(f"{'='*55}")
    print(f"\n  Confusion Matrix:")
    print(f"                 Predicted Normal   Predicted Anomaly")
    print(f"  Actual Normal       {cm[0][0]:>6}             {cm[0][1]:>6}")
    print(f"  Actual Anomaly      {cm[1][0]:>6}             {cm[1][1]:>6}")
    print(f"\n{classification_report(y_test, y_pred, target_names=['Normal', 'Anomaly'])}")

    # ── ROC curve ────────────────────────────────────────────────────────────
    fpr, tpr, thresholds = roc_curve(y_test, y_proba)
    roc_data = {
        "fpr": [round(float(x), 6) for x in fpr],
        "tpr": [round(float(x), 6) for x in tpr],
        "thresholds": [round(float(x), 6) for x in thresholds],
    }

    # ── Feature importance ───────────────────────────────────────────────────
    importance = model.feature_importances_
    feature_names = list(X_test.columns)
    imp_df = pd.DataFrame({
        "feature": feature_names,
        "importance": importance.astype(float),
    }).sort_values("importance", ascending=False)

    top_n = cfg.get("top_features_count", 20)
    top_features = imp_df.head(top_n).to_dict("records")
    print(f"\n  Top {top_n} Most Important Features:")
    print(f"  {'Feature':>12s}  {'Importance':>12s}")
    print(f"  {'-'*12}  {'-'*12}")
    for feat in top_features:
        print(f"  {feat['feature']:>12s}  {feat['importance']:>12.0f}")

    # ── Save evaluation report ───────────────────────────────────────────────
    print("\n[4/4] Saving evaluation report ...")
    eval_report = {
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc, 4),
        "confusion_matrix": {
            "true_negative": int(cm[0][0]),
            "false_positive": int(cm[0][1]),
            "false_negative": int(cm[1][0]),
            "true_positive": int(cm[1][1]),
        },
        "classification_report": report,
        "roc_curve": roc_data,
        "top_features": top_features,
    }

    report_path = models_dir / "evaluation_report.json"
    with open(str(report_path), "w") as f:
        json.dump(eval_report, f, indent=2)

    print(f"\n[OK]  Evaluation complete!")
    print(f"    Report saved: {report_path}")


if __name__ == "__main__":
    cfg = load_config()
    evaluate(cfg)
