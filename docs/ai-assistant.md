# JobSeeker Personal AI Assistant

The assistant is a first-class capability inside the existing JobSeeker dashboard and API. It reuses the authenticated candidate session, provider registry, quota reservations, AI usage ledger, conversation/message persistence, PostgreSQL database, and Redis/RQ worker. It is not a separate chatbot application.

## Dashboard and API

The light-mode assistant workspace is available at `/assistant`, linked from the existing application navigation. The authenticated API is mounted under `/api/v1/ai/assistant`.

- `POST /assistant/chat`
- `GET /assistant/memory`
- `PATCH /assistant/memory?enabled=true|false`
- `DELETE /assistant/memory`
- `GET /assistant/memory/export`
- `PATCH /assistant/memory/retention?days=365` (30 to 730 days)
- `PUT /assistant/preferences`
- `POST /assistant/feedback`
- `POST /assistant/ingest-async`
- `GET /assistant/ingestion/{job_id}`
- `DELETE /assistant/ingestion/{job_id}`

## Memory, retrieval and knowledge graph

- Persistent episodic memory is opt-in. Pausing it prevents new writes and retrieval.
- Episodic content, summaries, and extracted fact values are encrypted using the existing versioned AES-256-GCM credential keyring with purpose-specific associated data.
- New PostgreSQL memory records use 384-dimensional pgvector embeddings and an HNSW cosine index. Hybrid ranking combines dense similarity and lexical BM25-style scoring, with optional cross-encoder reranking.
- SQLite and non-PostgreSQL test environments retain the JSON embedding fallback.
- Existing legacy JSON vectors are not cast to a different dimension. Re-embedding/backfill is required before those records can participate in the pgvector index.
- Entity resolution is scoped to the authenticated user and entity type. It canonicalizes common technology aliases and extracts selected skills, employers, projects and roles. Fuzzy merges require a high confidence margin; ambiguous candidates are not merged.
- Working context is bounded and includes recent messages, relevant memory, facts, preferences and graph relationships.

## Background ingestion

Document uploads are stored as durable ingestion-job records and dispatched to the existing Redis/RQ worker on the dedicated `assistant` queue. The file payload is encrypted before persistence; Redis receives only the job identifier. The worker rechecks memory consent before parsing and indexing. Job status and cancellation are owner-scoped. Payload ciphertext is cleared after success, cancellation or terminal failure.

Supported input includes PDF, DOCX, text, Markdown, images with optional OCR, and Python source AST extraction. OCR requires Pillow, pytesseract and the Tesseract system binary.

## Agent orchestration and safety

The orchestration layer creates bounded multi-step plans and executes sequentially through a strict read-only capability registry for candidate profile, applications, interviews and job opportunities. Each step records status and attempts; transient read failures can be retried. This is deterministic bounded orchestration, not yet a model-directed ReAct loop or dynamic third-party tool system.

The assistant cannot submit applications, send email, change application lifecycle state, or perform external writes. Those remain within existing explicit approval workflows. Retrieved documents and memories are treated as untrusted data, and candidate records are always filtered by the authenticated user.

## Privacy and operations

- Memory starts disabled. Enabling it requires a configured encryption keyring.
- Configure `JOBSEEKER_CREDENTIAL_KEYRING` and `JOBSEEKER_CREDENTIAL_ACTIVE_KEY_ID`, or the supported legacy `JOBSEEKER_CREDENTIAL_KEK`, in the deployment secret manager. Do not commit key material.
- Retain old key IDs during key rotation until stored ciphertext has been rewrapped.
- New episodic memories receive a 365-day expiry by default; the owner can change retention from 30 to 730 days.
- Users can export their memory and facts, pause memory, cancel queued ingestion, or delete memories, facts and graph relations. Deletion disables memory and clears pending encrypted ingestion payloads.
- Graph entity labels and selected operational metadata remain structured database fields. Protect the database with TLS, encrypted storage, restricted service credentials and managed backups.

## Remaining engineering boundaries

- Full model-directed ReAct planning, browser automation and dynamic third-party tools are not implemented.
- Entity extraction covers selected patterns and does not yet create a universal graph over every project, person, qualification or connected data source.
- A dedicated toxicity classifier and independent post-generation moderation service are not implemented.
- Implicit dwell-time and scroll telemetry are not implemented.
- Repository-wide GitHub crawler/AST ingestion is not connected; Python source can be uploaded for local AST indexing.
- Hierarchical LLM summarization and a fact-verification UI remain future work.

## Migration and verification

Apply schema changes with:

```bash
alembic upgrade head
```

The new migration is `20261104_0022`, following `20261104_0021`. Install the standard project dependencies to include pgvector.

Before merge, run the focused assistant tests, the complete Python lint/type/test suite, Alembic upgrade and downgrade checks, frontend typecheck/build, and Docker Compose integration. GitHub Actions has reported failures on this branch; the available job-log endpoint currently returns BlobNotFound, so those failures have not been diagnosed. Do not merge or deploy until checks are passing.
