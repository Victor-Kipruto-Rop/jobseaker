PYTHON ?= python
.PHONY: test lint typecheck verify migrate dev compose-up compose-down
test:
	$(PYTHON) -m pytest -q
lint:
	ruff check .
typecheck:
	cd apps/web && pnpm lint
migrate:
	alembic upgrade head
verify:
	$(PYTHON) -m compileall -q apps packages tests
	$(PYTHON) -m pytest -q
	ruff check .
dev:
	uvicorn apps.api.app.main:app --reload --host 127.0.0.1 --port 8000
compose-up:
	docker compose -f infrastructure/compose/docker-compose.yml up --build
compose-down:
	docker compose -f infrastructure/compose/docker-compose.yml down
