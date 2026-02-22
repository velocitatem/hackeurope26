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

## What is implemented

- Scheduler core in `src/` with deterministic scoring and migration checks.
- Ruby on Rails control-plane integration for jobs, decisions, and migration events.
- ML inference API in `ml/inference.py` serving ONNX horizon models with mock fallback.
- Inventory loader from `ml/data/` covering provider sites and pricing.
- Web surfaces: Next.js dashboard (`apps/webapp`) and Streamlit prototype (`apps/webapp-minimal`).
- Docker Compose stack for local orchestration and OpenShift manifests for cluster deployment.

## Architecture

`Scheduler (Python)` -> `ML Inference (FastAPI/ONNX)` + `Inventory Loader` -> `Decision + Score` -> `Rails API` -> `Dashboard`

Core score:

`score = SCHED_W_DELTA * avg_delta + SCHED_W_COST * normalized_cost`

Default weights:

- `SCHED_W_DELTA=0.70`
- `SCHED_W_COST=0.30`
- `SCHED_MIGRATION_THRESHOLD=0.2`
- `SCHED_EVAL_EVERY_N_EPOCHS=10`

## Quick start

```bash
cp .env.example .env
make init
make up
```

Common dev commands:

```bash
make dev            # Next.js app on :3000
make run.scheduler  # scheduler loop
make run.ml         # ML inference API
make run.backend    # FastAPI or Flask backend
make test           # pytest
```

## Services

Default `make up` stack:

- `postgres`
- `rails`
- `ml-inference`
- `worker`
- `scheduler`
- `redis`

Optional profiles:

- `make lift.minio`
- `make lift.tensorboard`
- `make lift.logging`
- `make lift.database`

## Repository layout

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

## AI utilities

Set `ANTHROPIC_API_KEY` in `.env` and use:

```python
from lib import ask, stream, Agent
```

Useful Make targets:

- `make ai.agent`
- `make ai.plan IDEA="..."`
- `make ai.build TASK="..."`
- `make ai.review`

## Notes

- Scheduler geographies are configured through `SCHED_GEOS` (EU defaults in `src/config.py`).
- Current ONNX inference endpoint supports `UK` (with `GB` alias) and falls back to mock mode when models/dependencies are unavailable.
- Structured JSON logs are written to `./logs/` via `lib/logger.py`.
