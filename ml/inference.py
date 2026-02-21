import math
import os
import re
from pathlib import Path
from typing import Literal

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


SECONDS_PER_DAY = 60 * 60 * 24
SECONDS_PER_HOUR = 60 * 60
SUPPORTED_GEOS = ("UK",)
GEO_ALIASES = {"GB": "UK"}
MODEL_FILE_RE = re.compile(r"gap_horizon_(\d+)h\.onnx$")


class PredictInput(BaseModel):
    geo: Literal["UK"]
    t: float
    horizon_h: int = 1


class ModelBundle:
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


_MODEL_BUNDLE = ModelBundle()


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


def _predict_model_delta(t: float, horizon_h: int) -> tuple[float, int]:
    selected_h = _MODEL_BUNDLE.pick_horizon(horizon_h)
    session = _MODEL_BUNDLE.sessions[selected_h]
    input_meta = session.get_inputs()[0]
    input_shape = [dim if isinstance(dim, int) else 0 for dim in input_meta.shape]
    x = _build_input_tensor(input_shape, t)
    y = session.run(None, {input_meta.name: x})[0]
    delta = float(np.asarray(y, dtype=np.float32).reshape(-1)[0])
    return delta, selected_h


def _use_mock_mode() -> bool:
    env_flag = os.getenv("ML_MOCK", "false").strip().lower() == "true"
    return env_flag or (not _MODEL_BUNDLE.models_loaded)


app = FastAPI(title="ML Inference API", version="1.0.0")


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "healthy",
        "service": "ml-inference",
        "mode": "mock" if _use_mock_mode() else "model",
        "model_dir": str(_MODEL_BUNDLE.model_dir),
        "loaded_horizons_h": sorted(_MODEL_BUNDLE.sessions.keys()),
        "load_error": _MODEL_BUNDLE.load_error,
    }


@app.get("/predict/delta")
def predict_delta(
    geo: str = Query(..., description="Geography code: UK"),
    t: float = Query(..., description="Epoch timestamp in seconds"),
    horizon_h: int = Query(1, ge=1, le=24, description="Forecast horizon in hours"),
) -> dict:
    geo_norm = _normalize_geo(geo)
    if geo_norm not in SUPPORTED_GEOS:
        raise HTTPException(status_code=400, detail=f"Unsupported geo '{geo}'")

    if _use_mock_mode():
        return {
            "geo": geo_norm,
            "t": t,
            "horizon_h": horizon_h,
            "delta": _mock_delta_at(t),
            "source": "mock_sinusoidal",
        }

    try:
        delta, used_h = _predict_model_delta(t=t, horizon_h=horizon_h)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"ONNX inference failed: {exc}"
        ) from exc

    return {
        "geo": geo_norm,
        "t": t,
        "horizon_h": used_h,
        "delta": delta,
        "source": f"onnx_gap_horizon_{used_h}h",
    }


@app.post("/predict/delta")
def predict_delta_post(payload: PredictInput) -> dict:
    return predict_delta(geo=payload.geo, t=payload.t, horizon_h=payload.horizon_h)


@app.get("/predict/delta/series")
def predict_delta_series(
    geo: str = Query(..., description="Geography code: UK"),
    start: float = Query(..., description="Start epoch timestamp in seconds"),
    horizon_s: int = Query(48 * 60 * 60, ge=60, le=7 * 24 * 60 * 60),
    freq_s: int = Query(30 * 60, ge=60, le=6 * 60 * 60),
) -> dict:
    geo_norm = _normalize_geo(geo)
    if geo_norm not in SUPPORTED_GEOS:
        raise HTTPException(status_code=400, detail=f"Unsupported geo '{geo}'")

    points = []
    for offset in range(0, horizon_s + 1, freq_s):
        t = start + float(offset)
        if _use_mock_mode():
            points.append({"t": t, "delta": _mock_delta_at(t), "horizon_h": 1})
            continue

        requested_h = max(
            1, int(math.ceil((offset + freq_s) / float(SECONDS_PER_HOUR)))
        )
        try:
            delta, used_h = _predict_model_delta(t=t, horizon_h=requested_h)
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"ONNX inference failed: {exc}"
            ) from exc
        points.append({"t": t, "delta": delta, "horizon_h": used_h})

    return {
        "geo": geo_norm,
        "start": start,
        "horizon_s": horizon_s,
        "freq_s": freq_s,
        "series": points,
        "source": "mock_sinusoidal"
        if _use_mock_mode()
        else "onnx_gap_horizon_ensemble",
    }
