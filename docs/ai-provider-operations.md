# AI provider operations and usage

## Runtime providers

JobSeeker supports OpenAI and Anthropic through server-side API credentials. The mock provider is available for local development. Provider keys must only exist in the API process environment and must never be sent to the browser, committed, or stored in frontend configuration.

Codex CLI is a local developer tool. It is not an application runtime inference endpoint and a Codex subscription is not an OpenAI API key. Runtime inference requires an OpenAI API key or Anthropic API key and is billed by the respective provider.

## Configuration

Copy `.env.example` to `.env`, then configure:

- OpenAI: `OPENAI_ENABLED=true`, `OPENAI_API_KEY=...`, and `OPENAI_DEFAULT_MODEL=...`
- Anthropic: `ANTHROPIC_ENABLED=true`, `ANTHROPIC_API_KEY=...`, and `ANTHROPIC_DEFAULT_MODEL=...`
- `AI_DEFAULT_PROVIDER` selects the preferred provider.
- `AI_FALLBACK_PROVIDER` selects the fallback provider.

Restart the API after changing environment variables because the provider registry is initialized once per process.

## API

- `GET /api/v1/ai/providers` reports configured adapters, their adapter health result, selected default, model, and automation pause state.
- `POST /api/v1/ai/chat` accepts `message`, optional `provider`, optional `model`, optional `system_instruction`, and optional `max_tokens`.
- `GET /api/v1/ai/usage` returns installation-wide persisted input/output token totals grouped by provider and model.

The usage ledger persists provider, model, token counts, and request count. Monetary cost is intentionally null until a verified, versioned provider pricing catalog is implemented. Do not interpret missing cost as zero cost. The current endpoint is installation-wide because authentication and tenant isolation are not implemented.

## Safety and production readiness

AI output is advisory. Candidate facts must be checked against source evidence. Email sending and application submission remain disabled; global automation remains paused by default. The API foundation does not yet include production authentication, authorization, tenant isolation, request-level user quotas, or an audited pricing/budget enforcement system. Do not expose it publicly or use it with sensitive candidate data.

Provider health checks are adapter-level checks, not a guarantee that a live API request will succeed. Live provider calls, Docker startup, migrations, and full integration tests must be verified in the local environment before relying on this system.
