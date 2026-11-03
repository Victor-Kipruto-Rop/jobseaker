# AI provider operations and usage

## Runtime providers

JobSeeker supports OpenAI and Anthropic through server-side API credentials. The mock provider is available for local development. Provider keys must only exist in the API process environment and must never be sent to the browser, committed, or stored in frontend configuration.

Codex CLI is a local developer tool. It is not an application runtime inference endpoint and a Codex subscription is not an OpenAI API key. Runtime inference requires an OpenAI API key or Anthropic API key and is billed by the respective provider.

## Configuration

- OpenAI: OPENAI_ENABLED=true, OPENAI_API_KEY, OPENAI_DEFAULT_MODEL
- Anthropic: ANTHROPIC_ENABLED=true, ANTHROPIC_API_KEY, ANTHROPIC_DEFAULT_MODEL
- AI_DEFAULT_PROVIDER selects the preferred provider.
- AI_FALLBACK_PROVIDER selects the fallback provider.

Restart the API after changing environment variables because the provider registry is initialized once per process.

## API

- GET /api/v1/ai/providers reports adapter credential checks and configured models.
- POST /api/v1/ai/chat generates an assistant response and persists conversation messages.
- GET /api/v1/ai/conversations lists the authenticated user's conversations.
- GET /api/v1/ai/conversations/{id}/messages returns only messages owned by the current user.
- GET /api/v1/ai/usage returns per-user persisted token totals grouped by provider and model.
- GET/PUT /api/v1/ai/budget reads and updates per-user monthly token limits.
- POST /api/v1/career-tools/cv-tailor creates a CV draft from an uploaded CV and job description.
- POST /api/v1/career-tools/cover-letter creates a cover-letter draft.
- POST /api/v1/career-tools/interview-prep creates an interview preparation pack.
- POST /api/v1/career-tools/skills-roadmap creates a 30/60/90-day learning plan.

Generated career artifacts are persisted as drafts and can be edited by their owner. They are never automatically sent or submitted.

## Budget accounting

The current hard budget is token-based. It reserves an approximate input token count plus the configured maximum output tokens before sending a request. It is a conservative estimate, not an exact tokenizer result.

Monetary cost is intentionally null until a verified, versioned provider pricing catalog is populated and applied. Do not interpret missing cost as zero cost. No live price is fabricated.

## Safety and readiness

AI output is advisory. Candidate facts must be checked against source evidence. Job descriptions and uploaded CV text are treated as untrusted prompt content. Email sending and application submission remain disabled; global automation remains paused by default.

Provider health checks are adapter-level checks, not a guarantee that a live API request will succeed. Live provider calls, Docker startup, migrations, and full integration tests must be verified locally before relying on this system.
