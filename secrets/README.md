# Local secrets

This directory is a mount point for local development only. **Never commit credentials, OAuth client files, access tokens, refresh tokens, private keys, or production configuration here.**

## Supply secrets

- Use environment variables in an untracked root `.env` file for local development. Start from `.env.example` and replace placeholders with locally generated values.
- For containers, use a local secret file mounted read-only or environment variables injected by the deployment platform. Do not bake secrets into Docker images.
- In production, use the hosting provider's secret/environment-variable manager or a dedicated secrets manager. Grant each service only the credentials it needs.
- Keep Google OAuth client secrets and any token cache outside the repository. The Compose development stack mounts this directory read-only at `/run/secrets`.
- Rotate any credential that may have appeared in Git history. Removing a file from the current tree does not remove it from earlier commits.

## Local handling

1. Copy `.env.example` to `.env` and set a unique local `APP_SECRET_KEY`.
2. Keep provider integrations disabled unless explicitly testing them with dedicated development credentials.
3. Never use production credentials in local development.
4. Check `git status --ignored` before sharing logs or archives.
5. Run Gitleaks locally and in pre-commit/CI before pushing.

Only this README and `.gitkeep` belong in the tracked directory.
