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
