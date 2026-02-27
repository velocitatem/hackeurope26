"""Pure feature engineering functions for energy-gap prediction.

All functions are stateless - they transform a timestamp and optional
context into a feature value or vector. No side effects.
"""
from __future__ import annotations

import math
import re
from typing import Any

SECONDS_PER_DAY = 60 * 60 * 24
SECONDS_PER_HOUR = 60 * 60

GAP_TARGET_RE = re.compile(r"gap_t_plus_(\d+)h$", re.IGNORECASE)

_TEMPORAL_KEYS = {
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "month_sin", "month_cos", "hour", "dow", "month",
}


def temporal_features(t: float) -> dict[str, float]:
    """Cyclic time encoding from epoch seconds."""
    day_pos = (t % SECONDS_PER_DAY) / float(SECONDS_PER_DAY)
    week_pos = (t % (7 * SECONDS_PER_DAY)) / float(7 * SECONDS_PER_DAY)
    hour = int((t // SECONDS_PER_HOUR) % 24)
    dow = int((t // SECONDS_PER_DAY) % 7)
    month = int(((t // SECONDS_PER_DAY) // 30) % 12) + 1
    return {
        "hour": float(hour),
        "dow": float(dow),
        "month": float(month),
        "hour_sin": math.sin(2.0 * math.pi * day_pos),
        "hour_cos": math.cos(2.0 * math.pi * day_pos),
        "dow_sin": math.sin(2.0 * math.pi * week_pos),
        "dow_cos": math.cos(2.0 * math.pi * week_pos),
        "month_sin": math.sin(2.0 * math.pi * month / 12.0),
        "month_cos": math.cos(2.0 * math.pi * month / 12.0),
    }


def synthetic_value(feature_name: str, t: float) -> float:
    """Fallback synthetic value for a single named feature."""
    key = feature_name.lower()
    temps = temporal_features(t)
    if key in temps:
        return temps[key]
    if "share" in key:
        return 0.25
    return 0.0


def synthesize_vector(
    feature_names: list[str], t: float, expected_size: int | None = None
) -> list[float]:
    """Build a full feature vector from names using synthetic values."""
    vector = [synthetic_value(name, t) for name in feature_names]
    return _pad_or_trim(vector, expected_size)


def vector_from_gap_targets(
    horizons: list[float],
    feature_names: list[str],
    t: float,
    expected_size: int | None = None,
) -> list[float]:
    """Map gap horizon predictions back into model feature space."""
    if not horizons:
        horizons = [0.0]
    base = horizons[0]
    mean = sum(horizons) / len(horizons)
    mn, mx = min(horizons), max(horizons)

    vector: list[float] = []
    for name in feature_names:
        key = name.lower()
        lag_m = re.search(r"_lag_(\d+)$", key)
        if key == "gap":
            v = base
        elif lag_m:
            lag = int(lag_m.group(1))
            v = horizons[(max(1, lag) - 1) % len(horizons)]
        elif "roll_mean" in key or "ewm" in key:
            v = mean
        elif "roll_min" in key:
            v = mn
        elif "roll_max" in key:
            v = mx
        elif "imbalance_log_ratio" in key:
            v = math.log1p(abs(base))
        elif "gen_minus_load" in key:
            v = base
        elif key in _TEMPORAL_KEYS:
            v = synthetic_value(key, t)
        elif "fossil_share" in key or "renewable_share" in key:
            v = 0.25
        else:
            v = horizons[len(vector) % len(horizons)]
        vector.append(float(v))

    return _pad_or_trim(vector, expected_size)


def extract_target_horizons(columns: list[str], row: list[float]) -> list[float]:
    """Extract ordered gap horizon values from a target row."""
    ordered: list[tuple[int, float]] = []
    for idx, name in enumerate(columns):
        m = GAP_TARGET_RE.search(name.strip())
        if m and idx < len(row):
            ordered.append((int(m.group(1)), float(row[idx])))
    if ordered:
        ordered.sort(key=lambda x: x[0])
        return [v for _, v in ordered]
    return [float(v) for v in row]


def prepare_numeric_df(df: Any) -> Any:  # type: ignore[return]
    """Convert a DataFrame to all-float, replacing datetimes with epoch floats."""
    try:
        import pandas as pd
    except ModuleNotFoundError:
        return df
    prepared = df.copy()
    for col in prepared.columns:
        if getattr(prepared[col].dtype, "kind", "") == "M":
            prepared[col] = prepared[col].astype("int64") / 1_000_000_000.0
        else:
            prepared[col] = pd.to_numeric(prepared[col], errors="coerce")
    return prepared.fillna(0.0)


def _pad_or_trim(vector: list[float], size: int | None) -> list[float]:
    if size is None or len(vector) == size:
        return vector
    if len(vector) < size:
        return [*vector, *([0.0] * (size - len(vector)))]
    return vector[:size]
