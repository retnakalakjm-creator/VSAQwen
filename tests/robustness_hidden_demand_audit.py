from __future__ import annotations

import random


def bootstrap_delta(
    pairs,
    *,
    iterations: int = 5000,
    seed: int = 42,
) -> tuple[float, float, float]:
    if not pairs:
        raise ValueError("pairs must not be empty")
    if iterations <= 0:
        raise ValueError("iterations must be greater than zero")

    deltas = [
        float(pair.target.forward_return) - float(pair.control.forward_return)
        for pair in pairs
        if pair.target.forward_return is not None
        and pair.control.forward_return is not None
    ]
    if not deltas:
        raise ValueError("pairs must contain usable forward returns")

    observed = sum(deltas) / len(deltas)
    rng = random.Random(seed)
    bootstraps = [
        sum(deltas[rng.randrange(len(deltas))] for _ in deltas) / len(deltas)
        for _ in range(iterations)
    ]
    bootstraps.sort()
    low = bootstraps[int(0.025 * iterations)]
    high = bootstraps[min(int(0.975 * iterations), iterations - 1)]
    return observed, low, high


def summarize(pairs, *, iterations: int = 5000) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for horizon in (3, 5, 10):
        bucket = [pair for pair in pairs if pair.target.horizon == horizon]
        if not bucket:
            continue
        observed, low, high = bootstrap_delta(bucket, iterations=iterations)
        rows.append({
            "horizon": horizon,
            "pairs": len(bucket),
            "observed_delta": observed,
            "ci_low": low,
            "ci_high": high,
            "robust": "positive" if low > 0.0 else "negative" if high < 0.0 else "inconclusive",
        })
    return rows
