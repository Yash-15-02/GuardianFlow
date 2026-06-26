"""
ThreatTron AI — Data Preprocessing Pipeline
=============================================
Loads the raw banking anomaly dataset, cleans it, encodes categoricals,
drops fully-empty columns, and persists artifacts for downstream training.
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
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.yaml"

def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def preprocess(cfg: dict) -> None:
    """Full preprocessing pipeline."""
    dataset_path = (BASE_DIR / cfg["paths"]["dataset"]).resolve()
    processed_dir = BASE_DIR / cfg["paths"]["processed_dir"]
    models_dir = BASE_DIR / cfg["paths"]["models_dir"]
    processed_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    target_col = cfg["target_column"]
    cat_cols = cfg["categorical_columns"]
    drop_cols = cfg.get("drop_columns", [])

    # ── 1. Load ──────────────────────────────────────────────────────────────
    print(f"[1/6] Loading dataset from {dataset_path} ...")
    df = pd.read_csv(str(dataset_path), low_memory=False)
    print(f"       Raw shape: {df.shape}")

    # ── 2. Drop explicit columns ─────────────────────────────────────────────
    existing_drops = [c for c in drop_cols if c in df.columns]
    if existing_drops:
        df.drop(columns=existing_drops, inplace=True)
        print(f"[2/6] Dropped columns: {existing_drops}")
    else:
        print("[2/6] No explicit drop columns found — skipping.")

    # ── 3. Separate target ───────────────────────────────────────────────────
    if target_col not in df.columns:
        print(f"ERROR: Target column '{target_col}' not found.")
        sys.exit(1)

    y = df[target_col].copy()
    df.drop(columns=[target_col], inplace=True)
    print(f"[3/6] Target '{target_col}' separated — class distribution:")
    print(f"       {dict(y.value_counts())}")

    # ── 4. Drop 100 % NaN columns ───────────────────────────────────────────
    all_nan_cols = [c for c in df.columns if df[c].isnull().all()]
    if all_nan_cols:
        df.drop(columns=all_nan_cols, inplace=True)
        print(f"[4/6] Dropped {len(all_nan_cols)} all-NaN columns.")
    else:
        print("[4/6] No all-NaN columns found.")

    # ── 5. Encode categoricals ───────────────────────────────────────────────
    encoders: dict[str, LabelEncoder] = {}
    present_cat_cols = [c for c in cat_cols if c in df.columns]

    for col in present_cat_cols:
        le = LabelEncoder()
        # Handle NaN by converting to string "MISSING"
        series = df[col].fillna("MISSING").astype(str)
        le.fit(series)
        df[col] = le.transform(series)
        encoders[col] = le
        print(f"[5/6] Encoded '{col}' -> {len(le.classes_)} classes")

    # ── 6. Impute remaining NaN with 0 (LightGBM handles NaN natively,
    #        but we store 0 for downstream JSON serialisation safety) ─────────
    nan_before = int(df.isnull().sum().sum())
    df.fillna(0, inplace=True)
    print(f"[6/6] Imputed {nan_before:,} remaining NaN values with 0.")

    # ── Persist ──────────────────────────────────────────────────────────────
    feature_columns = list(df.columns)

    df.to_csv(str(processed_dir / "X_processed.csv"), index=False)
    y.to_csv(str(processed_dir / "y_target.csv"), index=False)

    with open(str(models_dir / "encoders.pkl"), "wb") as f:
        pickle.dump(encoders, f)

    with open(str(models_dir / "feature_columns.pkl"), "wb") as f:
        pickle.dump(feature_columns, f)

    # Save a lightweight metadata summary
    meta = {
        "total_rows": len(df),
        "total_features": len(feature_columns),
        "categorical_encoded": present_cat_cols,
        "all_nan_dropped": len(all_nan_cols),
        "nan_imputed": nan_before,
        "class_distribution": {int(k): int(v) for k, v in y.value_counts().items()},
    }
    with open(str(processed_dir / "preprocessing_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print("\n[OK] Preprocessing complete!")
    print(f"    Features  : {len(feature_columns)}")
    print(f"    Rows      : {len(df)}")
    print(f"    Saved to  : {processed_dir}")
    print(f"    Encoders  : {models_dir / 'encoders.pkl'}")


if __name__ == "__main__":
    cfg = load_config()
    preprocess(cfg)
