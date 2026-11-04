# Canonical repository layout

The repository uses one application root, one Python dependency manifest, and one local Compose definition.

```text
.
├── apps/
│   ├── api/                 # FastAPI application and API Dockerfile
│   ├── web/                 # Next.js application and web Dockerfile
│   ├── worker/              # RQ worker entry point and Dockerfile
│   └── scheduler/           # RQ scheduler entry point and Dockerfile
├── packages/                # Shared Python domain, database, AI, and integration packages
├── migrations/              # Canonical Alembic migration history
├── infrastructure/
│   └── compose/
│       └── docker-compose.yml
├── config/                  # Reviewed, non-secret YAML defaults
├── data/
│   └── samples/              # Fabricated fixtures only; private runtime data is ignored
├── secrets/                 # Local mount point; only README and .gitkeep are tracked
├── scripts/                 # Operator and verification utilities
├── tests/                   # Python unit, integration, and security tests
├── docs/                    # Architecture, operations, audit, and security records
├── pyproject.toml            # Sole Python dependency/build manifest
├── package.json              # pnpm workspace root
└── pnpm-workspace.yaml
```

## Canonical choices

| Concern | Canonical location | Retired duplicate |
|---|---|---|
| Python application | `apps/api` and shared `packages/` | Root `app/` |
| Python dependencies and packaging | Root `pyproject.toml` | Root `requirements.txt` |
| Local multi-service runtime | `infrastructure/compose/docker-compose.yml` | Root `docker-compose.yml` |
| Container build definitions | `apps/api/Dockerfile`, `apps/web/Dockerfile`, `apps/worker/Dockerfile`, `apps/scheduler/Dockerfile` | Root `Dockerfile` |
| Local release verification | `scripts/verify_local_security.py` | Earlier host-only Python verification entry point |

## Removed legacy components

The root `app/` package was an earlier, separate FastAPI application with its own SQLAlchemy models and direct database initialization. Its only repository callers were the legacy Gmail sync and CSV import scripts. Those scripts used the root package and did not share the current account-scoped data model or Alembic lifecycle. They have been removed rather than silently adapted into the active application.

The current Gmail integration lives in `packages/integrations/gmail/` and is mounted through the API router. Its required scope is `gmail.readonly`. Outreach import scripts were not ported because their legacy models and non-tenant-aware data model do not meet the current account isolation contract.

## Docker build commands

Run from the repository root:

```powershell
docker build -f apps/api/Dockerfile -t jobseeker-api:local .
docker build -f apps/web/Dockerfile -t jobseeker-web:local --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 .
docker build -f apps/worker/Dockerfile -t jobseeker-worker:local .
docker build -f apps/scheduler/Dockerfile -t jobseeker-scheduler:local .
docker compose -f infrastructure/compose/docker-compose.yml config --quiet
```

The four Dockerfiles have been statically inspected for their build context and required source copies. These commands have **not** been executed by the remote repository editor; successful image builds must be recorded in `docs/VERIFICATION.md` after local execution.
