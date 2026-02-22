from src.signals.windows import best_positive_window


def _series(start: int, step: int, deltas: list[float]) -> list[dict[str, float]]:
    return [
        {"t": float(start + idx * step), "delta": delta}
        for idx, delta in enumerate(deltas)
    ]


def test_best_positive_window_finds_highest_average_gap() -> None:
    series = _series(start=0, step=60, deltas=[-1.0, 2.0, 3.0, -1.0, 4.0, 5.0])

    window = best_positive_window(geo="DE", series=series, duration_s=120)

    assert window is not None
    assert window.geo == "DE"
    assert window.start_ts == 240.0
    assert window.end_ts == 300.0
    assert window.avg_delta == 4.5


def test_best_positive_window_returns_none_when_no_positive_gap() -> None:
    series = _series(start=0, step=60, deltas=[-1.0, 0.0, -2.0, 0.0])

    window = best_positive_window(geo="FR", series=series, duration_s=120)

    assert window is None
