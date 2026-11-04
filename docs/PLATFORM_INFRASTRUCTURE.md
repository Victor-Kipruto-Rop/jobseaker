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

OpenTelemetry API/SQLAlchemy tracing and Prometheus API/outbox/consumer metrics are implemented as opt-in instrumentation. Distributed trace propagation through Kafka and worker processes, a managed external schema-registry service, the full downstream job-processing consumer fleet, managed KMS integration, malware scanning, provider-wide circuit-breaker wiring and production SLOs remain incomplete. Google Calendar OAuth and candidate-triggered event sync are implemented but remain opt-in and require live OAuth verification. Do not describe the platform as production-ready until these gates have evidence.

## Additional master-spec implementation notes

### Durable candidate activity and preference drift
- Recommendation interactions persist exposure, action type, source, position, dwell duration, scroll depth and bounded feature snapshots.
- User activity is written to the transactional outbox in the same database transaction as the interaction.
- The event consumer uses the inbox deduplication helper and updates a bounded, per-candidate preference vector. The online recommendation query includes the strongest positive preference dimensions.
- Impression-only batches do not alter preference weights. View/click engagement is bounded by dwell and scroll signals; explicit saves and applications carry stronger positive weight, while dismissals and skips carry negative weight.
- This is a transparent online preference heuristic, not a trained deep preference model. Model promotion still requires offline evaluation and an operator-controlled registry action.

### Event consumer runtime
- Local Compose runs a dedicated consumer for user.activity and email.classified.
- Consumer offsets are committed only after the inbox transaction succeeds. Failures retry with capped exponential backoff, then publish to a topic-specific DLQ stream and commit the source offset to prevent poison-message loops.
- The outbox relay and consumer are at-least-once. The database inbox makes supported handlers idempotent. Monitor DLQ volume and provide an operator-reviewed replay process before production.

### Interview calendar integration
- Google Calendar is a separate, opt-in integration (CALENDAR_ENABLED=false by default) with its own OAuth redirect and only the Calendar Events scope.
- Credentials are encrypted with the dedicated credential KEK; OAuth state is hashed, short-lived and single-use.
- Candidate-owned interview records can be synced as calendar events, with duration and explicit timezone. Sync updates the existing event rather than creating a duplicate when the stored event ID is present.
- Gmail remains read-only and is not reused as a Calendar write authorization. Configure a Google OAuth client and the dedicated Calendar callback URL before enabling.

### Resume and generated document support
- Resume normalization accepts PDF, DOCX, Markdown and UTF-8 plain text.
- Cover-letter prompts can use the candidate's saved project history and sourced employer description from an owned opportunity. Unavailable company mission details are explicitly marked unavailable; unsupported claims are not fabricated.

### Explicitly excluded automation
- The platform does not spoof browser fingerprints, evade CAPTCHA, rotate residential proxies to circumvent rate limits, defeat bot protections or submit third-party applications unattended.
- Browser assistance is limited to candidate-authorized field mapping and review. Low-confidence fields and challenge pages pause for the candidate; the candidate completes final submission.
- These exclusions are deliberate safeguards. Respect each ATS's terms, published automation policy and rate limits.

### Release status
The implementation is committed to the existing Phase 4 branch and PR #9. It is NOT production-verified. The latest observed head has no associated PR workflow runs. Local Compose startup, database migration execution, full tests, static checks, frontend build, integration OAuth tests and real ATS browser review must still pass before merge or deployment.
## Credential key rotation operations

The credential vault now writes versioned AES-256-GCM envelopes with a key identifier. Configure a JSON keyring containing both the current and previous keys, then set the active key ID. Keep old keys available until rewrapping and backup-restore checks complete.

Example environment configuration (use generated 32-byte random keys; never commit real values):
- JOBSEEKER_CREDENTIAL_KEYRING: JSON map of key IDs to URL-safe-base64 keys
- JOBSEEKER_CREDENTIAL_ACTIVE_KEY_ID: key ID used for new ciphertext

Run an inventory first, then rotate:

```powershell
python -m apps.worker.rotate_credentials --dry-run
python -m apps.worker.rotate_credentials
```

The worker rewraps supported Gmail and Calendar ciphertext without changing OAuth token contents. Historical Gmail Fernet records are intentionally skipped by this worker and are upgraded by the next successful Gmail sync. Remove a retired key only after a fresh inventory shows no records depend on it and a recovery test confirms backups remain decryptable.

## Event schema validation

packages/events/schema_registry.py validates envelopes against the registered JSON Schema version and exposes backward-compatibility checks. Additive optional fields are allowed; required-field additions, property removal, type narrowing and enum narrowing are rejected. The current repository registers envelope v1 only. Deploying a managed registry service, subject naming strategy, compatibility policy and schema rollout pipeline remains a production infrastructure task.

## Operational metrics

The API exposes Prometheus metrics at /metrics. HTTP request totals and latency use route templates to avoid high-cardinality path labels. The outbox relay and event consumer expose independent scrape endpoints at localhost:9101/metrics and localhost:9102/metrics in local Compose; these export outbox delivery/backlog and consumer retry/DLQ metrics respectively. Outbox events carry W3C trace context from the API into Kafka; the consumer extracts that context and creates a processing span when OTLP instrumentation is installed. Configure the OTLP endpoint to enable API and SQLAlchemy tracing. The relay's broker-send span, scheduler spans and full service dependency map still need additional instrumentation. Protect metrics endpoints with network policy or an authenticated metrics gateway in production.