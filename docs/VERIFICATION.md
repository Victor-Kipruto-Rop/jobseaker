# Verification log

This file records commands actually executed and their observed results. A source file or test existing in the repository is not evidence that it passes.

## Phase 0: security and repository hygiene

**Audit ref:** `feature/premium-ai-platform`  
**Audit commit:** `b9adde99b2792d4c17e4ae53a1cef2e7618de014`  
**Phase branch:** `phase-0-security-hygiene`

| Check | Command / method | Result |
|---|---|---|
| Repository tree inventory | GitHub recursive Git tree API | Completed; 571 entries observed |
| Selected configuration inspection | GitHub file contents API | Completed |
| Current secrets directory inventory | Recursive Git tree API | Only `secrets/.gitkeep` observed at audited HEAD |
| Full-history Gitleaks scan | Requires local clone and Gitleaks binary | Not run; historical exposure unknown |
| TruffleHog scan | Requires local clone and TruffleHog binary | Not run |
| Pre-commit hook execution | Requires local checkout and pre-commit | Not run |
| GitHub Actions Gitleaks workflow | Added in Phase 0 | Not run by this environment |
| History rewrite | Manual owner operation only | Not run; no force-push |
| Docker / tests / lint / migrations | Local runtime required | Not run in Phase 0 |

No test, Docker build, migration, lint, or secret-scan pass is claimed in this log.

## Required owner-side commands

Run from a fresh local clone after pulling `phase-0-security-hygiene`:

```powershell
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Install Gitleaks separately, then scan the full history without printing secret values:

```powershell
gitleaks git . --redact --report-format json --report-path gitleaks-history-report.json
```

Protect the report as sensitive security metadata. Do not commit an unredacted report. Record finding counts and credential categories here, not credential values.

The full local verification gate is recorded separately in the later phases. Do not mark checks as passed until the command output has been captured and reviewed.


## Phase 1: structure cleanup

**Branch:** `phase-1-structure-cleanup`  
**Static inspection commit:** `06f1c0d4838e9fdf48a8d01e43c9bde23995b089`

| Check | Method | Result |
|---|---|---|
| Root and nested tree inventory | GitHub recursive Git tree API | Completed |
| Active application import references | GitHub code search and selected source inspection | Root `app/` only referenced by legacy scripts; active services use `apps/` and `packages/` |
| Canonical Compose references | Selected README, Makefile, operations docs | Infrastructure Compose path retained |
| Dependency manifest references | Selected Dockerfiles and project configuration | `pyproject.toml` retained; root `requirements.txt` removed with obsolete root Dockerfile |
| Four service Dockerfiles | Static source inspection | Present and structurally consistent; builds not run |
| Root duplicate files | Git tree inspection after commit | Root Dockerfile, root Compose, and requirements manifest removed |
| Legacy root application | Git tree inspection after commit | Root `app/` removed |
| Python tests / Ruff / mypy | Local execution | Not run |
| pnpm lint/build | Local execution | Not run |
| Docker image builds | Docker engine required | Not run |
| Compose config validation | Docker Compose required | Not run |
| Alembic migration from empty DB | Local PostgreSQL required | Not run |

No Docker image build or runtime check is claimed as successful. Use the four explicit build commands in `docs/architecture/repository-layout.md` and paste their actual output before marking the Dockerfile build check complete.


## Phase 2: runtime and CI verification foundation

**Branch:** `phase-2-runtime-ci-verification`

### Implemented

- Added `.github/workflows/ci.yml` with separate Python, web, and Docker jobs.
- Python CI provisions PostgreSQL 16 and Redis 7, installs the project with development extras, compiles Python, runs Ruff and mypy, applies Alembic migrations to a clean PostgreSQL service, checks schema drift, runs pytest with coverage output, and runs pip-audit.
- Web CI installs pnpm dependencies, runs the TypeScript check, builds Next.js, and audits production dependencies.
- Docker CI validates the canonical Compose file and builds API, web, worker, and scheduler images.
- Added pytest-cov and mypy to the Python development extras and configured baseline mypy options.
- Updated the local Compose-backed release gate to run mypy and pytest coverage.
- Removed three obsolete tests that imported the retired root `app/` package and tested deleted outreach/Gmail legacy functionality.

### Static checks completed in this environment

| Check | Method | Result |
|---|---|---|
| CI workflow source | GitHub file inspection | Added; not executed |
| PostgreSQL and Redis service definitions | Workflow source inspection | Present |
| Migration and drift steps | Workflow source inspection | Present |
| Python test/coverage steps | Workflow source inspection | Present |
| Python type-check step | Workflow source inspection | Present |
| Web type-check/build/audit steps | Workflow source inspection | Present |
| Four Docker build steps | Workflow source inspection | Present |
| Removed legacy test files | Recursive Git tree inspection | Absent from Phase 2 tree |
| Local release gate command | Source inspection | Updated; not executed |

### Outstanding execution evidence

No GitHub Actions run, Docker build, Compose start, Alembic migration, pytest, Ruff, mypy, frontend build, pip-audit, or pnpm audit has been observed for this branch. Do not treat the workflow definition as a passing workflow.

### Known reproducibility limitation

There is no committed `pnpm-lock.yaml` in the repository. The web CI and Docker build currently use `pnpm install --no-frozen-lockfile`, so transitive frontend dependency resolution is not yet lockfile-reproducible. Generate and commit a pnpm lockfile from a local pnpm 9.15.0 install, then change CI and the web Dockerfile to frozen-lockfile mode.

### Coverage status

Coverage reporting is enabled, but no measured percentage is available yet. The target of 80% for service and authentication code remains unverified and is not represented as achieved.
