from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from celery import Celery
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import redis
import requests

from lib.vfs import VirtualFileSystem

from claude_agent_sdk import ClaudeAgentOptions, query

try:
    from git import Repo
except Exception:
    Repo = None


def _load_env() -> None:
    here = Path(__file__).resolve()
    candidates = [
        here.parent / ".env",
        here.parent.parent / ".env",
        here.parent.parent.parent / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate, override=False)


_load_env()
log = logging.getLogger(__name__)


def _resolve_redis_url() -> str:
    raw = os.getenv("REDIS_URL", "redis://localhost:6379")
    if "$" not in raw:
        return raw
    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    db = os.getenv("REDIS_DB", "0")
    return f"redis://{host}:{int(port)}/{db}"


REDIS_URL = _resolve_redis_url()
app = Celery("worker", broker=REDIS_URL, backend=REDIS_URL)


class RepoSubmitPayload(BaseModel):
    repo_url: str
    branch: str = "main"
    job_id: str = Field(default_factory=lambda: f"job-{uuid.uuid4().hex[:10]}")
    allowed_geos: list[str] = Field(default_factory=lambda: ["FR", "DE", "ES"])
    max_price_usd_hour: float | None = None
    image: str | None = None
    dry_run: bool = False
    timeout: int = 300
    verbose: bool = False


class ExecutePreparedPayload(BaseModel):
    job_id: str
    image: str | None = None
    namespace: str | None = None


class RepoAnalysis(BaseModel):
    framework: str
    entrypoint: str
    gpu_count: int
    gpu_mem_gib: int
    estimated_hours: float
    requires_dockerfile: bool
    dependencies: list[str]
    notes: str


def _redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _update_job(job_id: str, **fields: Any) -> None:
    client = _redis()
    payload = {
        k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        for k, v in fields.items()
    }
    payload["updated_at"] = str(int(time.time()))
    client.hset(f"job:{job_id}", mapping=payload)
    client.expire(f"job:{job_id}", 24 * 60 * 60)
    client.sadd("jobs:index", job_id)
    client.expire("jobs:index", 24 * 60 * 60)


def _decode_value(value: str) -> object:
    try:
        return json.loads(value)
    except Exception:
        return value


def _read_job(job_id: str) -> dict[str, Any] | None:
    raw = _redis().hgetall(f"job:{job_id}")
    if not raw:
        return None
    return {k: _decode_value(v) for k, v in raw.items()}


def _clone_repo(repo_url: str, branch: str, target_dir: str) -> None:
    if Repo is not None:
        try:
            Repo.clone_from(repo_url, target_dir, branch=branch, depth=1)
            return
        except Exception:
            pass

    git_path = shutil.which("git")
    if git_path:
        subprocess.run(
            [
                git_path,
                "clone",
                "--depth",
                "1",
                "--branch",
                branch,
                repo_url,
                target_dir,
            ],
            check=True,
        )
        return

    if "github.com" in repo_url:
        _clone_github_archive(repo_url=repo_url, branch=branch, target_dir=target_dir)
        return

    raise RuntimeError(
        "git executable not found in container and repo is not a GitHub URL for archive fallback"
    )


def _clone_github_archive(repo_url: str, branch: str, target_dir: str) -> None:
    cleaned = repo_url.strip().rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    parts = cleaned.split("/")
    if len(parts) < 2:
        raise ValueError(f"invalid GitHub repo URL: {repo_url}")
    owner = parts[-2]
    repo = parts[-1]

    candidates = [
        f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip",
        f"https://github.com/{owner}/{repo}/archive/refs/tags/{branch}.zip",
    ]

    last_error = None
    for url in candidates:
        try:
            response = requests.get(url, timeout=60)
            if response.status_code != 200:
                continue
            with zipfile.ZipFile(BytesIO(response.content)) as archive:
                archive.extractall(target_dir)
            extracted_roots = [p for p in Path(target_dir).iterdir() if p.is_dir()]
            if len(extracted_roots) == 1:
                root = extracted_roots[0]
                for item in root.iterdir():
                    item.rename(Path(target_dir) / item.name)
                root.rmdir()
            return
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(
        f"failed to clone GitHub repository archive: {repo_url}"
    ) from last_error


def _build_agent_prompt(vfs: VirtualFileSystem) -> str:
    relevant = vfs.relevant_files()
    relevant_text = "\n\n".join(
        f"FILE: {path}\n{text[:12000]}" for path, text in list(relevant.items())[:20]
    )
    return (
        "Analyze this ML training repository and return JSON only with keys: "
        "framework, entrypoint, gpu_count, gpu_mem_gib, estimated_hours, "
        "requires_dockerfile, dependencies, notes.\n"
        "Use conservative defaults when uncertain.\n\n"
        "Repository tree:\n"
        f"{vfs.tree_summary(max_entries=200)}\n\n"
        "Key files:\n"
        f"{relevant_text}"
    )


def _normalize_result(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value)
    except TypeError:
        return str(value)


def _preview_text(text: str, limit: int = 200) -> str:
    snippet = " ".join(text.strip().split())
    if len(snippet) <= limit:
        return snippet
    return f"{snippet[:limit]}..."


def _extract_content_text(content: object) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str) and text.strip():
                    chunks.append(text)
                continue
            text = getattr(item, "text", None)
            if isinstance(text, str) and text.strip():
                chunks.append(text)
        joined = "\n".join(chunk for chunk in chunks if chunk.strip())
        return joined if joined.strip() else None
    return None


def _extract_message_output(message: object) -> str | None:
    for key in ("result", "output", "value", "text"):
        if hasattr(message, key):
            value = getattr(message, key)
            if value is not None and value != "":
                return _normalize_result(value)
    content_text = _extract_content_text(getattr(message, "content", None))
    if content_text and content_text.strip():
        return content_text
    return None


def _describe_message(message: object) -> str:
    parts = [message.__class__.__name__]
    for key in ("type", "subtype", "role", "tool_name", "tool"):
        value = getattr(message, key, None)
        if value:
            parts.append(f"{key}={value}")
    result = getattr(message, "result", None) if hasattr(message, "result") else None
    if result not in (None, ""):
        preview = _preview_text(_normalize_result(result), limit=160)
        parts.append(f"result_preview={preview}")
    content_text = _extract_content_text(getattr(message, "content", None))
    if isinstance(content_text, str) and content_text.strip():
        preview = _preview_text(content_text, limit=160)
        parts.append(f"content_preview={preview}")
    return " | ".join(parts)


async def _run_agent(prompt: str, timeout: int = 300, verbose: bool = False) -> str:
    if query is None or ClaudeAgentOptions is None:
        raise RuntimeError("claude_agent_sdk is required")

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep"],
        permission_mode="bypassPermissions",
    )

    async def _collect() -> str:
        final: str | None = None
        async for message in query(prompt=prompt, options=options):
            if verbose:
                log.info("agent message: %s", _describe_message(message))
            extracted = _extract_message_output(message)
            if extracted is not None:
                final = extracted
                if verbose:
                    log.info("agent result: %s", _preview_text(final, limit=300))
        return _normalize_result(final)

    if timeout > 0:
        return await asyncio.wait_for(_collect(), timeout=timeout)
    return await _collect()


def _parse_analysis(raw: str) -> RepoAnalysis:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    data = json.loads(cleaned)
    return RepoAnalysis.model_validate(data)


def _docker_base(framework: str) -> str:
    if framework in {"pytorch", "huggingface"}:
        return "pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime"
    if framework == "tensorflow":
        return "tensorflow/tensorflow:2.15.0-gpu"
    if framework == "jax":
        return "nvcr.io/nvidia/jax:23.10-paxml-py3"
    return "python:3.11-slim"


def _default_dockerfile(analysis: RepoAnalysis) -> str:
    base = _docker_base(analysis.framework)
    entrypoint = analysis.entrypoint
    return (
        f"FROM {base}\n\n"
        "WORKDIR /workspace\n"
        "COPY . /workspace\n"
        "RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi\n"
        f'CMD ["python", "{entrypoint}"]\n'
    )


def _manifest_yaml(job_id: str, analysis: RepoAnalysis, allowed_geos: list[str]) -> str:
    duration_s = max(3600, int(analysis.estimated_hours * 3600))
    allowed = ",".join(f'"{geo}"' for geo in allowed_geos)
    return (
        "apiVersion: energy.io/v1alpha1\n"
        "kind: TrainingJob\n"
        "metadata:\n"
        f"  name: {job_id}\n"
        "spec:\n"
        f"  durationSeconds: {duration_s}\n"
        f"  gpuCount: {analysis.gpu_count}\n"
        f"  minGpuMemoryMib: {analysis.gpu_mem_gib * 1024}\n"
        f"  allowedGeos: [{allowed}]\n"
        f"  framework: {analysis.framework}\n"
        f"  entrypoint: {analysis.entrypoint}\n"
    )


def _schedule_choice(allowed_geos: list[str]) -> dict[str, str]:
    preferred = allowed_geos[0] if allowed_geos else "FR"
    return {
        "geo": preferred,
        "provider": "GCP",
        "region": "europe-west4",
        "sku": "demo-pod",
    }


def _job_name(job_id: str) -> str:
    safe = re.sub(r"[^a-z0-9-]", "-", job_id.lower())
    safe = re.sub(r"-+", "-", safe).strip("-")
    if not safe:
        safe = "training-job"
    return (safe[:45] + "-run")[:52]


def _parse_rails_patch_decision(patch_b64: str) -> dict[str, Any] | None:
    try:
        patch_raw = base64.b64decode(patch_b64).decode("utf-8")
        operations = json.loads(patch_raw)
    except Exception:
        return None

    decision: dict[str, Any] = {}
    for op in operations:
        path = op.get("path")
        value = op.get("value")
        if path == "/spec/nodeSelector" and isinstance(value, dict):
            decision["geo"] = value.get("energy.io/geo")
            decision["provider"] = value.get("energy.io/provider")
            decision["region"] = value.get("energy.io/region")
            decision["sku"] = value.get("energy.io/sku")
        elif path == "/metadata/annotations/energy.io~1window-start":
            decision["start_ts"] = value
        elif path == "/metadata/annotations/energy.io~1window-end":
            decision["end_ts"] = value
        elif path == "/metadata/annotations/energy.io~1score":
            decision["score"] = value

    required = ["geo", "provider", "region", "sku"]
    if any(not decision.get(k) for k in required):
        return None
    return decision


def _schedule_with_rails(
    *,
    job_id: str,
    allowed_geos: list[str],
    analysis: RepoAnalysis,
    max_price_usd_hour: float | None,
) -> dict[str, Any] | None:
    base_url = os.getenv("RAILS_API_URL", "http://rails-control-plane:3001").rstrip("/")
    url = f"{base_url}/webhook/pods"
    duration_s = max(3600, int(analysis.estimated_hours * 3600))

    annotations: dict[str, str] = {
        "energy.io/duration-s": str(duration_s),
        "energy.io/min-gpu-memory-mib": str(analysis.gpu_mem_gib * 1024),
        "energy.io/allowed-geos": ",".join(allowed_geos),
    }
    if max_price_usd_hour is not None:
        annotations["energy.io/max-price-usd-hour"] = str(max_price_usd_hour)

    review = {
        "request": {
            "uid": f"worker-{job_id}",
            "object": {
                "metadata": {
                    "name": job_id,
                    "labels": {
                        "energy-scheduling": "true",
                        "job-id": job_id,
                    },
                    "annotations": annotations,
                },
                "spec": {
                    "containers": [
                        {
                            "name": "trainer",
                            "resources": {
                                "limits": {
                                    "nvidia.com/gpu": analysis.gpu_count,
                                }
                            },
                        }
                    ]
                },
            },
        }
    }

    try:
        response = requests.post(url, json=review, timeout=30)
        response.raise_for_status()
        body = response.json()
        patch = (
            body.get("response", {}).get("patch") if isinstance(body, dict) else None
        )
        if not isinstance(patch, str) or not patch:
            return None
        return _parse_rails_patch_decision(patch)
    except Exception as exc:
        log.warning("rails scheduling request failed: %s", exc)
        return None


def _dispatch_job_to_openshift(
    *,
    job_id: str,
    image: str,
    namespace: str,
    decision: dict[str, Any],
) -> dict[str, Any]:
    try:
        from kubernetes import client as k8s_client
        from kubernetes import config as k8s_config
    except Exception as exc:
        raise RuntimeError(
            "kubernetes package missing; add it to requirements.txt"
        ) from exc

    try:
        k8s_config.load_incluster_config()
    except Exception:
        k8s_config.load_kube_config()

    name = _job_name(job_id)
    labels = {
        "app": "repo-training",
        "job-id": job_id,
        "energy.io/geo": str(decision.get("geo", "")),
        "energy.io/provider": str(decision.get("provider", "")),
        "energy.io/region": str(decision.get("region", "")),
        "energy.io/sku": str(decision.get("sku", "")),
    }
    annotations = {
        "energy.io/window-start": str(decision.get("start_ts", "")),
        "energy.io/window-end": str(decision.get("end_ts", "")),
        "energy.io/score": str(decision.get("score", "")),
    }

    env_items = [
        k8s_client.V1EnvVar(name="JOB_ID", value=job_id),
        k8s_client.V1EnvVar(name="ENERGY_GEO", value=str(decision.get("geo", ""))),
        k8s_client.V1EnvVar(
            name="ENERGY_PROVIDER", value=str(decision.get("provider", ""))
        ),
        k8s_client.V1EnvVar(
            name="ENERGY_REGION", value=str(decision.get("region", ""))
        ),
        k8s_client.V1EnvVar(name="ENERGY_SKU", value=str(decision.get("sku", ""))),
    ]

    pull_secret = os.getenv("IMAGE_PULL_SECRET", "").strip()
    image_pull_secrets = (
        [k8s_client.V1LocalObjectReference(name=pull_secret)] if pull_secret else None
    )

    container = k8s_client.V1Container(
        name="trainer",
        image=image,
        image_pull_policy=os.getenv("JOB_IMAGE_PULL_POLICY", "Always"),
        env=env_items,
        resources=k8s_client.V1ResourceRequirements(
            requests={"cpu": "250m", "memory": "512Mi"},
            limits={"cpu": "2", "memory": "4Gi"},
        ),
    )

    template = k8s_client.V1PodTemplateSpec(
        metadata=k8s_client.V1ObjectMeta(labels=labels, annotations=annotations),
        spec=k8s_client.V1PodSpec(
            restart_policy="Never",
            containers=[container],
            image_pull_secrets=image_pull_secrets,
        ),
    )

    job = k8s_client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=k8s_client.V1ObjectMeta(name=name, labels=labels),
        spec=k8s_client.V1JobSpec(backoff_limit=0, template=template),
    )

    api = k8s_client.BatchV1Api()
    created = api.create_namespaced_job(namespace=namespace, body=job)
    return {
        "job_name": created.metadata.name,
        "namespace": namespace,
    }


def _analyze_from_vfs(job_id: str, timeout: int, verbose: bool) -> RepoAnalysis:
    vfs = VirtualFileSystem.from_redis(_redis(), f"vfs:{job_id}")
    prompt = _build_agent_prompt(vfs)
    raw = asyncio.run(_run_agent(prompt, timeout=timeout, verbose=verbose))
    return _parse_analysis(raw)


def _generate_manifest_for_job(
    job_id: str, analysis: RepoAnalysis, allowed_geos: list[str]
) -> str:
    return _manifest_yaml(job_id, analysis, allowed_geos)


@app.task(bind=True, name="repo.analyze", max_retries=1, default_retry_delay=10)
def analyze_repository(self, payload: dict[str, Any]) -> dict[str, Any]:
    job_id = str(payload.get("job_id") or "")
    timeout = int(payload.get("timeout") or 300)
    verbose = bool(payload.get("verbose") or False)
    try:
        analysis = _analyze_from_vfs(job_id=job_id, timeout=timeout, verbose=verbose)
    except Exception as exc:
        raise self.retry(exc=exc)

    return analysis.model_dump()


@app.task(bind=True, name="repo.generate_manifest")
def generate_manifest(self, payload: dict[str, Any]) -> dict[str, Any]:
    job_id = str(payload.get("job_id") or "")
    allowed_geos = payload.get("allowed_geos") or ["FR", "DE", "ES"]
    analysis = RepoAnalysis.model_validate(payload.get("analysis") or {})
    manifest = _generate_manifest_for_job(job_id, analysis, allowed_geos)
    return {"manifest_yaml": manifest}


@app.task(
    bind=True, name="job.deploy_from_github", max_retries=1, default_retry_delay=20
)
def deploy_from_github(self, payload: dict[str, Any]) -> dict[str, Any]:
    inp = RepoSubmitPayload.model_validate(payload)
    _update_job(
        inp.job_id,
        status="queued",
        repo_url=inp.repo_url,
        branch=inp.branch,
        dry_run=inp.dry_run,
        created_at=int(time.time()),
        celery_task_id=self.request.id,
    )

    try:
        _update_job(inp.job_id, status="cloning")
        with tempfile.TemporaryDirectory(prefix=f"repo-{inp.job_id}-") as tmp_dir:
            _clone_repo(inp.repo_url, inp.branch, tmp_dir)
            vfs = VirtualFileSystem.from_directory(inp.repo_url, inp.branch, tmp_dir)
            vfs.to_redis(_redis(), f"vfs:{inp.job_id}", ttl_s=3600)

        _update_job(inp.job_id, status="analyzing")
        analysis = _analyze_from_vfs(
            job_id=inp.job_id,
            timeout=inp.timeout,
            verbose=inp.verbose,
        )

        dockerfile_content = ""
        if analysis.requires_dockerfile:
            dockerfile_content = _default_dockerfile(analysis)

        _update_job(inp.job_id, status="scheduling")
        decision = _schedule_with_rails(
            job_id=inp.job_id,
            allowed_geos=inp.allowed_geos,
            analysis=analysis,
            max_price_usd_hour=inp.max_price_usd_hour,
        )
        if not decision:
            decision = _schedule_choice(inp.allowed_geos)

        _update_job(inp.job_id, status="generating_manifest")
        manifest_yaml = _generate_manifest_for_job(
            job_id=inp.job_id,
            analysis=analysis,
            allowed_geos=inp.allowed_geos,
        )

        cloud_mode = os.getenv("CLOUD_MODE", "mock").strip().lower()
        selected_image = inp.image or os.getenv("DEFAULT_TRAINING_IMAGE", "").strip()
        status = (
            "prepared"
            if inp.dry_run
            else ("mock_dispatched" if cloud_mode == "mock" else "dispatched")
        )
        openshift_job: dict[str, Any] | None = None
        if (not inp.dry_run) and cloud_mode != "mock":
            if not selected_image:
                raise RuntimeError("image is required when CLOUD_MODE is not mock")
            _update_job(inp.job_id, status="dispatching", image=selected_image)
            namespace = os.getenv("OPENSHIFT_NAMESPACE", "drosel-ieu2022-dev")
            openshift_job = _dispatch_job_to_openshift(
                job_id=inp.job_id,
                image=selected_image,
                namespace=namespace,
                decision=decision,
            )

        _update_job(
            inp.job_id,
            status=status,
            analysis=analysis.model_dump(),
            scheduling_decision=decision,
            manifest_yaml=manifest_yaml,
            dockerfile_content=dockerfile_content,
            selected_image=selected_image,
            openshift_job=openshift_job or {},
        )

        return {
            "job_id": inp.job_id,
            "status": status,
            "analysis": analysis.model_dump(),
            "scheduling_decision": decision,
            "manifest_yaml": manifest_yaml,
            "dockerfile_content": dockerfile_content,
            "selected_image": selected_image,
            "openshift_job": openshift_job,
        }
    except Exception as exc:
        log.exception("deploy_from_github failed")
        _update_job(inp.job_id, status="failed", error=str(exc))
        raise self.retry(exc=exc)


@app.task(bind=True, name="job.execute_prepared", max_retries=1, default_retry_delay=15)
def execute_prepared(self, payload: dict[str, Any]) -> dict[str, Any]:
    inp = ExecutePreparedPayload.model_validate(payload)
    job = _read_job(inp.job_id)
    if not job:
        raise RuntimeError(f"job not found: {inp.job_id}")

    decision = job.get("scheduling_decision")
    if not isinstance(decision, dict):
        raise RuntimeError("scheduling_decision missing; prepare the job first")

    image = inp.image or str(job.get("selected_image") or "").strip()
    if not image:
        image = os.getenv("DEFAULT_TRAINING_IMAGE", "").strip()
    if not image:
        raise RuntimeError("image is required to execute prepared job")

    namespace = inp.namespace or os.getenv("OPENSHIFT_NAMESPACE", "drosel-ieu2022-dev")
    _update_job(inp.job_id, status="dispatching", image=image)

    try:
        openshift_job = _dispatch_job_to_openshift(
            job_id=inp.job_id,
            image=image,
            namespace=namespace,
            decision=decision,
        )
    except Exception as exc:
        _update_job(inp.job_id, status="failed", error=str(exc))
        raise self.retry(exc=exc)

    _update_job(
        inp.job_id,
        status="dispatched",
        image=image,
        openshift_job=openshift_job,
    )
    return {
        "job_id": inp.job_id,
        "status": "dispatched",
        "image": image,
        "openshift_job": openshift_job,
    }


@app.task(bind=True, max_retries=1, default_retry_delay=15)
def carryout_task(self, task_input: dict[str, Any]) -> dict[str, Any]:
    try:
        inp = RepoSubmitPayload.model_validate(task_input)
        return deploy_from_github.run(payload=inp.model_dump())
    except Exception as exc:
        raise self.retry(exc=exc)


@app.task
def simple_task(message: str) -> str:
    time.sleep(1)
    return f"Processed: {message}"


if __name__ == "__main__":
    app.worker_main(argv=["worker", "--loglevel=info"])
