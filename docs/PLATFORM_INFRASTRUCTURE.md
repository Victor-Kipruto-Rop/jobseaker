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
## Six-area acceptance criteria: latest implementation details

### 1. Reliable event backbone
- Event envelopes accept schema version 1 only and validate UUID event IDs, allowed event types, and required user/application/email references for the corresponding topics. Unsupported versions and malformed payloads are rejected into the consumer DLQ path.
- Outbox delivery remains at-least-once. If a DLQ publish fails, the source outbox record remains retryable; it is never marked terminal until the broker acknowledges the DLQ record.
- Gmail import, last-sync state and stable-ID classification outbox records now share one database transaction. A replay of the same Gmail provider message does not create another message/outbox event.
- The inbox remains scoped by consumer and event ID. Kafka consumer transactions are traced when OTLP is enabled.

### 2. Recommendation intelligence
- Online preference drift now reweights the actual ranking feature values rather than adding feature names to the semantic candidate query.
- Offline ranking uses LightGBM LambdaRank with graded feedback labels and candidate-level query groups. Validation holds out entire candidates to reduce user leakage and reports AUC plus NDCG@10.
- Ranker artifacts remain unelevated candidates until both ranking-quality promotion thresholds pass. The API serves only integrity-checked active LambdaRank artifacts and falls back to transparent hybrid ranking when no supported model is active.
- This is a supervised ranker, not a continuously retrained model. Training requires enough real candidate/job interactions with feature snapshots and both positive and negative relevance labels.

### 3. Application automation and submission safety
- ATS mapping validates every proposed field against the inspected form and candidate-supplied facts. Candidate approval is required before filling; challenge detection pauses the workflow; submission is never performed by the browser helper.
- Browser failure evidence is stored privately and DOM redaction now removes script bodies, input values and textarea contents before persistence.
- Candidate approval and submission confirmation are separate API actions. A candidate must move a ready application through explicit approval, then confirm that they personally submitted it on the external ATS. Idempotency keys prevent duplicate confirmation records.
- A locally confirmed submission is not evidence that an external ATS accepted or processed the application. External receipt links are recorded as candidate-supplied evidence only.

### 4. Application lifecycle and email intelligence
- Application lifecycle transitions are centralized in a shared finite-state machine. Email classification only proposes a next state; a candidate confirmation endpoint requires high-confidence intent, an unambiguous application match and recorded email evidence before applying a valid transition.
- The confirmation action is idempotent when the application already has the proposed state and writes an audit event plus an outbox event in the same transaction.
- Interview calendar sync uses a deterministic Google event ID so retries update an existing event rather than creating duplicates after a lost local commit.

### 5. Resume intelligence
- Tailored CV outputs and cover letters are saved as separate draft artifacts. CV tailoring can be linked to an owned opportunity; cover letters can use saved candidate projects and employer details sourced from that opportunity.
- The CV tailoring route validates opportunity ownership before linking the generated version. Generated text remains a draft and does not overwrite the uploaded source resume.

### 6. Security, operations and observability
- Credential ciphertext supports a versioned AES-GCM keyring and active key IDs. Gmail and Calendar credentials are rewrapped with the active key when they are next used.
- The API exposes FastAPI/SQLAlchemy traces when OTLP is configured. Event consumers emit Kafka processing spans, and worker processes can export OTLP traces/metrics. Prometheus counters and backlog gauges remain available for operational scraping.
- Redis sliding-window limits, provider circuit breakers, bounded retry loops and dead-letter counters provide operational protection. Production still requires dashboards, alert thresholds, credential-rotation runbooks and a tested replay operator workflow.

### Verification caveat
All changes above are source-level implementation. They have not been executed against a local Docker environment or a live Google/ATS account in this session. CI, migration execution, unit tests, frontend builds and integration smoke tests must pass on the latest branch head before PR #9 is merged.
## Phase 4 master specification: operational contract and release criteria

This section supersedes earlier draft notes in this document that describe event delivery as best-effort or describe Gmail credentials as single-key Fernet-only storage.

### Event backbone
- Domain writes enqueue versioned events in the same SQL transaction using the transactional outbox.
- The relay uses stable event IDs, per-candidate partition keys, bounded exponential retries, stale-lease recovery and DLQ delivery. If DLQ publication itself fails, the original outbox record remains retryable and is not marked terminal.
- Consumers validate the registered JSON Schema and Pydantic topic contract, then execute database-only handlers with per-consumer inbox deduplication. Kafka offset commit follows successful processing or acknowledged DLQ delivery.
- Delivery semantics are at-least-once. Every handler must be replay-safe; external side effects must be represented by an outbox event.
- packages/events/schema_registry.py is the repository-local schema registry and compatibility checker. It is not a hosted registry; production still needs managed registry deployment, topic ACLs, retention, replication and compatibility policy enforcement.

### Recommendation intelligence
- Retrieval combines lexical/TF-IDF, semantic embeddings/pgvector when configured, collaborative signals, skill graph evidence, role/location/salary/recency features and exploration.
- Candidate interaction updates are online preference heuristics, not a trained personalization model.
- The optional LightGBM LambdaRank trainer groups candidate/job interactions and uses candidate-level holdout evaluation. A trained artifact remains a candidate until it passes AUC and NDCG promotion gates. Active artifacts are checksum-verified before loading.
- Do not describe the ranker as trained or production-effective until the dataset is sufficiently large and representative and offline plus online evaluation, cohort fairness, drift and rollback are reviewed.

### Candidate-controlled application automation and lifecycle
- Structured form mappings may only copy candidate-provided facts and published select options. Low-confidence or unresolved required fields remain for human completion.
- Candidate approval is required before browser field filling. CAPTCHA/challenge pages pause the workflow. The browser helper does not submit forms; the candidate submits on the ATS website.
- Failure screenshots and DOM evidence are private. DOM evidence redacts scripts, input values and textarea contents; screenshots mask form-control text. Validate redaction on target ATS pages before storing real candidate evidence.
- Application status transitions use packages/applications/fsm.py. The ready-to-approved action and approved-to-submitted confirmation are explicit candidate actions. The latter records candidate confirmation, not verified acceptance by an external ATS.
- Gmail remains read-only. Intent extraction links an email only when the application match is unambiguous; it records phrase evidence and proposed status/interview-time text. State changes and calendar creation require candidate review/confirmation. Calendar OAuth is separately opted-in and uses candidate-owned interview records.

### Resume intelligence
- PDF, DOCX, Markdown and UTF-8 plain text extraction is bounded by upload size, page/entry count and extracted-text limits.
- Tailored CVs and cover letters are saved as drafts. Generation is grounded in the candidate's own resume, saved projects and source-published employer/opportunity data; missing facts must be marked for candidate input rather than invented.
- Private source documents and generated artifacts remain owner-scoped. Production still needs malware scanning, retention/deletion controls and managed private object storage.

### Enterprise security and operations
- OAuth credentials use versioned AES-256-GCM envelopes with key IDs and an active/previous keyring. Use python -m apps.worker.rotate_credentials --dry-run before rotation, then run without --dry-run after validating backup/restore and retaining old keys until all records are rewrapped.
- API, SQLAlchemy, relay and consumer telemetry expose request/event metrics and optional OTLP traces. Relay/consumer scrape endpoints are separate from API metrics.
- Redis sliding-window rate limits and provider circuit-breaker primitives are present. Production must verify coverage for each external provider, configure alerting/SLOs, restrict metrics endpoints to trusted networks and provision managed KMS/secret storage.
- Local Compose credentials and local MinIO are development-only.

### Release verification
Source commits and unit tests are not evidence of a passing runtime. Before merging, run the full test suite, Ruff, mypy, Alembic upgrade from both the current release head and a clean database, frontend lint/build, Compose validation/build/startup, and authenticated end-to-end tests for outbox relay/replay/DLQ, recommendation tracking/ranking fallback, browser approval/recovery, Gmail review, Calendar sync, resume upload/extraction and credential rotation. Inspect actual CI logs on the final PR head. Keep PR #9 draft and unmerged until those checks pass.