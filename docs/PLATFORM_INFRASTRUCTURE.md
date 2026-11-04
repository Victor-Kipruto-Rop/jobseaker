# JobSeeker platform infrastructure

## Local service topology

The local Compose stack includes PostgreSQL 16 with pgvector and pg_trgm, Redis, Redpanda (Kafka-compatible), MinIO (private S3-compatible storage), API, web, worker, scheduler, event relay and migration services.

Start from `infrastructure/compose`:

```powershell
docker compose up --build
docker compose ps
```

| Service | Local endpoint |
| --- | --- |
| Web | http://localhost:3000 |
| API | http://localhost:8000 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |
| Redpanda Kafka | localhost:19092 |
| MinIO API | http://localhost:9000 |
| MinIO Console | http://localhost:9001 |

Local MinIO credentials are development-only. Never reuse them outside a local machine. Compose binds service ports to loopback. Email sending and external discovery remain disabled; global submission automation remains paused.

## Event contracts and delivery

Supported topics: `job.raw`, `job.enriched`, `user.activity`, `application.dispatched`, `application.status_changed` and `email.classified`. The versioned JSON Schema contract is `schemas/events/envelope.v1.schema.json`; the Pydantic envelope validator is `packages/events/contracts.py`.

Application lifecycle changes and recommendation interactions now write to `event_outbox` in the same SQL transaction as the domain mutation. The dedicated `event-relay` Compose service publishes stable event IDs to Redpanda. Retries use capped exponential backoff; exhausted records are retained with `dead_letter` status and are also sent to the topic's `.dlq` stream when the broker accepts it.

`packages/events/inbox.py` provides per-consumer/event deduplication. Consumer handlers must perform database work in the same transaction and put external side effects back through the outbox. Delivery is **at least once**, not exactly once: a crash after broker acknowledgement and before the outbox status commit can replay an event. Consumers must use the inbox helper.

The outbox relay reclaims stale processing leases after five minutes. Monitor pending age, retry count, dead-letter count and relay health. Kafka topic provisioning, retention, ACLs, replication and schema-registry enforcement still require production configuration.

## Recommendation intelligence

The online path combines text/keyword similarity, semantic embeddings where the optional Sentence Transformers model is available, pgvector where installed, collaborative signals, a curated skill-equivalence graph, job/company graph signals and channel-level Thompson/UCB exploration. The feed reserves up to 18% of slots for recently published opportunities without prior candidate interaction when such candidates exist.

Recent positive candidate interactions contribute job language to the query representation. The skill graph returns evidence and distance rather than treating related tools as identical proficiency.

Train a candidate LightGBM ranker from explicit save/apply/interview/offer versus dismiss/skip feature snapshots:

```powershell
python -m apps.worker.train_ranker --min-rows 100
```

Training uses a chronological holdout and records AUC/NDCG metrics, feature schema version and artifact checksum. New artifacts remain `candidate`; they are not automatically served. Promote a model only after reviewing metrics:

```powershell
python -m apps.worker.train_ranker --promote-model-id <ID> --minimum-auc 0.60
```

The API serves only a registered active artifact after its SHA-256 integrity check. Without one, it uses the transparent hybrid ranker. Model output is relevance, not hiring probability. Real-world quality, fairness and drift still require monitoring and sufficient representative labels.

## Browser-assisted application workflow

Install `pip install -e ".[browser]"` and the matching Playwright browser binaries only for candidate-approved workflows. `packages/automation/form_assist.py` validates structured field mappings against candidate-provided facts, enforces published select options, holds low-confidence required fields for review, pauses on CAPTCHA/challenge detection and never clicks submit. Candidate approval is required before filling; the candidate completes the final submission manually.

Failure evidence is stored as private objects. DOM snapshots redact scripts and form values; screenshots mask form-control text. Review the redaction behavior in the target ATS before enabling evidence capture with real candidate data.

Do not evade bot controls, rotate proxies to defeat site limits, solve CAPTCHAs to bypass controls, manipulate hidden fields or submit without explicit candidate authorization. Respect site terms, rate limits and automation rules.

## Email and application state

Gmail OAuth remains read-only. The synchronizer reads only the candidate-authorized mailbox and extracts bounded plain-text content in memory; it stores only message snippets and structured evidence, not full message bodies. The email intelligence parser can suggest an application, lifecycle status and interview-time text. Ambiguous matches remain unlinked. Email suggestions never mutate application state; the candidate must confirm changes.

New Gmail OAuth credentials use AES-GCM with the dedicated `JOBSEEKER_CREDENTIAL_KEK` (URL-safe base64 encoding of 32 random bytes). Existing Fernet ciphertext is read for compatibility and re-encrypted on the next successful sync. Configure the key in a secret manager, back it up securely and plan key-versioned rewrapping before production key rotation.

Application lifecycle transitions are validated by the API. Submission recording requires the application to have passed the approval workflow and is protected by a database-enforced idempotency reservation per candidate and normalized job key. This records a candidate-confirmed submission; it is not an unattended ATS submission engine.

## Security and operational primitives

- `packages/security/credential_vault.py`: AES-256-GCM authenticated encryption with purpose-bound associated data.
- `packages/automation/idempotency.py`: database-enforced dispatch reservations and payload binding.
- `packages/ops/circuit_breaker.py`: process-local circuit breaker primitive for provider adapters.
- Existing Redis rate limiting fails closed in non-development environments when Redis is unavailable.
- Private object storage uses opaque keys and authenticated owner-scoped API access.

The circuit breaker is currently a reusable primitive, not yet attached to every outbound provider. The credential vault does not itself perform managed KMS key rotation. Malware scanning, full content-type validation, storage lifecycle enforcement and deletion/retention workflows remain production gates.

## Verification and release gates

Run from the repository root:

```powershell
python -m pytest -q tests/unit/test_reliability_primitives.py tests/unit/test_form_assist.py tests/unit/test_email_intelligence.py
python -m pytest -q
ruff check .
mypy apps packages
alembic upgrade head
pnpm --dir apps/web lint
pnpm --dir apps/web build
docker compose -f infrastructure/compose/docker-compose.yml config
docker compose -f infrastructure/compose/docker-compose.yml up --build
```

Also verify migration upgrades from the Phase 3 revision and a clean database, relay crash/replay behavior, DLQ recovery, active model promotion and rollback, authenticated Gmail sync, ATS form approval, storage redaction, cross-account isolation, load behavior, restore drills and accessibility.

OpenTelemetry distributed traces, production schema-registry compatibility enforcement, full downstream Kafka consumer fleet, managed secret/KMS rotation, calendar OAuth/write sync, malware scanning, provider-wide circuit-breaker wiring and production SLOs remain incomplete. Do not describe the platform as production-ready until these gates have evidence.
