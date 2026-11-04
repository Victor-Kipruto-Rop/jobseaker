# Repository audit

**Audit target:** `Victor-Kipruto-Rop/jobseaker`  
**Audited ref:** `feature/premium-ai-platform`  
**Audited commit:** `b9adde99b2792d4c17e4ae53a1cef2e7618de014`  
**Audit date:** 2026-11-04  
**Method:** GitHub repository tree and selected tracked-file inspection. No repository clone or local runtime was available for this inspection.

## Executive summary

The repository contains a substantial FastAPI/Next.js application under `apps/`, shared Python packages, PostgreSQL/Alembic migrations, Redis/RQ worker and scheduler services, and a large test suite. It also contains legacy application code under root-level `app/`, multiple Compose definitions, overlapping Python dependency manifests, and data files that appear to contain outreach/contact or SACCO verification records.

The current branch is **not verified as runnable**. The source tree contains Dockerfiles for API, web, worker, and scheduler, but no Docker build or Compose execution was performed during this audit. No CI workflow files were present under `.github/workflows/` at the audited ref. Tests, lint, migrations, type checks, and frontend builds have not been run.

## Repository tree (observed)

Top-level entries:

```text
.dockerignore
.env.example
.github/
.gitignore
.pre-commit-config.yaml
CHANGELOG.md
CODE_OF_CONDUCT.md
CONTRIBUTING.md
Dockerfile
LICENSE
Makefile
README.md
SECURITY.md
SECURITY_VERIFICATION.md
alembic.ini
app/                         # legacy/duplicate Python application tree
apps/                        # current multi-service application tree
config/
data/
docker-compose.yml           # root Compose definition
docs/
historical_sacco_verification.csv
infrastructure/
migrations/
outreach_reconciliation_report.md
package.json
packages/
pnpm-workspace.yaml
pyproject.toml
reconciled_outreach_contacts.csv
requirements.txt
scripts/
secrets/
tests/
```

The recursive Git tree contained 571 entries at audit time.

### Main application layout

- `apps/api/`: FastAPI application, API routes, dependencies, core services, and API Dockerfile.
- `apps/web/`: Next.js frontend and web Dockerfile.
- `apps/worker/`: background worker service and Dockerfile.
- `apps/scheduler/`: scheduled-job service and Dockerfile.
- `packages/`: shared Python packages, including database, security, integrations, and AI-related code.
- `migrations/` and `alembic.ini`: Alembic migration system.
- `infrastructure/compose/docker-compose.yml`: the Compose file referenced by the current Makefile and README setup instructions.
- `tests/`: unit, integration, security, and integration-adapter tests. The tree also contains placeholder-only test directories.

### Legacy and duplicate structure

- Root `app/` exists alongside `apps/api/app/`. Root `app/` contains older configuration/database/model code and outreach/Gmail modules. Its runtime ownership and imports need tracing before deletion or migration.
- Root `Dockerfile` exists alongside dedicated Dockerfiles for API, web, worker, and scheduler. The root Dockerfile is Python-only and starts the API.
- Root `docker-compose.yml` exists alongside `infrastructure/compose/docker-compose.yml`. The latter is the currently documented canonical Compose path; the root file must be compared before removal.
- `requirements.txt` overlaps substantially with `pyproject.toml`. The latter is the richer package/build manifest and includes development extras, but references must be checked before removing the former.

## Runtime inventory (static inspection only)

| Component | Source/configuration found | Runtime status |
|---|---|---|
| FastAPI API | `apps/api`, `apps/api/Dockerfile` | Not executed |
| Next.js web | `apps/web`, `apps/web/Dockerfile` | Not executed |
| RQ worker | `apps/worker`, `apps/worker/Dockerfile` | Not executed |
| RQ scheduler | `apps/scheduler`, `apps/scheduler/Dockerfile` | Not executed |
| PostgreSQL | Compose service, SQLAlchemy models, Alembic | Not started |
| Redis | Compose service and RQ/rate-limit configuration | Not started |
| Migrations | `migrations/`, `alembic.ini` | Not executed |
| Tests | `tests/` | Not executed |
| CI | No files found under `.github/workflows/` | Not configured at audited ref |
| Pre-commit | Ruff and standard hygiene hooks | Configured; gitleaks absent |

The canonical Compose file configures API, web, worker, scheduler, migration, PostgreSQL, and Redis services. Local environment overrides set the AI provider to mock and disable external email, Gmail, and job-discovery automation. Email sending and application submission are configured off. Gmail's intended permission scope is read-only.

## Security and repository hygiene findings

### Secret inventory

- The tracked `secrets/` directory contains only `secrets/.gitkeep` at the audited HEAD. No credential file was observed in the current tree.
- `.gitignore` currently ignores files under `secrets/` while allowing `.gitkeep`.
- The repository contains `.env.example`; it uses placeholders/empty provider fields in the inspected content. It must remain free of live values.
- No full-history secret scan has been completed. The GitHub connector can inspect repository objects but cannot run Gitleaks/TruffleHog against a complete local clone here. Therefore, **historical secret exposure is unknown**, not clean.
- No secret values are reproduced in this report.

### Potential personal or operational data tracked at HEAD

The following tracked files should be treated as private data until their contents are reviewed locally by the repository owner. Their contents were deliberately not fetched or printed:

- `historical_sacco_verification.csv` (5,459 bytes)
- `reconciled_outreach_contacts.csv` (30,480 bytes)
- `outreach_reconciliation_report.md` (3,021 bytes)

The requested files `kenya_data_opportunities_contacts.csv` and `outreach_send_log.csv` were not present in the audited HEAD tree. Their historical presence has not been established.

The root `.gitignore` currently ignores all of `data/`, so a tracked anonymised sample-fixture directory needs an explicit negation rule if sample fixtures are to be committed.

### History and rotation status

- Full Git history scan: **not run**.
- Gitleaks/TruffleHog findings: **unknown**.
- Historical removal: **not performed**.
- Force-push: **not performed**.
- Credential rotation: **not yet determined**. Rotate any provider, OAuth, SMTP, database, signing, or session credentials found by the owner's local history scan. See the rotation checklist in the Phase 0 completion report.

## Documentation and configuration inconsistencies

- README local admin instructions refer to `scripts/promote_admin.py`, while the audited tree contains `scripts/set_user_role.py`; the README command is stale.
- README verification references both `scripts/verification/verify_local.py` and `scripts/verify_local_security.py`. These are distinct scripts and their responsibilities need reconciliation.
- README numbering in the local setup section is duplicated.
- Root Compose and infrastructure Compose both exist; only the infrastructure path is referenced by the current documented startup path.
- The root Python `requirements.txt` and `pyproject.toml` have overlapping dependencies.
- The current web Dockerfile installs dependencies without a lockfile/frozen install, so dependency resolution is not fully reproducible.
- No GitHub Actions workflow files were found at the audited ref.
- The current pre-commit config has Ruff, YAML/TOML, whitespace, and private-key hooks, but no Gitleaks hook.

## What appears implemented

Based on tracked source/configuration, not runtime proof:

- FastAPI API and Next.js frontend.
- PostgreSQL persistence and Alembic migrations.
- Redis-backed RQ worker/scheduler configuration.
- AI provider adapters with mock configuration.
- Candidate authentication/session and role policy code.
- Application approval workflow code.
- Gmail read-only integration code.
- Job discovery and matching modules.
- Security, isolation, and lifecycle test files.
- Dedicated Dockerfiles for API, web, worker, and scheduler.

## What is broken, risky, dead, or unverified

| Finding | Classification | Evidence / next action |
|---|---|---|
| Private-looking CSV/report files tracked at root | Security/privacy risk | Move out of Git and inspect locally |
| No complete history secret scan | Unknown security exposure | Run Gitleaks/TruffleHog locally against all refs |
| Root `app/` beside `apps/` | Duplicate/legacy structure | Trace imports and history before removal |
| Root and infrastructure Compose files | Duplicate configuration | Compare service definitions; retain one canonical file |
| `requirements.txt` and `pyproject.toml` | Duplicate dependency manifests | Trace Docker/CI/scripts, then standardize |
| README points to missing admin script | Documentation defect | Update to the audited operator script |
| Multiple verification script references | Documentation ambiguity | Select canonical verification entry point |
| No CI workflows | Missing automation | Add CI in the appropriate later phase |
| No Gitleaks pre-commit hook | Missing security guard | Add in Phase 0 |
| Web Dockerfile has no committed lockfile | Reproducibility gap | Generate lockfile and use frozen install |
| Dockerfiles exist but are not built | Unverified | Build all four service images |
| Test suite not executed | Unverified | Run full test suite locally |
| DB migration chain not executed | Unverified | Upgrade empty PostgreSQL database to head |
| Type checking not configured in inspected pyproject | Unverified/missing | Add mypy and resolve findings in Phase 2 |

No directory or module should be labelled dead solely because it is not referenced in the README. Deletion requires import/reference analysis and a reversible migration.

## Phase 0 scope boundary

Phase 0 is limited to repository hygiene and exposure reduction:

1. Remove private data files from the current branch and add anonymised sample fixtures only where safe.
2. Add an explicit private-data ignore policy.
3. Add a secrets handling README and keep placeholder directory.
4. Add Gitleaks to pre-commit and CI configuration (CI workflow creation may be staged with Phase 2 if keeping phase boundaries strict).
5. Prepare, but do not execute, a history-purge script and owner-operated checklist.
6. Identify credentials that require rotation after a complete local scan.
7. Preserve history; do not force-push.

A clean current tree does not prove a clean Git history. History purge and credential rotation remain owner-controlled operations.
