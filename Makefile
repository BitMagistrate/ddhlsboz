# RoadPulse universal Makefile. Thin wrappers over service-local commands.

SHELL := /bin/bash
PY := python3.11
PIP := $(PY) -m pip
PNPM := pnpm
VENV := .venv
ACTIVATE := source $(VENV)/bin/activate

.DEFAULT_GOAL := help

.PHONY: help bootstrap venv install install.web install.api seed up down \
        dev.api dev.web dev.b2c lint typecheck test test.api test.web \
        test.contract test.e2e test.ml.eval load clean format docs.serve

help: ## Show this help.
	@grep -E '^[a-zA-Z._-]+:.*?##' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

bootstrap: venv install install.web ## One-shot dev setup (python + node + pre-commit).
	@if [ -f .pre-commit-config.yaml ]; then \
	  $(ACTIVATE) && pip install pre-commit && pre-commit install --install-hooks; \
	fi

venv: ## Create local python virtualenv.
	test -d $(VENV) || $(PY) -m venv $(VENV)
	$(ACTIVATE) && pip install -U pip

install: venv ## Install Python deps (editable workspace).
	$(ACTIVATE) && pip install -e ".[dev]"
	$(ACTIVATE) && pip install -e packages/python/roadpulse_privacy
	$(ACTIVATE) && pip install -e packages/python/roadpulse_features
	$(ACTIVATE) && pip install -e packages/python/roadpulse_routing
	$(ACTIVATE) && pip install -e packages/python/roadpulse_ml
	$(ACTIVATE) && pip install -e packages/python/roadpulse_telemetry

install.web: ## Install pnpm workspace deps.
	command -v $(PNPM) >/dev/null 2>&1 || corepack enable
	$(PNPM) install --frozen-lockfile || $(PNPM) install

seed: ## Generate synthetic VETC + weather + SAR fixtures.
	$(ACTIVATE) && python tools/seed_dataset.py --out data/seed

up: ## Start local docker-compose stack.
	docker compose -f compose.dev.yaml up -d

down: ## Tear down local docker-compose stack.
	docker compose -f compose.dev.yaml down -v

dev.api: ## Run FastAPI api-gateway with reload.
	$(ACTIVATE) && uvicorn apps.api-gateway.app.main:app --reload --port 8000

dev.web: ## Run B2B dashboard dev server.
	cd apps/b2b-dashboard && $(PNPM) dev --host

dev.b2c: ## Run Expo dev server for B2C app.
	cd apps/b2c-app && $(PNPM) start

lint: ## Lint python + ts.
	$(ACTIVATE) && ruff check .
	cd apps/b2b-dashboard && $(PNPM) lint || true

format: ## Auto-format python + ts.
	$(ACTIVATE) && ruff format .
	$(ACTIVATE) && ruff check --fix .

typecheck: ## Static type-check both stacks.
	$(ACTIVATE) && mypy packages/python apps/api-gateway/app apps/eta-service/app apps/flood-service/app apps/routing-engine/app apps/trigger-feed/app || true
	cd apps/b2b-dashboard && $(PNPM) typecheck || true

test: test.api test.web ## Run all unit + integration tests.

test.api: ## Pytest for python services.
	$(ACTIVATE) && pytest -q

test.web: ## Vitest for b2b-dashboard.
	cd apps/b2b-dashboard && $(PNPM) test --run || true

test.contract: ## Contract tests (Schemathesis vs OpenAPI).
	$(ACTIVATE) && python -m pytest tests/contract -q

test.e2e: ## End-to-end golden journey tests.
	cd apps/b2b-dashboard && $(PNPM) test:e2e || true

test.ml.eval: ## Run ML eval harness (MAPE / PR-ROC).
	$(ACTIVATE) && python ml/eval/harness.py --fixture data/seed

load: ## Load test /v1/route with k6 (if installed).
	@command -v k6 >/dev/null 2>&1 || { echo "k6 not installed; skipping"; exit 0; }
	k6 run tools/loadtest/route.js

clean: ## Remove caches and build artefacts.
	rm -rf .venv .pytest_cache .mypy_cache .ruff_cache htmlcov
	find . -name '__pycache__' -type d -exec rm -rf {} +
	find . -name '*.pyc' -delete
	rm -rf apps/b2b-dashboard/dist apps/b2b-dashboard/.vite
	rm -rf apps/b2c-app/.expo apps/b2c-app/dist

docs.serve: ## Serve docs locally.
	$(ACTIVATE) && python -m http.server 8001 -d docs
