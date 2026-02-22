import math
import os
import re
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

try:
    import numpy as np
except Exception:
    np = None

try:
    import onnxruntime as ort
except Exception:
    ort = None

try:
    import joblib
except Exception:
    joblib = None

try:
    import pandas as pd
except Exception:
    pd = None


SECONDS_PER_DAY = 60 * 60 * 24
SECONDS_PER_HOUR = 60 * 60
SUPPORTED_GEOS = ("UK", "FR", "FIN", "IT")
GEO_ALIASES = {
    "GB": "UK",
    "FRANCE": "FR",
    "FI": "FIN",
    "FINLAND": "FIN",
    "ITALY": "IT",
}
MODEL_FILE_RE = re.compile(r"gap_horizon_(\d+)h\.onnx$")
FEATURE_FILE_RE = re.compile(r"([a-z]{2,3})_x_test_set\.parquet$")


class PredictInput(BaseModel):
    geo: Literal["UK", "FR", "FIN", "IT"]
    t: float
    horizon_h: int = 1


class PredictSeriesInput(BaseModel):
    geo: Literal["UK", "FR", "FIN", "IT"]
    start: float
    horizon_s: int = 48 * 60 * 60
    freq_s: int = 30 * 60


class UKOnnxBundle:
    def __init__(self) -> None:
        self.model_dir = Path(
            os.getenv(
                "ML_MODEL_DIR",
                str(Path(__file__).resolve().parent / "models" / "base"),
            )
        )
        self.sessions: dict[int, "ort.InferenceSession"] = {}
        self.load_error: str | None = None
        self.models_loaded = False
        self._load_models()

    def _load_models(self) -> None:
        missing = []
        if ort is None:
            missing.append("onnxruntime")
        if np is None:
            missing.append("numpy")
        if missing:
            self.load_error = f"missing dependencies: {', '.join(missing)}"
            return
        if not self.model_dir.exists():
            self.load_error = f"model directory not found: {self.model_dir}"
            return

        loaded: dict[int, "ort.InferenceSession"] = {}
        for candidate in sorted(self.model_dir.glob("gap_horizon_*h.onnx")):
            match = MODEL_FILE_RE.search(candidate.name)
            if match is None:
                continue
            horizon_h = int(match.group(1))
            try:
                loaded[horizon_h] = ort.InferenceSession(str(candidate))
            except Exception:
                continue

        if not loaded:
            self.load_error = f"no loadable ONNX models in {self.model_dir}"
            return

        self.sessions = loaded
        self.models_loaded = True

    def pick_horizon(self, horizon_h: int) -> int:
        available = sorted(self.sessions.keys())
        if not available:
            return 1
        clamped = max(1, min(available[-1], horizon_h))
        if clamped in self.sessions:
            return clamped
        return min(available, key=lambda h: abs(h - clamped))


class TabularCountryModels:
    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parent
        self.model_paths = {
            "FR": Path(
                os.getenv("ML_FR_MODEL_PATH", str(base_dir / "fr" / "fr_model.joblib"))
            ),
            "FIN": Path(
                os.getenv(
                    "ML_FIN_MODEL_PATH", str(base_dir / "fin" / "fin_model.joblib")
                )
            ),
            "IT": Path(
                os.getenv("ML_IT_MODEL_PATH", str(base_dir / "it" / "it_model.joblib"))
            ),
        }
        self.models: dict[str, Any] = {}
        self.load_errors: dict[str, str] = {}
        self._load_models()

    def _load_models(self) -> None:
        if joblib is None:
            for geo in self.model_paths:
                self.load_errors[geo] = "missing dependency: joblib"
            return

        for geo, path in self.model_paths.items():
            if not path.exists():
                self.load_errors[geo] = f"model file not found: {path}"
                continue
            try:
                self.models[geo] = joblib.load(path)
            except Exception as exc:
                self.load_errors[geo] = f"failed to load model: {exc}"

    def is_loaded(self, geo: str) -> bool:
        return geo in self.models

    def get_model(self, geo: str) -> Any:
        return self.models[geo]

    def required_features(self, geo: str) -> int | None:
        model = self.models.get(geo)
        if model is None:
            return None

        if hasattr(model, "n_features_in_"):
            return int(model.n_features_in_)

        estimators = getattr(model, "estimators_", None)
        if estimators:
            first = estimators[0]
            if hasattr(first, "n_features_in_"):
                return int(first.n_features_in_)

        return None


class QuantifidFeatureStore:
    def __init__(self) -> None:
        self.feature_dir = Path(
            os.getenv(
                "ML_FEATURES_DIR",
                str(Path(__file__).resolve().parent / "features_quantifid"),
            )
        )
        self.vectors: dict[str, list[list[float]]] = {}
        self.feature_count: dict[str, int] = {}
        self.load_errors: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if pd is None:
            self.load_errors["GLOBAL"] = "missing dependency: pandas"
            return
        if not self.feature_dir.exists():
            self.load_errors["GLOBAL"] = (
                f"feature directory not found: {self.feature_dir}"
            )
            return

        for candidate in sorted(self.feature_dir.glob("*_x_test_set.parquet")):
            match = FEATURE_FILE_RE.search(candidate.name)
            if match is None:
                continue
            geo = match.group(1).upper()
            if geo == "FI":
                geo = "FIN"
            try:
                df = pd.read_parquet(candidate)
                if df.empty:
                    self.load_errors[geo] = f"feature set empty: {candidate.name}"
                    continue
                prepared = df.copy()
                for col in prepared.columns:
                    series = prepared[col]
                    if getattr(series.dtype, "kind", "") == "M":
                        prepared[col] = series.astype("int64") / 1_000_000_000.0
                    else:
                        prepared[col] = pd.to_numeric(series, errors="coerce")
                prepared = prepared.fillna(0.0)
                matrix = prepared.astype("float32").values.tolist()
                self.vectors[geo] = matrix
                self.feature_count[geo] = int(len(matrix[0]))
            except Exception as exc:
                self.load_errors[geo] = f"failed to load features: {exc}"

    def has_geo(self, geo: str) -> bool:
        return geo in self.vectors and len(self.vectors[geo]) > 0

    def vector_for(self, geo: str, t: float, horizon_h: int) -> list[float]:
        rows = self.vectors.get(geo)
        if not rows:
            raise ValueError(f"no hardcoded feature vectors for {geo}")
        seed = int(max(0.0, t)) // SECONDS_PER_HOUR
        idx = int((seed + max(1, horizon_h)) % len(rows))
        return rows[idx]

    def feature_names(self, geo: str) -> list[str] | None:
        model = self.models.get(geo)
        if model is None:
            return None

        if hasattr(model, "feature_names_in_"):
            return [str(name) for name in model.feature_names_in_]

        estimators = getattr(model, "estimators_", None)
        if estimators:
            first = estimators[0]
            if hasattr(first, "feature_names_in_"):
                return [str(name) for name in first.feature_names_in_]

        return None


_UK_MODELS = UKOnnxBundle()
_TABULAR_MODELS = TabularCountryModels()
_FEATURE_STORE = QuantifidFeatureStore()


def _normalize_geo(geo: str) -> str:
    normalized = geo.strip().upper()
    return GEO_ALIASES.get(normalized, normalized)


def _mock_delta_at(t: float) -> float:
    return float(
        6.5 * math.sin((2.0 * math.pi * t / SECONDS_PER_DAY) - (math.pi / 10.0))
    )


def _time_features(t: float) -> list[float]:
    day_pos = (t % SECONDS_PER_DAY) / float(SECONDS_PER_DAY)
    week_pos = (t % (7 * SECONDS_PER_DAY)) / float(7 * SECONDS_PER_DAY)
    return [
        math.sin(2.0 * math.pi * day_pos),
        math.cos(2.0 * math.pi * day_pos),
        math.sin(2.0 * math.pi * week_pos),
        math.cos(2.0 * math.pi * week_pos),
        day_pos,
        week_pos,
        t / float(SECONDS_PER_DAY),
        1.0,
    ]


def _build_input_tensor(expected_shape: list[int], t: float) -> "np.ndarray":
    base = np.asarray(_time_features(t), dtype=np.float32)

    if not expected_shape:
        expected_shape = [1, len(base)]

    target_shape = list(expected_shape)
    for idx, dim in enumerate(target_shape):
        if dim <= 0:
            target_shape[idx] = 1 if idx < len(target_shape) - 1 else len(base)

    total_size = math.prod(target_shape)
    payload = np.zeros((total_size,), dtype=np.float32)
    payload[: min(total_size, len(base))] = base[: min(total_size, len(base))]
    return payload.reshape(tuple(target_shape))


def _predict_uk_delta(t: float, horizon_h: int) -> tuple[float, int]:
    selected_h = _UK_MODELS.pick_horizon(horizon_h)
    session = _UK_MODELS.sessions[selected_h]
    input_meta = session.get_inputs()[0]
    input_shape = [dim if isinstance(dim, int) else 0 for dim in input_meta.shape]
    x = _build_input_tensor(input_shape, t)
    y = session.run(None, {input_meta.name: x})[0]
    delta = float(np.asarray(y, dtype=np.float32).reshape(-1)[0])
    return delta, selected_h


def _resolve_feature_vector(geo: str, t: float, horizon_h: int) -> list[float]:
    vector = _FEATURE_STORE.vector_for(geo=geo, t=t, horizon_h=horizon_h)
    expected = _TABULAR_MODELS.required_features(geo)
    if expected is not None and len(vector) != expected:
        if len(vector) < expected:
            vector = [*vector, *([0.0] * (expected - len(vector)))]
        else:
            vector = vector[:expected]
    return [float(v) for v in vector]


def _predict_tabular_delta(
    geo: str,
    t: float,
    horizon_h: int,
) -> tuple[float, int]:
    model = _TABULAR_MODELS.get_model(geo)
    vector = _resolve_feature_vector(geo=geo, t=t, horizon_h=horizon_h)
    x = np.asarray([vector], dtype=np.float32)

    y = model.predict(x)
    flat = np.asarray(y, dtype=np.float32).reshape(-1)
    if flat.size == 0:
        raise ValueError("model returned empty prediction")

    max_h = int(flat.size)
    selected_h = max(1, min(max_h, int(horizon_h)))
    delta = float(flat[selected_h - 1])
    return delta, selected_h


def _predict_tabular_series(
    geo: str,
    start: float,
    horizon_s: int,
    freq_s: int,
) -> list[dict[str, float]]:
    points = []
    for offset in range(0, horizon_s + 1, freq_s):
        t = start + float(offset)
        requested_h = max(
            1, int(math.ceil((offset + freq_s) / float(SECONDS_PER_HOUR)))
        )
        delta, used_h = _predict_tabular_delta(
            geo=geo,
            t=t,
            horizon_h=requested_h,
        )
        points.append({"t": t, "delta": float(delta), "horizon_h": used_h})

    return points


def _geo_readiness_error(geo: str) -> str | None:
    if np is None:
        return "numpy is required for inference"
    if geo == "UK":
        if not _UK_MODELS.models_loaded:
            return _UK_MODELS.load_error or "UK ONNX models are not loaded"
        return None
    if geo in ("FR", "FIN", "IT"):
        if not _TABULAR_MODELS.is_loaded(geo):
            return _TABULAR_MODELS.load_errors.get(
                geo, f"{geo} tabular model is not loaded"
            )
        if not _FEATURE_STORE.has_geo(geo):
            return _FEATURE_STORE.load_errors.get(
                geo, f"{geo} hardcoded feature vectors are not loaded"
            )
        return None
    return f"unsupported geo '{geo}'"


def _ensure_geo_ready(geo: str) -> None:
    err = _geo_readiness_error(geo)
    if err:
        raise HTTPException(
            status_code=503, detail=f"Inference unavailable for {geo}: {err}"
        )


app = FastAPI(title="ML Inference API", version="1.1.0")


@app.get("/health")
def health_check() -> dict:
    loaded_tabular_geos = sorted(_TABULAR_MODELS.models.keys())
    tabular_required = {
        geo: _TABULAR_MODELS.required_features(geo) for geo in loaded_tabular_geos
    }
    readiness = {
        geo: {
            "ready": _geo_readiness_error(geo) is None,
            "error": _geo_readiness_error(geo),
        }
        for geo in SUPPORTED_GEOS
    }
    return {
        "status": "healthy",
        "service": "ml-inference",
        "mode": "model-only",
        "uk": {
            "model_dir": str(_UK_MODELS.model_dir),
            "loaded_horizons_h": sorted(_UK_MODELS.sessions.keys()),
            "load_error": _UK_MODELS.load_error,
        },
        "tabular": {
            "loaded_geos": loaded_tabular_geos,
            "required_features": tabular_required,
            "load_errors": _TABULAR_MODELS.load_errors,
        },
        "hardcoded_feature_vectors": {
            "feature_dir": str(_FEATURE_STORE.feature_dir),
            "loaded_geos": sorted(_FEATURE_STORE.vectors.keys()),
            "feature_count": _FEATURE_STORE.feature_count,
            "load_errors": _FEATURE_STORE.load_errors,
        },
        "readiness": readiness,
    }


@app.get("/predict/delta")
def predict_delta(
    geo: str = Query(..., description="Geography code: UK, FR, FIN, IT"),
    t: float = Query(..., description="Epoch timestamp in seconds"),
    horizon_h: int = Query(1, ge=1, le=24, description="Forecast horizon in hours"),
) -> dict:
    geo_norm = _normalize_geo(geo)
    if geo_norm not in SUPPORTED_GEOS:
        raise HTTPException(status_code=400, detail=f"Unsupported geo '{geo}'")
    _ensure_geo_ready(geo_norm)

    try:
        if geo_norm == "UK":
            delta, used_h = _predict_uk_delta(t=t, horizon_h=horizon_h)
            source = f"onnx_gap_horizon_{used_h}h"
        else:
            delta, used_h = _predict_tabular_delta(
                geo=geo_norm,
                t=t,
                horizon_h=horizon_h,
            )
            source = f"joblib_{geo_norm.lower()}_gap_model"
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Model inference failed: {exc}"
        ) from exc

    return {
        "geo": geo_norm,
        "t": t,
        "horizon_h": used_h,
        "delta": delta,
        "source": source,
    }


@app.post("/predict/delta")
def predict_delta_post(payload: PredictInput) -> dict:
    geo_norm = _normalize_geo(payload.geo)
    if geo_norm not in SUPPORTED_GEOS:
        raise HTTPException(status_code=400, detail=f"Unsupported geo '{payload.geo}'")
    _ensure_geo_ready(geo_norm)

    if geo_norm == "UK":
        return predict_delta(geo=geo_norm, t=payload.t, horizon_h=payload.horizon_h)

    try:
        delta, used_h = _predict_tabular_delta(
            geo=geo_norm,
            t=payload.t,
            horizon_h=payload.horizon_h,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "geo": geo_norm,
        "t": payload.t,
        "horizon_h": used_h,
        "delta": delta,
        "source": f"joblib_{geo_norm.lower()}_gap_model",
    }


@app.get("/predict/delta/series")
def predict_delta_series(
    geo: str = Query(..., description="Geography code: UK, FR, FIN, IT"),
    start: float = Query(..., description="Start epoch timestamp in seconds"),
    horizon_s: int = Query(48 * 60 * 60, ge=60, le=7 * 24 * 60 * 60),
    freq_s: int = Query(30 * 60, ge=60, le=6 * 60 * 60),
) -> dict:
    geo_norm = _normalize_geo(geo)
    if geo_norm not in SUPPORTED_GEOS:
        raise HTTPException(status_code=400, detail=f"Unsupported geo '{geo}'")
    _ensure_geo_ready(geo_norm)

    points = []
    for offset in range(0, horizon_s + 1, freq_s):
        t = start + float(offset)
        requested_h = max(
            1, int(math.ceil((offset + freq_s) / float(SECONDS_PER_HOUR)))
        )
        try:
            if geo_norm == "UK":
                delta, used_h = _predict_uk_delta(t=t, horizon_h=requested_h)
            else:
                delta, used_h = _predict_tabular_delta(
                    geo=geo_norm,
                    t=t,
                    horizon_h=requested_h,
                )
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Model inference failed: {exc}"
            ) from exc
        points.append({"t": t, "delta": delta, "horizon_h": used_h})

    return {
        "geo": geo_norm,
        "start": start,
        "horizon_s": horizon_s,
        "freq_s": freq_s,
        "series": points,
        "source": "onnx_gap_horizon_ensemble"
        if geo_norm == "UK"
        else f"joblib_{geo_norm.lower()}_gap_model",
    }


@app.post("/predict/delta/series")
def predict_delta_series_post(payload: PredictSeriesInput) -> dict:
    geo_norm = _normalize_geo(payload.geo)
    if geo_norm not in SUPPORTED_GEOS:
        raise HTTPException(status_code=400, detail=f"Unsupported geo '{payload.geo}'")

    if payload.horizon_s < 60 or payload.horizon_s > 7 * 24 * 60 * 60:
        raise HTTPException(status_code=400, detail="horizon_s must be in [60, 604800]")
    if payload.freq_s < 60 or payload.freq_s > 6 * 60 * 60:
        raise HTTPException(status_code=400, detail="freq_s must be in [60, 21600]")

    if _use_mock_mode_for_geo(geo_norm):
        return predict_delta_series(
            geo=geo_norm,
            start=payload.start,
            horizon_s=payload.horizon_s,
            freq_s=payload.freq_s,
        )

    if geo_norm == "UK":
        return predict_delta_series(
            geo=geo_norm,
            start=payload.start,
            horizon_s=payload.horizon_s,
            freq_s=payload.freq_s,
        )

    try:
        points = _predict_tabular_series(
            geo=geo_norm,
            start=payload.start,
            horizon_s=payload.horizon_s,
            freq_s=payload.freq_s,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "geo": geo_norm,
        "start": payload.start,
        "horizon_s": payload.horizon_s,
        "freq_s": payload.freq_s,
        "series": points,
        "source": f"joblib_{geo_norm.lower()}_gap_model",
    }
