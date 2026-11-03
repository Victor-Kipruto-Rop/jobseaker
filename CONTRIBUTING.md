# Contributing

- Keep domain logic out of HTTP handlers.
- Add tests for behavior and failure paths.
- Keep provider SDKs behind `packages/ai/providers`.
- Validate inputs and outputs at package boundaries.
- Never commit credentials, OAuth tokens, resumes, or inbox exports.
- External side effects require policy checks, approvals, idempotency, and audit records.
- Run `make test` and `make lint` before opening a pull request.
