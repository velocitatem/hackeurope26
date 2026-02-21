from __future__ import annotations

import os
from typing import Any

import requests

from src.models import JobSpec, SchedulingDecision


class RailsClient:
    def __init__(self, base_url: str | None = None, timeout_s: float = 3.0):
        self.base_url = (
            base_url or os.getenv("RAILS_API_URL", "http://localhost:3001")
        ).rstrip("/")
        self.timeout_s = timeout_s

    def upsert_job(self, job: JobSpec) -> None:
        payload = {
            "job": {
                "external_id": job.job_id,
                "status": "pending",
                "duration_s": job.duration_s,
                "gpu_count": job.gpu_count,
                "min_gpu_memory_mib": job.min_gpu_memory_mib,
                "max_price_usd_hour": job.max_price_usd_hour,
                "current_epoch": job.current_epoch,
                "allowed_geos": job.allowed_geos,
            }
        }
        try:
            existing = self._find_job_by_external_id(job.job_id)
            if existing is None:
                requests.post(
                    f"{self.base_url}/api/jobs", json=payload, timeout=self.timeout_s
                ).raise_for_status()
            else:
                requests.patch(
                    f"{self.base_url}/api/jobs/{existing['id']}",
                    json=payload,
                    timeout=self.timeout_s,
                ).raise_for_status()
        except Exception:
            return

    def post_decision(
        self, decision: SchedulingDecision, source: str = "scheduler"
    ) -> None:
        payload = {
            "scheduling_decision": {
                "job_external_id": decision.job_id,
                "geo": decision.geo,
                "provider": decision.provider,
                "region": decision.region,
                "sku": decision.sku,
                "start_ts": int(decision.start_ts),
                "end_ts": int(decision.end_ts),
                "avg_delta": decision.avg_delta,
                "score": decision.score,
                "source": source,
                "reason_json": decision.reason,
            }
        }
        try:
            requests.post(
                f"{self.base_url}/api/scheduling_decisions",
                json=payload,
                timeout=self.timeout_s,
            ).raise_for_status()
        except Exception:
            return

    def post_migration_event(
        self,
        job_id: str,
        epoch: int,
        from_region: str,
        from_sku: str,
        from_score: float,
        to_region: str,
        to_sku: str,
        to_score: float,
        status: str,
        message: str,
        reason_json: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "migration_event": {
                "job_external_id": job_id,
                "trigger_epoch": epoch,
                "from_region": from_region,
                "from_sku": from_sku,
                "from_score": from_score,
                "to_region": to_region,
                "to_sku": to_sku,
                "to_score": to_score,
                "status": status,
                "message": message,
                "reason_json": reason_json or {},
            }
        }
        try:
            requests.post(
                f"{self.base_url}/api/migration_events",
                json=payload,
                timeout=self.timeout_s,
            ).raise_for_status()
        except Exception:
            return

    def _find_job_by_external_id(self, external_id: str) -> dict[str, Any] | None:
        response = requests.get(f"{self.base_url}/api/jobs", timeout=self.timeout_s)
        response.raise_for_status()
        for job in response.json():
            if job.get("external_id") == external_id:
                return job
        return None
