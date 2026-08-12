from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_LOW, COL_WEEK
from evidence.campaign import has_recent_weakness, _recent_structural_weakness
from evidence.demand import _collect_test
from evidence.engine import EvidenceEngine
from evidence.rules import (
    is_bearish_bar,
    is_confirmed_downtrend,
    is_low_volume,
    is_narrow_spread,
    is_strong_close,
    is_weak_close,
    makes_higher_low,
    volume_decreasing,
)
from metrics_engine import MetricsEngine
from scanner import ScannerEngine
from trend import TrendAnalyzer


SYMBOL = "BHARTIARTL.NS"
TARGET_INDEX = None
CONTEXT_WINDOW = 5
FORWARD_HORIZONS = (1, 2, 4, 8)
FOLLOW_THROUGH_HORIZONS = (1, 2, 4)
RESPONSE_LOOKAHEAD = 4

BULLISH_CONTEXT_CODES = {
    "no_supply",
    "shakeout",
    "selling_climax",
    "structural_progression_improving",
}

BEARISH_CONTEXT_CODES = {
    "buying_climax",
    "upthrust",
    "supply_coming_in",
    "increasing_supply",
    "no_demand",
}


def build_point_in_time_contexts(metrics, target_index: int):
    """Create audit-only contexts without enabling TEST in production."""
    scanner = ScannerEngine()
    contexts = []

    for index in range(scanner.MIN_REPLAY_BARS, target_index + 1):
        replay_metrics = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay_metrics)
        swings = tuple(trend.structure.structural_swings)

        engine = EvidenceEngine()
        result = engine.collect(
            metrics=replay_metrics,
            trend=trend,
            structural_swings=swings,
        )

        assert engine._ctx is not None
        contexts.append((index, engine._ctx, result))

    return contexts


def diagnostic_test_requirements(ctx):
    """Return TEST detector requirements without pytest treating this as a test."""
    bar = ctx.current
    previous = ctx.previous

    if previous is None:
        return {
            "selling_campaign": False,
            "down_bar": is_bearish_bar(bar),
            "low_volume": is_low_volume(bar),
            "narrow_spread": is_narrow_spread(bar),
            "volume_decreasing": False,
            "strong_close": is_strong_close(bar),
            "higher_low": False,
        }

    from evidence.campaign import has_selling_campaign

    return {
        "selling_campaign": has_selling_campaign(ctx),
        "down_bar": is_bearish_bar(bar),
        "low_volume": is_low_volume(bar),
        "narrow_spread": is_narrow_spread(bar),
        "volume_decreasing": volume_decreasing(bar, previous),
        "strong_close": is_strong_close(bar),
        "higher_low": makes_higher_low(bar, previous),
    }


def exact_bar_evidence(result, bar_index: int) -> tuple[str, ...]:
    """Return evidence whose own event timestamp matches the requested bar."""
    return tuple(
        str(item.code)
        for item in result.evidence
        if item.bar_index == bar_index
    )


def latest_swing_snapshot(ctx):
    swings = ctx.structural_swings

    if not swings:
        return None

    latest = swings[-1]
    evaluation = latest.evaluation
    snapshot = evaluation.structure.snapshot

    return {
        "type": str(latest.swing.type),
        "bar_index": latest.swing.bar_index,
        "confirmation_index": latest.swing.confirmation_index,
        "price": latest.swing.price,
        "grade": str(latest.grade),
        "professional_score": evaluation.professional.overall,
        "spread_adjusted_amplitude": snapshot.current_spread_adjusted_amplitude,
    }


def campaign_profile(ctx):
    """Describe the exact recent-weakness campaign used by TEST."""
    bars = ctx.bars

    down_bars = sum(is_bearish_bar(bar) for bar in bars)
    lower_closes = sum(
        current.close_price < previous.close_price
        for previous, current in zip(bars, bars[1:])
    )
    weak_closes = sum(is_weak_close(bar) for bar in bars)

    structural_weakness = _recent_structural_weakness(ctx)
    confirmed_downtrend = is_confirmed_downtrend(ctx.trend)

    score = 0
    if confirmed_downtrend:
        score += 1
    if down_bars >= config.CAMPAIGN_MIN_DOWN_BARS:
        score += 1
    if lower_closes >= config.CAMPAIGN_MIN_LOWER_CLOSES:
        score += 1
    if weak_closes >= config.CAMPAIGN_MIN_WEAK_CLOSES:
        score += 1
    if structural_weakness:
        score += 1

    return {
        "window_bars": len(bars),
        "down_bars": down_bars,
        "lower_closes": lower_closes,
        "weak_closes": weak_closes,
        "confirmed_downtrend": confirmed_downtrend,
        "structural_weakness": structural_weakness,
        "recent_weakness_score": score,
        "campaign_required_score": config.CAMPAIGN_REQUIRED_SCORE,
        "has_recent_weakness": has_recent_weakness(ctx),
    }


def response_analysis(contexts_by_index, metrics, test_index: int):
    """Measure TEST-area hold and speed of renewed supply."""
    test_row = metrics.iloc[test_index]
    test_low = float(test_row[COL_LOW])

    first_supply_bar = None
    first_area_break_bar = None
    first_bullish_evidence_bar = None
    holding_bars = 0
    responses = []

    end_index = min(
        test_index + RESPONSE_LOOKAHEAD,
        len(metrics) - 1,
    )

    for future_index in range(test_index + 1, end_index + 1):
        item = contexts_by_index.get(future_index)
        if item is None:
            break

        _, ctx, result = item
        exact_codes = exact_bar_evidence(result, future_index)
        bullish = tuple(
            code for code in exact_codes if code in BULLISH_CONTEXT_CODES
        )
        bearish = tuple(
            code for code in exact_codes if code in BEARISH_CONTEXT_CODES
        )

        bar_low = float(metrics.iloc[future_index][COL_LOW])
        holds_test_area = bar_low >= test_low
        if holds_test_area:
            holding_bars += 1
        elif first_area_break_bar is None:
            first_area_break_bar = future_index

        if bearish and first_supply_bar is None:
            first_supply_bar = future_index

        if bullish and first_bullish_evidence_bar is None:
            first_bullish_evidence_bar = future_index

        responses.append({
            "bar_index": future_index,
            "direction": ctx.current.direction.name.lower(),
            "close_position": ctx.current.close_position.name.lower(),
            "volume": ctx.current.volume.name.lower(),
            "spread": ctx.current.spread.name.lower(),
            "low": bar_low,
            "holds_test_low": holds_test_area,
            "higher_low_vs_previous": (
                makes_higher_low(ctx.current, ctx.previous)
                if ctx.previous is not None
                else False
            ),
            "exact_evidence": exact_codes,
            "bullish_evidence": bullish,
            "bearish_evidence": bearish,
        })

    return {
        "holding_bars": holding_bars,
        "lookahead_bars": len(responses),
        "first_supply_bar_offset": (
            first_supply_bar - test_index
            if first_supply_bar is not None
            else None
        ),
        "first_area_break_offset": (
            first_area_break_bar - test_index
            if first_area_break_bar is not None
            else None
        ),
        "first_bullish_evidence_offset": (
            first_bullish_evidence_bar - test_index
            if first_bullish_evidence_bar is not None
            else None
        ),
        "responses": responses,
    }


def main() -> None:
    daily = download_data(SYMBOL)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)

    target_index = len(metrics) - 1 if TARGET_INDEX is None else TARGET_INDEX

    point_contexts = build_point_in_time_contexts(metrics, target_index)

    contexts_by_index = {
        context_index: (context_index, context, result)
        for context_index, context, result in point_contexts
    }

    test_events = []
    for index, ctx, _ in point_contexts:
        for event in _collect_test(ctx):
            test_events.append((index, event))

    by_bar = Counter(index for index, _ in test_events)

    print("\n" + "=" * 70)
    print("AUDIT-ONLY TEST DETECTOR DIAGNOSTIC")
    print("=" * 70)
    print("DIAGNOSTIC_VERSION = test-detector-audit-v5")
    print({
        "symbol": SYMBOL,
        "target_bar_index": target_index,
        "target_week": str(metrics.iloc[target_index][COL_WEEK]),
    })

    print("\nTEST DISTRIBUTION")
    print({
        "count": len(test_events),
        "unique_bars": len(by_bar),
        "bar_indices": sorted(by_bar),
        "events_per_bar": dict(sorted(by_bar.items())),
    })

    print("\nTEST CAMPAIGN / RESPONSE AUDIT")
    for bar_index in sorted(by_bar):
        event = next(event for index, event in test_events if index == bar_index)
        ctx = contexts_by_index[bar_index][1]
        result = contexts_by_index[bar_index][2]
        close = float(metrics.iloc[bar_index][COL_CLOSE])

        forward = {}
        for horizon in FORWARD_HORIZONS:
            future_index = bar_index + horizon
            if future_index < len(metrics):
                future_close = float(metrics.iloc[future_index][COL_CLOSE])
                forward[horizon] = (future_close / close) - 1.0
            else:
                forward[horizon] = None

        print({
            "bar_index": bar_index,
            "week": str(metrics.iloc[bar_index][COL_WEEK]),
            "test_strength": event.strength,
            "test_quality": event.quality,
            "test_requirements_and_confirmations": diagnostic_test_requirements(ctx),
            "campaign_profile": campaign_profile(ctx),
            "exact_evidence_at_test": exact_bar_evidence(result, bar_index),
            "response_analysis": response_analysis(
                contexts_by_index,
                metrics,
                bar_index,
            ),
            "trend_direction": str(ctx.trend.direction),
            "trend_state": str(ctx.trend.state),
            "latest_structural_swing": latest_swing_snapshot(ctx),
            "forward_returns": forward,
        })

    print("\nTEST RESPONSE SUMMARY")
    summary = {
        "events": len(by_bar),
        "supply_within_1_bar": 0,
        "supply_within_2_bars": 0,
        "supply_within_4_bars": 0,
        "area_break_within_1_bar": 0,
        "area_break_within_2_bars": 0,
        "area_break_within_4_bars": 0,
        "held_test_low_through_4_bars": 0,
    }

    for bar_index in sorted(by_bar):
        analysis = response_analysis(contexts_by_index, metrics, bar_index)
        supply_offset = analysis["first_supply_bar_offset"]
        break_offset = analysis["first_area_break_offset"]

        if supply_offset == 1:
            summary["supply_within_1_bar"] += 1
        if supply_offset is not None and supply_offset <= 2:
            summary["supply_within_2_bars"] += 1
        if supply_offset is not None and supply_offset <= 4:
            summary["supply_within_4_bars"] += 1

        if break_offset == 1:
            summary["area_break_within_1_bar"] += 1
        if break_offset is not None and break_offset <= 2:
            summary["area_break_within_2_bars"] += 1
        if break_offset is not None and break_offset <= 4:
            summary["area_break_within_4_bars"] += 1

        if analysis["lookahead_bars"] == RESPONSE_LOOKAHEAD and analysis["holding_bars"] == RESPONSE_LOOKAHEAD:
            summary["held_test_low_through_4_bars"] += 1

    print(summary)
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
