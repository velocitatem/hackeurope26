from __future__ import annotations

import asyncio
import base64
import difflib
import json
import logging
import os
import re
import shlex
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
from pydantic import BaseModel, Field, field_validator
import redis
import requests

from lib.vfs import VirtualFileSystem

try:
    from claude_agent_sdk import ClaudeAgentOptions, query
except Exception:
    ClaudeAgentOptions = None
    query = None

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
SCHEDULING_MODE = os.getenv("SCHEDULING_MODE", "prepared").strip().lower()
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


class AgentAutonomyResult(BaseModel):
    framework: str
    entrypoint: str
    gpu_count: int
    gpu_mem_gib: int
    estimated_hours: float
    requires_dockerfile: bool
    dependencies: list[str] = Field(default_factory=list)
    notes: str = ""
    dockerfile_path: str = "Dockerfile"
    training_command: list[str] = Field(default_factory=list)
    codecarbon_summary: str = ""

    @field_validator("dockerfile_path", mode="before")
    @classmethod
    def _normalize_dockerfile_path(cls, value: object) -> str:
        text = str(value or "").strip()
        return text or "Dockerfile"

    @field_validator("dependencies", mode="before")
    @classmethod
    def _normalize_dependencies(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        if not text:
            return []
        if "," in text:
            return [part.strip() for part in text.split(",") if part.strip()]
        if "\n" in text:
            return [part.strip() for part in text.splitlines() if part.strip()]
        return [text]

    @field_validator("training_command", mode="before")
    @classmethod
    def _normalize_training_command(cls, value: object) -> list[str]:
        def _tokens(text: str) -> list[str]:
            stripped = text.strip()
            if not stripped:
                return []
            try:
                parts = shlex.split(stripped)
            except Exception:
                parts = stripped.split()
            return [part for part in parts if part.strip()]

        if value is None:
            return []
        if isinstance(value, list):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            if len(cleaned) == 1:
                parsed = _tokens(cleaned[0])
                if parsed:
                    return parsed
            return cleaned
        if isinstance(value, str):
            return _tokens(value)
        return _tokens(str(value))


READ_ONLY_AGENT_TOOLS = ["Read", "Glob", "Grep"]
CODE_AGENT_TOOLS = ["Read", "Glob", "Grep", "Edit", "Write", "Bash"]


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


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _effective_gpu_count(requested: int) -> int:
    override_raw = os.getenv("GPU_COUNT_OVERRIDE", "").strip()
    if override_raw:
        try:
            return max(0, int(override_raw))
        except Exception:
            pass
    if _env_flag("DISABLE_GPU_REQUESTS", default=False):
        return 0
    return max(0, int(requested))


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


def _build_autonomous_code_prompt(
    job_id: str, selected_image: str | None = None
) -> str:
    image_note = selected_image.strip() if isinstance(selected_image, str) else ""
    image_hint = image_note or "<generate image externally if not provided>"
    return (
        "You are an autonomous AI code agent operating on a cloned training "
        "repository.\n"
        "Objectives:\n"
        "1) Integrate CodeCarbon instrumentation so training runs emit carbon "
        "metrics.\n"
        "2) Make concrete source-code edits in this repository.\n"
        "3) Ensure dependencies include CodeCarbon in the project's existing "
        "dependency system.\n"
        "4) Ensure a Dockerfile exists and starts the real training job "
        "entrypoint.\n"
        "5) Prefer minimal, targeted edits; do not rewrite the project.\n"
        "6) Validate by running lightweight checks only (syntax/help/import where "
        "possible).\n\n"
        "Hard requirements:\n"
        "- Detect the likely training entrypoint (script/module/command).\n"
        "- Add robust CodeCarbon tracker start/stop around training execution.\n"
        "- Keep the repository runnable without requiring cloud credentials.\n"
        "- If no clear insertion point exists, create a thin wrapper entrypoint.\n"
        "- If Dockerfile is missing, create one that installs deps and runs "
        "training.\n"
        "- Never output markdown in final response.\n"
        "- Final response must be strict JSON only with keys: framework, "
        "entrypoint, gpu_count, gpu_mem_gib, estimated_hours, "
        "requires_dockerfile, dependencies, notes, dockerfile_path, "
        "training_command, codecarbon_summary.\n\n"
        "Context:\n"
        f"- job_id: {job_id}\n"
        f"- preferred image tag: {image_hint}\n"
    )


def _strip_code_fence(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return cleaned


async def _run_agent(
    prompt: str,
    *,
    timeout: int = 300,
    verbose: bool = False,
    allowed_tools: list[str] | None = None,
    cwd: str | None = None,
    max_turns: int | None = None,
    system_prompt: str | None = None,
) -> str:
    if query is None or ClaudeAgentOptions is None:
        raise RuntimeError("claude_agent_sdk is required")

    options = ClaudeAgentOptions(
        allowed_tools=allowed_tools or READ_ONLY_AGENT_TOOLS,
        permission_mode="bypassPermissions",
        cwd=cwd,
        max_turns=max_turns,
        system_prompt=system_prompt,
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


def _parse_autonomous_result(raw: str) -> AgentAutonomyResult:
    cleaned = _strip_code_fence(raw)
    try:
        data = json.loads(cleaned)
    except Exception:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(cleaned[start : end + 1])
        else:
            raise
    return AgentAutonomyResult.model_validate(data)


def _collect_text_files(root: Path, max_file_kb: int = 512) -> dict[str, str]:
    max_file_bytes = max_file_kb * 1024
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        parts = set(path.relative_to(root).parts)
        if parts.intersection(
            {".git", "node_modules", ".venv", "venv", "dist", "build"}
        ):
            continue
        if path.stat().st_size > max_file_bytes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = path.relative_to(root).as_posix()
        files[rel] = text
    return files


def _build_unified_patch(
    before: dict[str, str], after: dict[str, str]
) -> tuple[str, list[str]]:
    changed = sorted(set(before) | set(after))
    patch_parts: list[str] = []
    changed_files: list[str] = []
    for rel in changed:
        old = before.get(rel)
        new = after.get(rel)
        if old == new:
            continue
        changed_files.append(rel)
        diff = difflib.unified_diff(
            (old or "").splitlines(),
            (new or "").splitlines(),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
            lineterm="",
        )
        patch_parts.append("\n".join(diff))
    return "\n\n".join(part for part in patch_parts if part), changed_files


def _dockerfile_has_entrypoint_or_cmd(dockerfile_text: str) -> bool:
    for line in dockerfile_text.splitlines():
        upper = line.strip().upper()
        if upper.startswith("ENTRYPOINT") or upper.startswith("CMD"):
            return True
    return False


def _ensure_dockerfile_with_entrypoint(
    repo_dir: Path,
    dockerfile_path: str,
    analysis: RepoAnalysis,
    training_command: list[str],
) -> str:
    rel = dockerfile_path.strip() or "Dockerfile"
    path = repo_dir / rel
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if _dockerfile_has_entrypoint_or_cmd(text):
            return rel

    if training_command:
        cmd = json.dumps(training_command)
        fallback = (
            f"FROM {_docker_base(analysis.framework)}\n\n"
            "WORKDIR /workspace\n"
            "COPY . /workspace\n"
            "RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi\n"
            f"CMD {cmd}\n"
        )
    else:
        fallback = _default_dockerfile(analysis)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fallback, encoding="utf-8")
    return rel


def _resolve_container_builder() -> str | None:
    docker_path = shutil.which("docker")
    if docker_path:
        return docker_path
    podman_path = shutil.which("podman")
    if podman_path:
        return podman_path
    return None


def _build_container_image(
    repo_dir: Path,
    image_tag: str,
    dockerfile_path: str,
    timeout_s: int,
) -> dict[str, Any]:
    builder = _resolve_container_builder()
    if not builder:
        raise RuntimeError("neither docker nor podman is available in worker runtime")

    dockerfile = Path(dockerfile_path)
    if dockerfile.is_absolute():
        dockerfile_arg = str(dockerfile)
    else:
        dockerfile_arg = str((repo_dir / dockerfile).resolve())
    command = [builder, "build", "-f", dockerfile_arg, "-t", image_tag, "."]
    result = subprocess.run(
        command,
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=False,
        timeout=max(120, timeout_s),
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        raise RuntimeError(
            f"image build failed with code {result.returncode}; "
            f"stderr={_preview_text(stderr, 500)} stdout={_preview_text(stdout, 500)}"
        )

    return {
        "builder": Path(builder).name,
        "command": " ".join(command),
        "image": image_tag,
        "stdout_preview": _preview_text(result.stdout or "", 500),
    }


def _parse_analysis(raw: str) -> RepoAnalysis:
    data = json.loads(_strip_code_fence(raw))
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
    gpu_count = _effective_gpu_count(analysis.gpu_count)

    annotations: dict[str, str] = {
        "energy.io/duration-s": str(duration_s),
        "energy.io/allowed-geos": ",".join(allowed_geos),
    }
    if gpu_count > 0:
        annotations["energy.io/min-gpu-memory-mib"] = str(
            max(1024, analysis.gpu_mem_gib * 1024)
        )
    if max_price_usd_hour is not None and max_price_usd_hour > 0:
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
                                    "nvidia.com/gpu": gpu_count,
                                }
                            },
                        }
                    ]
                },
            },
        }
    }

    try:
        log.info("calling rails webhook at %s for job %s", url, job_id)
        response = requests.post(url, json=review, timeout=30)
        response.raise_for_status()
        body = response.json()
        patch = (
            body.get("response", {}).get("patch") if isinstance(body, dict) else None
        )
        if not isinstance(patch, str) or not patch:
            log.warning(
                "rails returned no patch for job %s (status=%s)",
                job_id,
                response.status_code,
            )
            return None
        decision = _parse_rails_patch_decision(patch)
        if decision:
            log.info("rails scheduling decision for %s: %s", job_id, decision)
        return decision
    except Exception as exc:
        log.warning("rails scheduling request to %s failed: %s", url, exc)
        return None


def _dispatch_job_to_openshift(
    *,
    job_id: str,
    image: str,
    namespace: str,
    analysis: RepoAnalysis,
    allowed_geos: list[str],
    max_price_usd_hour: float | None,
    decision: dict[str, Any] | None = None,
    scheduling_mode: str = "prepared",
) -> dict[str, Any]:
    name = _job_name(job_id)
    auth_required = _env_flag("OPENSHIFT_AUTH_REQUIRED", default=False)
    gpu_count = _effective_gpu_count(analysis.gpu_count)

    try:
        from kubernetes import client as k8s_client
        from kubernetes import config as k8s_config
    except Exception as exc:
        if not auth_required:
            reason = f"kubernetes client unavailable: {exc}"
            log.warning("dispatch deferred for job %s: %s", job_id, reason)
            return {
                "job_name": name,
                "namespace": namespace,
                "image": image,
                "dispatched": False,
                "mode": "planned",
                "scheduling_mode": scheduling_mode,
                "reason": reason,
            }
        raise RuntimeError(
            "kubernetes package missing; add it to requirements.txt"
        ) from exc

    auth_mode = ""
    try:
        k8s_config.load_incluster_config()
        auth_mode = "incluster"
    except Exception as incluster_exc:
        try:
            k8s_config.load_kube_config()
            auth_mode = "kubeconfig"
        except Exception as kubeconfig_exc:
            reason = (
                "unable to load kubernetes auth from incluster or kubeconfig; "
                f"incluster_error={incluster_exc}; kubeconfig_error={kubeconfig_exc}"
            )
            if not auth_required:
                log.warning("dispatch deferred for job %s: %s", job_id, reason)
                return {
                    "job_name": name,
                    "namespace": namespace,
                    "image": image,
                    "dispatched": False,
                    "mode": "planned",
                    "scheduling_mode": scheduling_mode,
                    "reason": reason,
                }
            raise RuntimeError(reason) from kubeconfig_exc

    # -- Labels --
    labels = {
        "app": "repo-training",
        "job-id": job_id,
        "energy-scheduling": "true",
    }

    # -- Annotations (base) --
    duration_s = max(3600, int(analysis.estimated_hours * 3600))
    annotations: dict[str, str] = {
        "energy.io/duration-s": str(duration_s),
        "energy.io/allowed-geos": ",".join(allowed_geos or ["FR", "DE", "ES"]),
        "energy.io/decision-source": scheduling_mode,
    }
    if gpu_count > 0:
        annotations["energy.io/min-gpu-memory-mib"] = str(
            max(1024, analysis.gpu_mem_gib * 1024)
        )
    if max_price_usd_hour is not None and max_price_usd_hour > 0:
        annotations["energy.io/max-price-usd-hour"] = str(max_price_usd_hour)

    # -- Scheduling decision fields (prepared mode bakes them in) --
    node_selector: dict[str, str] | None = None
    scheduler_name = "default-scheduler"
    prepared_scheduler_name = (
        os.getenv("PREPARED_SCHEDULER_NAME", "secondary-scheduler").strip()
        or "default-scheduler"
    )
    apply_prepared_selector = _env_flag("PREPARED_APPLY_NODE_SELECTOR", default=True)

    if isinstance(decision, dict):
        # Propagate decision into annotations
        for key in ("start_ts", "end_ts", "score", "provider", "region", "sku"):
            value = str(decision.get(key, "")).strip()
            if not value:
                continue
            anno_key = {
                "start_ts": "energy.io/window-start",
                "end_ts": "energy.io/window-end",
                "score": "energy.io/score",
                "provider": "energy.io/provider",
                "region": "energy.io/region",
                "sku": "energy.io/sku",
            }[key]
            annotations[anno_key] = value

        # In prepared mode, set nodeSelector and schedulerName directly
        if scheduling_mode == "prepared":
            scheduler_name = prepared_scheduler_name
            selector: dict[str, str] = {}
            for sel_key in ("geo", "provider", "region", "sku"):
                sel_val = str(decision.get(sel_key, "")).strip()
                if sel_val:
                    selector[f"energy.io/{sel_key}"] = sel_val
            if selector and apply_prepared_selector:
                node_selector = selector

    # -- Env vars --
    env_items = [
        k8s_client.V1EnvVar(name="JOB_ID", value=job_id),
        k8s_client.V1EnvVar(
            name="ENERGY_ALLOWED_GEOS", value=annotations["energy.io/allowed-geos"]
        ),
        k8s_client.V1EnvVar(name="TRAINING_ENTRYPOINT", value=analysis.entrypoint),
        k8s_client.V1EnvVar(name="SCHEDULING_MODE", value=scheduling_mode),
    ]
    if isinstance(decision, dict):
        for env_key, env_name in (
            ("geo", "ENERGY_GEO"),
            ("provider", "ENERGY_PROVIDER"),
            ("region", "ENERGY_REGION"),
            ("sku", "ENERGY_SKU"),
        ):
            env_val = str(decision.get(env_key, "")).strip()
            if env_val:
                env_items.append(k8s_client.V1EnvVar(name=env_name, value=env_val))

    # -- Container --
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
            limits={
                "cpu": "2",
                "memory": "4Gi",
                **({"nvidia.com/gpu": gpu_count} if gpu_count > 0 else {}),
            },
        ),
    )

    # -- Pod spec --
    pod_spec = k8s_client.V1PodSpec(
        restart_policy="Never",
        containers=[container],
        image_pull_secrets=image_pull_secrets,
        scheduler_name=scheduler_name,
    )
    if node_selector:
        pod_spec.node_selector = node_selector

    template = k8s_client.V1PodTemplateSpec(
        metadata=k8s_client.V1ObjectMeta(labels=labels, annotations=annotations),
        spec=pod_spec,
    )

    job = k8s_client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=k8s_client.V1ObjectMeta(name=name, labels=labels),
        spec=k8s_client.V1JobSpec(backoff_limit=0, template=template),
    )

    try:
        api = k8s_client.BatchV1Api()
        created = api.create_namespaced_job(namespace=namespace, body=job)
    except Exception as exc:
        reason = f"openshift job creation failed: {exc}"
        if not auth_required:
            log.warning("dispatch deferred for job %s: %s", job_id, reason)
            return {
                "job_name": name,
                "namespace": namespace,
                "image": image,
                "dispatched": False,
                "mode": "planned",
                "scheduling_mode": scheduling_mode,
                "reason": reason,
            }
        raise

    return {
        "job_name": created.metadata.name,
        "namespace": namespace,
        "image": image,
        "dispatched": True,
        "mode": "openshift",
        "scheduling_mode": scheduling_mode,
        "auth_mode": auth_mode,
    }


def _analyze_from_vfs(job_id: str, timeout: int, verbose: bool) -> RepoAnalysis:
    vfs = VirtualFileSystem.from_redis(_redis(), f"vfs:{job_id}")
    prompt = _build_agent_prompt(vfs)
    raw = asyncio.run(
        _run_agent(
            prompt,
            timeout=timeout,
            verbose=verbose,
            allowed_tools=READ_ONLY_AGENT_TOOLS,
        )
    )
    return _parse_analysis(raw)


def _autonomous_prepare_repo(
    *,
    repo_dir: Path,
    job_id: str,
    timeout: int,
    verbose: bool,
    selected_image: str | None,
) -> tuple[RepoAnalysis, str, str, list[str], dict[str, Any], str]:
    before_files = _collect_text_files(repo_dir)
    prompt = _build_autonomous_code_prompt(job_id=job_id, selected_image=selected_image)
    raw = asyncio.run(
        _run_agent(
            prompt,
            timeout=max(timeout, 300),
            verbose=verbose,
            allowed_tools=CODE_AGENT_TOOLS,
            cwd=str(repo_dir),
            max_turns=60,
        )
    )
    autonomy = _parse_autonomous_result(raw)
    analysis = RepoAnalysis(
        framework=autonomy.framework,
        entrypoint=autonomy.entrypoint,
        gpu_count=autonomy.gpu_count,
        gpu_mem_gib=autonomy.gpu_mem_gib,
        estimated_hours=autonomy.estimated_hours,
        requires_dockerfile=autonomy.requires_dockerfile,
        dependencies=autonomy.dependencies,
        notes=autonomy.notes,
    )
    dockerfile_rel = _ensure_dockerfile_with_entrypoint(
        repo_dir=repo_dir,
        dockerfile_path=autonomy.dockerfile_path,
        analysis=analysis,
        training_command=autonomy.training_command,
    )
    after_files = _collect_text_files(repo_dir)
    patch_text, changed_files = _build_unified_patch(before_files, after_files)
    max_patch_chars = int(os.getenv("MAX_GENERATED_PATCH_CHARS", "200000"))
    patch_truncated = False
    if len(patch_text) > max_patch_chars:
        patch_text = patch_text[:max_patch_chars] + "\n...<patch truncated>\n"
        patch_truncated = True
    dockerfile_content = (repo_dir / dockerfile_rel).read_text(encoding="utf-8")
    autonomy_payload = {
        "codecarbon_summary": autonomy.codecarbon_summary,
        "training_command": autonomy.training_command,
        "dockerfile_path": dockerfile_rel,
        "changed_files": changed_files,
        "patch_truncated": patch_truncated,
    }
    return (
        analysis,
        dockerfile_content,
        dockerfile_rel,
        changed_files,
        autonomy_payload,
        patch_text,
    )


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
    selected_image = inp.image or os.getenv("DEFAULT_TRAINING_IMAGE", "").strip()
    if not selected_image:
        image_repo = os.getenv(
            "DEFAULT_IMAGE_REPO", "quay.io/drosel_ieu2022/hackeurope-train"
        ).strip()
        selected_image = f"{image_repo}:{inp.job_id}"
    _update_job(
        inp.job_id,
        status="queued",
        repo_url=inp.repo_url,
        branch=inp.branch,
        dry_run=inp.dry_run,
        selected_image=selected_image,
        created_at=int(time.time()),
        celery_task_id=self.request.id,
    )

    try:
        _update_job(inp.job_id, status="cloning")
        with tempfile.TemporaryDirectory(prefix=f"repo-{inp.job_id}-") as tmp_dir:
            repo_dir = Path(tmp_dir)
            _clone_repo(inp.repo_url, inp.branch, tmp_dir)
            vfs = VirtualFileSystem.from_directory(inp.repo_url, inp.branch, repo_dir)
            vfs.to_redis(_redis(), f"vfs:{inp.job_id}", ttl_s=3600)

            _update_job(inp.job_id, status="agent_coding")
            (
                analysis,
                dockerfile_content,
                dockerfile_path,
                changed_files,
                autonomy_payload,
                generated_patch,
            ) = _autonomous_prepare_repo(
                repo_dir=repo_dir,
                job_id=inp.job_id,
                timeout=inp.timeout,
                verbose=inp.verbose,
                selected_image=selected_image,
            )

            prepared_vfs = VirtualFileSystem.from_directory(
                inp.repo_url, inp.branch, repo_dir
            )
            prepared_vfs.to_redis(_redis(), f"vfs:{inp.job_id}:prepared", ttl_s=3600)

            _update_job(inp.job_id, status="building_image")
            build_result: dict[str, Any] = {}
            image_build_error = ""
            try:
                build_result = _build_container_image(
                    repo_dir=repo_dir,
                    image_tag=selected_image,
                    dockerfile_path=dockerfile_path,
                    timeout_s=max(inp.timeout, 300),
                )
            except Exception as exc:
                image_build_error = str(exc)
                if os.getenv("REQUIRE_IMAGE_BUILD", "false").strip().lower() in {
                    "1",
                    "true",
                    "yes",
                }:
                    raise
                log.warning("container build skipped: %s", exc)

            _update_job(inp.job_id, status="generating_manifest")
            manifest_yaml = _generate_manifest_for_job(
                job_id=inp.job_id,
                analysis=analysis,
                allowed_geos=inp.allowed_geos,
            )

            decision: dict[str, Any] = {}
            status = "prepared"
            openshift_job: dict[str, Any] | None = None
            bundle = {
                "prepared_vfs_key": f"vfs:{inp.job_id}:prepared",
                "source_vfs_key": f"vfs:{inp.job_id}",
                "dockerfile_path": dockerfile_path,
                "image": selected_image,
                "changed_files_count": len(changed_files),
                "manifest_ready": True,
            }

            _update_job(
                inp.job_id,
                status=status,
                analysis=analysis.model_dump(),
                scheduling_decision=decision,
                manifest_yaml=manifest_yaml,
                dockerfile_content=dockerfile_content,
                dockerfile_path=dockerfile_path,
                selected_image=selected_image,
                allowed_geos=inp.allowed_geos,
                max_price_usd_hour=inp.max_price_usd_hour,
                confirmation_required=True,
                dispatch_ready=True,
                requested_dry_run=inp.dry_run,
                openshift_job=openshift_job or {},
                bundle=bundle,
                changed_files=changed_files,
                generated_patch=generated_patch,
                codecarbon_integration=autonomy_payload,
                image_build=build_result,
                image_build_error=image_build_error,
            )

            return {
                "job_id": inp.job_id,
                "status": status,
                "analysis": analysis.model_dump(),
                "scheduling_decision": decision,
                "manifest_yaml": manifest_yaml,
                "dockerfile_content": dockerfile_content,
                "dockerfile_path": dockerfile_path,
                "selected_image": selected_image,
                "openshift_job": openshift_job,
                "bundle": bundle,
                "changed_files": changed_files,
                "generated_patch": generated_patch,
                "codecarbon_integration": autonomy_payload,
                "image_build": build_result,
                "image_build_error": image_build_error,
                "confirmation_required": True,
                "dispatch_ready": True,
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

    try:
        analysis = RepoAnalysis.model_validate(job.get("analysis") or {})
    except Exception as exc:
        raise RuntimeError("analysis missing; prepare the job first") from exc

    allowed_geos_raw = job.get("allowed_geos")
    allowed_geos: list[str]
    if isinstance(allowed_geos_raw, list) and allowed_geos_raw:
        allowed_geos = [
            str(geo).upper() for geo in allowed_geos_raw if str(geo).strip()
        ]
    else:
        allowed_geos = ["FR", "DE", "ES"]

    max_price_raw = job.get("max_price_usd_hour")
    max_price_usd_hour: float | None
    if isinstance(max_price_raw, (int, float)):
        max_price_usd_hour = float(max_price_raw)
    elif isinstance(max_price_raw, str) and max_price_raw.strip():
        try:
            max_price_usd_hour = float(max_price_raw)
        except Exception:
            max_price_usd_hour = None
    else:
        max_price_usd_hour = None

    image = inp.image or str(job.get("selected_image") or "").strip()
    if not image:
        image = os.getenv("DEFAULT_TRAINING_IMAGE", "").strip()
    if not image:
        raise RuntimeError("image is required to execute prepared job")

    namespace = inp.namespace or os.getenv("OPENSHIFT_NAMESPACE", "drosel-ieu2022-dev")
    _update_job(inp.job_id, status="dispatching", image=image)

    try:
        decision: dict[str, Any] | None = None
        if SCHEDULING_MODE == "prepared":
            _update_job(inp.job_id, status="scheduling")
            decision = _schedule_with_rails(
                job_id=inp.job_id,
                allowed_geos=allowed_geos,
                analysis=analysis,
                max_price_usd_hour=max_price_usd_hour,
            )
            if decision is None:
                log.warning(
                    "rails scheduling unavailable for %s; using static fallback",
                    inp.job_id,
                )
                decision = _schedule_choice(allowed_geos)

        openshift_job = _dispatch_job_to_openshift(
            job_id=inp.job_id,
            image=image,
            namespace=namespace,
            analysis=analysis,
            allowed_geos=allowed_geos,
            max_price_usd_hour=max_price_usd_hour,
            decision=decision,
            scheduling_mode=SCHEDULING_MODE,
        )
    except Exception as exc:
        _update_job(inp.job_id, status="failed", error=str(exc))
        raise self.retry(exc=exc)

    dispatched = bool(openshift_job.get("dispatched"))
    status = "dispatched" if dispatched else "dispatch_planned"
    dispatch_reason = str(openshift_job.get("reason") or "")

    _update_job(
        inp.job_id,
        status=status,
        image=image,
        scheduling_mode=SCHEDULING_MODE,
        scheduling_decision=decision or {},
        openshift_job=openshift_job,
        confirmation_required=False,
        dispatch_ready=not dispatched,
        dispatch_error=dispatch_reason,
    )
    return {
        "job_id": inp.job_id,
        "status": status,
        "scheduling_mode": SCHEDULING_MODE,
        "image": image,
        "scheduling_decision": decision or {},
        "openshift_job": openshift_job,
        "dispatch_error": dispatch_reason,
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
