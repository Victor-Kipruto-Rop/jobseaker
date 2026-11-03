# JobSeeker Intelligence Platform

Local-first AI-assisted career operations for discovering jobs, evaluating fit, preparing applications, managing outreach, and monitoring recruiter conversations.

## Principles
- OpenAI and Anthropic are runtime AI providers behind a common adapter contract.
- Codex is a local development agent, not a runtime inference API. Use OpenAI API credentials for application intelligence.
- PostgreSQL is the system of record; Redis handles background work.
- AI-generated content is a draft until reviewed. Candidate facts require evidence.
- Gmail is read-only by default. Email sending and application submission are disabled by default.
- Local development is isolated from production endpoints and credentials.

## Architecture
The agreed modular structure lives under `apps/`, `packages/`, `infrastructure/`, `config/`, `docs/`, `scripts/`, and `tests/`. The previous foundation remains alongside it during migration to preserve existing outreach and Gmail import functionality.

## Quick start
1. Install Docker Desktop, Python 3.12+, Node.js 20+, and pnpm 9+.
2. Copy `.env.example` to `.env`.
3. Set a strong local `APP_SECRET_KEY`. Provider keys are optional for mock mode.
4. Run `docker compose -f infrastructure/compose/docker-compose.yml up --build`.
5. Open http://localhost:3000 and http://localhost:8000/docs.

## Commands
- `make test`: Python tests.
- `make lint`: Ruff and web TypeScript checks.
- `make compose-up`: start local containers.
- `make compose-down`: stop containers without deleting volumes.

## AI configuration
Configure `OPENAI_ENABLED`, `OPENAI_API_KEY`, `ANTHROPIC_ENABLED`, and `ANTHROPIC_API_KEY` in the private local `.env`. Never commit credentials. Codex CLI is intended for repository development and maintenance, not as a substitute for API credentials.

## Safety
External side effects require explicit policy checks and approval. The system does not send emails or submit applications automatically. See `docs/security/SECURITY_MODEL.md`.

## Current status
This branch adds the modular platform foundation and initial working slices. Live OAuth integrations, verified job-source connectors, production secret management, comprehensive migration of legacy records, and end-to-end runtime verification remain follow-up work. Do not treat the system as production-ready until the documented local test and security gates pass.
