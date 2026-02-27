"""Joblib-based tabular predictor (FR, FIN, IT, and any future geo).

Model resolution order per geo:
1. ``ML_{GEO}_MODEL_PATH`` env var
2. ``ml/artifacts/geo/{GEO}/model.joblib``
3. ``ml/{geo_lower}/{geo_lower}_model.joblib``   (legacy FR/FIN layout)
4. Any ``*.joblib`` in ``ml/{geo_lower}/``
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

_ML_ROOT = Path(__file__).resolve().parents[1]  # ml/ directory
SECONDS_PER_HOUR = 60 * 60


def _model_candidates(geo: str) -> list[Path]:
    env = os.getenv(f"ML_{geo.upper()}_MODEL_PATH")
    if env:
        return [Path(env)]

    geo_lower = geo.lower()
    artifact = _ML_ROOT / "artifacts" / "geo" / geo / "model.joblib"
    legacy_dir = _ML_ROOT / geo_lower
    legacy_default = legacy_dir / f"{geo_lower}_model.joblib"

    candidates = [artifact, legacy_default]
    if legacy_dir.exists():
        for p in sorted(legacy_dir.glob("*.joblib")):
            if p not in candidates:
                candidates.append(p)
    return candidates


def _load_feature_cols(geo: str) -> list[str] | None:
    """Look for a saved feature column list in canonical or legacy locations."""
    try:
        import joblib
    except ModuleNotFoundError:
        return None

    for candidate in [
        _ML_ROOT / "artifacts" / "geo" / geo / "feature_cols.joblib",
        _ML_ROOT / "data" / geo.lower() / "saved_models" / "feature_cols_single.joblib",
        _ML_ROOT / "data" / geo.lower() / "saved_models" / "feature_cols_multi.joblib",
        _ML_ROOT / "data" / "italy" / "saved_models" / "feature_cols_single.joblib"
        if geo == "IT"
        else Path("/dev/null"),
        _ML_ROOT / "data" / "uk" / "saved_models" / "feature_cols_single.joblib"
        if geo == "UK"
        else Path("/dev/null"),
    ]:
        if candidate.exists():
            try:
                cols = joblib.load(candidate)
                return [str(c) for c in cols]
            except Exception:
                continue
    return None


def _predict_chain(model: Any, x: Any) -> Any:
    """Manually run a RegressorChain to avoid sklearn version issues."""
    import numpy as np

    estimators = model.estimators_
    order_raw = getattr(model, "order_", None) or getattr(model, "order", None)
    n = len(estimators)
    ns = int(x.shape[0])

    if order_raw is None or str(order_raw).lower() == "random":
        order = list(range(n))
    else:
        order = [int(v) for v in list(order_raw)]
        if len(order) != n:
            order = list(range(n))

    chain = np.zeros((ns, n), dtype=np.float32)
    for i, est in enumerate(estimators):
        x_aug = x if i == 0 else np.hstack((x, chain[:, :i]))
        pred = np.asarray(est.predict(x_aug), dtype=np.float32).reshape(-1)
        chain[:, i] = pred

    y = np.zeros((ns, n), dtype=np.float32)
    for ci, ti in enumerate(order):
        if 0 <= ti < n:
            y[:, ti] = chain[:, ci]
    return y


def _predict_raw(model: Any, x: Any) -> Any:
    import numpy as np

    is_chain = hasattr(model, "estimators_") and (
        hasattr(model, "order") or hasattr(model, "order_")
    )
    if not is_chain:
        return np.asarray(model.predict(x), dtype=np.float32)
    try:
        return np.asarray(model.predict(x), dtype=np.float32)
    except Exception as exc:
        if "RegressorChain" not in str(exc):
            raise
        return _predict_chain(model, x)


class TabularGeoPredictor:
    """Wraps a joblib-serialized sklearn/xgboost model for one geo."""

    def __init__(
        self,
        geo: str,
        feature_store: Any | None = None,  # ml.features.FeatureStore
        model_path: str | Path | None = None,
    ):
        self._geo = geo
        self._feature_store = feature_store
        self._model: Any = None
        self._feature_cols: list[str] | None = None
        self._error: str | None = None
        self._model_path: str | None = None
        self._load(model_path)

    @property
    def geo(self) -> str:
        return self._geo

    def _load(self, override: str | Path | None) -> None:
        try:
            import joblib
        except ModuleNotFoundError:
            self._error = "missing dependency: joblib"
            return

        candidates = [Path(override)] if override else _model_candidates(self._geo)
        for path in candidates:
            if not path.exists():
                continue
            try:
                self._model = joblib.load(path)
                self._model_path = str(path)
                break
            except Exception as exc:
                self._error = f"failed to load {path}: {exc}"

        if self._model is None:
            checked = ", ".join(str(p) for p in candidates)
            self._error = self._error or f"model not found; checked: {checked}"
            return

        self._feature_cols = _load_feature_cols(self._geo) or self._cols_from_model()

    def _cols_from_model(self) -> list[str] | None:
        m = self._model
        if hasattr(m, "feature_names_in_"):
            return [str(n) for n in m.feature_names_in_]
        ests = getattr(m, "estimators_", None)
        if ests and hasattr(ests[0], "feature_names_in_"):
            return [str(n) for n in ests[0].feature_names_in_]
        return None

    def n_features(self) -> int | None:
        m = self._model
        if m is None:
            return None
        if hasattr(m, "n_features_in_"):
            return int(m.n_features_in_)
        ests = getattr(m, "estimators_", None)
        if ests and hasattr(ests[0], "n_features_in_"):
            return int(ests[0].n_features_in_)
        return None

    def is_ready(self) -> bool:
        return self._model is not None

    def load_error(self) -> str | None:
        return self._error

    def _feature_vector(self, t: float, horizon_h: int) -> list[float]:
        if self._feature_store is None:
            from ml.features.store import FeatureStore
            self._feature_store = FeatureStore()
        return self._feature_store.vector_for(
            geo=self._geo,
            t=t,
            horizon_h=horizon_h,
            feature_names=self._feature_cols,
            expected_size=self.n_features(),
        )

    def predict(self, t: float, horizon_h: int) -> tuple[float, int]:
        import numpy as np

        vec = self._feature_vector(t, horizon_h)
        x = np.asarray([vec], dtype=np.float32)
        flat = _predict_raw(self._model, x).reshape(-1)
        if flat.size == 0:
            raise ValueError("model returned empty prediction")
        max_h = int(flat.size)
        selected_h = max(1, min(max_h, int(horizon_h)))
        return float(flat[selected_h - 1]), selected_h

    def predict_series(
        self, start: float, horizon_s: int, freq_s: int
    ) -> list[dict[str, float]]:
        points = []
        for offset in range(0, horizon_s + 1, freq_s):
            t = start + float(offset)
            req_h = max(1, int(math.ceil((offset + freq_s) / float(SECONDS_PER_HOUR))))
            delta, used_h = self.predict(t, req_h)
            points.append({"t": t, "delta": float(delta), "horizon_h": used_h})
        return points
