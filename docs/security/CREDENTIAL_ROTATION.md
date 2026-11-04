# Credential rotation checklist

## Scan status

No credential exposure has been confirmed by a full-history scan. The repository audit found no credential files in the current `secrets/` directory and found only placeholders/empty values in the inspected `.env.example`. A full Git-history scan has not yet run, so historical exposure remains unknown.

**Rotate or revoke each credential below if it appears in Gitleaks/TruffleHog findings, an earlier committed environment file, a secret file, logs, or an exposed backup. Do not rotate credentials solely because their variable names appear in this checklist.**

## Credentials to inspect

| Credential type | What to rotate/revoke if exposed | Follow-up |
|---|---|---|
| Application signing secret | `APP_SECRET_KEY` and any session/token signing key | Rotate; invalidate existing sessions/tokens where required |
| OpenAI | `OPENAI_API_KEY` | Revoke exposed key and issue a new restricted key |
| Anthropic | `ANTHROPIC_API_KEY` | Revoke exposed key and issue a new restricted key |
| Google OAuth | OAuth client secret, refresh tokens, access tokens, client-secret JSON | Rotate client secret where possible; revoke affected grants/tokens and re-authorize |
| SMTP/email | SMTP username/password or provider API token | Revoke/reset and review provider send logs |
| PostgreSQL | Database passwords and connection credentials | Rotate role password; update dependent services |
| Redis | Redis password/ACL credentials or managed-service token | Rotate and invalidate old credentials |
| GitHub | Personal access tokens, deploy keys, GitHub App private keys | Revoke exposed tokens/keys and audit repository access |
| Cloud/object storage | S3/R2 access key, secret key, bucket credentials | Revoke and replace with least-privilege credentials |
| Sentry/monitoring | DSN auth tokens or ingestion/management tokens | Rotate any privileged token; confirm DSN exposure impact |
| Other integrations | Any third-party API key, webhook signing secret, or private key | Revoke with the issuing provider and audit usage |

## Rotation procedure

1. Run Gitleaks across every branch and tag in a complete local clone.
2. Review redacted findings and identify the issuing service and credential owner.
3. Revoke exposed credentials before history rewriting.
4. Generate replacements in the provider console or secrets manager.
5. Update local `.env` and deployment secret stores without committing values.
6. Restart affected services and verify authentication using safe, non-production checks.
7. Review provider audit logs for suspicious use during the exposure window.
8. Record credential type, owner, rotation date, and completion status here. Never record the credential value.
9. Re-run Gitleaks after rotation and after the coordinated history rewrite.
