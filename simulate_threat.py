"""
ThreatTron AI — Threat Simulator (Demo Tool)
==============================================
Extracts ONLY anomalous rows (F3924 == 1) from DataSet.csv and streams
them rapidly to the backend to trigger HIGH-RISK alerts in the dashboard.

Usage:
    python simulate_threat.py              # streams all 81 anomaly rows
    python simulate_threat.py --delay 0.5  # half-second between batches
    python simulate_threat.py --batch 10   # 10 anomalies per batch
"""

import os
import sys
import time
import uuid
import socket
import hashlib
import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agent.src.sender.sender import send_batch

DATASET_PATH = ROOT / "DataSet.csv"

CAT_COLS_MAP = {
    "F3886": "account_type",
    "F3891": "occupation",
    "F3893": "segment",
    "F3890": "area",
}

ALL_CAT_COLS = {"F2230", "F3886", "F3888", "F3889", "F3890", "F3891", "F3892", "F3893"}


def build_event(row: pd.Series) -> dict:
    meta: dict = {}
    for raw_col, nice_name in CAT_COLS_MAP.items():
        val = row.get(raw_col)
        meta[nice_name] = str(val) if pd.notna(val) else None

    features: dict = {}
    for col, val in row.items():
        if col in ALL_CAT_COLS or col == "Unnamed: 0" or col == "F3924":
            continue
        features[col] = 0.0 if pd.isna(val) else float(val)

    return {**meta, "features": features}


def simulate(delay: float, batch_size: int) -> None:
    print("[sim] ThreatTron AI - Threat Simulator")
    print("="*55)
    print(f"[sim] Loading dataset from {DATASET_PATH} ...")
    df = pd.read_csv(str(DATASET_PATH), low_memory=False)

    # Filter to anomalies only
    anomalies = df[df["F3924"] == 1].copy()
    print(f"[sim] Found {len(anomalies)} anomaly rows out of {len(df)} total.")

    if anomalies.empty:
        print("[sim] No anomalies found. Exiting.")
        return

    session_id = f"threat-sim-{uuid.uuid4().hex[:8]}"
    agent_id = f"threat-simulator-{hashlib.sha256(socket.gethostname().encode()).hexdigest()[:8]}"
    hostname = f"THREAT-SIM-{socket.gethostname()}"

    print(f"[sim] Session  : {session_id}")
    print(f"[sim] Agent ID : {agent_id}")
    print(f"[sim] Streaming {len(anomalies)} high-risk events in batches of {batch_size} ...")
    print("="*55)

    sent = 0
    batch: list[dict] = []

    for idx, (_, row) in enumerate(anomalies.iterrows()):
        event = build_event(row)
        batch.append(event)

        if len(batch) >= batch_size:
            resp = send_batch(
                session_id=session_id,
                events=batch,
                agent_id=agent_id,
                hostname=hostname,
            )
            sent += len(batch)
            if resp and isinstance(resp, list):
                scores = [f"{e.get('risk_score', 0):.2f}" for e in resp]
                levels = [e.get("risk_level", "?") for e in resp]
                for s, l in zip(scores, levels):
                    flag = "[HIGH] RISK ALERT" if l == "HIGH" else ("[MEDIUM]" if l == "MEDIUM" else "[LOW]")
                    print(f"  [{sent}] Risk: {s} - {flag}")
            else:
                print(f"  [{sent}] [WARNING] No response from backend")
            batch = []
            time.sleep(delay)

    # Send remaining
    if batch:
        resp = send_batch(
            session_id=session_id,
            events=batch,
            agent_id=agent_id,
            hostname=hostname,
        )
        sent += len(batch)
        if resp and isinstance(resp, list):
            for e in resp:
                s = f"{e.get('risk_score', 0):.2f}"
                l = e.get("risk_level", "?")
                flag = "[HIGH] RISK ALERT" if l == "HIGH" else ("[MEDIUM]" if l == "MEDIUM" else "[LOW]")
                print(f"  [{sent}] Risk: {s} - {flag}")

    print(f"\n[OK] Threat simulation complete! Sent {sent} anomaly events.")
    print("     Check the dashboard for HIGH RISK alerts.")


def main():
    parser = argparse.ArgumentParser(description="ThreatTron AI — Threat Simulator")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between batches (default: 1)")
    parser.add_argument("--batch", type=int, default=1, help="Anomalies per batch (default: 1)")
    args = parser.parse_args()
    simulate(delay=args.delay, batch_size=args.batch)


if __name__ == "__main__":
    main()
