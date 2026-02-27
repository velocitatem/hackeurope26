"""Protocol interfaces for scheduler providers.

Any energy signal source, inventory backend, or dispatch target can implement
these protocols and be passed directly to Scheduler without subclassing.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from src.models import InventoryNode

if TYPE_CHECKING:
    from src.models import SchedulingDecision


@runtime_checkable
class EnergyProvider(Protocol):
    """Provides renewable-energy delta time-series for a geography."""

    def delta_series(self, geo: str, start_ts: float) -> list[dict[str, float]]:
        """Return [{t: float, delta: float}, ...] sorted by t ascending."""
        ...


@runtime_checkable
class InventoryProvider(Protocol):
    """Returns compute nodes that satisfy job constraints."""

    def feasible_nodes(
        self,
        geo: str,
        gpu_count: int,
        min_gpu_memory_mib: int,
        max_price_usd_hour: float | None,
    ) -> list[InventoryNode]:
        ...


@runtime_checkable
class DispatchProvider(Protocol):
    """Executes the actual scheduling decision (e.g. submit to k8s, call Rails)."""

    def dispatch(self, decision: "SchedulingDecision") -> None:
        ...
