# JobSeeker platform infrastructure

## Local service topology

The local Compose stack includes PostgreSQL 16 with pgvector and pg_trgm, Redis, Redpanda (Kafka-compatible), MinIO (private S3-compatible storage), API, web, worker, scheduler and migration services.

Start from infrastructure/compose:

    docker compose up --build

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

## Event contracts

Supported topic names: job.raw, job.enriched, user.activity, application.dispatched, application.status_changed and email.classified.

Events use a versioned envelope containing event_id, event_type, schema_version, occurred_at, producer and data. packages/events/kafka.py validates topic names and publishes asynchronously when KAFKA_ENABLED=true. Delivery failure is logged and reported; it must not be interpreted as successful delivery.

Consumers must be idempotent on event_id. Production should add a transactional outbox before Kafka delivery becomes a hard dependency for user-facing writes. The current publisher is an integration adapter, not exactly-once delivery.

## Object storage

packages/storage/objects.py stores private objects in S3-compatible storage or local filesystem. It returns opaque object keys, never public URLs. Resume and document access must remain behind authenticated API routes and ownership checks. Add malware scanning, content-type verification, encryption, retention and deletion policies before production.

## Machine learning extras

Install optional packages with pip install -e ".[ml]". The core recommender works without optional dependencies. Sentence Transformers and LightGBM must report availability and training state; do not claim a model is trained without labelled data. Use versioned model artifacts and offline evaluation before promotion.

## Browser-assisted applications

Install pip install -e ".[browser]" and matching Playwright browser binaries only for approved workflows. Browser assistance may map candidate-approved profile fields into supported application forms and pause for candidate review. Do not evade bot controls, rotate proxies to defeat site limits, solve CAPTCHAs to bypass controls, or submit without explicit candidate authorization. Respect robots, terms, rate limits and site-specific automation rules.

## Email and application state

Gmail OAuth is the initial supported mailbox integration. Parsing must be restricted to the user-authorized mailbox, verify webhook/OAuth ownership, store minimal parsed evidence and treat LLM classification as a suggestion with confidence thresholds. Email alone must not silently mark an application as an offer or rejection; state transitions need evidence and an audit trail.

## Production gates

1. Use managed PostgreSQL with pgvector, managed Redis and managed Kafka/Redpanda.
2. Provision private S3 with encryption, lifecycle rules, least-privilege IAM and backups.
3. Add transactional outbox/inbox tables and replay-safe consumers.
4. Add schema registry or compatibility tests for event envelopes.
5. Add malware scanning and retention/deletion workflows for uploaded CVs.
6. Add model registry, offline ranking metrics, drift monitoring and fairness review.
7. Add OAuth token encryption/rotation, email webhook verification and consent revocation.
8. Add rate limiting, audit logging, tenant isolation tests, restore drills and service SLOs.
9. Keep application dispatch human-approved and idempotent.