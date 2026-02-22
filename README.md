# Project Sustain

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![Ruby on Rails](https://img.shields.io/badge/Ruby_on_Rails-Control_Plane-CC0000?logo=rubyonrails&logoColor=white)](https://rubyonrails.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![OpenShift Ready](https://img.shields.io/badge/OpenShift-Ready-EE0000?logo=redhatopenshift&logoColor=white)](https://www.redhat.com/en/technologies/cloud-computing/openshift)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)

<p align="center">
  <img src="./output.gif" alt="Project Sustain demo" width="920" />
</p>

Project Sustain is a full-stack energy-aware training scheduler for GPU workloads. It combines a Python scheduling engine, Ruby on Rails control plane, FastAPI inference service, Next.js dashboard, and containerized runtime to place and reevaluate jobs across providers and regions.

## Setup Requirements

Minimum (local dev):

- Linux/macOS (Windows via WSL2)
- Docker Engine + Docker Compose v2
- Python 3.12
- Bun (for `apps/webapp`)

Recommended for full end-to-end runs:

- 8 CPU cores minimum
- 16 GB RAM minimum
- 60 GB free disk space recommended

Optional (only if you run services outside Docker):

- Ruby 3.4.8 + Bundler (Rails control plane)
- `oc` CLI (OpenShift deployment flow)

## What it does

Project Sustain schedules GPU training jobs using forecasted energy signals and live infrastructure data.

- Forecast carbon-intensity deltas over time windows.
- Join forecasts with live multi-cloud GPU inventory and price signals.
- Produce deterministic placement decisions with explicit scoring rationale.
- Reevaluate placements during training and emit migration recommendations.
- Persist state and events through a Rails control plane for observability.

## Architecture

`Scheduler (Python)` -> `ML Inference (FastAPI/ONNX)` + `Inventory Loader` -> `Decision + Score` -> `Rails API` -> `Dashboard`

Core score:

`score = SCHED_W_DELTA * avg_delta + SCHED_W_COST * normalized_cost`

Default weights:

- `SCHED_W_DELTA=0.70`
- `SCHED_W_COST=0.30`
- `SCHED_MIGRATION_THRESHOLD=0.2`
- `SCHED_EVAL_EVERY_N_EPOCHS=10`

## System

```text
apps/webapp/          Next.js 15 + React 19 + Tailwind 4 + Supabase auth
apps/webapp-minimal/  Streamlit prototype
apps/backend/         FastAPI, Flask, and Rails control-plane apps
apps/worker/          Celery worker
ml/                   Inference API, models, and ETL data
lib/                  Shared logger, scraper, and AI agent helpers
src/                  Scheduler, models, signals, hooks, jobs
k8s/openshift/        OpenShift manifests and job CRDs
```

## End-to-End Quickstart

This is the fastest path: run backend services in Docker and run the webapp locally.

### 1) Configure environment

```bash
cp .env.example .env
```

Set these values in `.env` for local end-to-end usage:

```dotenv
BACKEND_URL=http://localhost:9812
RAILS_API_URL=http://localhost:3001
NEXT_PUBLIC_REQUIRE_AUTH=false
```

### 2) Bootstrap local toolchain

```bash
make doctor
make init
```

### 3) Start backend stack

```bash
make up
docker compose up -d fastapi
```

`make up` starts `postgres`, `ml-inference`, `worker`, `rails`, and `scheduler`.
The extra `docker compose` command starts `fastapi` for the dashboard/API flow.

### 4) Start the webapp

```bash
make run.webapp
```

Then open `http://localhost:3000`.

### 5) Verify services

```bash
curl http://localhost:3000/api/health
curl http://localhost:9812/health
curl http://localhost:3001/up
curl http://localhost:8226/health
```

If these return healthy responses, the full flow is ready:

1. Open the dashboard.
2. Submit a GitHub repository.
3. Track preparation/execution state and audit events.

## Default Local Ports

- Webapp: `3000`
- FastAPI backend: `9812`
- Rails control plane: `3001`
- ML inference: `8226` (container port `8000`)
- PostgreSQL: `5432`
- Redis: `6378`

## Useful Commands

- `make ps` - show running containers
- `make logs` - stream logs
- `make down` - stop all services
- `make test` - run Python tests
- `make run.scheduler` - run scheduler loop locally
- `make run.worker` - run Celery worker locally

## OpenShift Deployment

For cluster deployment flows, use:

- `OPENSHIFT.md`
- `k8s/openshift/README.md`

## Operational Notes

- Scheduler geographies are configured through `SCHED_GEOS` (EU defaults in `src/config.py`).
- Current ONNX inference endpoint supports `UK` (with `GB` alias) and falls back to mock mode when models/dependencies are unavailable.
- Structured JSON logs are written to `./logs/` via `lib/logger.py`.
