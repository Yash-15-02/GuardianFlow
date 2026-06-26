"""
ThreatTron AI — Agent HTTP Sender
==================================
Batches event payloads and POSTs them to the backend ingestion endpoint.
"""

import os
import json
import requests
from typing import Any

BACKEND_URL = os.environ.get(
    "THREATTRON_BACKEND_URL",
    "http://localhost:8000",
)

BATCH_ENDPOINT = f"{BACKEND_URL}/events/batch"


def send_batch(
    session_id: str,
    events: list[dict[str, Any]],
    agent_id: str | None = None,
    hostname: str | None = None,
) -> dict | None:
    """
    Send a batch of events to the ThreatTron backend.

    Parameters
    ----------
    session_id : str
        Unique identifier for this agent session.
    events : list[dict]
        Each dict has keys: account_type, occupation, segment, area, features.
    agent_id : str, optional
        Machine identifier.
    hostname : str, optional
        Human-readable hostname.

    Returns
    -------
    dict or None
        JSON response from the backend, or None on failure.
    """
    payload = {
        "session": {
            "session_id": session_id,
            "agent_id": agent_id,
            "hostname": hostname,
        },
        "events": [
            {
                "session_id": session_id,
                "account_type": ev.get("account_type"),
                "occupation": ev.get("occupation"),
                "segment": ev.get("segment"),
                "area": ev.get("area"),
                "features": ev.get("features", {}),
            }
            for ev in events
        ],
    }

    try:
        resp = requests.post(
            BATCH_ENDPOINT,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[sender] Error posting batch: {e}")
        return None
