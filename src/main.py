import os
import time

from lib import get_logger

from src import config
from src.jobs.pytorch_train_example import JOB_SPEC, make_trainer
from src.migration import MigrationManager
from src.rails_client import RailsClient
from src.scheduler import Scheduler
from src.signals import EnergyClient, InventoryClient


def main() -> None:
    logger = get_logger("scheduler", level="DEBUG")
    train_epochs = int(os.getenv("TRAIN_EPOCHS", "15"))
    epoch_sim_s = int(os.getenv("TRAIN_EPOCH_SIM_S", str(config.FREQ_S)))
    rails = RailsClient()
    migration = MigrationManager(rails_client=rails)

    scheduler = Scheduler(
        energy=EnergyClient(),
        inventory=InventoryClient(),
        dispatch_callback=migration.dispatch,
        warm_start_callback=migration.warm_start_target,
    )
    rails.bulk_upsert_nodes(scheduler.inventory.load())

    rails.upsert_job(JOB_SPEC)

    jobs = rails.fetch_pending_jobs()
    if not jobs:
        jobs = [JOB_SPEC]

    for job in jobs:
        base_now_ts = time.time()
        decision = scheduler.schedule(job, now_ts=base_now_ts)
        rails.update_job_status(job.job_id, "scheduled", current_epoch=0)
        trainer = make_trainer()
        logger.info(
            "Simulation settings job=%s epochs=%d epoch_sim_s=%d eval_every=%d migration_threshold=%.3f",
            job.job_id,
            train_epochs,
            epoch_sim_s,
            config.EVAL_EVERY_N_EPOCHS,
            config.MIGRATION_SCORE_THRESHOLD,
        )
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
        for epoch in range(1, train_epochs + 1):
            loss = trainer.train_epoch()
            job.current_epoch = epoch
            rails.update_job_status(job.job_id, "running", current_epoch=epoch)
            logger.info(
                "job=%s epoch=%d avg_loss=%.6f geo=%s region=%s sku=%s",
                job.job_id,
                epoch,
                loss,
                decision.geo,
                decision.region,
                decision.sku,
            )
            epoch_now_ts = base_now_ts + (epoch * epoch_sim_s)
            candidate = scheduler.evaluate_migration(
                job=job,
                current=decision,
                last_migration_ts=last_migration_ts,
                now_ts=epoch_now_ts,
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
                if epoch % config.EVAL_EVERY_N_EPOCHS == 0:
                    reevaluated = scheduler.schedule(
                        job=job,
                        now_ts=epoch_now_ts,
                        dispatch=False,
                    )
                    logger.info(
                        "Migration check epoch=%d current=%s/%s score=%.3f candidate=%s/%s score=%.3f delta=%.3f threshold=%.3f",
                        epoch,
                        decision.region,
                        decision.sku,
                        decision.score,
                        reevaluated.region,
                        reevaluated.sku,
                        reevaluated.score,
                        reevaluated.score - decision.score,
                        config.MIGRATION_SCORE_THRESHOLD,
                    )
                logger.debug("job=%s epoch=%d no migration", job.job_id, epoch)
        trainer.writer.close()
        rails.update_job_status(job.job_id, "completed", current_epoch=train_epochs)


if __name__ == "__main__":
    main()
