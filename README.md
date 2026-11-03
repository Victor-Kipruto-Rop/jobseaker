# JobSeeker Intelligence

JobSeeker is a local-first AI-assisted career operations platform. It combines opportunity discovery, candidate evidence, CV analysis, application tracking, recruiter records, interview planning, read-only Gmail intelligence, and AI-generated career drafts.

## Product principles

- User-owned career records are scoped by authenticated account ID.
- OpenAI and Anthropic are runtime providers behind a common adapter contract. Mock mode supports local development.
- Codex CLI is a local development agent, not an application runtime inference API.
- AI-generated CVs, cover letters, interview packs, and roadmaps are drafts. They are not automatically sent or submitted.
- Job matching exposes a transparent, versioned keyword coverage baseline with matched/missing skill evidence, not a hiring probability.
- Application submission requires a user-owned approval record; approval does not itself submit anything externally.
- Saved-search discovery respects the global automation pause and interview reminders are designed to be idempotent.
- Gmail access is read-only and uses the gmail.readonly scope.
- Email sending and application submission remain disabled.
- Resume uploads use persistent local storage in development. Production uploads remain disabled until private object storage is configured.

## Current application workspaces

- Dashboard: /dashboard
- Opportunity Radar: /discovery
- Saved opportunities: /opportunities
- Candidate profile and skills: /profile
- CV upload and keyword analysis: /cv-studio
- AI career drafts: /career-studio
- Applications: /applications
- Companies: /companies
- Recruiter CRM: /recruiters
- Gmail inbox intelligence: /inbox
- Interviews: /interviews
- Career analytics: /analytics
- Approval center: /approvals
- AI settings and token budget: /settings
- API documentation: /docs

## Architecture

See [Platform architecture and engineering contracts](docs/architecture/platform-design.md) for bounded contexts, runtime topology, data flows, security invariants, lifecycle rules, reliability expectations, and release quality gates.

- FastAPI API under apps/api
- Next.js web application under apps/web
- PostgreSQL system of record
- Redis rate limiting and RQ queues
- RQ worker and RQ Scheduler services
- SQLAlchemy models and Alembic migrations
- Provider adapters for OpenAI, Anthropic, and mock mode
- Integration packages for Greenhouse, Lever, Gmail, and SMTP

## Local setup

1. Install Docker Desktop, Python 3.12+, Node.js 20+, pnpm 9+, and Git.
2. Copy .env.example to .env.
3. Keep APP_ENV=local. Replace APP_SECRET_KEY with a random local secret of at least 32 characters.
4. For local Python verification, create a virtual environment and install the development dependencies: `python -m venv .venv`, activate it (PowerShell: `.venv\\Scripts\\Activate.ps1`), then run `python -m pip install -e ".[dev]"`.
5. For local web verification, run `pnpm install` from the repository root.
6. Run:

   docker compose -f infrastructure/compose/docker-compose.yml config
   docker compose -f infrastructure/compose/docker-compose.yml up --build

7. Open http://localhost:3000 and register an account.

The API applies Alembic migrations automatically in local, development, and test environments. Production does not auto-migrate.

## Verification

   python scripts/verification/verify_local.py
   cd apps/web
   pnpm lint
   pnpm build

The local verification script runs Python compile checks, pytest, and Ruff. It does not start Docker or perform live OpenAI, Anthropic, Gmail, or SMTP calls.

## AI configuration

Configure OpenAI or Anthropic credentials only in the private API environment. Never expose provider credentials to the browser or commit them. See docs/ai-provider-operations.md.

## Integrations

- Job discovery: docs/job-discovery.md
- Gmail OAuth: docs/gmail-integration.md
- Security and data protection: docs/security-and-data-protection.md
- Local development: docs/local-development.md

## Current release status

This is an actively developed feature branch, not a production-ready release. Authentication, user-scoped workflows, persistent AI conversations and drafts, provider routing, job-board connectors, Gmail read-only integration, local CV processing, approval-gated application tracking, and recurring discovery have implementation code. However, this turn has not run Python tests, frontend lint/build, Docker Compose, database migrations, or live third-party integrations. Production object storage, backup/restore drills, full account deletion/export, richer job-source coverage, production OAuth review, and comprehensive end-to-end security verification remain outstanding. Do not merge or deploy based on code presence alone.
