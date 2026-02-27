"""GeoRegistry: maps geo codes to the right predictor implementation.

Supported geos and their predictor types:
- UK  -> OnnxGeoPredictor (multi-horizon ONNX ensemble)
- FR, FIN, IT -> TabularGeoPredictor (joblib sklearn/xgboost)

Alias map (case-insensitive):
  GB -> UK, FI/FINLAND -> FIN, FRANCE -> FR, ITALY -> IT
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ml.geo.onnx_predictor import OnnxGeoPredictor
from ml.geo.tabular_predictor import TabularGeoPredictor

if TYPE_CHECKING:
    from ml.geo.base import GeoPredictor
    from ml.features.store import FeatureStore

SUPPORTED = frozenset({"UK", "FR", "FIN", "IT"})

_ALIASES: dict[str, str] = {
    "GB": "UK",
    "FRANCE": "FR",
    "FI": "FIN",
    "FINLAND": "FIN",
    "ITALY": "IT",
}

_ONNX_GEOS = frozenset({"UK"})


def normalize_geo(geo: str) -> str:
    g = geo.strip().upper()
    return _ALIASES.get(g, g)


class GeoRegistry:
    """Lazy-loads one predictor per geo on first access."""

    def __init__(self, feature_store: "FeatureStore | None" = None):
        self._store = feature_store
        self._predictors: dict[str, "GeoPredictor"] = {}

    def _ensure_store(self) -> "FeatureStore":
        if self._store is None:
            from ml.features.store import FeatureStore
            self._store = FeatureStore()
        return self._store

    def get(self, geo: str) -> "GeoPredictor":
        if geo not in self._predictors:
            self._predictors[geo] = self._build(geo)
        return self._predictors[geo]

    def _build(self, geo: str) -> "GeoPredictor":
        if geo in _ONNX_GEOS:
            return OnnxGeoPredictor(geo=geo)
        return TabularGeoPredictor(geo=geo, feature_store=self._ensure_store())

    def is_ready(self, geo: str) -> bool:
        return self.get(geo).is_ready()

    def load_error(self, geo: str) -> str | None:
        return self.get(geo).load_error()

    def readiness(self) -> dict[str, dict]:
        return {
            geo: {"ready": self.is_ready(geo), "error": self.load_error(geo)}
            for geo in SUPPORTED
        }
