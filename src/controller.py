from __future__ import annotations

import time

from lib import get_logger

from src.models import JobSpec, SchedulingDecision
from src.scheduler import Scheduler


class AdaptiveController:
    def __init__(self, scheduler: Scheduler):
        self.scheduler = scheduler
        self.logger = get_logger("adaptive-controller", level="DEBUG")
        self._decisions: dict[str, SchedulingDecision] = {}
        self._last_migration_ts: dict[str, float] = {}

    def register_job(self, job: JobSpec) -> SchedulingDecision:
        decision = self.scheduler.schedule(job)
        self._decisions[job.job_id] = decision
        self.logger.info(
            "Registered job=%s initial geo=%s region=%s sku=%s score=%.3f",
            decision.job_id,
            decision.geo,
            decision.region,
            decision.sku,
            decision.score,
        )
        return decision

    def on_epoch(self, job: JobSpec) -> SchedulingDecision | None:
        current = self._decisions.get(job.job_id)
        if current is None:
            raise ValueError(f"Unknown job_id={job.job_id}")

        candidate = self.scheduler.evaluate_migration(
            job=job,
            current=current,
            last_migration_ts=self._last_migration_ts.get(job.job_id),
            now_ts=time.time(),
        )
        if candidate is None:
            return None

        self._decisions[job.job_id] = candidate
        self._last_migration_ts[job.job_id] = time.time()
        self.logger.info(
            "Migration candidate job=%s from=%s/%s to=%s/%s old=%.3f new=%.3f",
            job.job_id,
            current.region,
            current.sku,
            candidate.region,
            candidate.sku,
            current.score,
            candidate.score,
        )
        return candidate
