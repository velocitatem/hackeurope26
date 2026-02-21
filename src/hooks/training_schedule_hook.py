from __future__ import annotations

import json
import sys
import time

from src.models import JobSpec
from src.scheduler import Scheduler
from src.signals import EnergyClient, InventoryClient


def _coerce_job_spec(payload: dict) -> JobSpec:
    return JobSpec(
        job_id=str(payload.get("job_id") or "webhook-job"),
        duration_s=int(payload.get("duration_s", 6 * 60 * 60)),
        gpu_count=max(1, int(payload.get("gpu_count", 1))),
        min_gpu_memory_mib=int(payload.get("min_gpu_memory_mib", 16 * 1024)),
        allowed_geos=list(payload.get("allowed_geos") or ["FR", "DE", "ES"]),
        max_price_usd_hour=(
            float(payload["max_price_usd_hour"])
            if payload.get("max_price_usd_hour") is not None
            else None
        ),
        current_epoch=int(payload.get("current_epoch", 0)),
    )


def main() -> int:
    if len(sys.argv) < 2:
        print("{}")
        return 1

    try:
        payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        print("{}")
        return 1

    scheduler = Scheduler(
        energy=EnergyClient(),
        inventory=InventoryClient(),
    )

    now_ts = payload.get("now_ts")
    if now_ts is None:
        now_ts = time.time()

    try:
        job = _coerce_job_spec(payload)
        try:
            decision = scheduler.schedule(
                job=job,
                now_ts=float(now_ts),
                dispatch=False,
            )
        except TypeError as exc:
            if "dispatch" not in str(exc):
                raise
            decision = scheduler.schedule(job=job, now_ts=float(now_ts))
    except Exception as exc:
        print(f"hook_error={exc}", file=sys.stderr)
        print("{}")
        return 2

    print(
        json.dumps(
            {
                "job_id": decision.job_id,
                "geo": decision.geo,
                "provider": decision.provider,
                "region": decision.region,
                "sku": decision.sku,
                "start_ts": int(decision.start_ts),
                "end_ts": int(decision.end_ts),
                "avg_delta": float(decision.avg_delta),
                "score": float(decision.score),
                "reason": decision.reason,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
