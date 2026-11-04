# Advanced career operations

This branch extends the existing candidate workspace and APIs. External actions remain candidate-controlled.

## ATS field automation

1. Create and review a mapping with `POST /api/v1/applications/{application_id}/ats-draft`.
2. Confirm the complete mapping with `POST /api/v1/applications/{application_id}/ats-draft/approve`.
3. Approve each field separately with `POST /api/v1/applications/{application_id}/ats-draft/actions/{field_id}/approve`.
4. A browser worker with a candidate-authenticated Playwright page can call `packages.automation.ats_execution.execute_ats_field` for one approved field at a time.
5. Each fill is digest-bound to the approved draft and value, checks the HTTPS origin against the application URL, uses an idempotency record, verifies the field value, and stores a private screenshot evidence object.

The adapter only fills a single labelled control. It does not click submit, change pages, or send an application. A separate submission workflow and confirmation are intentionally required. Browser profile/session provisioning and a deployed browser worker are not included by this library integration alone.

## Gmail and interview lifecycle

Gmail remains read-only. Message classification is linked to an application only when role/company evidence is unambiguous. Application status changes require explicit confirmation and a valid FSM transition.

For interview invitations, the candidate supplies a timezone-aware date/time and confirms it through `POST /api/v1/gmail/messages/{email_id}/confirm-interview`. The service creates a local interview record and returns the existing calendar sync route. `POST /api/v1/calendar/reconcile` explicitly retries calendar synchronization for upcoming interviews. Deterministic Google event IDs make updates and retries idempotent.

## Resume extraction and variants

Resume uploads now accept PDF, DOCX, text, Markdown and common image formats. Install the optional OCR extra and the Tesseract system binary for image OCR and scanned-PDF OCR:

```bash
pip install -e ".[document-ocr]"
```

Scanned PDF OCR is bounded to 30 pages and rendered pixel limits. Image OCR has a 40-million-pixel limit. OCR errors are reported instead of silently accepting an unreadable scanned file.

Tailored resume outputs are stored as versioned `GeneratedArtifact` records. They preserve the source resume and retain source/job-description hashes and optional parent artifact lineage. Drafts require candidate review.

## Ranking experiments

`GET /api/v1/recommendations/experiments/{experiment_id}/assignment` returns a stable candidate-level control/explore assignment and propensity. Include the experiment ID, arm and propensity when logging impressions and interactions. `packages.recommendations.bandit_experiments.evaluate_experiment` reports arm-level CTR, application rate, reward, Wilson intervals and inverse-propensity-weighted reward. Insufficient exposure blocks a decision and model promotion is never automatic.

LTR training remains offline and candidate-group-held-out. Registered rankers must pass the existing AUC and NDCG gates before promotion.

## Event operations

- Event envelopes support explicitly registered schema v1 and additive v2.
- The outbox validates event schemas before persisting messages.
- Replay is an explicit, bounded operation over already-published records; preserve original event IDs. For intentional consumer reprocessing, use a new consumer name so inbox deduplication remains meaningful.
- The Redis sliding-window limiter uses atomic Lua operations and fails closed when Redis is unavailable in production.
- Worker metrics are exposed on `WORKER_METRICS_PORT` (default `9101`); scrape that endpoint separately from the API's `/metrics`.
- Worker alert evaluation emits structured warnings and Prometheus counters/gauges for backlog age, DLQ count and threshold alerts.

## Operational validation

Before deployment:
- Apply migrations through revision `20261104_0025`.
- Install `.[document-ocr]` only where OCR is required and install the Tesseract binary.
- Configure private object storage for browser evidence screenshots.
- Provision an authenticated browser profile and a controlled Playwright runner before enabling ATS field execution.
- Configure Prometheus scraping for both API and worker metrics.
- Run Python lint, typing, migration upgrade/downgrade tests, route tests, and the full test suite against PostgreSQL and Redis.
