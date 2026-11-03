# Architecture overview

JobSeeker is a modular monolith with separate API, worker, scheduler, and web processes. Domain packages own business rules. Integration packages own external systems. AI provider adapters isolate vendor SDKs. PostgreSQL is the system of record and Redis transports background work.

Jobs should be idempotent, bounded in retries, user-scoped, observable, and safe to replay. Extract microservices only when scaling requirements justify it.

## Operational observability

- Every API request receives a validated or server-generated correlation identifier in X-Request-ID.
- Structured request logs record method, path, status code and duration without logging query strings, request bodies, CV text, email content or credentials.
- The correlation identifier is returned to clients and exposed through CORS for support diagnostics.
- Readiness checks validate PostgreSQL and Redis; liveness remains independent of downstream dependencies.
