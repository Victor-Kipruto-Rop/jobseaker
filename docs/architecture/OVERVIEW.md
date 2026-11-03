# Architecture overview

JobSeeker is a modular monolith with separate API, worker, scheduler, and web processes. Domain packages own business rules. Integration packages own external systems. AI provider adapters isolate vendor SDKs. PostgreSQL is the system of record and Redis transports background work.

Jobs should be idempotent, bounded in retries, user-scoped, observable, and safe to replay. Extract microservices only when scaling requirements justify it.
