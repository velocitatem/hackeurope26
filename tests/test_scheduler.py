from src.models import InventoryNode, JobSpec
from src.scheduler import NoEnergyWindowError, Scheduler


def _series(start: int, step: int, deltas: list[float]) -> list[dict[str, float]]:
    return [
        {"t": float(start + idx * step), "delta": delta}
        for idx, delta in enumerate(deltas)
    ]


class FakeEnergyClient:
    def __init__(self, by_geo: dict[str, list[dict[str, float]]]):
        self.by_geo = by_geo

    def delta_series(self, geo: str, start_ts: float) -> list[dict[str, float]]:
        return self.by_geo[geo]


class FakeInventoryClient:
    def __init__(self, by_geo: dict[str, list[InventoryNode]]):
        self.by_geo = by_geo
        self.calls: list[dict[str, object]] = []

    def feasible_nodes(
        self,
        geo: str,
        gpu_count: int,
        min_gpu_memory_mib: int,
        max_price_usd_hour: float | None,
    ) -> list[InventoryNode]:
        self.calls.append(
            {
                "geo": geo,
                "gpu_count": gpu_count,
                "min_gpu_memory_mib": min_gpu_memory_mib,
                "max_price_usd_hour": max_price_usd_hour,
            }
        )
        return self.by_geo.get(geo, [])


def test_schedule_picks_best_geo_gap_and_suggests_cheapest_node() -> None:
    energy = FakeEnergyClient(
        {
            "FR": _series(start=0, step=60, deltas=[-1.0, 1.0, 1.0, -1.0]),
            "DE": _series(start=0, step=60, deltas=[-1.0, 3.0, 3.0, -1.0]),
        }
    )
    inventory = FakeInventoryClient(
        {
            "DE": [
                InventoryNode(
                    provider="AWS",
                    region="eu-central-1",
                    geo="DE",
                    sku="expensive",
                    price_usd_hour=2.0,
                    gpu_count=1,
                    gpu_memory_mib=24000,
                ),
                InventoryNode(
                    provider="AWS",
                    region="eu-central-1",
                    geo="DE",
                    sku="cheap",
                    price_usd_hour=1.0,
                    gpu_count=1,
                    gpu_memory_mib=24000,
                ),
            ]
        }
    )
    scheduler = Scheduler(energy=energy, inventory=inventory)

    decision = scheduler.schedule(
        JobSpec(
            job_id="job-1",
            duration_s=120,
            gpu_count=1,
            min_gpu_memory_mib=16000,
            allowed_geos=["FR", "DE"],
        ),
        now_ts=0,
    )

    assert inventory.calls[0]["geo"] == "DE"
    assert decision.geo == "DE"
    assert decision.sku == "cheap"
    assert decision.start_ts == 60.0
    assert decision.end_ts == 120.0
    assert decision.avg_delta == 3.0


def test_schedule_raises_when_no_positive_gap_exists() -> None:
    energy = FakeEnergyClient(
        {
            "FR": _series(start=0, step=60, deltas=[-1.0, -1.0, -0.5]),
        }
    )
    inventory = FakeInventoryClient({"FR": []})
    scheduler = Scheduler(energy=energy, inventory=inventory)

    try:
        scheduler.schedule(
            JobSpec(
                job_id="job-2",
                duration_s=120,
                gpu_count=1,
                min_gpu_memory_mib=16000,
                allowed_geos=["FR"],
            ),
            now_ts=0,
        )
        assert False, "Expected NoEnergyWindowError"
    except NoEnergyWindowError as exc:
        assert "No positive energy window" in str(exc)
