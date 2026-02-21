from __future__ import annotations

from lib import get_logger

from src.rails_client import RailsClient
from src.models import SchedulingDecision


class MigrationManager:
    def __init__(self, rails_client: RailsClient | None = None):
        self.logger = get_logger("migration-manager", level="DEBUG")
        self.rails_client = rails_client

    def warm_start_target(self, decision: SchedulingDecision) -> None:
        self.logger.info(
            "Warm-start callback pending implementation geo=%s region=%s sku=%s",
            decision.geo,
            decision.region,
            decision.sku,
        )
        if self.rails_client is not None:
            self.rails_client.post_migration_event(
                job_id=decision.job_id,
                epoch=0,
                from_region="",
                from_sku="",
                from_score=0.0,
                to_region=decision.region,
                to_sku=decision.sku,
                to_score=decision.score,
                status="warm_start",
                message="Warm-start callback invoked",
                reason_json=decision.reason,
            )

    def dispatch(self, decision: SchedulingDecision) -> None:
        self.logger.info(
            "Dispatch callback pending implementation job=%s region=%s sku=%s",
            decision.job_id,
            decision.region,
            decision.sku,
        )
        if self.rails_client is not None:
            self.rails_client.post_decision(decision, source="scheduler")
