"""Audit-only TEST sequence analysis.

Measures the relationship between preceding selling effort, price result,
and the subsequent TEST. Production TEST detection is not changed.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_LOW, COL_AVG_SPREAD, COL_WEEK
from evidence.campaign import _recent_structural_weakness, has_selling_campaign
from evidence.demand import _collect_test
from evidence.engine import EvidenceEngine
from evidence.rules import (
    is_bearish_bar,
    is_low_volume,
    is_narrow_spread,
    is_strong_close,
    is_weak_close,
    volume_decreasing,
)
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer

SYMBOL = "BHARTIARTL.NS"
TARGET_INDEX = None
SEQUENCE_LOOKBACK = 6


def build_contexts(metrics, target_index: int):
    contexts = []
    for index in range(20, target_index + 1):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        swings = tuple(trend.structure.structural_swings)
        engine = EvidenceEngine()
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=swings,
        )
        assert engine._ctx is not None
        contexts.append((index, engine._ctx, result))
    return contexts


def exact_codes(result, bar_index: int) -> tuple[str, ...]:
    return tuple(str(item.code) for item in result.evidence if item.bar_index == bar_index)


def effort_result_bar(bar) -> dict[str, object]:
    """Describe selling effort and its immediate result on one prior bar."""
    high_effort = int(bar.volume) >= 5
    very_high_effort = int(bar.volume) >= 6
    weak_result = is_weak_close(bar)
    down_result = is_bearish_bar(bar)
    narrow_result = is_narrow_spread(bar)

    if very_high_effort and not weak_result:
        result_class = "HIGH_EFFORT_WEAK_RESULT"
    elif high_effort and weak_result:
        result_class = "HIGH_EFFORT_WEAK_RESULT"
    elif high_effort and down_result:
        result_class = "HIGH_EFFORT_DOWN_RESULT"
    elif high_effort:
        result_class = "HIGH_EFFORT_MIXED_RESULT"
    elif is_low_volume(bar) and narrow_result:
        result_class = "LOW_EFFORT_NARROW"
    else:
        result_class = "ORDINARY"

    return {
        "volume_rank": int(bar.volume),
        "spread_rank": int(bar.spread),
        "down_bar": down_result,
        "weak_close": weak_result,
        "narrow_spread": narrow_result,
        "low_volume": is_low_volume(bar),
        "high_effort": high_effort,
        "very_high_effort": very_high_effort,
        "result_class": result_class,
    }


def sequence_profile(ctx, metrics, test_index: int) -> dict[str, object]:
    bars = list(ctx.bars)
    prior = bars[:-1]
    window = prior[-SEQUENCE_LOOKBACK:]

    if not window:
        return {"available": False, "reason": "no_pre_test_bars"}

    profiles = [effort_result_bar(bar) for bar in window]
    high_effort = [p for p in profiles if p["high_effort"]]
    weak_high_effort = [
        p for p in profiles
        if p["high_effort"] and (p["weak_close"] or p["down_bar"])
    ]
    low_effort_narrow = [p for p in profiles if p["result_class"] == "LOW_EFFORT_NARROW"]

    closes = [float(bar.close_price) for bar in window]
    lows = [float(bar.low) for bar in window]
    last_three = profiles[-3:]

    last_close = closes[-1]
    first_close = closes[0]
    net_price_change = last_close / first_close - 1.0 if first_close else 0.0

    downside_progression = sum(
        current < previous
        for previous, current in zip(lows, lows[1:])
    )

    # "Effort losing effectiveness" is descriptive only:
    # at least one meaningful prior effort, followed by lower/no greater
    # downside pressure and a low-effort/narrow bar before TEST.
    meaningful_effort = bool(high_effort)
    effort_did_not_expand = downside_progression <= max(1, len(window) // 2)
    low_effort_end = bool(low_effort_narrow)
    losing_effectiveness = meaningful_effort and effort_did_not_expand and low_effort_end

    return {
        "available": True,
        "lookback_bars": len(window),
        "high_effort_bars": len(high_effort),
        "high_effort_with_down_or_weak_result": len(weak_high_effort),
        "low_effort_narrow_bars": len(low_effort_narrow),
        "downside_progression_count": downside_progression,
        "net_price_change_before_test": net_price_change,
        "meaningful_prior_effort": meaningful_effort,
        "effort_did_not_expand": effort_did_not_expand,
        "low_effort_end": low_effort_end,
        "descriptive_losing_effectiveness": losing_effectiveness,
        "last_three": last_three,
        "bars": profiles,
        "campaign_context": {
            "has_selling_campaign": has_selling_campaign(ctx),
            "structural_weakness": _recent_structural_weakness(ctx),
            "confirmed_downtrend": bool(getattr(ctx.trend, "direction", None) is not None),
        },
        "test_index": test_index,
        "test_close": float(metrics.iloc[test_index][COL_CLOSE]),
        "test_low": float(metrics.iloc[test_index][COL_LOW]),
    }


def main() -> None:
    daily = download_data(SYMBOL)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)

    target = len(metrics) - 1 if TARGET_INDEX is None else TARGET_INDEX
    contexts = build_contexts(metrics, target)

    tests: dict[int, object] = {}
    context_map = {index: (ctx, result) for index, ctx, result in contexts}
    for index, ctx, _ in contexts:
        events = _collect_test(ctx)
        if events:
            tests[index] = events[0]

    print("=" * 72)
    print("TEST PRECEDING EFFORT / RESULT SEQUENCE AUDIT")
    print("=" * 72)
    print({"symbol": SYMBOL, "target_bar_index": target, "test_count": len(tests)})

    groups: dict[str, list[int]] = defaultdict(list)

    for index in sorted(tests):
        ctx, result = context_map[index]
        profile = sequence_profile(ctx, metrics, index)
        response = "UNKNOWN"
        next_ctx = context_map.get(index + 1)

        if next_ctx is not None:
            next_result = next_ctx[1]
            codes = exact_codes(next_result, index + 1)
            if "increasing_supply" in codes:
                response = "RENEWED_SUPPLY"
            else:
                response = "NO_RENEWED_SUPPLY"

        if profile["descriptive_losing_effectiveness"]:
            sequence_class = "SELLING_EFFECTIVENESS_LOSING"
        elif profile["meaningful_prior_effort"]:
            sequence_class = "SELLING_STILL_EFFECTIVE_OR_UNCLEAR"
        else:
            sequence_class = "INSUFFICIENT_PRIOR_EFFORT"

        groups[sequence_class].append(index)

        print({
            "bar_index": index,
            "week": str(metrics.iloc[index][COL_WEEK]),
            "sequence_class": sequence_class,
            "pre_test_sequence": profile,
            "next_bar_response": response,
            "test_evidence": exact_codes(result, index),
        })

    print("\nTEST SEQUENCE GROUP SUMMARY")
    for classification, indices in sorted(groups.items()):
        print({
            "classification": classification,
            "events": len(indices),
            "bars": indices,
        })


if __name__ == "__main__":
    main()
