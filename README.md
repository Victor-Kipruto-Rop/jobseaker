# JobSeeker Intelligence

Local-first, AI-assisted job discovery and application management for Kenya and remote opportunities.

> **Current status:** Foundation scaffold. Gmail sync, external discovery connectors, AI provider integration, and portal submission are not yet enabled. Live sending and application submission remain disabled by default.

## Architecture decisions

- Hybrid AI: cloud model providers behind a provider interface; canonical records and credentials remain local.
- Local-first persistence: SQLite for development, SQLAlchemy models designed for PostgreSQL migration.
- Gmail intelligence: planned monitoring of job-related conversations, including historic outreach, with incremental sync and message/thread deduplication.
- Application automation: only submit automatically when an enabled, explicit user-approved rule matches and every required answer/document is verified. All exceptions require confirmation.
- Original outreach CSV and send log are immutable migration sources. Imports are additive, idempotent, and produce reconciliation reports.

## Quick start

Python 3.11+ is recommended.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for the API.

## Initial endpoints

- `GET /health` - service health
- `GET /api/v1/dashboard/summary` - local database counts
- `POST /api/v1/import/outreach/preview` - validate a CSV without writing
- `POST /api/v1/import/outreach` - idempotently import a CSV into the local database

The import never edits the source CSV. It records original row data and reports invalid rows.

## Safe data import

Keep the existing `kenya_data_opportunities_contacts.csv` and `outreach_send_log.csv` in a private local directory outside Git. Do not commit CVs, OAuth tokens, Gmail message bodies, databases, or personal contact exports.

Example:

```powershell
python scripts/import_outreach.py "C:\\path\\to\\kenya_data_opportunities_contacts.csv" --dry-run
python scripts/import_outreach.py "C:\\path\\to\\kenya_data_opportunities_contacts.csv"
```

A future send-log importer will link known Gmail message IDs and thread IDs without treating SENT as proof of delivery or reading.

## Configuration

See `.env.example`. All integrations are disabled unless explicitly configured. Never commit `.env`, OAuth credentials, tokens, CVs, or private outreach data.

## Development

```powershell
pytest
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md), and [docs/SAFE_AUTOMATION.md](docs/SAFE_AUTOMATION.md).
