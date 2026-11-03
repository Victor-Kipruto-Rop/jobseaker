PYTHON ?= python
PNPM ?= pnpm
DOCKER ?= docker
COMPOSE = $(DOCKER) compose -f infrastructure/compose/docker-compose.yml
WEB_DIR = apps/web

.PHONY: test lint typecheck web-build migrate python-verify compose-config verify verify-all dev compose-up compose-down

test:
	$(PYTHON) -m pytest -q

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
	$(PYTHON) -m pytest -q
	ruff check .

compose-config:
	$(COMPOSE) config --quiet

# One local release-gate command. Requires the configured database, pnpm dependencies,
# and Docker Compose to be available; it does not start containers or call live providers.
verify: python-verify typecheck web-build compose-config

verify-all: verify

dev:
	uvicorn apps.api.app.main:app --reload --host 127.0.0.1 --port 8000

compose-up:
	$(COMPOSE) up --build

compose-down:
	$(COMPOSE) down
