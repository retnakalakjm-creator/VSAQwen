from __future__ import annotations

from collections import defaultdict


def summarize_by_symbol(pairs) -> list[dict[str, object]]:
    buckets: dict[tuple[str, str, str, int], list] = defaultdict(list)
    for pair in pairs:
        target = pair.target
        if target.state == "correcting" and target.direction == "bullish" or (
            target.state == "healthy" and target.direction == "bearish"
        ):
            buckets[(target.symbol, target.state, target.direction, target.horizon)].append(pair)

    rows: list[dict[str, object]] = []
    for (symbol, state, direction, horizon), bucket in sorted(buckets.items()):
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
                "symbol": symbol,
                "state": state,
                "direction": direction,
                "horizon": horizon,
                "pairs": len(deltas),
                "mean_delta": sum(deltas) / len(deltas),
                "positive": sum(delta > 0 for delta in deltas),
            }
        )
    return rows


def stable_symbol_counts(rows: list[dict[str, object]], *, min_cases: int = 3) -> dict[tuple[str, str, str], int]:
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for row in rows:
        if int(row["pairs"]) >= min_cases:
            counts[(str(row["symbol"]), str(row["state"]), str(row["direction"]))] += 1
    return dict(counts)
