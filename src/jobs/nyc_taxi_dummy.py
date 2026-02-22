from __future__ import annotations

import random


def generate_rows(n: int = 5000, seed: int = 42) -> list[list[float]]:
    random.seed(seed)
    rows: list[list[float]] = []
    for _ in range(n):
        pickup_hour = random.randint(0, 23)
        trip_distance = max(0.5, random.gauss(4.0, 1.8))
        passengers = random.randint(1, 4)
        is_peak = 1.0 if pickup_hour in {7, 8, 9, 16, 17, 18, 19} else 0.0
        fare = (
            2.5
            + 2.2 * trip_distance
            + 0.6 * passengers
            + 1.8 * is_peak
            + random.gauss(0.0, 1.0)
        )
        rows.append(
            [
                pickup_hour / 23.0,
                trip_distance / 10.0,
                passengers / 4.0,
                is_peak,
                fare,
            ]
        )
    return rows


def train_linear_regression(
    rows: list[list[float]], epochs: int = 100
) -> tuple[list[float], float]:
    w = [0.0, 0.0, 0.0, 0.0]
    b = 0.0
    lr = 0.08

    for epoch in range(1, epochs + 1):
        grad_w = [0.0, 0.0, 0.0, 0.0]
        grad_b = 0.0
        mse = 0.0

        for x1, x2, x3, x4, y in rows:
            pred = (w[0] * x1) + (w[1] * x2) + (w[2] * x3) + (w[3] * x4) + b
            err = pred - y
            mse += err * err
            grad_w[0] += err * x1
            grad_w[1] += err * x2
            grad_w[2] += err * x3
            grad_w[3] += err * x4
            grad_b += err

        n = float(len(rows))
        for i in range(4):
            w[i] -= lr * (2.0 / n) * grad_w[i]
        b -= lr * (2.0 / n) * grad_b

        if epoch % 20 == 0:
            print(f"epoch={epoch} mse={mse / n:.4f}")

    return w, b


def main() -> None:
    rows = generate_rows()
    w, b = train_linear_regression(rows)

    sample = [14 / 23.0, 3.2 / 10.0, 2 / 4.0, 0.0]
    sample_fare = sum(sample[i] * w[i] for i in range(4)) + b

    print("training complete")
    print("sample_input={'pickup_hour': 14, 'trip_distance': 3.2, 'passengers': 2}")
    print(f"predicted_fare_usd={sample_fare:.2f}")


if __name__ == "__main__":
    main()
