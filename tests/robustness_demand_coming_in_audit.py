from __future__ import annotations

import random


def _field(pair, name: str):
    if hasattr(pair, name):
        return getattr(pair, name)
    target = getattr(pair, "target")
    control = getattr(pair, "control")
    if name == "horizon":
        return target.horizon
    if name == "target_return":
        return target.forward_return
    if name == "control_return":
        return control.forward_return
    raise AttributeError(name)


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
        float(_field(pair, "target_return"))
        - float(_field(pair, "control_return"))
        for pair in pairs
    ]
    observed = sum(deltas) / len(deltas)
    rng = random.Random(seed)
    bootstraps: list[float] = []
    for _ in range(iterations):
        sample = [deltas[rng.randrange(len(deltas))] for _ in deltas]
        bootstraps.append(sum(sample) / len(sample))
    bootstraps.sort()
    low = bootstraps[int(0.025 * iterations)]
    high = bootstraps[int(0.975 * iterations)]
    return observed, low, high


def summarize(
    pairs,
    *,
    iterations: int = 5000,
) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    for horizon in (3, 5, 10):
        bucket = [pair for pair in pairs if _field(pair, "horizon") == horizon]
        if not bucket:
            continue
        observed, low, high = bootstrap_delta(bucket, iterations=iterations)
        rows.append(
            {
                "horizon": horizon,
                "pairs": len(bucket),
                "observed_delta": observed,
                "ci_low": low,
                "ci_high": high,
                "negative_deltas": sum(
                    float(_field(pair, "target_return"))
                    - float(_field(pair, "control_return"))
                    < 0
                    for pair in bucket
                ),
            }
        )
    return rows
