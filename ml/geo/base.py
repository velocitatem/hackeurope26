"""GeoPredictor Protocol — any geo model must satisfy this interface."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class GeoPredictor(Protocol):
    """Predicts renewable-energy delta for a geographic region."""

    @property
    def geo(self) -> str: ...

    def predict(self, t: float, horizon_h: int) -> tuple[float, int]:
        """Return (delta, actual_horizon_h_used)."""
        ...

    def predict_series(
        self, start: float, horizon_s: int, freq_s: int
    ) -> list[dict[str, float]]:
        """Return [{t, delta, horizon_h}, ...] covering [start, start+horizon_s]."""
        ...

    def is_ready(self) -> bool: ...

    def load_error(self) -> str | None: ...
