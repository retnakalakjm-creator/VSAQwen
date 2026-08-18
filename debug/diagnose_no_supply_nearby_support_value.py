from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
    COL_WEEK,
)
from evidence.demand import _collect_no_supply, _collect_stopping_volume
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass
from trend import TrendAnalyzer


SYMBOLS = (
    "BHARTIARTL.NS",
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "TCS.NS",
    "SBIN.NS",
    "LT.NS",
)

MIN_REPLAY_BARS = 20
FORWARD_HORIZON = 8
NEARBY_WINDOW = 4
PRIMARY_CODES = {"stopping_volume"}


def get_candidate_anchor_bars(metrics) -> list[int]:
    """Cheap necessary-condition prefilter for potential STOPPING_VOLUME bars."""
    candidates: list[int] = []

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]
        if Direction(int(row.get(COL_DIRECTION, Direction.NEUTRAL))) != Direction.DOWN:
            continue
        if VolumeClass(int(row.get(COL_VOLUME_CLASS, VolumeClass.ULTRA_LOW))) < VolumeClass.HIGH:
            continue
        if SpreadClass(int(row.get(COL_SPREAD_CLASS, SpreadClass.NARROW))) < SpreadClass.ABOVE_AVERAGE:
            continue
        candidates.append(index)

    return candidates


def build_point_in_time_contexts(metrics, indices: list[int]):
    """Build heavy point-in-time contexts only for required anchor/support bars."""
    contexts: dict[int, object] = {}

    for index in sorted(set(indices)):
        replay = metrics.iloc[: index + 1]
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        engine._reset(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=replay,
        )
        assert engine._ctx is not None
        contexts[index] = engine._ctx

    return contexts


def outcome(metrics, bar_index: int) -> str:
    future = bar_index + FORWARD_HORIZON
    if future >= len(metrics):
        return "INSUFFICIENT_FORWARD_DATA"

    current = float(metrics.iloc[bar_index][COL_CLOSE])
    future_close = float(metrics.iloc[future][COL_CLOSE])

    if future_close > current:
        return "POSITIVE_8_BAR"
    if future_close < current:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def collect_symbol_events(symbol: str):
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)

    # 1. Cheap O(N) prefilter for possible primary anchors.
    candidate_anchors = get_candidate_anchor_bars(metrics)

    # 2. Only build contexts for anchors and the prior directional support window.
    support_indices = {
        index
        for anchor in candidate_anchors
        for index in range(max(MIN_REPLAY_BARS, anchor - NEARBY_WINDOW), anchor)
    }
    context_indices = sorted(set(candidate_anchors) | support_indices)
    contexts = build_point_in_time_contexts(metrics, context_indices)

    primary_by_bar: set[int] = set()
    no_supply_bars: set[int] = set()

    # 3. Evaluate primary anchors only on candidate bars.
    for anchor_bar in candidate_anchors:
        ctx = contexts[anchor_bar]
        primary = tuple(
            event
            for event in _collect_stopping_volume(ctx)
            if event.code.value in PRIMARY_CODES and event.bar_index == anchor_bar
        )
        if primary:
            primary_by_bar.add(anchor_bar)

    # 4. Evaluate NO_SUPPLY only on bars that can support a later anchor.
    for support_bar in support_indices:
        ctx = contexts[support_bar]
        no_supply = _collect_no_supply(ctx)
        if any(
            event.code.value == "no_supply" and event.bar_index == support_bar
            for event in no_supply
        ):
            no_supply_bars.add(support_bar)

    rows = []
    for anchor_bar in sorted(primary_by_bar):
        # Point-in-time safe: only NO_SUPPLY bars before the anchor can support it.
        nearby = [
            index
            for index in sorted(no_supply_bars)
            if anchor_bar - NEARBY_WINDOW <= index < anchor_bar
        ]

        rows.append(
            {
                "symbol": symbol,
                "anchor_bar_index": anchor_bar,
                "anchor_week": str(metrics.iloc[anchor_bar][COL_WEEK]),
                "outcome": outcome(metrics, anchor_bar),
                "no_supply_before_anchor": bool(nearby),
                "no_supply_bar_indices": nearby,
                "nearest_no_supply_offset": min(
                    (anchor_bar - index for index in nearby),
                    default=None,
                ),
            }
        )

    return rows


def summarize(rows):
    counts = Counter(row["outcome"] for row in rows)
    decisive = counts["POSITIVE_8_BAR"] + counts["NEGATIVE_8_BAR"]

    return {
        "events": len(rows),
        "positive": counts["POSITIVE_8_BAR"],
        "negative": counts["NEGATIVE_8_BAR"],
        "flat": counts["FLAT_8_BAR"],
        "insufficient_forward_data": counts["INSUFFICIENT_FORWARD_DATA"],
        "decisive": decisive,
        "positive_decisive_rate": (
            counts["POSITIVE_8_BAR"] / decisive if decisive else 0.0
        ),
    }


def main() -> None:
    all_rows = []
    failures = []
    by_symbol: dict[str, list[dict]] = defaultdict(list)

    for symbol in SYMBOLS:
        try:
            rows = collect_symbol_events(symbol)
            all_rows.extend(rows)
            by_symbol[symbol].extend(rows)
        except Exception as exc:
            failures.append({"symbol": symbol, "error": repr(exc)})

    with_support = [row for row in all_rows if row["no_supply_before_anchor"]]
    without_support = [row for row in all_rows if not row["no_supply_before_anchor"]]

    print("NO SUPPLY NEARBY SUPPORT-VALUE SUMMARY")
    print(
        {
            "symbols_requested": len(SYMBOLS),
            "symbols_with_primary_events": len({row["symbol"] for row in all_rows}),
            "primary_anchor_events": len(all_rows),
            "nearby_window_bars": NEARBY_WINDOW,
            "support_direction": "NO_SUPPLY before primary anchor only",
            "with_nearby_no_supply": len(with_support),
            "without_nearby_no_supply": len(without_support),
            "failures": failures,
        }
    )

    print("NO SUPPLY NEARBY SUPPORT-VALUE COMPARISON")
    print(
        {
            "with_nearby_no_supply": summarize(with_support),
            "without_nearby_no_supply": summarize(without_support),
        }
    )

    print("NO SUPPLY NEARBY SUPPORT-VALUE BY_SYMBOL")
    for symbol in SYMBOLS:
        rows = by_symbol[symbol]
        print(symbol)
        print(
            {
                "with_nearby_no_supply": summarize(
                    [row for row in rows if row["no_supply_before_anchor"]]
                ),
                "without_nearby_no_supply": summarize(
                    [row for row in rows if not row["no_supply_before_anchor"]]
                ),
            }
        )

    print("NO SUPPLY NEARBY SUPPORT-VALUE EVENTS")
    for row in all_rows:
        print(row)


if __name__ == "__main__":
    main()
