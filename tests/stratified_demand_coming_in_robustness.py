from __future__ import annotations

import random


def _delta(pair) -> float:
    return float(pair.target.forward_return) - float(pair.control.forward_return)


def bootstrap_bucket(pairs, *, iterations: int = 5000, seed: int = 42) -> tuple[float, float, float, int]:
    if not pairs:
        raise ValueError("pairs must not be empty")
    if iterations <= 0:
        raise ValueError("iterations must be greater than zero")

    deltas = [_delta(pair) for pair in pairs]
    observed = sum(deltas) / len(deltas)
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(iterations):
        total = sum(deltas[rng.randrange(len(deltas))] for _ in deltas)
        samples.append(total / len(deltas))
    samples.sort()
    low = samples[int(0.025 * iterations)]
    high = samples[int(0.975 * iterations)]
    positive = sum(delta > 0 for delta in deltas)
    return observed, low, high, positive


def summarize(pairs, *, iterations: int = 5000) -> list[dict[str, object]]:
    buckets: dict[tuple[str, str, int], list] = {}
    for pair in pairs:
        target = pair.target
        key = (str(target.state), str(target.direction), int(target.horizon))
        buckets.setdefault(key, []).append(pair)

    rows: list[dict[str, object]] = []
    for (state, direction, horizon), bucket in sorted(buckets.items()):
        observed, low, high, positive = bootstrap_bucket(bucket, iterations=iterations)
        rows.append(
            {
                "state": state,
                "direction": direction,
                "horizon": horizon,
                "pairs": len(bucket),
                "observed_delta": observed,
                "ci_low": low,
                "ci_high": high,
                "positive": positive,
            }
        )
    return rows
