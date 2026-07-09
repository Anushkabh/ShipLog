PY := .venv/bin/python
UVICORN := .venv/bin/uvicorn
ALEMBIC := .venv/bin/alembic

.PHONY: install up down migrate revision run smoke lint test

install:            ## Create venv + install deps
	uv sync

up:                 ## Start Postgres + Redis
	cd ../.. && docker compose up -d db redis

down:               ## Stop containers
	cd ../.. && docker compose down

migrate:            ## Apply migrations
	$(ALEMBIC) upgrade head

revision:           ## Autogenerate a migration: make revision m="add x"
	$(ALEMBIC) revision --autogenerate -m "$(m)"

run:                ## Run the API with reload
	$(UVICORN) app.main:app --reload --port 8000

smoke:              ## End-to-end product-loop test (API must be running)
	$(PY) scripts/smoke.py

lint:
	.venv/bin/ruff check app

test:
	.venv/bin/pytest -q
