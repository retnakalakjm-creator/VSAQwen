from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_WEEK
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
        # collect() builds the canonical internal BackgroundContext. TEST is
        # deliberately invoked afterward as an audit-only detector.
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

    down_bars = sum(
        is_bearish_bar(bar)
        for bar in bars
    )

    lower_closes = sum(
        current.close_price < previous.close_price
        for previous, current in zip(bars, bars[1:])
    )

    weak_closes = sum(
        is_weak_close(bar)
        for bar in bars
    )

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


def next_bar_response(contexts_by_index, bar_index: int, horizon: int):
    """Inspect actual bar-level response, not background-window evidence."""
    responses = []

    for future_index in range(bar_index + 1, bar_index + horizon + 1):
        item = contexts_by_index.get(future_index)
        if item is None:
            break

        _, ctx, result = item
        exact_codes = exact_bar_evidence(result, future_index)
        bullish = tuple(
            code
            for code in exact_codes
            if code in BULLISH_CONTEXT_CODES
        )
        bearish = tuple(
            code
            for code in exact_codes
            if code in BEARISH_CONTEXT_CODES
        )

        responses.append({
            "bar_index": future_index,
            "direction": ctx.current.direction.name.lower(),
            "close_position": ctx.current.close_position.name.lower(),
            "volume": ctx.current.volume.name.lower(),
            "spread": ctx.current.spread.name.lower(),
            "higher_low_vs_previous": (
                makes_higher_low(ctx.current, ctx.previous)
                if ctx.previous is not None
                else False
            ),
            "exact_evidence": exact_codes,
            "bullish_evidence": bullish,
            "bearish_evidence": bearish,
        })

    return responses


def main() -> None:
    daily = download_data(SYMBOL)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    scanner = ScannerEngine()

    target_index = len(metrics) - 1 if TARGET_INDEX is None else TARGET_INDEX

    point_contexts = build_point_in_time_contexts(metrics, target_index)

    contexts_by_index = {}

    for context_index, context, result in point_contexts:
        contexts_by_index[context_index] = (
            context_index,
            context,
            result,
        )

    test_events = []
    for index, ctx, _ in point_contexts:
        events = _collect_test(ctx)
        for event in events:
            test_events.append((index, event))

    by_bar = Counter(index for index, _ in test_events)

    print("\n" + "=" * 70)
    print("AUDIT-ONLY TEST DETECTOR DIAGNOSTIC")
    print("=" * 70)
    print("DIAGNOSTIC_VERSION = test-detector-audit-v4")
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

    print("\nTEST CAMPAIGN AND RESPONSE AUDIT")
    for bar_index in sorted(by_bar):
        event = next(
            event
            for index, event in test_events
            if index == bar_index
        )

        ctx = contexts_by_index[bar_index][1]
        result = contexts_by_index[bar_index][2]
        requirements = diagnostic_test_requirements(ctx)

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
            "close": close,
            "test_strength": event.strength,
            "test_quality": event.quality,
            "test_direction": str(event.direction),
            "test_requirements_and_confirmations": requirements,
            "campaign_profile": campaign_profile(ctx),
            "exact_evidence_at_test": exact_bar_evidence(result, bar_index),
            "next_1_4_bar_response": next_bar_response(
                contexts_by_index,
                bar_index,
                4,
            ),
            "trend_direction": str(ctx.trend.direction),
            "trend_state": str(ctx.trend.state),
            "trend_strength": ctx.trend.strength,
            "trend_confidence": ctx.trend.confidence,
            "latest_structural_swing": latest_swing_snapshot(ctx),
            "forward_returns": forward,
        })

    print("\nTEST FOLLOW-THROUGH SUMMARY")
    summary = {}

    for horizon in FOLLOW_THROUGH_HORIZONS:
        valid = 0
        bullish_context = 0
        bearish_context = 0
        positive_return = 0

        for bar_index in sorted(by_bar):
            future_index = bar_index + horizon

            if future_index >= len(metrics):
                continue

            valid += 1
            exact_codes = exact_bar_evidence(
                contexts_by_index[future_index][2],
                future_index,
            )

            if any(
                code in BULLISH_CONTEXT_CODES
                for code in exact_codes
            ):
                bullish_context += 1

            if any(
                code in BEARISH_CONTEXT_CODES
                for code in exact_codes
            ):
                bearish_context += 1

            close = float(metrics.iloc[bar_index][COL_CLOSE])
            future_close = float(metrics.iloc[future_index][COL_CLOSE])

            if future_close > close:
                positive_return += 1

        summary[horizon] = {
            "events": valid,
            "bullish_exact_event_follow_through": bullish_context,
            "bearish_exact_event_follow_through": bearish_context,
            "positive_price_follow_through": positive_return,
        }

    print(summary)
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
