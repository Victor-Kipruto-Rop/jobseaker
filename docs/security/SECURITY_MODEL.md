# Security model

- Keep secrets in private environment files or a production secret manager.
- Never commit Gmail tokens, OAuth client secrets, API keys, CVs, or inbox exports.
- Gmail remains read-only unless a separate sending capability is explicitly implemented and approved.
- Email sending and application submission are disabled by default.
- Treat AI output as untrusted. Validate structured output and preserve evidence for candidate facts.
- External side effects require authorization, approval, idempotency, and audit records.
- Never log email bodies, CV content, API keys, or OAuth refresh tokens.
- Bind local services to localhost.

- Authenticated browser mutations validate the configured Origin or Referer origin, reject cross-site Fetch Metadata, and require a double-submit CSRF token bound to the server-side session hash.
- The CSRF bootstrap endpoint returns the actual cookie token and preserves a valid token across tabs; it only repairs a missing or invalid token.
- Session identifiers and account recovery tokens are stored as hashes. Password reset revokes all active sessions.
- Rate limiting uses Redis in production and fails closed when Redis is unavailable.
- Candidate opportunity source URLs have a per-user partial unique index. Scheduled imports use savepoints so a concurrent duplicate does not discard the rest of a batch.
- Production resume upload remains disabled until private object storage, encryption, retention and deletion workflows are configured.
