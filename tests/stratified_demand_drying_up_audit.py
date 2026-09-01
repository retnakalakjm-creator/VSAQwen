from __future__ import annotations

from collections import defaultdict


def summarize(pairs) -> list[dict[str, object]]:
    buckets = defaultdict(list)
    for pair in pairs:
        target = pair.target
        buckets[(target.state, target.direction, target.horizon)].append(pair)

    rows: list[dict[str, object]] = []
    for (state, direction, horizon), bucket in sorted(buckets.items()):
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
                "state": state,
                "direction": direction,
                "horizon": horizon,
                "pairs": len(deltas),
                "mean_delta": sum(deltas) / len(deltas),
                "positive": sum(delta > 0 for delta in deltas),
            }
        )
    return rows
