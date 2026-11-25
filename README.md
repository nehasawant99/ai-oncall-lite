# AI On-Call Engineer Lite (Homingo Edition 01 — Track B3)

Lightweight Python (`FastAPI` + `SQLite`) incident triage service that ingests error log windows, identifies root causes, proposes remediation steps, and separates safe auto-remediations from actions requiring human approval.

## Architecture
1. **Ingest (`POST /triage`):** Accepts log lines (`ERROR`, `CRITICAL`, auth failures, or service exceptions).
2. **Diagnose:** Uses Gemini API when `GEMINI_API_KEY` is configured, with a deterministic rule-based fallback for offline/low-latency runs.
3. **Verify & Escalate:** Classifies fixes into `verified_safe_fix` vs. `needs_human_approval` and stores incidents in SQLite (`incidents.db`).
4. **Dashboard (`GET /`):** Bootstrap 5 console with live incident simulation and summary counters.

## Measured Evaluation (`sample_logs.jsonl` — Rule-Based Mode)
* **Root-Cause Accuracy:** 10/10 (100.0%)
* **Avg Triage Latency:** < 1 ms (sub-millisecond local rule triage)
* **Safe Auto-Fixes:** 6/10 (`verified_safe_fix`)
* **Human Escalations:** 4/10 (`needs_human_approval`)
