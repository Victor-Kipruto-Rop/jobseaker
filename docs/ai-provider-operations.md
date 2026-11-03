# AI provider operations

## Supported runtime providers

JobSeeker supports OpenAI and Anthropic through server-side API credentials. The mock provider is available for local UI and contract testing. Provider keys must only exist in the API process environment and must never be sent to the browser, committed, or stored in frontend configuration.

Codex CLI is a local developer tool. It is not an application runtime inference endpoint and a Codex subscription is not an OpenAI API key. Runtime requests require an API key and are billed under the relevant provider's API account.

## Local configuration

Copy `.env.example` to `.env`, then set one or both providers:

- OpenAI: `OPENAI_ENABLED=true`, `OPENAI_API_KEY=...`, and `OPENAI_DEFAULT_MODEL=...`
- Anthropic: `ANTHROPIC_ENABLED=true`, `ANTHROPIC_API_KEY=...`, and `ANTHROPIC_DEFAULT_MODEL=...`

Set `AI_DEFAULT_PROVIDER` to `openai`, `anthropic`, or `mock`. Configure `AI_FALLBACK_PROVIDER` separately. Restart the API after changing environment variables because the provider registry is initialized once per process.

## API

- `GET /api/v1/ai/providers` reports configured adapters, their lightweight health result, selected default, model, and automation pause state.
- `POST /api/v1/ai/chat` accepts `message`, optional `provider`, optional `model`, optional `system_instruction`, and optional `max_tokens`.

The chat endpoint returns provider-reported token usage. Cost is not fabricated: it remains zero/unknown unless a provider adapter supplies a verified estimate. A hard budget, persistent conversation history, user-level quotas, and usage ledger are not yet implemented.

## Safety and current limitations

AI output is advisory. Candidate facts must be checked against source evidence. Email sending and application submission remain disabled; global automation remains paused by default. The current API foundation does not yet include production authentication or tenant isolation, so do not expose it publicly or use it with sensitive candidate data. Provider health checks are adapter-level checks, not a guarantee that a live API request will succeed.
