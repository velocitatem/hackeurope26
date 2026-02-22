from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JobSpec:
    job_id: str
    duration_s: int
    gpu_count: int
    min_gpu_memory_mib: int
    allowed_geos: list[str]
    max_price_usd_hour: float | None = None
    current_epoch: int = 0


@dataclass
class InventoryNode:
    provider: str
    region: str
    geo: str
    sku: str
    price_usd_hour: float
    gpu_count: int
    gpu_memory_mib: int | None


@dataclass
class TimeWindow:
    geo: str
    start_ts: float
    end_ts: float
    avg_delta: float


@dataclass
class SchedulingDecision:
    job_id: str
    geo: str
    provider: str
    region: str
    sku: str
    start_ts: float
    end_ts: float
    avg_delta: float
    score: float
    reason: dict
