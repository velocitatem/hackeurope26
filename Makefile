# Makefile - Ultiplate Template
.PHONY: help init bootstrap venv deps envlink fmt lint type test clean doctor
.PHONY: up down logs ps rebuild
.PHONY: dev run.webapp run.webapp.simple run.backend run.worker run.ml run.scheduler run.rails run.nyc.taxi db.migrate.rails db.seed.rails
.PHONY: lift lift.minio lift.tensorboard lift.logging lift.database
.PHONY: etl train infer seed
.PHONY: ai.plan ai.build ai.review ai.agent
.PHONY: openshift.check openshift.start openshift.stop openshift.ocenv openshift.bootstrap openshift.demo.nyc openshift.status
.DEFAULT_GOAL := help

WD         := $(shell pwd)
ENV        := $(shell readlink -f .env 2>/dev/null || echo .env)
REQ        := $(shell readlink -f requirements.txt 2>/dev/null || echo requirements.txt)
PYTHON_VER := 3.12
PYTHON     := python$(PYTHON_VER)
VENV       := .venv/bin
PIP        := $(VENV)/pip
PYTEST     := $(VENV)/pytest
MYPY       := $(VENV)/mypy
BLACK      := $(VENV)/black
RUFF       := $(VENV)/ruff
BUN        := $(shell command -v bun 2>/dev/null || echo bun)
OPENSHIFT_NAMESPACE ?= hackeurope26

## ── Quick Start ──────────────────────────────────────────────────────────────

init: bootstrap ## First-time setup (alias for bootstrap)

dev: run.webapp ## Start the Next.js webapp (fastest entry point)

## ── Environment Setup ────────────────────────────────────────────────────────

bootstrap: venv envlink deps ## Full initial setup: venv + deps + env linking
	@echo "Bootstrap complete. Activate Python env: source .venv/bin/activate"

venv: ## Create Python virtual environment (idempotent)
	@if [ ! -d ".venv" ]; then \
		echo "Creating venv (Python $(PYTHON_VER))..."; \
		$(PYTHON) -m venv .venv; \
		$(PIP) install --upgrade pip setuptools wheel; \
	fi

deps: venv ## Install/update Python dependencies
	@$(PIP) install -r requirements.txt
	@$(PIP) install -e . 2>/dev/null || true

envlink: ## Propagate root .env and requirements.txt to all sub-apps
	@mkdir -p apps/webapp apps/worker ml
	@touch "$(WD)/apps/webapp/.env" "$(WD)/apps/worker/.env" "$(WD)/ml/.env"
	@if [ -f "$(ENV)" ]; then \
		ln -sf "$(ENV)" "$(WD)/apps/webapp/.env"; \
		ln -sf "$(ENV)" "$(WD)/apps/worker/.env"; \
		ln -sf "$(ENV)" "$(WD)/ml/.env"; \
	fi
	@if [ -f "$(REQ)" ]; then \
		cp "$(REQ)" "$(WD)/ml/requirements.txt" 2>/dev/null || true; \
		cp "$(REQ)" "$(WD)/apps/worker/requirements.txt" 2>/dev/null || true; \
	fi

doctor: ## Verify toolchain (bun, docker, python)
	@echo "Checking toolchain..."
	@$(PYTHON) --version || (echo "python$(PYTHON_VER) not found"; exit 1)
	@$(BUN) --version || echo "bun not found - install: curl -fsSL https://bun.sh/install | bash"
	@docker --version || echo "docker not found"
	@docker compose version || echo "docker compose not found"
	@echo "OK"

## ── Code Quality ─────────────────────────────────────────────────────────────

fmt: venv ## Format Python with black
	@$(BLACK) src/ ml/ apps/worker/ apps/backend/ 2>/dev/null || echo "pip install black"

lint: venv ## Lint Python with ruff
	@$(RUFF) check src/ ml/ apps/worker/ apps/backend/ 2>/dev/null || echo "pip install ruff"

type: venv ## Type check Python with mypy
	@$(MYPY) src/ ml/ apps/worker/ apps/backend/ 2>/dev/null || echo "pip install mypy"

test: venv ## Run pytest
	@$(PYTEST) tests/ -v 2>/dev/null || echo "No tests yet - create tests/"

## ── Docker ───────────────────────────────────────────────────────────────────

up: ## Start core services (postgres, ml-inference, worker, rails, scheduler)
	@docker compose up -d postgres ml-inference worker rails scheduler

down: ## Stop all services
	@docker compose down

logs: ## Tail all service logs
	@docker compose logs -f

ps: ## Show service status
	@docker compose ps

rebuild: ## Rebuild + restart all services (no cache)
	@docker compose build --no-cache && docker compose up -d

## ── OpenShift Local (CRC) ────────────────────────────────────────────────────

openshift.check: ## Verify OpenShift local tools (crc, oc)
	@command -v crc >/dev/null || (echo "crc not found. Install OpenShift Local (CRC): https://developers.redhat.com/products/openshift-local/overview"; exit 1)
	@command -v oc >/dev/null || (echo "oc not found. Install OpenShift client tools: https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html-single/cli_tools/"; exit 1)

openshift.start: openshift.check ## Start local OpenShift cluster (requires pull secret configured in crc)
	@crc setup
	@crc start

openshift.stop: openshift.check ## Stop local OpenShift cluster
	@crc stop

openshift.ocenv: openshift.check ## Print shell command to configure oc path/env for CRC
	@crc oc-env

openshift.bootstrap: openshift.check ## Apply namespace + scheduler/webhook scaffolding manifests
	@oc apply -f k8s/openshift/namespace.yaml
	@oc apply -f k8s/openshift/trainingjob-crd.yaml
	@oc apply -f k8s/openshift/secondary-scheduler-configmap.yaml || true
	@oc apply -f k8s/openshift/mutating-webhook.yaml

openshift.demo.nyc: openshift.check ## Submit NYC taxi dummy training Job to OpenShift
	@oc apply -f k8s/openshift/nyc-taxi-demo-job.yaml

openshift.status: openshift.check ## Show project pods/jobs and event stream
	@oc get ns $(OPENSHIFT_NAMESPACE) >/dev/null 2>&1 || (echo "Namespace $(OPENSHIFT_NAMESPACE) not found. Run make openshift.bootstrap"; exit 1)
	@oc -n $(OPENSHIFT_NAMESPACE) get pods
	@oc -n $(OPENSHIFT_NAMESPACE) get jobs

## ── Service Profiles ─────────────────────────────────────────────────────────

lift: up ## Alias for 'up'

lift.minio: ## Start core services + MinIO object storage
	@docker compose --profile minio up -d
	@echo "MinIO console: http://localhost:9901 (minioadmin/minioadmin)"

lift.tensorboard: ## Start TensorBoard
	@docker compose --profile tensorboard up -d
	@echo "TensorBoard: http://localhost:6006"

lift.logging: ## Start Loki + Grafana logging stack
	@docker compose --profile logging up -d
	@if [ -f .env ]; then . ./.env 2>/dev/null; fi; \
	echo "Grafana: http://localhost:$${GRAFANA_PORT:-3000} (admin/admin)"; \
	echo "Loki:    http://localhost:$${LOKI_PORT:-3100}"

lift.database: ## Start database services (postgres/mongodb)
	@docker compose --profile database up -d

## ── Run Applications ─────────────────────────────────────────────────────────

run.webapp: ## Start Next.js webapp with bun (dev + turbopack)
	@echo "Starting webapp at http://localhost:3000"
	@cd apps/webapp && $(BUN) install --frozen-lockfile 2>/dev/null || $(BUN) install; $(BUN) dev

run.webapp.simple: ## Start Streamlit minimal webapp
	@cd apps/webapp-minimal && streamlit run app.py

run.backend: ## Start API backend (BACKEND_MODE=fastapi|flask, default: fastapi)
	@if [ -f .env ]; then . ./.env; fi; \
	MODE=$${BACKEND_MODE:-fastapi}; \
	if [ "$$MODE" = "fastapi" ]; then \
		cd apps/backend/fastapi && $(PYTHON) server.py; \
	elif [ "$$MODE" = "flask" ]; then \
		cd apps/backend/flask && $(PYTHON) server.py; \
	else \
		echo "Unknown BACKEND_MODE=$$MODE (fastapi|flask)"; exit 1; \
	fi

run.worker: ## Start Celery worker (requires redis)
	@cd apps/worker && celery -A worker:app worker --loglevel=info

run.ml: ## Start ML inference server (FastAPI)
	@cd ml && uvicorn inference:app --host 0.0.0.0 --port 8000 --reload

run.scheduler: ## Start the adaptive scheduler demo loop
	@$(PYTHON) -m src.main

run.nyc.taxi: ## Run the NYC taxi dummy training script locally
	@$(PYTHON) -m src.jobs.nyc_taxi_dummy

run.rails: ## Start Rails control-plane API
	@cd apps/backend/rails && bundle config set path 'vendor/bundle' && bundle install && bundle exec rails server -b 0.0.0.0 -p 3001

db.migrate.rails: ## Run Rails database migrations
	@cd apps/backend/rails && bundle config set path 'vendor/bundle' && bundle install && bundle exec rails db:migrate

db.seed.rails: ## Seed Rails database with starter nodes
	@cd apps/backend/rails && bundle config set path 'vendor/bundle' && bundle install && bundle exec rails db:seed

## ── ML Workflow ──────────────────────────────────────────────────────────────

etl: venv ## Run ETL pipeline
	@cd ml && $(PYTHON) data/etl.py

train: venv ## Run model training
	@cd ml && $(PYTHON) models/train.py

infer: run.ml ## Alias for run.ml

## ── AI / Agent Workflows ─────────────────────────────────────────────────────
# Requires: ANTHROPIC_API_KEY set in .env or environment
# Uses the Claude CLI (claude) - install: https://claude.ai/install

ai.plan: ## Describe your idea and get a build plan from Claude
	@if [ -z "$(IDEA)" ]; then echo "Usage: make ai.plan IDEA=\"describe your project\""; exit 1; fi
	@claude -p "You are a senior engineer helping plan a hackathon project built on the Ultiplate boilerplate. The project structure is: Next.js webapp (apps/webapp), Python backend (apps/backend/fastapi|flask), Celery worker (apps/worker), ML pipeline (ml/), and CLI/SDK (src/). Given this idea: \"$(IDEA)\" - produce a concise implementation plan listing which parts of the scaffold to use, what to build, and in what order. Be direct and specific."

ai.build: ## Run an agentic build session with Claude (guided)
	@if [ -z "$(TASK)" ]; then echo "Usage: make ai.build TASK=\"what to build\""; exit 1; fi
	@claude "$(TASK)"

ai.review: ## Ask Claude to review recent changes
	@git diff HEAD~1 2>/dev/null | claude -p "Review these changes for correctness, code quality, and any issues. Be concise and direct."

ai.agent: ## Start an interactive Claude Code session in this repo
	@claude

## ── Utilities ────────────────────────────────────────────────────────────────

seed: venv ## Seed development data
	@$(PYTHON) scripts/seed.py 2>/dev/null || echo "Create scripts/seed.py for seeding"

clean: ## Remove caches, build artifacts, and compiled files
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build/ dist/ 2>/dev/null || true

help: ## Show this help
	@echo "Ultiplate - make targets"
	@echo ""
	@echo "  Quick start:"
	@echo "    make init         - First-time setup"
	@echo "    make dev          - Start Next.js webapp"
	@echo "    make up           - Start Docker services"
	@echo "    make ai.agent     - Open Claude Code session"
	@echo ""
	@grep -E '^[a-zA-Z_.%-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-22s %s\n", $$1, $$2}'
