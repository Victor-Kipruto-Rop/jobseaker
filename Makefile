PYTHON ?= python
.PHONY: test lint dev compose-up compose-down
test:
	$(PYTHON) -m pytest -q
lint:
	ruff check .
dev:
	uvicorn apps.api.app.main:app --reload --host 127.0.0.1 --port 8000
compose-up:
	docker compose -f infrastructure/compose/docker-compose.yml up --build
compose-down:
	docker compose -f infrastructure/compose/docker-compose.yml down
