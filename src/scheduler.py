from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from src import config
from src.models import InventoryNode, JobSpec, SchedulingDecision
from src.signals import (
    EnergyClient,
    InventoryClient,
    EnergyWindow,
    best_positive_window,
)


DispatchCallback = Callable[[SchedulingDecision], None]
WarmStartCallback = Callable[[SchedulingDecision], None]


@dataclass
class NodeScore:
    node: InventoryNode
    score: float


class SchedulingError(Exception):
    pass


class NoEnergyWindowError(SchedulingError):
    pass


class NoFeasibleNodesError(SchedulingError):
    pass


def validate_job_spec(job: JobSpec) -> None:
    if job.duration_s <= 0:
        raise ValueError(f"job.duration_s must be > 0, got {job.duration_s}")
    if job.gpu_count <= 0:
        raise ValueError(f"job.gpu_count must be > 0, got {job.gpu_count}")
    if not job.allowed_geos:
        raise ValueError("job.allowed_geos cannot be empty")


def find_best_energy_window(
    energy_client: EnergyClient,
    job: JobSpec,
    start_ts: float,
) -> EnergyWindow:
    best_window = None
    for geo in job.allowed_geos:
        series = energy_client.delta_series(geo=geo, start_ts=start_ts)
        window = best_positive_window(geo=geo, series=series, duration_s=job.duration_s)
        if window and (not best_window or window.avg_delta > best_window.avg_delta):
            best_window = window

    if not best_window:
        raise NoEnergyWindowError(
            f"No positive energy window for job={job.job_id}, "
            f"geos={job.allowed_geos}, duration={job.duration_s}s"
        )
    return best_window


def fetch_feasible_nodes(
    inventory_client: InventoryClient,
    job: JobSpec,
    geo: str,
) -> list[InventoryNode]:
    candidates = inventory_client.feasible_nodes(
        geo=geo,
        gpu_count=job.gpu_count,
        min_gpu_memory_mib=job.min_gpu_memory_mib,
        max_price_usd_hour=job.max_price_usd_hour,
    )
    if not candidates:
        raise NoFeasibleNodesError(
            f"No feasible nodes in geo={geo} for job={job.job_id}"
        )
    return candidates


def normalize_cost(price: float, min_cost: float, max_cost: float) -> float:
    if max_cost == min_cost:
        return 1.0
    return 1.0 - (price - min_cost) / (max_cost - min_cost)


def select_best_node(nodes: list[InventoryNode], avg_delta: float) -> NodeScore:
    if not nodes:
        raise ValueError("nodes list cannot be empty")

    costs = [n.price_usd_hour for n in nodes]
    min_cost, max_cost = min(costs), max(costs)

    def score(node: InventoryNode) -> float:
        cost_score = normalize_cost(node.price_usd_hour, min_cost, max_cost)
        return config.WEIGHT_DELTA * avg_delta + config.WEIGHT_COST * cost_score

    best = max(nodes, key=score)
    return NodeScore(node=best, score=score(best))


def build_decision(
    job: JobSpec,
    window: EnergyWindow,
    node_score: NodeScore,
    candidate_count: int,
) -> SchedulingDecision:
    return SchedulingDecision(
        job_id=job.job_id,
        geo=window.geo,
        provider=node_score.node.provider,
        region=node_score.node.region,
        sku=node_score.node.sku,
        start_ts=window.start_ts,
        end_ts=window.end_ts,
        avg_delta=window.avg_delta,
        score=node_score.score,
        reason={
            "candidate_count": candidate_count,
            "weights": {"delta": config.WEIGHT_DELTA, "cost": config.WEIGHT_COST},
        },
    )


def should_evaluate_migration(
    job: JobSpec,
    last_migration_ts: float | None,
    now_ts: float,
) -> bool:
    if job.current_epoch == 0 or job.current_epoch % config.EVAL_EVERY_N_EPOCHS != 0:
        return False
    if last_migration_ts and now_ts - last_migration_ts < config.MIGRATION_COOLDOWN_S:
        return False
    return True


def migration_worthwhile(
    candidate: SchedulingDecision,
    current: SchedulingDecision,
) -> bool:
    return candidate.score > current.score + config.MIGRATION_SCORE_THRESHOLD


class Scheduler:
    """Energy-aware job scheduler using pure function composition."""

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

    def schedule(self, job: JobSpec, now_ts: float | None = None) -> SchedulingDecision:
        now_ts = now_ts or time.time()
        validate_job_spec(job)

        window = find_best_energy_window(self.energy, job, now_ts)
        candidates = fetch_feasible_nodes(self.inventory, job, window.geo)
        node_score = select_best_node(candidates, window.avg_delta)

        return build_decision(job, window, node_score, len(candidates))

    def dispatch(self, decision: SchedulingDecision) -> None:
        self.dispatch_callback(decision)

    def evaluate_migration(
        self,
        job: JobSpec,
        current: SchedulingDecision,
        last_migration_ts: float | None,
        now_ts: float | None = None,
    ) -> SchedulingDecision | None:
        now_ts = now_ts or time.time()

        if not should_evaluate_migration(job, last_migration_ts, now_ts):
            return None

        candidate = self.schedule(job, now_ts)

        if not migration_worthwhile(candidate, current):
            return None

        self.warm_start_callback(candidate)
        self.dispatch(candidate)
        return candidate
