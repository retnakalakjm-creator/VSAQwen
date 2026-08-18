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
WINDOWS = (4, 8, 12, 20)
MAX_WINDOW = max(WINDOWS)


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


def build_context(metrics, index: int):
    replay = metrics.iloc[: index + 1]
    from trend import TrendAnalyzer

    trend = TrendAnalyzer().analyze(replay)
    engine = EvidenceEngine()
    engine._reset(
        metrics=replay,
        trend=trend,
        structural_swings=tuple(trend.structure.structural_swings),
        validation_metrics=replay,
    )
    assert engine._ctx is not None
    return engine._ctx


def cheap_primary_candidates(metrics) -> list[int]:
    candidates: list[int] = []
    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]
        volume = int(row.get(COL_VOLUME_CLASS, 0))
        spread = int(row.get(COL_SPREAD_CLASS, 0))
        direction = int(row.get(COL_DIRECTION, 0))
        if (
            volume >= VolumeClass.HIGH
            and spread >= SpreadClass.ABOVE_AVERAGE
            and direction == Direction.DOWN
        ):
            candidates.append(index)
    return candidates


def cheap_no_supply_candidates(metrics, anchor_candidates: list[int]) -> set[int]:
    wanted: set[int] = set()
    for anchor in anchor_candidates:
        start = max(MIN_REPLAY_BARS, anchor - MAX_WINDOW)
        for index in range(start, anchor):
            row = metrics.iloc[index]
            volume = int(row.get(COL_VOLUME_CLASS, 0))
            spread = int(row.get(COL_SPREAD_CLASS, 0))
            direction = int(row.get(COL_DIRECTION, 0))
            if (
                volume <= VolumeClass.LOW
                and spread <= SpreadClass.NARROW
                and direction == Direction.DOWN
            ):
                wanted.add(index)
    return wanted


def collect_symbol(symbol: str):
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)

    anchor_candidates = cheap_primary_candidates(metrics)
    primary_anchors: set[int] = set()
    no_supply_candidates = cheap_no_supply_candidates(metrics, anchor_candidates)

    # Heavy work is limited to candidate anchors and relevant preceding NO_SUPPLY bars.
    relevant_indices = sorted(set(anchor_candidates) | no_supply_candidates)
    contexts = {index: build_context(metrics, index) for index in relevant_indices}

    for index in anchor_candidates:
        ctx = contexts[index]
        events = tuple(
            event
            for event in _collect_stopping_volume(ctx)
            if event.code.value == "stopping_volume" and event.bar_index == index
        )
        if events:
            primary_anchors.add(index)

    # A NO_SUPPLY bar is valid support only if it actually emits under its point-in-time context.
    no_supply_bars: set[int] = set()
    for index in no_supply_candidates:
        ctx = contexts[index]
        events = tuple(
            event
            for event in _collect_no_supply(ctx)
            if event.code.value == "no_supply" and event.bar_index == index
        )
        if events:
            no_supply_bars.add(index)

    rows = []
    for anchor in sorted(primary_anchors):
        row = {
            "symbol": symbol,
            "anchor_bar_index": anchor,
            "anchor_week": str(metrics.iloc[anchor][COL_WEEK]),
            "outcome": outcome(metrics, anchor),
        }
        for window in WINDOWS:
            support_indices = sorted(
                index
                for index in no_supply_bars
                if anchor - window <= index < anchor
            )
            row[f"no_supply_before_{window}"] = bool(support_indices)
            row[f"no_supply_indices_{window}"] = support_indices
            row[f"nearest_offset_{window}"] = (
                min(anchor - index for index in support_indices)
                if support_indices
                else None
            )
        rows.append(row)

    return rows, len(anchor_candidates), len(no_supply_candidates), len(no_supply_bars)


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
    all_rows: list[dict] = []
    failures: list[dict] = []
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    total_anchor_candidates = 0
    total_no_supply_candidates = 0
    total_valid_no_supply = 0

    for symbol in SYMBOLS:
        try:
            rows, anchor_candidates, no_supply_candidates, valid_no_supply = collect_symbol(symbol)
            total_anchor_candidates += anchor_candidates
            total_no_supply_candidates += no_supply_candidates
            total_valid_no_supply += valid_no_supply
            all_rows.extend(rows)
            by_symbol[symbol].extend(rows)
        except Exception as exc:
            failures.append({"symbol": symbol, "error": repr(exc)})

    print("NO SUPPLY SEQUENCE SUPPORT-VALUE SUMMARY")
    print(
        {
            "symbols_requested": len(SYMBOLS),
            "symbols_with_primary_events": len({row["symbol"] for row in all_rows}),
            "primary_anchor_events": len(all_rows),
            "primary_candidate_bars": total_anchor_candidates,
            "no_supply_candidate_bars_in_anchor_windows": total_no_supply_candidates,
            "validated_no_supply_bars": total_valid_no_supply,
            "windows": WINDOWS,
            "support_direction": "NO_SUPPLY before primary anchor only",
            "failures": failures,
        }
    )

    print("NO SUPPLY SEQUENCE SUPPORT-VALUE COMPARISON")
    for window in WINDOWS:
        with_support = [row for row in all_rows if row[f"no_supply_before_{window}"]]
        without_support = [row for row in all_rows if not row[f"no_supply_before_{window}"]]
        print(
            {
                "window": window,
                "with_nearby_no_supply": summarize(with_support),
                "without_nearby_no_supply": summarize(without_support),
            }
        )

    print("NO SUPPLY SEQUENCE SUPPORT-VALUE BY_SYMBOL")
    for symbol in SYMBOLS:
        rows = by_symbol[symbol]
        print(symbol)
        for window in WINDOWS:
            with_support = [row for row in rows if row[f"no_supply_before_{window}"]]
            without_support = [row for row in rows if not row[f"no_supply_before_{window}"]]
            print(
                {
                    "window": window,
                    "with_no_supply": summarize(with_support),
                    "without_no_supply": summarize(without_support),
                }
            )

    print("NO SUPPLY SEQUENCE SUPPORT-VALUE EVENTS")
    for row in all_rows:
        print(row)


if __name__ == "__main__":
    main()
