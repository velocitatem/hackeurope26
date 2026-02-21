from __future__ import annotations

import time
from typing import Callable

from src import config
from src.models import InventoryNode, JobSpec, SchedulingDecision
from src.signals import EnergyClient, InventoryClient, best_positive_window


DispatchCallback = Callable[[SchedulingDecision], None]
WarmStartCallback = Callable[[SchedulingDecision], None]


class Scheduler:
    def __init__(
        self,
        energy: EnergyClient,
        inventory: InventoryClient,
        dispatch_callback: DispatchCallback | None = None,
        warm_start_callback: WarmStartCallback | None = None,
    ):
        self.energy = energy
        self.inventory = inventory
        self.dispatch_callback = dispatch_callback or (lambda _: None)
        self.warm_start_callback = warm_start_callback or (lambda _: None)

    def schedule(
        self, job: JobSpec, now_ts: float | None = None, dispatch: bool = True
    ) -> SchedulingDecision:
        now_ts = now_ts or time.time()
        self._prefilter(job)

        best_window = None
        for geo in job.allowed_geos:
            series = self.energy.delta_series(geo=geo, start_ts=now_ts)
            window = best_positive_window(
                geo=geo, series=series, duration_s=job.duration_s
            )
            if window is None:
                continue
            if best_window is None or window.avg_delta > best_window.avg_delta:
                best_window = window

        if best_window is None:
            raise RuntimeError(
                f"No positive energy interval found for job={job.job_id}"
            )

        candidates = self.inventory.feasible_nodes(
            geo=best_window.geo,
            gpu_count=job.gpu_count,
            min_gpu_memory_mib=job.min_gpu_memory_mib,
            max_price_usd_hour=job.max_price_usd_hour,
        )
        if not candidates:
            raise RuntimeError(f"No feasible nodes found in geo={best_window.geo}")

        best_node, score = self._pick_best_node(candidates, best_window.avg_delta)
        decision = SchedulingDecision(
            job_id=job.job_id,
            geo=best_window.geo,
            provider=best_node.provider,
            region=best_node.region,
            sku=best_node.sku,
            start_ts=best_window.start_ts,
            end_ts=best_window.end_ts,
            avg_delta=best_window.avg_delta,
            score=score,
            reason={
                "candidate_count": len(candidates),
                "weights": {
                    "delta": config.WEIGHT_DELTA,
                    "cost": config.WEIGHT_COST,
                },
            },
        )

        if dispatch:
            self.dispatch_callback(decision)
        return decision

    def evaluate_migration(
        self,
        job: JobSpec,
        current: SchedulingDecision,
        last_migration_ts: float | None,
        now_ts: float | None = None,
    ) -> SchedulingDecision | None:
        if (
            job.current_epoch == 0
            or (job.current_epoch % config.EVAL_EVERY_N_EPOCHS) != 0
        ):
            return None

        now_ts = now_ts or time.time()
        if (
            last_migration_ts is not None
            and now_ts - last_migration_ts < config.MIGRATION_COOLDOWN_S
        ):
            return None

        candidate = self.schedule(job=job, now_ts=now_ts, dispatch=False)
        if candidate.score <= current.score + config.MIGRATION_SCORE_THRESHOLD:
            return None

        self.warm_start_callback(candidate)
        self.dispatch_callback(candidate)
        return candidate

    def _prefilter(self, job: JobSpec) -> None:
        if job.duration_s <= 0:
            raise ValueError("job.duration_s must be > 0")
        if job.gpu_count <= 0:
            raise ValueError("job.gpu_count must be > 0")
        if not job.allowed_geos:
            raise ValueError("job.allowed_geos cannot be empty")

    def _pick_best_node(
        self, nodes: list[InventoryNode], avg_delta: float
    ) -> tuple[InventoryNode, float]:
        costs = [node.price_usd_hour for node in nodes]
        min_cost = min(costs)
        max_cost = max(costs)

        best_node = nodes[0]
        best_score = -1e9
        for node in nodes:
            if max_cost == min_cost:
                cost_score = 1.0
            else:
                cost_score = 1.0 - (
                    (node.price_usd_hour - min_cost) / (max_cost - min_cost)
                )
            score = (config.WEIGHT_DELTA * avg_delta) + (
                config.WEIGHT_COST * cost_score
            )
            if score > best_score:
                best_score = score
                best_node = node
        return best_node, best_score
