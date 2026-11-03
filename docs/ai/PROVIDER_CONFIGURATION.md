# AI provider configuration

Set `OPENAI_ENABLED=true`, `OPENAI_API_KEY`, and `OPENAI_DEFAULT_MODEL` to enable OpenAI Responses API. Set `ANTHROPIC_ENABLED=true`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_DEFAULT_MODEL` to enable Anthropic Messages API. Restart API and workers after changing environment values.

Keys remain server-side. Never send them to the browser, log them, or commit them. Keep model identifiers configurable. Mock mode supports offline development.

Codex CLI is a developer agent for editing and testing this repository. It is not a general runtime API credential. JobSeeker runtime AI uses OpenAI API or Anthropic API credentials.
