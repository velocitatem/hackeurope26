import time

from lib import get_logger

from src import config
from src.migration import MigrationManager
from src.models import JobSpec
from src.rails_client import RailsClient
from src.scheduler import Scheduler
from src.signals import EnergyClient, InventoryClient


def main() -> None:
    logger = get_logger("scheduler", level="DEBUG")
    rails = RailsClient()
    migration = MigrationManager(rails_client=rails)

    scheduler = Scheduler(
        energy=EnergyClient(),
        inventory=InventoryClient(),
        dispatch_callback=migration.dispatch,
        warm_start_callback=migration.warm_start_target,
    )
    rails.bulk_upsert_nodes(scheduler.inventory.load())

    demo_job = JobSpec(
        job_id="demo-train-001",
        duration_s=6 * 60 * 60,
        gpu_count=1,
        min_gpu_memory_mib=16 * 1024,
        allowed_geos=config.GEOGRAPHIES,
    )
    rails.upsert_job(demo_job)

    jobs = rails.fetch_pending_jobs()
    if not jobs:
        jobs = [demo_job]

    for job in jobs:
        decision = scheduler.schedule(job)
        rails.update_job_status(job.job_id, "scheduled", current_epoch=0)
        logger.info(
            "Initial placement job=%s geo=%s region=%s provider=%s sku=%s window=[%s,%s] avg_delta=%.3f score=%.3f",
            decision.job_id,
            decision.geo,
            decision.region,
            decision.provider,
            decision.sku,
            int(decision.start_ts),
            int(decision.end_ts),
            decision.avg_delta,
            decision.score,
        )

        last_migration_ts = None
        for epoch in range(1, 31):
            job.current_epoch = epoch
            rails.update_job_status(job.job_id, "running", current_epoch=epoch)
            candidate = scheduler.evaluate_migration(
                job=job,
                current=decision,
                last_migration_ts=last_migration_ts,
            )
            if candidate is not None:
                rails.post_migration_event(
                    job_id=job.job_id,
                    epoch=epoch,
                    from_region=decision.region,
                    from_sku=decision.sku,
                    from_score=decision.score,
                    to_region=candidate.region,
                    to_sku=candidate.sku,
                    to_score=candidate.score,
                    status="recommended",
                    message="Adaptive reevaluation exceeded migration threshold",
                    reason_json=candidate.reason,
                )
                logger.info(
                    "Migration recommended at epoch=%d from=%s/%s to=%s/%s new_score=%.3f old_score=%.3f",
                    epoch,
                    decision.region,
                    decision.sku,
                    candidate.region,
                    candidate.sku,
                    candidate.score,
                    decision.score,
                )
                decision = candidate
                last_migration_ts = time.time()
            else:
                logger.debug("job=%s epoch=%d no migration", job.job_id, epoch)


if __name__ == "__main__":
    main()
