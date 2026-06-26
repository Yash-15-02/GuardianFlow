"""
ThreatTron AI — LightGBM Training Pipeline
============================================
Trains a single LightGBM classifier on the preprocessed banking anomaly
dataset with stratified splitting, class-imbalance handling, and full
metric reporting.  Saves the model, feature columns, and encoders.
"""

import os
import sys
import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
import lightgbm as lgb
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    classification_report,
    confusion_matrix,
)

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def train(cfg: dict) -> None:
    processed_dir = BASE_DIR / cfg["paths"]["processed_dir"]
    models_dir = BASE_DIR / cfg["paths"]["models_dir"]
    models_dir.mkdir(parents=True, exist_ok=True)

    lgb_cfg = cfg["lightgbm"]
    train_cfg = cfg["training"]

    # ── Load preprocessed data ───────────────────────────────────────────────
    print("[1/5] Loading preprocessed data ...")
    X = pd.read_csv(str(processed_dir / "X_processed.csv"))
    y = pd.read_csv(str(processed_dir / "y_target.csv")).squeeze()
    print(f"      X shape: {X.shape}  |  y distribution: {dict(y.value_counts())}")

    # ── Train / Test split ───────────────────────────────────────────────────
    print("[2/5] Stratified train/test split ...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=train_cfg["test_size"],
        random_state=train_cfg["random_state"],
        stratify=y,
    )
    print(f"      Train: {X_train.shape[0]}  |  Test: {X_test.shape[0]}")

    # ── Build LightGBM model ─────────────────────────────────────────────────
    print("[3/5] Training LightGBM classifier ...")
    model = lgb.LGBMClassifier(
        n_estimators=lgb_cfg["n_estimators"],
        learning_rate=lgb_cfg["learning_rate"],
        max_depth=lgb_cfg["max_depth"],
        num_leaves=lgb_cfg["num_leaves"],
        min_child_samples=lgb_cfg["min_child_samples"],
        subsample=lgb_cfg["subsample"],
        colsample_bytree=lgb_cfg["colsample_bytree"],
        reg_alpha=lgb_cfg["reg_alpha"],
        reg_lambda=lgb_cfg["reg_lambda"],
        scale_pos_weight=lgb_cfg["scale_pos_weight"],
        class_weight=lgb_cfg["class_weight"],
        verbosity=lgb_cfg["verbosity"],
        n_jobs=lgb_cfg["n_jobs"],
        random_state=train_cfg["random_state"],
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
    )

    # ── Evaluate ─────────────────────────────────────────────────────────────
    print("[4/5] Evaluating on test set ...")
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    roc = roc_auc_score(y_test, y_proba)
    cm = confusion_matrix(y_test, y_pred)

    print(f"\n{'='*50}")
    print(f"  Accuracy  : {acc:.4f}")
    print(f"  Precision : {prec:.4f}")
    print(f"  Recall    : {rec:.4f}")
    print(f"  F1-Score  : {f1:.4f}")
    print(f"  ROC-AUC   : {roc:.4f}")
    print(f"{'='*50}")
    print(f"\n  Confusion Matrix:\n{cm}")
    print(f"\n{classification_report(y_test, y_pred, target_names=['Normal', 'Anomaly'])}")

    # ── Cross-validation ─────────────────────────────────────────────────────
    print("[4b/5] Stratified K-Fold cross-validation ...")
    skf = StratifiedKFold(n_splits=train_cfg["n_splits"], shuffle=True, random_state=train_cfg["random_state"])
    cv_aucs = []
    for fold, (tr_idx, va_idx) in enumerate(skf.split(X, y), 1):
        fold_model = lgb.LGBMClassifier(
            n_estimators=lgb_cfg["n_estimators"],
            learning_rate=lgb_cfg["learning_rate"],
            max_depth=lgb_cfg["max_depth"],
            num_leaves=lgb_cfg["num_leaves"],
            min_child_samples=lgb_cfg["min_child_samples"],
            subsample=lgb_cfg["subsample"],
            colsample_bytree=lgb_cfg["colsample_bytree"],
            reg_alpha=lgb_cfg["reg_alpha"],
            reg_lambda=lgb_cfg["reg_lambda"],
            scale_pos_weight=lgb_cfg["scale_pos_weight"],
            class_weight=lgb_cfg["class_weight"],
            verbosity=-1,
            n_jobs=lgb_cfg["n_jobs"],
            random_state=train_cfg["random_state"],
        )
        fold_model.fit(X.iloc[tr_idx], y.iloc[tr_idx])
        fold_proba = fold_model.predict_proba(X.iloc[va_idx])[:, 1]
        fold_auc = roc_auc_score(y.iloc[va_idx], fold_proba)
        cv_aucs.append(fold_auc)
        print(f"      Fold {fold} AUC: {fold_auc:.4f}")
    print(f"      Mean CV AUC: {np.mean(cv_aucs):.4f} ± {np.std(cv_aucs):.4f}")

    # ── Feature importance ───────────────────────────────────────────────────
    importance = model.feature_importances_
    feature_names = list(X.columns)
    imp_df = pd.DataFrame({
        "feature": feature_names,
        "importance": importance,
    }).sort_values("importance", ascending=False)

    top_n = cfg.get("top_features_count", 20)
    print(f"\n  Top {top_n} features:")
    for _, row in imp_df.head(top_n).iterrows():
        print(f"    {row['feature']:>10s}  {row['importance']:>8.0f}")

    # ── Save artifacts ───────────────────────────────────────────────────────
    print("\n[5/5] Saving model artifacts ...")
    with open(str(models_dir / "model.pkl"), "wb") as f:
        pickle.dump(model, f)

    with open(str(models_dir / "feature_columns.pkl"), "wb") as f:
        pickle.dump(feature_names, f)

    imp_df.to_csv(str(models_dir / "feature_importance.csv"), index=False)

    metrics = {
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc, 4),
        "cv_auc_mean": round(float(np.mean(cv_aucs)), 4),
        "cv_auc_std": round(float(np.std(cv_aucs)), 4),
        "confusion_matrix": cm.tolist(),
        "top_features": imp_df.head(top_n)[["feature", "importance"]].to_dict("records"),
    }
    with open(str(models_dir / "training_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    # Save test data for evaluate.py
    X_test.to_csv(str(processed_dir / "X_test.csv"), index=False)
    y_test.to_csv(str(processed_dir / "y_test.csv"), index=False)

    print(f"\n[OK] Training complete!")
    print(f"    Model saved   : {models_dir / 'model.pkl'}")
    print(f"    Metrics saved : {models_dir / 'training_metrics.json'}")


if __name__ == "__main__":
    cfg = load_config()
    train(cfg)
