from __future__ import annotations

from collections import defaultdict


def _delta(pair) -> float | None:
    target = pair.target.forward_return
    control = pair.control.forward_return
    if target is None or control is None:
        return None
    return float(target) - float(control)


def summarize_by_symbol(pairs) -> list[dict[str, object]]:
    buckets: dict[tuple[str, int], list] = defaultdict(list)
    for pair in pairs:
        buckets[(pair.target.symbol, pair.target.horizon)].append(pair)

    rows: list[dict[str, object]] = []
    for (symbol, horizon), bucket in sorted(buckets.items()):
        deltas = [delta for pair in bucket if (delta := _delta(pair)) is not None]
        if not deltas:
            continue
        rows.append(
            {
                "symbol": symbol,
                "horizon": horizon,
                "pairs": len(deltas),
                "mean_delta": sum(deltas) / len(deltas),
                "positive": sum(delta > 0 for delta in deltas),
            }
        )
    return rows


def summarize_by_symbol_context(pairs) -> list[dict[str, object]]:
    buckets: dict[tuple[str, str, str, int], list] = defaultdict(list)
    for pair in pairs:
        target = pair.target
        buckets[(target.symbol, target.state, target.direction, target.horizon)].append(pair)

    rows: list[dict[str, object]] = []
    for (symbol, state, direction, horizon), bucket in sorted(buckets.items()):
        deltas = [delta for pair in bucket if (delta := _delta(pair)) is not None]
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


def stable_symbol_counts(
    rows: list[dict[str, object]], *, min_cases: int = 3
) -> dict[tuple[str, int], int]:
    counts: dict[tuple[str, int], int] = defaultdict(int)
    for row in rows:
        if int(row["pairs"]) >= min_cases:
            counts[(str(row["symbol"]), int(row["horizon"]))] += 1
    return dict(counts)
