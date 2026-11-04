# Local development

## Prerequisites

- Python 3.12+
- Node.js 20+
- pnpm
- Docker Desktop with Compose

## Configure

PowerShell:

   Copy-Item .env.example .env
   notepad .env

Keep APP_ENV=local. Replace APP_SECRET_KEY with a random local value. AI providers default to mock mode. Add OpenAI or Anthropic API credentials only when needed.

## Start the stack

   docker compose -f infrastructure/compose/docker-compose.yml config
   docker compose -f infrastructure/compose/docker-compose.yml up --build

The stack includes a one-shot Alembic migration service, API, Next.js web, RQ worker, RQ scheduler, PostgreSQL, and Redis. The API, worker, and scheduler wait for the migration service to complete successfully before starting.

## Local URLs

- Web: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- AI workspace: http://localhost:3000/intelligence

## Database migrations

The Compose stack runs Alembic as an explicit prerequisite service before the API, worker, and scheduler start. Local non-Compose development and test environments also apply migrations at API startup. To apply them manually:

   alembic upgrade head

Production does not auto-migrate. Run migrations as a controlled release step.

## Verification

   python scripts/verify_local_security.py
   cd apps/web
   pnpm lint
   pnpm build

The cross-platform release-gate script validates Compose configuration, starts the local Compose stack, waits for API and web readiness, confirms required services are running, applies Alembic migrations, checks schema drift, runs pytest and Ruff, and runs frontend type-check/build commands. It leaves the stack running if a check fails so logs can be inspected. It does not call live AI, Gmail, or SMTP providers.

## Gmail

See gmail-integration.md. Keep OAuth client credentials in the local secrets directory. Never commit them.
