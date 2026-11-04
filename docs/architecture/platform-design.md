# Platform architecture and engineering contracts

## Product boundary

JobSeeker is a personal career operations system. It is not an autonomous job applicant, recruiter, employment eligibility assessor, or hiring predictor. Its purpose is to organize candidate-owned evidence and make job-search work measurable and repeatable.

The platform has four primary outcomes:
1. Discover and normalize suitable opportunities from supported sources.
2. Explain role-to-profile skill coverage with traceable evidence and limitations.
3. Manage candidate-controlled applications, interviews, recruiter relationships, and follow-ups.
4. Use AI to produce editable, evidence-grounded drafts and analysis.

## Bounded contexts

| Context | Owns | Does not own |
|---|---|---|
| Identity and access | Accounts, password hashes, sessions, CSRF, verification and recovery tokens | Career decisions |
| Candidate profile | Candidate summary, target roles, skills and evidence | Claims not supplied by the candidate |
| Opportunity intelligence | Source ingestion, normalized jobs, deduplication and fit explanations | Hiring probability |
| Application operations | Application lifecycle, events, interviews and reminders | External submission |
| AI intelligence | Provider routing, conversations, usage and generated drafts | Truth verification or external actions |
| Integrations | Explicitly authorized Gmail read-only and job-board API access | Sending mail or modifying third-party accounts |
| Automation | Scheduled discovery, reminders, queue execution and approval records | Bypassing user approval |

## Runtime topology

- Next.js is the presentation layer. It never receives provider secrets.
- FastAPI is the authenticated application boundary and owns validation and authorization.
- PostgreSQL is the durable system of record.
- Redis provides rate limiting and RQ queue transport.
- The worker executes bounded background tasks.
- The scheduler enqueues recurring discovery and interview reminder tasks.
- OpenAI and Anthropic are optional server-side inference providers. Mock mode supports offline development.

All stateful API queries must include the authenticated user's ID. A record identifier supplied by a client is never sufficient authorization.

## Core data flows

### Opportunity discovery

1. A candidate explicitly configures a Greenhouse or Lever board.
2. The connector validates the board identifier and calls only the fixed public provider API host.
3. Listing URLs are checked for absolute HTTP(S) form before persistence.
4. Records are normalized and deduplicated per candidate account.
5. Fit output reports matched and missing skill keywords and the scoring method.
6. Scheduled discovery runs only when global automation is explicitly unpaused.

Do not add arbitrary URL fetching as a job source. New providers require a dedicated connector, source terms review, rate limits, timeout policy, normalization tests, and deduplication behavior.

### AI generation

1. The API verifies the authenticated owner of the source resume or profile.
2. Candidate documents and job descriptions are treated as untrusted input, not instructions.
3. A configured provider is selected through the provider registry and fallback router.
4. Generation has bounded input and output sizes and a request timeout.
5. The generated result is stored as a user-owned draft with provider/model provenance.
6. Token usage is recorded. Hard token budgets reserve estimated capacity in a short transaction before provider calls, expire abandoned reservations, and reconcile completed requests to actual usage.
7. Monthly threshold notifications are emitted once per account/month. Monetary cost remains unknown until a verified, dated pricing catalog is configured.

Never turn an AI response into an application submission, email, or other external action without a separate explicit approval workflow. Never invent candidate facts to improve a generated document.

### Application lifecycle

The supported lifecycle is:

- draft -> ready
- ready -> draft, withdrawn, archived
- approved -> submitted, ready, withdrawn
- submitted -> screening, interview, assessment, rejected, withdrawn
- screening -> interview, assessment, rejected, withdrawn
- interview -> assessment, offer, rejected, withdrawn
- assessment -> interview, offer, rejected, withdrawn
- offer -> accepted, rejected, withdrawn
- accepted/rejected/withdrawn -> archived

A ready application cannot become approved through a normal application update. An application_submission approval must reference an application owned by the requester and in ready state. Approval records the candidate's authorization and moves the application to approved; the platform still does not submit it externally.

Every lifecycle change and material detail update must produce an application event.

### Gmail

- OAuth is available only to verified accounts.
- Requested scope is gmail.readonly.
- Mailbox sync is user-scoped and rate-limited.
- Disconnect removes stored synchronized messages and account credentials.
- Sending, deleting, labeling, and modifying messages are outside the integration contract.

## Security invariants

- Passwords are hashed with the configured password hashing library; raw passwords are never persisted.
- Session cookies are HttpOnly, and unsafe browser requests require CSRF token and session binding.
- Session tokens and account recovery tokens are stored as hashes.
- Password reset revokes existing sessions.
- Login and recovery have IP and account-level throttles.
- External integrations require a verified account.
- API keys and OAuth credentials are server-side secrets.
- User-facing record access is owner-scoped.
- Approval decisions are one-time, user-scoped, and audited.
- Production requires PostgreSQL, HTTPS origins, a non-default strong application secret, and an already-migrated schema.
- Local resume storage is not a production storage design.

## Reliability and operational contracts

- Redis failure causes rate-limited operations to fail closed outside local/test environments.
- External HTTP calls have explicit timeouts and bounded result sizes.
- Background jobs must be idempotent and safe to retry.
- Scheduled work respects the global automation pause.
- Repeated reminders must not create duplicate notifications.
- Database schema changes are explicit Alembic revisions, not runtime metadata mutation.
- Logs must avoid passwords, bearer tokens, OAuth codes, resume contents, and full email bodies.
- Health checks must distinguish process liveness from dependency readiness.

## Quality gates

Before a release candidate can be marked ready:

1. Run python scripts/verify_local_security.py from a clean local checkout with Docker, Python dependencies, pnpm dependencies, and a local .env configured.
2. Run frontend lint, typecheck, and production build.
3. Validate Compose configuration and start every service.
4. Apply Alembic migrations against a clean PostgreSQL database and an upgrade fixture.
5. Exercise account registration, login, CSRF, recovery, session revocation, and cross-user access denial.
6. Exercise opportunity ingestion, duplicate handling, URL validation, and job fit explanations.
7. Exercise AI provider mock mode, timeout, fallback, usage recording, budget enforcement, and draft ownership.
8. Exercise approval-gated application transitions and retry-safe scheduled jobs.
9. Verify Gmail read-only scope, OAuth state handling, sync isolation, and disconnect behavior.
10. Run backup/restore and data deletion/export drills before production use.

## Deliberate non-goals for this release

- Automatically applying to jobs.
- Sending recruiter emails.
- Claiming an ATS score is a hiring prediction.
- Claiming a skill match proves proficiency.
- Estimating provider costs from unverified price assumptions.
- Storing production CVs on a container filesystem.
- Treating a configured API key as proof that an upstream provider is healthy.
