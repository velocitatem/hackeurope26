"""FastAPI inference server for energy-gap delta prediction.

Delegates all model logic to ml.geo (GeoRegistry) and ml.features (FeatureStore).
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Literal

from ml.features.store import FeatureStore
from ml.geo.registry import GeoRegistry, SUPPORTED, normalize_geo


_STORE = FeatureStore()
_REGISTRY = GeoRegistry(feature_store=_STORE)

app = FastAPI(title="ML Inference API", version="2.0.0")


class PredictInput(BaseModel):
    geo: Literal["UK", "FR", "FIN", "IT"]
    t: float
    horizon_h: int = 1


class PredictSeriesInput(BaseModel):
    geo: Literal["UK", "FR", "FIN", "IT"]
    start: float
    horizon_s: int = 48 * 60 * 60
    freq_s: int = 30 * 60


def _check(geo: str) -> None:
    if geo not in SUPPORTED:
        raise HTTPException(status_code=400, detail=f"Unsupported geo '{geo}'")
    if not _REGISTRY.is_ready(geo):
        err = _REGISTRY.load_error(geo)
        raise HTTPException(status_code=503, detail=f"Inference unavailable for {geo}: {err}")


@app.get("/health")
def health() -> dict:
    return {
        "status": "healthy",
        "service": "ml-inference",
        "readiness": _REGISTRY.readiness(),
        "feature_store": {
            "x_geos": sorted(_STORE._x.keys()),
            "y_geos": sorted(_STORE._y.keys()),
            "errors": _STORE.errors,
        },
    }


@app.get("/predict/delta")
def predict_delta(
    geo: str = Query(...),
    t: float = Query(...),
    horizon_h: int = Query(1, ge=1, le=24),
) -> dict:
    geo_norm = normalize_geo(geo)
    _check(geo_norm)
    try:
        delta, used_h = _REGISTRY.get(geo_norm).predict(t, horizon_h)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"geo": geo_norm, "t": t, "horizon_h": used_h, "delta": delta}


@app.post("/predict/delta")
def predict_delta_post(payload: PredictInput) -> dict:
    geo_norm = normalize_geo(payload.geo)
    _check(geo_norm)
    try:
        delta, used_h = _REGISTRY.get(geo_norm).predict(payload.t, payload.horizon_h)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"geo": geo_norm, "t": payload.t, "horizon_h": used_h, "delta": delta}


@app.get("/predict/delta/series")
def predict_delta_series(
    geo: str = Query(...),
    start: float = Query(...),
    horizon_s: int = Query(48 * 60 * 60, ge=60, le=7 * 24 * 60 * 60),
    freq_s: int = Query(30 * 60, ge=60, le=6 * 60 * 60),
) -> dict:
    geo_norm = normalize_geo(geo)
    _check(geo_norm)
    try:
        series = _REGISTRY.get(geo_norm).predict_series(start, horizon_s, freq_s)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"geo": geo_norm, "start": start, "horizon_s": horizon_s, "freq_s": freq_s, "series": series}


@app.post("/predict/delta/series")
def predict_delta_series_post(payload: PredictSeriesInput) -> dict:
    geo_norm = normalize_geo(payload.geo)
    _check(geo_norm)
    if not (60 <= payload.horizon_s <= 7 * 24 * 60 * 60):
        raise HTTPException(status_code=400, detail="horizon_s out of range")
    if not (60 <= payload.freq_s <= 6 * 60 * 60):
        raise HTTPException(status_code=400, detail="freq_s out of range")
    try:
        series = _REGISTRY.get(geo_norm).predict_series(
            payload.start, payload.horizon_s, payload.freq_s
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "geo": geo_norm,
        "start": payload.start,
        "horizon_s": payload.horizon_s,
        "freq_s": payload.freq_s,
        "series": series,
    }
