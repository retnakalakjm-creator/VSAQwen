from __future__ import annotations

from collections import defaultdict

from robustness_demand_drying_up_audit import bootstrap_delta


DEFAULT_TARGET_CONTEXTS = frozenset(
    {
        ("healthy", "bearish", 3),
        ("healthy", "bearish", 5),
        ("healthy", "bullish", 3),
        ("healthy", "bullish", 5),
        ("unknown", "bearish", 3),
        ("unknown", "bearish", 5),
        ("unknown", "bullish", 3),
        ("unknown", "bullish", 5),
        ("exhausted", "bearish", 10),
    }
)


def _delta(pair) -> float | None:
    target = pair.target.forward_return
    control = pair.control.forward_return
    if target is None or control is None:
        return None
    return float(target) - float(control)


def _context(pair) -> tuple[str, str, int]:
    target = pair.target
    return target.state, target.direction, int(target.horizon)


def summarize_context_set(
    pairs,
    contexts: frozenset[tuple[str, str, int]],
    *,
    iterations: int = 5000,
    min_cases: int = 3,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    selected = [pair for pair in pairs if _context(pair) in contexts]
    for horizon in (3, 5, 10):
        bucket = [pair for pair in selected if pair.target.horizon == horizon]
        if len(bucket) < min_cases:
            continue
        observed, low, high = bootstrap_delta(bucket, iterations=iterations)
        rows.append(
            {
                "horizon": horizon,
                "pairs": len(bucket),
                "observed_delta": observed,
                "ci_low": low,
                "ci_high": high,
                "robust_negative": high < 0.0,
                "robust_positive": low > 0.0,
            }
        )
    return rows


def summarize_by_context(
    pairs,
    *,
    iterations: int = 5000,
    min_cases: int = 3,
) -> list[dict[str, object]]:
    buckets: dict[tuple[str, str, int], list] = defaultdict(list)
    for pair in pairs:
        buckets[_context(pair)].append(pair)

    rows: list[dict[str, object]] = []
    for context, bucket in sorted(buckets.items()):
        if len(bucket) < min_cases:
            continue
        observed, low, high = bootstrap_delta(bucket, iterations=iterations)
        state, direction, horizon = context
        rows.append(
            {
                "state": state,
                "direction": direction,
                "horizon": horizon,
                "pairs": len(bucket),
                "observed_delta": observed,
                "ci_low": low,
                "ci_high": high,
                "robust_negative": high < 0.0,
                "robust_positive": low > 0.0,
            }
        )
    return rows


def summarize_complement(
    pairs,
    contexts: frozenset[tuple[str, str, int]],
    *,
    iterations: int = 5000,
    min_cases: int = 3,
) -> list[dict[str, object]]:
    all_contexts = {_context(pair) for pair in pairs}
    return summarize_context_set(
        pairs,
        frozenset(all_contexts - set(contexts)),
        iterations=iterations,
        min_cases=min_cases,
    )


def context_case_counts(pairs, contexts: frozenset[tuple[str, str, int]]) -> dict[int, int]:
    return {
        horizon: sum(1 for pair in pairs if _context(pair) in contexts and pair.target.horizon == horizon)
        for horizon in (3, 5, 10)
    }
