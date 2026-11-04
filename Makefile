PYTHON ?= python
PNPM ?= pnpm
DOCKER ?= docker
COMPOSE = $(DOCKER) compose -f infrastructure/compose/docker-compose.yml
WEB_DIR = apps/web

.PHONY: test lint typecheck web-build migrate python-verify compose-config verify verify-all verify-stack dev compose-up compose-down

test:
	$(PYTHON) -m pytest -q --cov=apps.api.app --cov=packages --cov-report=term-missing

lint:
	ruff check .

typecheck:
	cd $(WEB_DIR) && $(PNPM) lint

web-build:
	cd $(WEB_DIR) && $(PNPM) build

migrate:
	alembic upgrade head

python-verify:
	$(PYTHON) -m compileall -q apps packages tests migrations scripts
	alembic upgrade head
	alembic check
	$(PYTHON) -m mypy apps/api packages --ignore-missing-imports --follow-imports=silent
	$(PYTHON) -m pytest -q --cov=apps.api.app --cov=packages --cov-report=term-missing
	ruff check .

compose-config:
	$(COMPOSE) config --quiet

# Host-only verification uses an already-running database. The Compose-backed release gate
# starts the local stack and does not call live AI, Gmail, or SMTP providers.
verify: python-verify typecheck web-build compose-config

verify-all: verify-stack

# Starts the isolated local stack and runs the full release gate, including PostgreSQL tests.
verify-stack:
	$(PYTHON) scripts/verify_local_security.py

dev:
	uvicorn apps.api.app.main:app --reload --host 127.0.0.1 --port 8000

compose-up:
	$(COMPOSE) up --build

compose-down:
	$(COMPOSE) down
