from __future__ import annotations

from collections import defaultdict

from robustness_demand_drying_up_audit import bootstrap_delta


def summarize_symbol_robustness(
    pairs,
    *,
    iterations: int = 5000,
    min_cases: int = 3,
) -> list[dict[str, object]]:
    buckets: dict[tuple[str, int], list] = defaultdict(list)
    for pair in pairs:
        buckets[(pair.target.symbol, pair.target.horizon)].append(pair)

    rows: list[dict[str, object]] = []
    for (symbol, horizon), bucket in sorted(buckets.items()):
        if len(bucket) < min_cases:
            continue
        observed, low, high = bootstrap_delta(bucket, iterations=iterations)
        rows.append(
            {
                "symbol": symbol,
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


def leave_one_symbol_out(pairs) -> list[dict[str, object]]:
    symbols = sorted({pair.target.symbol for pair in pairs})
    rows: list[dict[str, object]] = []
    for symbol in symbols:
        for horizon in (3, 5, 10):
            bucket = [
                pair
                for pair in pairs
                if pair.target.horizon == horizon and pair.target.symbol != symbol
            ]
            if not bucket:
                continue
            deltas = [
                float(pair.target.forward_return) - float(pair.control.forward_return)
                for pair in bucket
                if pair.target.forward_return is not None
                and pair.control.forward_return is not None
            ]
            if not deltas:
                continue
            rows.append(
                {
                    "excluded_symbol": symbol,
                    "horizon": horizon,
                    "pairs": len(deltas),
                    "mean_delta": sum(deltas) / len(deltas),
                }
            )
    return rows
