# Ultiplate

![](./output.gif)

Template for any project: SaaS webapp, API server, ML pipeline, scraper, CLI, or background worker. AI-native, platform-agnostic, managed via Makefile.

## Quick Start

```bash
cp .env.example .env        # fill in NAME and any keys you need
make init                   # venv + python deps + env linking
make dev                    # Next.js webapp at http://localhost:3000
```

For Docker services (redis, ml inference, worker):
```bash
make up
```

## Directory

```
apps/
  webapp/          Next.js 15 + React 19 + Tailwind 4 + Supabase auth (Bun, Turbopack)
  webapp-minimal/  Streamlit quick prototype
  backend/
    fastapi/       FastAPI server (set BACKEND_MODE=fastapi)
    flask/         Flask server  (set BACKEND_MODE=flask)
  worker/          Celery background worker backed by Redis
ml/
  models/          arch.py (architecture) + train.py (training loop)
  data/            etl.py - raw -> PyTorch dataset pipeline
  inference.py     FastAPI inference server
  notebooks/       Jupyter notebooks
lib/               Shared Python utilities (logger, scraper, agent)
src/               Simple scripts / CLI entry points
```

## Make Targets

| Target | Description |
|--------|-------------|
| `make init` | First-time setup |
| `make dev` | Start Next.js webapp |
| `make up` | Start Docker core services |
| `make run.backend` | Start API backend |
| `make run.worker` | Start Celery worker |
| `make ai.agent` | Open Claude Code session |
| `make ai.plan IDEA="..."` | Get a build plan from Claude |
| `make ai.build TASK="..."` | Agentic build session |
| `make ai.review` | Review recent git changes |
| `make lift.minio` | Start MinIO object storage |
| `make lift.logging` | Start Loki + Grafana |
| `make lift.database` | Start Postgres / MongoDB |
| `make openshift.start` | Start OpenShift Local (CRC) |
| `make openshift.demo.nyc` | Submit NYC taxi dummy job |
| `make doctor` | Verify toolchain |

Run `make help` for the full list.

## AI Agent Capacity

Set `ANTHROPIC_API_KEY` in `.env`. Then use:

```python
from lib import ask, stream, Agent

# One-shot
print(ask("Summarize this data: ..."))

# Streaming
for chunk in stream("Write a Celery task that ..."):
    print(chunk, end="", flush=True)

# Multi-turn
agent = Agent(system="You are a senior Python developer.")
agent.chat("Scaffold a FastAPI endpoint for user profiles")
agent.chat("Add input validation and error handling")
```

Claude Code slash commands (type `/` in a Claude Code session):
- `/plan` - implementation plan for an idea within this boilerplate
- `/build` - implement a feature end-to-end
- `/api` - scaffold a new backend endpoint
- `/page` - scaffold a new Next.js page
- `/review` - code review of recent changes
- `/ship` - stage and commit changes

## Logging

```python
from lib import get_logger
logger = get_logger("service")
```

Outputs structured JSON to console + `./logs/`. Optional Loki push when `LOKI_PORT` is set and `make lift.logging` is running. View in Grafana at `http://localhost:$GRAFANA_PORT` (add Loki data source: `http://loki:3100`).

## Services (docker compose profiles)

| Profile | Services | Command |
|---------|----------|---------|
| _(default)_ | redis, ml-inference, worker | `make up` |
| `minio` | + MinIO object storage | `make lift.minio` |
| `tensorboard` | + TensorBoard | `make lift.tensorboard` |
| `logging` | + Loki + Grafana | `make lift.logging` |
| `database` | + Postgres + MongoDB | `make lift.database` |

## Webapp Auth

Auth is off by default (`NEXT_PUBLIC_REQUIRE_AUTH=false`). Set it to `true` and configure Supabase keys to enable session-based auth gating across all routes.
