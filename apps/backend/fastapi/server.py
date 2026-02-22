from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
import json
import os
import time
import uuid

from celery import Celery
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import redis
import uvicorn

from lib.vfs import VirtualFileSystem

try:
    from src.models import JobSpec
except Exception:

    @dataclass
    class JobSpec:
        job_id: str
        duration_s: int
        gpu_count: int
        min_gpu_memory_mib: int
        allowed_geos: list[str]
        max_price_usd_hour: float | None = None
        current_epoch: int = 0


load_dotenv()


def _resolve_redis_url() -> str:
    raw = os.getenv("REDIS_URL", "redis://localhost:6379")
    if "$" not in raw:
        return raw
    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    db = os.getenv("REDIS_DB", "0")
    return f"redis://{host}:{int(port)}/{db}"


REDIS_URL = _resolve_redis_url()
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
celery_client = Celery("backend", broker=REDIS_URL, backend=REDIS_URL)


class SubmitRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    allowed_geos: list[str] = Field(default_factory=lambda: ["FR", "DE", "ES"])
    max_price_usd_hour: float | None = None
    image: str | None = None
    timeout: int = 300
    verbose: bool = False


class ExecuteRequest(BaseModel):
    image: str | None = None
    namespace: str | None = None


def _decode_value(value: str) -> object:
    try:
        return json.loads(value)
    except Exception:
        return value


def _read_job(job_id: str) -> dict[str, object] | None:
    raw = redis_client.hgetall(f"job:{job_id}")
    if not raw:
        return None
    return {k: _decode_value(v) for k, v in raw.items()}


def _suggest_image(job_id: str) -> str:
    repo = os.getenv("DEFAULT_IMAGE_REPO", "quay.io/drosel_ieu2022/hackeurope-train")
    return f"{repo}:{job_id}"


def _estimate_job_spec(job_id: str, job: dict[str, object]) -> dict[str, object] | None:
    analysis = job.get("analysis")
    if not isinstance(analysis, dict):
        return None

    allowed_geos = job.get("allowed_geos")
    if not isinstance(allowed_geos, list):
        allowed_geos = ["FR", "DE", "ES"]

    estimated_hours_raw = analysis.get("estimated_hours", 1)
    try:
        estimated_hours = float(estimated_hours_raw)
    except Exception:
        estimated_hours = 1.0

    gpu_count_raw = analysis.get("gpu_count", 1)
    gpu_mem_gib_raw = analysis.get("gpu_mem_gib", 16)
    try:
        gpu_count = int(gpu_count_raw)
    except Exception:
        gpu_count = 1
    try:
        gpu_mem_gib = int(gpu_mem_gib_raw)
    except Exception:
        gpu_mem_gib = 16

    max_price = job.get("max_price_usd_hour")
    if isinstance(max_price, str):
        try:
            max_price = float(max_price)
        except Exception:
            max_price = None
    elif not isinstance(max_price, (float, int)):
        max_price = None

    spec = JobSpec(
        job_id=job_id,
        duration_s=max(3600, int(estimated_hours * 3600)),
        gpu_count=max(1, gpu_count),
        min_gpu_memory_mib=max(1024, gpu_mem_gib * 1024),
        allowed_geos=[str(g).upper() for g in allowed_geos],
        max_price_usd_hour=float(max_price) if max_price is not None else None,
    )
    return asdict(spec)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/prepare")
async def prepare_repo(body: SubmitRequest) -> dict[str, str]:
    job_id = f"job-{uuid.uuid4().hex[:10]}"
    selected_image = body.image or _suggest_image(job_id)
    payload = {
        "job_id": job_id,
        "repo_url": body.repo_url,
        "branch": body.branch,
        "allowed_geos": body.allowed_geos,
        "max_price_usd_hour": body.max_price_usd_hour,
        "image": selected_image,
        "dry_run": True,
        "timeout": body.timeout,
        "verbose": body.verbose,
    }
    result = celery_client.send_task(
        "job.deploy_from_github", kwargs={"payload": payload}
    )

    now = int(time.time())
    redis_client.hset(
        f"job:{job_id}",
        mapping={
            "job_id": job_id,
            "status": "queued",
            "repo_url": body.repo_url,
            "branch": body.branch,
            "allowed_geos": json.dumps(body.allowed_geos),
            "max_price_usd_hour": (
                str(body.max_price_usd_hour)
                if body.max_price_usd_hour is not None
                else ""
            ),
            "image": selected_image,
            "selected_image": selected_image,
            "created_at": str(now),
            "updated_at": str(now),
            "celery_task_id": result.id,
        },
    )
    redis_client.expire(f"job:{job_id}", 24 * 60 * 60)
    redis_client.sadd("jobs:index", job_id)
    redis_client.expire("jobs:index", 24 * 60 * 60)

    return {
        "job_id": job_id,
        "status": "queued",
        "phase": "preparing",
        "selected_image": selected_image,
        "celery_task_id": result.id,
    }


@app.post("/submit")
async def submit_repo(body: SubmitRequest) -> dict[str, str]:
    return await prepare_repo(body)


@app.post("/jobs/{job_id}/execute")
async def execute_prepared_job(job_id: str, body: ExecuteRequest) -> dict[str, str]:
    job = _read_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")

    dispatch_ready_raw = job.get("dispatch_ready")
    if isinstance(dispatch_ready_raw, bool):
        dispatch_ready = dispatch_ready_raw
    elif isinstance(dispatch_ready_raw, str):
        dispatch_ready = dispatch_ready_raw.strip().lower() in {"1", "true", "yes"}
    else:
        dispatch_ready = False
    if not dispatch_ready and str(job.get("status") or "") != "prepared":
        raise HTTPException(
            status_code=409,
            detail="job is not prepared for deployment yet",
        )

    payload = {
        "job_id": job_id,
        "image": body.image,
        "namespace": body.namespace,
    }
    result = celery_client.send_task(
        "job.execute_prepared", kwargs={"payload": payload}
    )
    now = int(time.time())
    redis_client.hset(
        f"job:{job_id}",
        mapping={
            "status": "execution_queued",
            "updated_at": str(now),
            "execution_task_id": result.id,
            "image": body.image or str(job.get("selected_image") or ""),
        },
    )

    return {
        "job_id": job_id,
        "status": "execution_queued",
        "phase": "executing",
        "celery_task_id": result.id,
    }


@app.get("/jobs")
async def list_jobs() -> dict[str, object]:
    job_ids = sorted(redis_client.smembers("jobs:index"))
    jobs: list[dict[str, object]] = []
    for job_id in job_ids:
        job = _read_job(job_id)
        if job:
            job["estimated_job_spec"] = _estimate_job_spec(job_id, job)
            jobs.append(job)
    jobs.sort(key=lambda item: int(item.get("created_at", 0)), reverse=True)
    return {"count": len(jobs), "jobs": jobs}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, object]:
    job = _read_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    task_id = job.get("celery_task_id")
    if isinstance(task_id, str) and task_id:
        job["celery_state"] = celery_client.AsyncResult(task_id).state
    execution_task_id = job.get("execution_task_id")
    if isinstance(execution_task_id, str) and execution_task_id:
        job["execution_celery_state"] = celery_client.AsyncResult(
            execution_task_id
        ).state
    job["estimated_job_spec"] = _estimate_job_spec(job_id, job)
    return job


@app.get("/jobs/{job_id}/files")
async def get_job_files(job_id: str, stage: str = "prepared") -> dict[str, object]:
    stage_norm = stage.strip().lower()
    if stage_norm not in {"prepared", "source"}:
        raise HTTPException(
            status_code=400, detail="stage must be 'prepared' or 'source'"
        )

    keys: list[tuple[str, str]]
    if stage_norm == "prepared":
        keys = [("prepared", f"vfs:{job_id}:prepared"), ("source", f"vfs:{job_id}")]
    else:
        keys = [("source", f"vfs:{job_id}")]

    vfs = None
    selected_stage = ""
    for label, key in keys:
        try:
            vfs = VirtualFileSystem.from_redis(redis_client, key)
            selected_stage = label
            break
        except KeyError:
            continue
    if vfs is None:
        raise HTTPException(status_code=404, detail=f"vfs not found for job {job_id}")

    return {
        "job_id": job_id,
        "stage": selected_stage,
        "root_url": vfs.root_url,
        "branch": vfs.branch,
        "file_count": len(vfs.tree),
        "text_file_count": len(vfs.files),
        "binary_file_count": len(vfs.binary_files),
        "tree": vfs.tree,
        "key_files": vfs.relevant_files(max_items=15),
    }


if __name__ == "__main__":
    port = int(os.getenv("BACKEND_PORT", 5000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
