"""FeatureStore: loads per-geo feature matrices from parquet files.

Directory convention (overridable via ML_FEATURES_DIR env var)::

    ml/artifacts/geo/{GEO}/
        test_X.parquet    - feature matrix
        test_y.parquet    - target horizon values

Older layout (ml/features_quantifid/) is also scanned as a fallback.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from ml.features.engineering import (
    SECONDS_PER_HOUR,
    extract_target_horizons,
    prepare_numeric_df,
    synthesize_vector,
    vector_from_gap_targets,
)

_X_RE = re.compile(r"([a-z]{2,3})_x_test_set\.parquet$")
_Y_RE = re.compile(r"([a-z]{2,3})_y_test_set\.parquet$")

_GEO_ALIASES = {"FI": "FIN"}

_DEFAULT_FEATURE_DIR = Path(__file__).resolve().parents[1] / "features_quantifid"
_ARTIFACT_GEO_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "geo"


def _normalize(token: str) -> str:
    g = token.upper()
    return _GEO_ALIASES.get(g, g)


class FeatureStore:
    """Loads feature/target parquet matrices per geography.

    Falls back to synthetic generation when no parquet is available.
    """

    def __init__(self, feature_dir: str | Path | None = None, synthetic: bool = True):
        self.synthetic = synthetic
        self._feature_dir = Path(
            feature_dir
            or os.getenv("ML_FEATURES_DIR", str(_DEFAULT_FEATURE_DIR))
        )
        self._x: dict[str, list[list[float]]] = {}
        self._x_cols: dict[str, list[str]] = {}
        self._y: dict[str, list[list[float]]] = {}
        self._y_cols: dict[str, list[str]] = {}
        self.errors: dict[str, str] = {}
        self._load()

    # ------------------------------------------------------------------ loading
    def _load(self) -> None:
        try:
            import pandas as pd
        except ModuleNotFoundError:
            self.errors["GLOBAL"] = "missing dependency: pandas"
            return

        dirs_to_scan = [self._feature_dir]
        if _ARTIFACT_GEO_DIR.exists():
            for geo_dir in sorted(_ARTIFACT_GEO_DIR.iterdir()):
                if geo_dir.is_dir():
                    dirs_to_scan.append(geo_dir)

        for scan_dir in dirs_to_scan:
            if not scan_dir.exists():
                continue
            for candidate in sorted(scan_dir.glob("*.parquet")):
                self._try_load_x(candidate, pd)
                self._try_load_y(candidate, pd)

    def _try_load_x(self, path: Path, pd: Any) -> None:
        # canonical name: test_X.parquet in a GEO directory
        if path.name.lower() == "test_x.parquet" and path.parent != self._feature_dir:
            geo = _normalize(path.parent.name)
        else:
            m = _X_RE.search(path.name)
            if not m:
                return
            geo = _normalize(m.group(1))
        if geo in self._x:
            return
        try:
            df = prepare_numeric_df(pd.read_parquet(path))
            if df.empty:
                return
            self._x_cols[geo] = [str(c) for c in df.columns]
            self._x[geo] = df.astype("float32").values.tolist()
        except Exception as exc:
            self.errors[geo] = f"x load failed: {exc}"

    def _try_load_y(self, path: Path, pd: Any) -> None:
        if path.name.lower() == "test_y.parquet" and path.parent != self._feature_dir:
            geo = _normalize(path.parent.name)
        else:
            m = _Y_RE.search(path.name)
            if not m:
                return
            geo = _normalize(m.group(1))
        if geo in self._y:
            return
        try:
            df = prepare_numeric_df(pd.read_parquet(path))
            if df.empty:
                return
            self._y_cols[geo] = [str(c) for c in df.columns]
            self._y[geo] = df.astype("float32").values.tolist()
        except Exception as exc:
            self.errors[geo] = f"y load failed: {exc}"

    # ------------------------------------------------------------------ query
    def has_x(self, geo: str) -> bool:
        return bool(self._x.get(geo))

    def has_y(self, geo: str) -> bool:
        return bool(self._y.get(geo))

    def vector_for(
        self,
        geo: str,
        t: float,
        horizon_h: int,
        feature_names: list[str] | None,
        expected_size: int | None,
    ) -> list[float]:
        seed = int(max(0.0, t)) // SECONDS_PER_HOUR

        if self.has_x(geo):
            rows = self._x[geo]
            row = rows[(seed + max(1, horizon_h)) % len(rows)]
            if feature_names:
                col_map = {
                    self._x_cols[geo][i]: float(v)
                    for i, v in enumerate(row)
                    if i < len(self._x_cols.get(geo, []))
                }
                from ml.features.engineering import synthetic_value, _pad_or_trim
                vec = [float(col_map.get(n, synthetic_value(n, t))) for n in feature_names]
                return _pad_or_trim(vec, expected_size)
            from ml.features.engineering import _pad_or_trim
            return _pad_or_trim([float(v) for v in row], expected_size)

        if self.has_y(geo):
            rows = self._y[geo]
            row = rows[(seed + max(1, horizon_h)) % len(rows)]
            horizons = extract_target_horizons(self._y_cols.get(geo, []), row)
            if feature_names:
                return vector_from_gap_targets(horizons, feature_names, t, expected_size)
            from ml.features.engineering import _pad_or_trim
            return _pad_or_trim([float(v) for v in horizons], expected_size)

        if self.synthetic and (feature_names or expected_size):
            if feature_names:
                return synthesize_vector(feature_names, t, expected_size)
            from ml.features.engineering import _pad_or_trim
            return _pad_or_trim([0.0] * (expected_size or 0), expected_size)

        raise ValueError(f"no feature data for geo={geo}")

    # ------------------------------------------------------------------ meta
    def vector_source(self, geo: str) -> str:
        if self.has_x(geo):
            return "parquet_x"
        if self.has_y(geo):
            return "parquet_y_derived"
        return "synthetic" if self.synthetic else "missing"
