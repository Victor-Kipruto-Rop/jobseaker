# JobSeeker security verification

This document defines the local security release gate. It is not a claim that the
checks have already passed.

## Authorization policy

- Self-service registration creates only the `candidate` role.
- The database constrains roles to `candidate` and `admin`.
- Candidate-facing API routers enforce `require_roles("candidate")` at router
  inclusion, so newly added endpoints inherit the candidate policy.
- Administrative APIs must use explicit `require_roles("admin")` dependencies.
  No administrative API is currently exposed.
- Initial administrator promotion/demotion is performed through the audited
  `scripts/set_user_role.py` operator command. It requires
  `ADMIN_BOOTSTRAP_ENABLED=true`, an operator identity, and exact email confirmation;
  it is not exposed as a self-service API.
- Role checks do not grant cross-user access. Every resource query must still
  scope by the authenticated user's ID.
- Gmail OAuth callback is exempt from cookie-session authorization only because
  it validates a short-lived, single-use state bound to the initiating candidate.
- Public auth routes are limited to CSRF bootstrap, registration, login, password
  reset request/confirmation, and email verification confirmation. Authenticated
  account routes validate the session directly.

## Required test suites

- `tests/security/test_csrf_asgi.py`: real FastAPI ASGI middleware behavior.
- `tests/security/test_route_authorization_policy.py`: every API route has an
  explicit authentication boundary and candidate endpoints carry the candidate role.
- `tests/security/test_cross_user_resource_isolation.py`: cross-user resource
  isolation, including profile, saved searches, notifications, resumes, recruiters,
  companies, interviews, applications, opportunities, AI conversations, generated
  artifacts, approvals, Gmail records and OAuth state.
- `tests/integration/test_postgres_security.py`: PostgreSQL-backed Alembic
  migration, session and recovery behavior. The suite creates a unique temporary
  schema and removes it after each test.

## Local release gate (Windows PowerShell or POSIX shell)

1. Copy `.env.example` to `.env`. Keep secrets local. Do not put production
   credentials in this file.
2. Ensure Docker Desktop, Python dependencies, Ruff, pnpm and frontend dependencies
   are installed.
3. Run:

   ```shell
   python scripts/verify_local_security.py
   ```

The script validates Compose configuration, starts the canonical local stack,
waits for API readiness, applies and checks Alembic migrations, runs the full
pytest suite including PostgreSQL integration tests, runs Ruff and frontend
lint/build, and prints service status. It forces local PostgreSQL/Redis endpoints
and disables Gmail, job discovery, email sending, application submission and
automation.

The stack is intentionally left running after success or failure for inspection.
Stop it with:

```shell
docker compose -f infrastructure/compose/docker-compose.yml down
```

To run only the PostgreSQL integration suite after the stack is up:

PowerShell:

```powershell
$env:JOBSEEKER_TEST_DATABASE_URL = "postgresql+psycopg://jobseeker:jobseeker_local@localhost:5432/jobseeker"
python -m pytest -q tests/integration/test_postgres_security.py
```

## Operator role management

For a deliberate operator-managed role change, temporarily set
`ADMIN_BOOTSTRAP_ENABLED=true` in the local environment, then run:

```shell
python scripts/set_user_role.py --email candidate@example.com --role admin --operator "security-operator" --confirm-email candidate@example.com
```

Use `--role candidate` to revoke administrator access. The command writes an
application audit event and refuses to run unless the feature flag and exact
email confirmation are supplied. Return the flag to false after the operation.

## Sign-off requirements

Security remains incomplete until the local script completes successfully,
migration upgrade/downgrade tests pass, all authorization tests pass, and a
route-by-route review confirms that every new resource query is owner-scoped.
Critical/high severity findings must be resolved. Do not deploy this branch as a
production security baseline until independent review and verification are complete.
