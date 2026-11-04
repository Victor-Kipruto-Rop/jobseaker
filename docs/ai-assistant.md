# JobSeeker Personal AI Assistant

The assistant is exposed under `/api/v1/ai/assistant` and the dashboard route `/assistant`.
It reuses the existing AI provider registry, token reservations, usage ledger, authenticated
candidate session and conversation/message tables.

## Features

- User-scoped episodic memories, extracted facts, semantic entity nodes and typed relationships.
- Explicit opt-in for persistent memory. Pausing memory stops new writes and retrieval.
- Hybrid retrieval: dense cosine similarity plus lexical BM25-style scoring, with optional
  SentenceTransformer embeddings and optional CrossEncoder reranking.
- Bounded working context: recent conversation window, retrieved memory shortlist and a
  character budget.
- Extractive summaries for compact memory records.
- Candidate-scoped read-only tools for applications, interviews, profile/CV and opportunities.
- Feedback records and preference adaptation signals.
- PDF, DOCX, text, Markdown, image OCR (optional) and Python AST ingestion.
- PII-like token, email, phone and long-number redaction before memory persistence and model context.
- Memory overview, pause/resume and full memory/graph deletion endpoints.

## API

- `POST /api/v1/ai/assistant/chat`
- `GET /api/v1/ai/assistant/memory`
- `PATCH /api/v1/ai/assistant/memory?enabled=true|false`
- `DELETE /api/v1/ai/assistant/memory`
- `PUT /api/v1/ai/assistant/preferences`
- `POST /api/v1/ai/assistant/feedback`
- `POST /api/v1/ai/assistant/ingest` (multipart field: `file`)

## Database

Apply the migration after the Phase 4 head:

```bash
alembic upgrade head
```

Migration `20261104_0021` adds memory, fact, preference, feedback, entity and relation tables.
All records are owned by `user_id`; foreign keys cascade on account deletion.

## Optional ML and OCR

Install optional extras:

```bash
pip install -e ".[ml,document-ocr]"
```

Configure `JOBSEEKER_MEMORY_EMBEDDING_MODEL` to a locally available SentenceTransformer
model and `JOBSEEKER_CROSS_ENCODER_MODEL` to a locally available CrossEncoder model.
The default offline path uses deterministic feature-hash vectors and lexical retrieval.
For OCR, install the Tesseract system binary in addition to the Python extra.

## Safety boundaries and limitations

- Memory is opt-in and can be paused or deleted independently of chat history.
- Extracted facts are unverified until a user-facing verification flow is implemented.
- The assistant only executes read-only internal context tools automatically. External actions
  such as sending email or submitting applications remain behind existing approval workflows.
- The baseline vector representation is stored in PostgreSQL JSON and ranked in application
  memory. It is suitable for an initial bounded deployment, not a substitute for pgvector or a
  dedicated vector database at high scale.
- The built-in ranking fallback is lexical plus feature-hash cosine. Transformer and
  cross-encoder quality depends on locally installed model artifacts.
- Image OCR is optional and requires Tesseract. Scanned PDFs need OCR conversion before ingestion.
- Repository-wide AST indexing is not wired to a GitHub connector yet; Python source files
  can be uploaded and indexed through the document ingestion endpoint.
- Tool planning currently uses a deterministic allowlisted intent router rather than an
  unconstrained autonomous agent. No browser or external write tool is auto-executed.

## Explicit implementation boundaries

This is the first integrated assistant release, not a claim that every advanced subsystem
in the long-term architecture is production-complete.

Not yet implemented:
- Durable background ingestion/fact extraction workers; document parsing and memory writes
  currently run synchronously in the authenticated API request.
- Dedicated vector database or pgvector-backed assistant memory index. JSON embeddings are
  persisted in PostgreSQL and the application retrieves a bounded recent set.
- Full entity resolution across every project, employer, skill and person. The graph currently
  captures explicitly extracted career goals, target roles, technology preferences and style facts.
- Autonomous multi-step ReAct tool execution, external browser tools or dynamic third-party API
  routing. The assistant uses a deterministic allowlist of read-only internal data tools.
- Implicit dwell-time and scroll telemetry. Feedback ratings and explicit corrections are captured.
- A dedicated toxicity classifier or independent post-generation moderation service. Safety
  currently relies on input redaction, bounded tool permissions and model instructions.
- Application-level encryption of episodic memory fields. Use encrypted database volumes,
  TLS, strict database access controls and managed backups; credential secrets continue to use
  the existing credential vault.
- Automated fact verification UI. Extracted facts are labelled unverified and must not be
  treated as confirmed candidate declarations.
- GitHub-wide repository crawler/AST indexer. Uploaded Python source files are parsed locally.
- Hierarchical LLM summarization of entire old conversations. Current memory summaries are
  bounded extractive summaries.

These boundaries are intentionally explicit so operators do not mistake optional fallbacks or
initial integrations for completed infrastructure guarantees.
