from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from data import daily_to_weekly, download_data
from engine.columns import COL_AVG_SPREAD, COL_CLOSE, COL_LOW, COL_WEEK
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
from trend import TrendAnalyzer


SYMBOL = "BHARTIARTL.NS"
TARGET_INDEX = None
FORWARD_HORIZONS = (1, 2, 4, 8)
RESPONSE_LOOKAHEAD = 4
STRUCTURAL_LOCATION_LOOKBACK = 6
CAMPAIGN_CHANGE_LOOKBACK = 6

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
    contexts = []

    for index in range(20, target_index + 1):
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


def point_in_time_scorecard(ctx):
    """Descriptive audit score using only information available at TEST bar."""
    requirements = diagnostic_test_requirements(ctx)
    campaign = campaign_profile(ctx)

    factors = {
        "structural_weakness": campaign["structural_weakness"],
        "not_confirmed_downtrend": not campaign["confirmed_downtrend"],
        "higher_low": requirements["higher_low"],
        "volume_decreasing": requirements["volume_decreasing"],
        "strong_close": requirements["strong_close"],
    }

    return {
        "supportive_factor_count": sum(factors.values()),
        "supportive_factor_total": len(factors),
        "factors": factors,
    }


def exact_bar_evidence(result, bar_index: int) -> tuple[str, ...]:
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


def structural_location_profile(ctx, metrics):
    """Describe TEST location relative to confirmed prior structural lows."""
    current_index = ctx.current.bar_index
    current_low = float(ctx.current.low)

    prior_lows = [
        swing
        for swing in ctx.structural_swings
        if swing.swing.type.name.lower() == "low"
        and swing.swing.confirmation_index <= current_index
        and swing.swing.bar_index < current_index
    ]

    prior_lows = prior_lows[-STRUCTURAL_LOCATION_LOOKBACK:]

    if not prior_lows:
        return {
            "prior_structural_lows": 0,
            "nearest_low": None,
            "distance_to_nearest_low": None,
            "distance_to_nearest_low_in_spreads": None,
            "tests_recent_structural_low": False,
            "below_nearest_structural_low": False,
        }

    nearest = min(
        prior_lows,
        key=lambda swing: abs(float(swing.swing.price) - current_low),
    )

    nearest_price = float(nearest.swing.price)
    distance = current_low - nearest_price
    avg_spread = float(metrics.iloc[current_index][COL_AVG_SPREAD])
    distance_in_spreads = distance / avg_spread if avg_spread > 0 else None

    return {
        "prior_structural_lows": len(prior_lows),
        "nearest_low": {
            "bar_index": nearest.swing.bar_index,
            "confirmation_index": nearest.swing.confirmation_index,
            "price": nearest_price,
            "grade": str(nearest.grade),
        },
        "distance_to_nearest_low": distance,
        "distance_to_nearest_low_in_spreads": distance_in_spreads,
        "tests_recent_structural_low": (
            distance_in_spreads is not None
            and abs(distance_in_spreads) <= 1.5
        ),
        "below_nearest_structural_low": distance < 0,
    }


def campaign_profile(ctx):
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


def pre_test_change_character(ctx):
    """Audit-only measure of whether selling pressure was losing effectiveness before TEST."""
    bars = list(ctx.bars)
    if len(bars) < 4:
        return {
            "lookback_bars": len(bars),
            "available": False,
            "reason": "insufficient_bars",
        }

    recent_count = min(CAMPAIGN_CHANGE_LOOKBACK, len(bars) - 1)
    prior_count = min(CAMPAIGN_CHANGE_LOOKBACK, len(bars) - 1 - recent_count)
    if prior_count <= 0:
        return {
            "lookback_bars": len(bars),
            "available": False,
            "reason": "insufficient_prior_window",
        }

    prior = bars[-1 - recent_count - prior_count:-1 - recent_count]
    recent = bars[-1 - recent_count:-1]

    def metrics(window):
        return {
            "bars": len(window),
            "down_bars": sum(is_bearish_bar(bar) for bar in window),
            "weak_closes": sum(is_weak_close(bar) for bar in window),
            "low_volume": sum(is_low_volume(bar) for bar in window),
            "narrow_spread": sum(is_narrow_spread(bar) for bar in window),
            "avg_volume_rank": sum(int(bar.volume) for bar in window) / len(window),
            "avg_spread_rank": sum(int(bar.spread) for bar in window) / len(window),
        }

    prior_stats = metrics(prior)
    recent_stats = metrics(recent)

    changes = {
        "down_bar_count_change": recent_stats["down_bars"] - prior_stats["down_bars"],
        "weak_close_count_change": recent_stats["weak_closes"] - prior_stats["weak_closes"],
        "low_volume_count_change": recent_stats["low_volume"] - prior_stats["low_volume"],
        "narrow_spread_count_change": recent_stats["narrow_spread"] - prior_stats["narrow_spread"],
        "avg_volume_rank_change": recent_stats["avg_volume_rank"] - prior_stats["avg_volume_rank"],
        "avg_spread_rank_change": recent_stats["avg_spread_rank"] - prior_stats["avg_spread_rank"],
    }

    supportive_changes = {
        "fewer_down_bars": changes["down_bar_count_change"] < 0,
        "fewer_weak_closes": changes["weak_close_count_change"] < 0,
        "more_low_volume": changes["low_volume_count_change"] > 0,
        "more_narrow_spread": changes["narrow_spread_count_change"] > 0,
    }

    return {
        "lookback_bars": recent_count,
        "available": True,
        "prior": prior_stats,
        "recent": recent_stats,
        "changes": changes,
        "supportive_change_count": sum(supportive_changes.values()),
        "supportive_changes": supportive_changes,
    }


def response_analysis(contexts_by_index, metrics, test_index: int):
    test_low = float(metrics.iloc[test_index][COL_LOW])
    first_supply_bar = None
    first_area_break_bar = None
    first_bullish_evidence_bar = None
    holding_bars = 0
    responses = []

    end_index = min(test_index + RESPONSE_LOOKAHEAD, len(metrics) - 1)

    for future_index in range(test_index + 1, end_index + 1):
        item = contexts_by_index.get(future_index)
        if item is None:
            break

        _, ctx, result = item
        exact_codes = exact_bar_evidence(result, future_index)
        bullish = tuple(code for code in exact_codes if code in BULLISH_CONTEXT_CODES)
        bearish = tuple(code for code in exact_codes if code in BEARISH_CONTEXT_CODES)

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
            first_supply_bar - test_index if first_supply_bar is not None else None
        ),
        "first_area_break_offset": (
            first_area_break_bar - test_index if first_area_break_bar is not None else None
        ),
        "first_bullish_evidence_offset": (
            first_bullish_evidence_bar - test_index
            if first_bullish_evidence_bar is not None
            else None
        ),
        "responses": responses,
    }


def classify_response(response: dict) -> str:
    holding_bars = response["holding_bars"]
    lookahead = response["lookahead_bars"]
    supply_offset = response["first_supply_bar_offset"]
    break_offset = response["first_area_break_offset"]

    if lookahead == 0:
        return "NO_RESPONSE"

    if holding_bars == lookahead and supply_offset is None:
        return "STRONG_HOLD"

    if holding_bars > 0 and (supply_offset is None or supply_offset > 2):
        return "PARTIAL_HOLD"

    if break_offset is not None and break_offset <= 2:
        return "EARLY_AREA_FAILURE"

    if supply_offset is not None and supply_offset <= 2:
        return "EARLY_SUPPLY_FAILURE"

    return "MIXED"


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
    rows = []

    print("\n" + "=" * 70)
    print("AUDIT-ONLY TEST DETECTOR DIAGNOSTIC")
    print("=" * 70)
    print("DIAGNOSTIC_VERSION = test-detector-audit-v10")
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

    print("\nTEST PRE-TEST CHANGE-OF-CHARACTER AUDIT")
    for bar_index in sorted(by_bar):
        event = next(event for index, event in test_events if index == bar_index)
        ctx = contexts_by_index[bar_index][1]
        result = contexts_by_index[bar_index][2]
        change = pre_test_change_character(ctx)
        print({
            "bar_index": bar_index,
            "week": str(metrics.iloc[bar_index][COL_WEEK]),
            "response_classification": classify_response(
                response_analysis(contexts_by_index, metrics, bar_index)
            ),
            "pre_test_change": change,
            "exact_evidence_at_test": exact_bar_evidence(result, bar_index),
            "test_strength": event.strength,
            "test_quality": event.quality,
        })

    print("\nTEST PRE-TEST CHANGE GROUP SUMMARY")
    groups = defaultdict(list)
    for bar_index in sorted(by_bar):
        ctx = contexts_by_index[bar_index][1]
        change = pre_test_change_character(ctx)
        classification = classify_response(
            response_analysis(contexts_by_index, metrics, bar_index)
        )
        groups[classification].append((bar_index, change))

    change_summary = {}
    for classification, items in sorted(groups.items()):
        usable = [change for _, change in items if change.get("available")]
        change_summary[classification] = {
            "events": len(items),
            "bars": [bar for bar, _ in items],
            "avg_supportive_change_count": (
                sum(change["supportive_change_count"] for change in usable) / len(usable)
                if usable else None
            ),
            "supportive_change_count_distribution": (
                dict(Counter(change["supportive_change_count"] for change in usable))
                if usable else {}
            ),
        }

    print(change_summary)
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
