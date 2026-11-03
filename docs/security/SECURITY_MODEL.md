# Security model

- Keep secrets in private environment files or a production secret manager.
- Never commit Gmail tokens, OAuth client secrets, API keys, CVs, or inbox exports.
- Gmail remains read-only unless a separate sending capability is explicitly implemented and approved.
- Email sending and application submission are disabled by default.
- Treat AI output as untrusted. Validate structured output and preserve evidence for candidate facts.
- External side effects require authorization, approval, idempotency, and audit records.
- Never log email bodies, CV content, API keys, or OAuth refresh tokens.
- Bind local services to localhost.
