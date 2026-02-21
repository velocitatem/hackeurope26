from __future__ import annotations

import math
from typing import Any

import requests

from src import config


class EnergyClient:
    def __init__(self, base_url: str | None = None, timeout_s: float = 3.0):
        self.base_url = (base_url or config.ML_INFERENCE_URL).rstrip("/")
        self.timeout_s = timeout_s

    def delta_series(self, geo: str, start_ts: float) -> list[dict[str, float]]:
        try:
            response = requests.get(
                f"{self.base_url}/predict/delta/series",
                params={
                    "geo": geo,
                    "start": start_ts,
                    "horizon_s": config.HORIZON_S,
                    "freq_s": config.FREQ_S,
                },
                timeout=self.timeout_s,
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            series = payload.get("series", [])
            if series:
                return series
        except Exception:
            pass
        return self._fallback_series(geo, start_ts)

    def _fallback_series(self, geo: str, start_ts: float) -> list[dict[str, float]]:
        daily_phase_map = {"FR": math.pi / 4.0, "DE": 0.0, "ES": -math.pi / 6.0}
        trend_phase_map = {
            "FR": 0.0,
            "DE": 2.0 * math.pi / 3.0,
            "ES": 4.0 * math.pi / 3.0,
        }
        daily_phase = daily_phase_map.get(geo, 0.0)
        trend_phase = trend_phase_map.get(geo, 0.0)
        daily_amplitude = 6.5
        trend_amplitude = 2.0
        trend_period_s = 3.0 * 24.0 * 60.0 * 60.0

        series: list[dict[str, float]] = []
        for offset in range(0, config.HORIZON_S + 1, config.FREQ_S):
            t = start_ts + float(offset)
            daily_component = daily_amplitude * math.sin(
                (2.0 * math.pi * t / (24.0 * 60.0 * 60.0)) + daily_phase
            )
            trend_component = trend_amplitude * math.sin(
                (2.0 * math.pi * t / trend_period_s) + trend_phase
            )
            delta = daily_component + trend_component
            series.append({"t": t, "delta": float(delta)})
        return series
