from __future__ import annotations

from src import config
from src.models import TimeWindow


def best_positive_window(
    geo: str, series: list[dict[str, float]], duration_s: int
) -> TimeWindow | None:
    if len(series) < 2:
        return None

    freq_s = int(series[1]["t"] - series[0]["t"])
    steps = max(1, duration_s // freq_s)
    if len(series) < steps:
        return None

    deltas = [point["delta"] for point in series]
    times = [point["t"] for point in series]

    best: TimeWindow | None = None
    for i in range(0, len(series) - steps + 1):
        window_deltas = deltas[i : i + steps]
        if any(delta <= config.MIN_DELTA_THRESHOLD for delta in window_deltas):
            continue
        avg_delta = sum(window_deltas) / len(window_deltas)
        candidate = TimeWindow(
            geo=geo,
            start_ts=times[i],
            end_ts=times[i + steps - 1],
            avg_delta=avg_delta,
        )
        if best is None or candidate.avg_delta > best.avg_delta:
            best = candidate

    return best
