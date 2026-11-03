# Security and data protection

## Current controls

- Passwords are hashed with Argon2 through pwdlib.
- Session cookies are HttpOnly, SameSite=Lax, and Secure in production.
- Session tokens are random opaque values. Only SHA-256 digests are stored.
- Sessions expire after seven days and can be revoked at logout.
- CSRF tokens are double-submitted and bound to the stored session digest.
- Login and password recovery have IP and account-level rate limits; job discovery and Gmail synchronization are rate-limited.
- Account recovery tokens are random, short-lived, single-use values stored only as hashes. Production never returns recovery tokens in API responses.
- Gmail OAuth requires a verified account.
- User-owned profile, skills, CV metadata, applications, recruiters, companies, interviews, AI conversations, messages, usage, notifications, and saved searches are filtered by authenticated user ID.
- Gmail OAuth credentials are encrypted at rest using Fernet with a key derived from APP_SECRET_KEY.
- Gmail requests use only the gmail.readonly scope.
- Email sending and external application submission remain disabled. Application submission approval is explicit, user-scoped, one-time, and audited; approval does not submit externally.
- Local CV uploads are stored under a user-specific directory and excluded from Git.

## Local-only boundaries

The current local filesystem CV storage adapter is not a production object-storage implementation. Resume uploads are therefore disabled when APP_ENV=production.

Production deployment must configure durable private object storage, backup and restore, key rotation, email delivery, security monitoring, and an external secrets manager before accepting candidate documents.

## Required configuration

Generate a unique secret of at least 32 characters. Keep it stable because it also encrypts stored Gmail credentials. Rotating it requires re-encrypting those credentials before changing the value.

Never commit .env, OAuth client secrets, access tokens, uploaded CVs, database files, or exported candidate data.

## Account isolation

Every private API endpoint must use get_current_user and every query must filter by that user's ID. New tables containing candidate data must include user_id or a documented parent relationship that is itself user-scoped.

Review foreign-key references when accepting IDs from request bodies. Never trust an opportunity, company, recruiter, interview, or application ID without checking that it belongs to the authenticated user.

## Production release gates

- Configure HTTPS and secure cookies.
- Replace local file storage with private object storage.
- Run Alembic migrations explicitly.
- Configure PostgreSQL backups and restore drills.
- Configure Redis authentication, TLS, and persistence.
- Configure secret management and rotation.
- Add email verification and password reset delivery.
- Run dependency, SAST, DAST, authorization, and tenant-isolation tests.
- Review retention, export, and deletion workflows.
