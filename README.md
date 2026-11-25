# AI On-Call Engineer Lite (Homingo Edition 01 — Track B3)

Lightweight Python (`FastAPI` + `SQLite`) incident triage service that ingests error log windows, identifies root causes, proposes remediation steps, and separates safe auto-remediations from actions requiring human approval.

## Problem & Solution
* **Problem (Track B3 — The AI on-call engineer):** Diagnosing service failures from raw logs takes manual effort, while unguarded automated fixes can cause outages or unintended changes.
* **Solution:** An incident triage API and Bootstrap 5 dashboard that parses log windows, classifies root causes and fixes (`verified_safe_fix` vs. `needs_human_approval`), supports optional Gemini API triage with deterministic rule-based fallback, tracks resolution states in SQLite, and exposes summary metrics (`/summary`).

##  AI On-Call Engineer Lite Dashboard:

<img width="1469" height="780" alt="image" src="https://github.com/user-attachments/assets/93aca941-105a-49dd-8135-0a8748733fb6" />


## Project Structure
```text
ai-oncall-lite/
├── app.py               # FastAPI endpoints (/triage, /incidents, /summary, /)
├── index.html           # Bootstrap 5 dashboard with filters and resolve controls
├── sample_logs.jsonl    # 10 sample incident scenarios for evaluation
├── test_incidents.py    # Benchmark runner for accuracy and latency metrics
├── .gitignore           # Ignores .venv/, incidents.db, and cache files
└── README.md            # Project documentation


