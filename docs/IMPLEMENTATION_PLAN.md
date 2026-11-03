# Implementation Plan

- [x] Initialize repository and local-first project documentation.
- [x] Add FastAPI and SQLAlchemy foundation.
- [x] Add protected, idempotent outreach CSV importer.
- [x] Add baseline tests for CSV import behavior.
- [ ] Audit and import the existing Gmail send log, preserving message/thread IDs.
- [ ] Add Alembic migrations and schema versioning.
- [ ] Add candidate profile and document metadata (never store CVs in Git).
- [ ] Add Gmail OAuth and incremental read-only sync for historic and new job-related threads.
- [ ] Add email classification with evidence and confidence.
- [ ] Add job source registry and compliant connectors.
- [ ] Add deduplication, job matching and explainable score breakdowns.
- [ ] Add hybrid AI provider interface and prompt/data minimization.
- [ ] Add application preparation and review queue.
- [ ] Add approved-rule evaluator, global pause, dry-run and audit events.
- [ ] Add supported ATS adapters and verified submission receipts.
- [ ] Add dashboard frontend, reports and assistant chat.
- [ ] Add Docker local stack, integration tests, backup/restore and security review.

No live Gmail sending or job-site submission is enabled in this foundation.
