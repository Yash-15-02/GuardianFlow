"""
ThreatTron AI — Streaming Agent Simulator
==========================================
Reads rows sequentially from DataSet.csv and streams them as telemetry
events to the backend API at a configurable pace.

Usage:
    python -m agent.src.main                  # default: 1 event every 3 seconds
    python -m agent.src.main --delay 1        # 1 event per second
    python -m agent.src.main --batch 5        # 5 events per batch
    python -m agent.src.main --rows 200       # only send 200 rows then stop
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

# ── Ensure project root is on path ──────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from agent.src.sender.sender import send_batch

DATASET_PATH = ROOT / "DataSet.csv"

# ── Categorical column names (will be extracted as metadata) ─────────────────
CAT_COLS_MAP = {
    "F3886": "account_type",
    "F3891": "occupation",
    "F3893": "segment",
    "F3890": "area",
}

# All categorical columns to exclude from numeric features dict
ALL_CAT_COLS = {"F2230", "F3886", "F3888", "F3889", "F3890", "F3891", "F3892", "F3893"}


def generate_agent_id() -> str:
    mac = uuid.getnode()
    host = socket.gethostname()
    return hashlib.sha256(f"{mac}-{host}".encode()).hexdigest()[:16]


def build_event(row: pd.Series) -> dict:
    """Convert a DataFrame row into an event payload."""
    meta: dict = {}
    for raw_col, nice_name in CAT_COLS_MAP.items():
        val = row.get(raw_col)
        meta[nice_name] = str(val) if pd.notna(val) else None

    # Numerical features (everything except categoricals and target)
    features: dict = {}
    for col, val in row.items():
        if col in ALL_CAT_COLS or col == "Unnamed: 0" or col == "F3924":
            continue
        features[col] = 0.0 if pd.isna(val) else float(val)

    return {**meta, "features": features}


def run_agent(delay: float, batch_size: int, max_rows: int | None) -> None:
    print(f"[agent] Loading dataset from {DATASET_PATH} ...")
    df = pd.read_csv(str(DATASET_PATH), low_memory=False)
    print(f"[agent] Dataset loaded: {df.shape[0]} rows × {df.shape[1]} columns")

    session_id = str(uuid.uuid4())
    agent_id = generate_agent_id()
    hostname = socket.gethostname()

    total_to_send = min(len(df), max_rows) if max_rows else len(df)
    print(f"[agent] Session : {session_id}")
    print(f"[agent] Agent   : {agent_id}")
    print(f"[agent] Sending {total_to_send} events in batches of {batch_size}, delay={delay}s")
    print(f"{'='*60}")

    sent = 0
    batch: list[dict] = []

    for idx in range(total_to_send):
        row = df.iloc[idx]
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
            if resp:
                # Show risk scores from the response
                scores = [f"{e.get('risk_score', 0):.2f}" for e in resp] if isinstance(resp, list) else ["?"]
                print(f"[agent] Sent batch #{sent // batch_size} | rows {sent - batch_size + 1}–{sent} | risks: {', '.join(scores[:5])}")
            else:
                print(f"[agent] Sent batch #{sent // batch_size} | rows {sent - batch_size + 1}–{sent} | [WARNING] no response")
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
        print(f"[agent] Sent final batch | rows {sent - len(batch) + 1}–{sent}")

    print(f"\n[OK] Agent finished. Total events sent: {sent}")


def main():
    parser = argparse.ArgumentParser(description="ThreatTron AI Streaming Agent")
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds between batches (default: 3)")
    parser.add_argument("--batch", type=int, default=1, help="Events per batch (default: 1)")
    parser.add_argument("--rows", type=int, default=None, help="Max rows to send (default: all)")
    args = parser.parse_args()

    run_agent(delay=args.delay, batch_size=args.batch, max_rows=args.rows)


if __name__ == "__main__":
    main()
