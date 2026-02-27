"""ONNX-based multi-horizon predictor (used for UK).

Model directory layout::

    {model_dir}/
        gap_horizon_1h.onnx
        gap_horizon_2h.onnx
        ...
        gap_horizon_12h.onnx

Directory is resolved in order:
1. ``model_dir`` constructor arg
2. ``ML_MODEL_DIR`` env var
3. ``ml/models/base/``  (legacy)
4. ``ml/artifacts/geo/{GEO}/onnx/``
"""
from __future__ import annotations

import math
import os
import re
from pathlib import Path

_MODEL_RE = re.compile(r"gap_horizon_(\d+)h\.onnx$")
SECONDS_PER_DAY = 60 * 60 * 24
SECONDS_PER_HOUR = 60 * 60


def _time_features(t: float) -> list[float]:
    day_pos = (t % SECONDS_PER_DAY) / float(SECONDS_PER_DAY)
    week_pos = (t % (7 * SECONDS_PER_DAY)) / float(7 * SECONDS_PER_DAY)
    return [
        math.sin(2.0 * math.pi * day_pos),
        math.cos(2.0 * math.pi * day_pos),
        math.sin(2.0 * math.pi * week_pos),
        math.cos(2.0 * math.pi * week_pos),
        day_pos, week_pos,
        t / float(SECONDS_PER_DAY),
        1.0,
    ]


class OnnxGeoPredictor:
    """Wraps a directory of per-horizon ONNX models for one geo."""

    def __init__(self, geo: str, model_dir: str | Path | None = None):
        self._geo = geo
        self._model_dir = Path(
            model_dir
            or os.getenv("ML_MODEL_DIR", "")
            or Path(__file__).resolve().parents[1] / "models" / "base"
        )
        self._sessions: dict[int, object] = {}
        self._error: str | None = None
        self._load()

    @property
    def geo(self) -> str:
        return self._geo

    def _load(self) -> None:
        try:
            import onnxruntime as ort
            import numpy  # noqa: F401 -- ensure numpy available too
        except ModuleNotFoundError as exc:
            self._error = f"missing dependency: {exc}"
            return

        if not self._model_dir.exists():
            # also try artifacts layout
            alt = Path(__file__).resolve().parents[1] / "artifacts" / "geo" / self._geo / "onnx"
            if alt.exists():
                self._model_dir = alt
            else:
                self._error = f"model directory not found: {self._model_dir}"
                return

        loaded: dict[int, object] = {}
        for candidate in sorted(self._model_dir.glob("gap_horizon_*h.onnx")):
            m = _MODEL_RE.search(candidate.name)
            if m is None:
                continue
            try:
                loaded[int(m.group(1))] = ort.InferenceSession(str(candidate))
            except Exception:
                continue

        if not loaded:
            self._error = f"no loadable ONNX models in {self._model_dir}"
            return
        self._sessions = loaded

    def is_ready(self) -> bool:
        return bool(self._sessions)

    def load_error(self) -> str | None:
        return self._error

    def _pick(self, horizon_h: int) -> int:
        available = sorted(self._sessions.keys())
        clamped = max(1, min(available[-1], horizon_h))
        if clamped in self._sessions:
            return clamped
        return min(available, key=lambda h: abs(h - clamped))

    def _run(self, t: float, horizon_h: int) -> tuple[float, int]:
        import numpy as np

        selected = self._pick(horizon_h)
        session = self._sessions[selected]
        meta = session.get_inputs()[0]
        shape = [d if isinstance(d, int) else 0 for d in meta.shape]
        base = np.asarray(_time_features(t), dtype=np.float32)
        if not shape:
            shape = [1, len(base)]
        target = list(shape)
        for i, d in enumerate(target):
            if d <= 0:
                target[i] = 1 if i < len(target) - 1 else len(base)
        total = math.prod(target)
        payload = np.zeros((total,), dtype=np.float32)
        payload[: min(total, len(base))] = base[: min(total, len(base))]
        x = payload.reshape(tuple(target))
        y = session.run(None, {meta.name: x})[0]
        delta = float(np.asarray(y, dtype=np.float32).reshape(-1)[0])
        return delta, selected

    def predict(self, t: float, horizon_h: int) -> tuple[float, int]:
        return self._run(t, horizon_h)

    def predict_series(
        self, start: float, horizon_s: int, freq_s: int
    ) -> list[dict[str, float]]:
        import math as _math
        points = []
        for offset in range(0, horizon_s + 1, freq_s):
            t = start + float(offset)
            req_h = max(1, int(_math.ceil((offset + freq_s) / float(SECONDS_PER_HOUR))))
            delta, used_h = self._run(t, req_h)
            points.append({"t": t, "delta": float(delta), "horizon_h": used_h})
        return points
