import math
import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel


SECONDS_PER_DAY = 60 * 60 * 24
SUPPORTED_GEOS = ("FR", "DE", "ES")

# Deterministic sinusoidal mock until trained models are wired.
GEO_PARAMS = {
    "FR": {"amplitude": 5.0, "phase": math.pi / 4.0},
    "DE": {"amplitude": 8.0, "phase": 0.0},
    "ES": {"amplitude": 7.0, "phase": -math.pi / 6.0},
}


class PredictInput(BaseModel):
    geo: Literal["FR", "DE", "ES"]
    t: float


def _delta_at(geo: str, t: float) -> float:
    params = GEO_PARAMS[geo]
    phase = params["phase"]
    amplitude = params["amplitude"]
    # t is unix epoch seconds, projected to day cycle.
    return float(amplitude * math.sin((2.0 * math.pi * t / SECONDS_PER_DAY) + phase))


app = FastAPI(title="ML Inference API", version="1.0.0")


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "healthy",
        "service": "ml-inference",
        "mode": "mock" if os.getenv("ML_MOCK", "true").lower() == "true" else "model",
    }


@app.get("/predict/delta")
def predict_delta(
    geo: str = Query(..., description="Geography code: FR, DE, ES"),
    t: float = Query(..., description="Epoch timestamp in seconds"),
) -> dict:
    if geo not in SUPPORTED_GEOS:
        raise HTTPException(status_code=400, detail=f"Unsupported geo '{geo}'")
    return {"geo": geo, "t": t, "delta": _delta_at(geo, t), "source": "mock_sinusoidal"}


@app.post("/predict/delta")
def predict_delta_post(payload: PredictInput) -> dict:
    return {
        "geo": payload.geo,
        "t": payload.t,
        "delta": _delta_at(payload.geo, payload.t),
        "source": "mock_sinusoidal",
    }


@app.get("/predict/delta/series")
def predict_delta_series(
    geo: str = Query(..., description="Geography code: FR, DE, ES"),
    start: float = Query(..., description="Start epoch timestamp in seconds"),
    horizon_s: int = Query(48 * 60 * 60, ge=60, le=7 * 24 * 60 * 60),
    freq_s: int = Query(30 * 60, ge=60, le=6 * 60 * 60),
) -> dict:
    if geo not in SUPPORTED_GEOS:
        raise HTTPException(status_code=400, detail=f"Unsupported geo '{geo}'")
    points = []
    for offset in range(0, horizon_s + 1, freq_s):
        t = start + float(offset)
        points.append({"t": t, "delta": _delta_at(geo, t)})
    return {
        "geo": geo,
        "start": start,
        "horizon_s": horizon_s,
        "freq_s": freq_s,
        "series": points,
        "source": "mock_sinusoidal",
    }
