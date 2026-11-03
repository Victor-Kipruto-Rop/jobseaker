# Architecture

## System shape

The application is local-first. FastAPI exposes a local API, SQLAlchemy persists normalized records to SQLite, and a future frontend consumes the API. PostgreSQL is the intended multi-user/deployment database, but the first milestone is deliberately local.

```text
Job boards / company career pages ----> Discovery connectors ----> Jobs
Gmail OAuth --------------------------> Email sync -------------> Email events
Local outreach CSV + send log -------> Import/reconciliation ---> Outreach history
Candidate profile + CV --------------> Profile store (local)
                                      |
                                      v
                              Matching + AI gateway
                                      |
                     +----------------+----------------+
                     v                                 v
              Recommendation store              Application queue
                                                       |
                                               Rule evaluation
                                                       |
                                     +-----------------+----------------+
                                     v                                  v
                              Auto-submit (approved)              Human approval
```

## Data boundaries

- Candidate CVs, Gmail tokens, email content, databases, and contact exports stay outside Git.
- Cloud AI receives only the minimum context needed for a requested task. Provider calls are disabled until configured.
- AI output is advisory. Candidate facts and application answers must be verified.
- Source records include provenance and timestamps.
- Gmail message IDs and thread IDs are unique synchronization keys.

## Automation safety

Global pause defaults to true. Auto-submission defaults to false. A future rule engine must require an enabled user-approved rule, a supported application adapter, verified required answers, a valid document, duplicate checks, and a captured confirmation. Anything else enters a human approval queue.

## Persistence

SQLite is used for local development. Models use SQLAlchemy and avoid SQLite-only types where possible. Database migrations will be added before schema changes become operationally important.
