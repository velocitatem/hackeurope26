# Rails Control Plane

This Rails API is the control plane for energy-aware ML scheduling.

## Responsibilities

- Job submission and status tracking (`/api/jobs`)
- Node inventory management (`/api/nodes`)
- Scheduling audit logs (`/api/scheduling_decisions`)
- Migration audit logs (`/api/migration_events`)
- OpenShift/Kubernetes admission webhook (`/webhook/pods`)

## Run locally

1. `cd apps/backend/rails`
2. `bundle install --path vendor/bundle`
3. `bundle exec rails db:create db:migrate db:seed`
4. `bundle exec rails server -b 0.0.0.0 -p 3001`

Environment variables:

- `DATABASE_URL` (PostgreSQL)
- `ML_INFERENCE_URL` (FastAPI inference service, default `http://ml-inference:8000`)
- `SCHED_HOOK_ROOT` (Python scheduler source root, default `/opt/hackeurope`)

## Webhook behavior

Pods labeled `energy-scheduling=true` are mutated to:

- use `schedulerName: secondary-scheduler`
- target a selected geography via `nodeSelector: { energy.io/geo: <geo> }`
- include window/score/provider/region/sku annotations

The webhook first invokes the Python scheduler hook (`src/hooks/training_schedule_hook.py`) so admission decisions share the same algorithm used by training scheduling. If the hook fails, it falls back to the Rails-native scorer.
