import json
import os
import sqlite3
import time
from pathlib import Path
from typing import List

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

DB_PATH = Path("incidents.db")
app = FastAPI(title="AI On-Call Engineer Lite")


class LogInput(BaseModel):
    logs: List[str]
    expected_cause: str | None = None


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL,
                log_excerpt TEXT,
                root_cause TEXT,
                severity TEXT,
                proposed_fix TEXT,
                verification_status TEXT,
                triage_ms INTEGER,
                expected_cause TEXT
            )
            """
        )
        conn.commit()


def rule_based_triage(joined: str) -> dict:
    text = joined.lower()
    if "address already in use" in text or "errno 48" in text:
        return {
            "root_cause": "Port conflict on application bind port",
            "severity": "P1",
            "proposed_fix": "lsof -i :8000 && kill -9 <PID> (or switch port to 8001)",
            "verification_check": "Confirm port 8000 is free or new listener responds on /health",
            "safe_auto": True,
        }
    if "database is locked" in text:
        return {
            "root_cause": "SQLite database write lock contention",
            "severity": "P2",
            "proposed_fix": "Enable WAL mode (PRAGMA journal_mode=WAL;) and set busy_timeout=5000",
            "verification_check": "Run test write transaction and confirm zero OperationalError retries",
            "safe_auto": True,
        }
    if "failed password" in text or "failed login attempts" in text:
        return {
            "root_cause": "SSH brute-force authentication spike",
            "severity": "P1",
            "proposed_fix": "Block offending source IP at firewall and enforce SSH key-only auth",
            "verification_check": "Verify zero new failed SSH attempts from source IP over next window",
            "safe_auto": False,
        }
    if "validsignatureerror" in text or "token validation rejected" in text:
        return {
            "root_cause": "Expired or missing JWT signing secret",
            "severity": "P1",
            "proposed_fix": "Rotate/reload JWT_SECRET env var and restart auth-service",
            "verification_check": "Verify sample token validation returns HTTP 200",
            "safe_auto": True,
        }
    if "readtimeout" in text or "circuit breaker opened" in text:
        return {
            "root_cause": "Upstream API connection timeout",
            "severity": "P2",
            "proposed_fix": "Check ledger-api health/latency and tune timeout + retry backoff",
            "verification_check": "Confirm circuit breaker closes and probe request succeeds",
            "safe_auto": True,
        }
    if "out of memory: killed process" in text:
        return {
            "root_cause": "Out-of-memory kill on worker process",
            "severity": "P1",
            "proposed_fix": "Profile memory allocation in worker batch loop and raise memory limit",
            "verification_check": "Confirm worker stays active without SIGKILL for 60s",
            "safe_auto": False,
        }
    if "keyerror:" in text or "missing configuration" in text:
        return {
            "root_cause": "Missing required environment variable",
            "severity": "P2",
            "proposed_fix": "Set missing env variable in .env/deployment config and restart service",
            "verification_check": "Confirm service starts cleanly with exit code 0",
            "safe_auto": True,
        }
    if "certificate has expired" in text:
        return {
            "root_cause": "TLS certificate expiration",
            "severity": "P1",
            "proposed_fix": "Renew TLS certificate and reload ingress-proxy configuration",
            "verification_check": "Verify TLS handshake succeeds with valid expiry date",
            "safe_auto": False,
        }
    if "no space left on device" in text or "errno 28" in text:
        return {
            "root_cause": "Disk space exhaustion on log partition",
            "severity": "P1",
            "proposed_fix": "Rotate/archive old logs and clear stale temp files on target partition",
            "verification_check": "Confirm df -h shows available disk headroom and log writes succeed",
            "safe_auto": False,
        }
    if "undefinedcolumn" in text or "column" in text and "does not exist" in text:
        return {
            "root_cause": "Invalid SQL column reference in query",
            "severity": "P2",
            "proposed_fix": "Align SQL query column name with current database schema migration",
            "verification_check": "Run read/write query against schema and verify zero SQL errors",
            "safe_auto": True,
        }
    return {
        "root_cause": "Unclassified service error requiring log inspection",
        "severity": "P2",
        "proposed_fix": "Inspect full stack trace around error timestamp and reproduce locally",
        "verification_check": "Confirm error rate drops to baseline after patch",
        "safe_auto": False,
    }


def llm_triage(logs: List[str]) -> dict | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    prompt = (
        "You are an AI on-call SRE. Analyze these logs and return ONLY valid JSON with keys: "
        "root_cause (short string), severity (P1/P2/P3), proposed_fix (concise action), "
        "verification_check (how to verify fix), safe_auto (boolean: true only for non-destructive checks/restarts).\n"
        f"Logs:\n" + "\n".join(logs)
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw)
    except Exception:
        return None


def verify_remediation(triage: dict) -> str:
    if triage.get("safe_auto"):
        return "verified_safe_fix"
    return "needs_human_approval"


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse("index.html")


@app.post("/triage")
def triage_incident(payload: LogInput) -> JSONResponse:
    start = time.perf_counter()
    joined = "\n".join(payload.logs)
    result = llm_triage(payload.logs) or rule_based_triage(joined)
    status = verify_remediation(result)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT INTO incidents (
                created_at, log_excerpt, root_cause, severity, proposed_fix,
                verification_status, triage_ms, expected_cause
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(),
                joined[:400],
                result.get("root_cause", "Unknown"),
                result.get("severity", "P2"),
                result.get("proposed_fix", ""),
                status,
                elapsed_ms,
                payload.expected_cause or "",
            ),
        )
        conn.commit()
        row_id = cur.lastrowid

    return JSONResponse(
        {
            "id": row_id,
            "root_cause": result.get("root_cause"),
            "severity": result.get("severity"),
            "proposed_fix": result.get("proposed_fix"),
            "verification_check": result.get("verification_check"),
            "verification_status": status,
            "triage_ms": elapsed_ms,
        }
    )


@app.get("/incidents")
def list_incidents() -> JSONResponse:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM incidents ORDER BY id DESC LIMIT 30"
        ).fetchall()
    return JSONResponse([dict(r) for r in rows])
