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
python -m scripts.import_outreach "C:\\path\\to\\kenya_data_opportunities_contacts.csv" --dry-run
python -m scripts.import_outreach "C:\\path\\to\\kenya_data_opportunities_contacts.csv"
```

Import the historical Gmail send log without editing the source:

```powershell
python -m scripts.import_send_log "C:\\path\\to\\outreach_send_log.csv" --dry-run
python -m scripts.import_send_log "C:\\path\\to\\outreach_send_log.csv"
```

Then configure a Google OAuth Desktop client outside the repository, set `GMAIL_ENABLED=true`, `GMAIL_CLIENT_SECRET_FILE`, and `GMAIL_TOKEN_FILE` in local `.env`, and run:

```powershell
python -m scripts.sync_gmail --max-messages 500
```

The Gmail connector requests read-only access and fetches metadata/snippets. It does not send or modify mail. See [Gmail intelligence](docs/GMAIL_INTELLIGENCE.md) and [outreach reconciliation](docs/OUTREACH_RECONCILIATION.md).

## Configuration

See `.env.example`. All integrations are disabled unless explicitly configured. Never commit `.env`, OAuth credentials, tokens, CVs, or private outreach data.

## Development

```powershell
pytest
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md), and [docs/SAFE_AUTOMATION.md](docs/SAFE_AUTOMATION.md).
