PYTHON ?= python
COMPOSE = docker compose -f infrastructure/compose/docker-compose.yml
.PHONY: test lint typecheck web-build verify verify-all migrate dev compose-up compose-down compose-config

test:
	$(PYTHON) -m pytest -q

lint:
	ruff check .

typecheck:
	cd apps/web && pnpm lint

web-build:
	cd apps/web && pnpm build

migrate:
	alembic upgrade head

verify:
	$(PYTHON) -m compileall -q apps packages tests migrations scripts
	alembic upgrade head
	alembic check
	$(PYTHON) -m pytest -q
	ruff check .

compose-config:
	$(COMPOSE) config --quiet

verify-all: verify typecheck web-build compose-config

dev:
	uvicorn apps.api.app.main:app --reload --host 127.0.0.1 --port 8000

compose-up:
	$(COMPOSE) up --build

compose-down:
	$(COMPOSE) down
