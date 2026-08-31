from __future__ import annotations

from metrics_engine import MetricsEngine
from trend import TrendAnalyzer
from evidence.engine import EvidenceEngine
from evidence.fast_context import create_context_fast

from tests.test_incremental_trend import _bars


def _bar_signature(bar) -> tuple[object, ...]:
    return (
        bar.week_beginning,
        bar.bar_index,
        bar.spread,
        bar.volume,
        bar.direction,
        bar.close_position,
        bar.spread_ratio,
        bar.volume_ratio,
        bar.open,
        bar.high,
        bar.low,
        bar.close_price,
        bar.body,
        bar.upper_shadow,
        bar.lower_shadow,
        bar.close_ratio,
        bar.prev_high,
        bar.prev_low,
        bar.prev_close,
        bar.prev_spread,
    )


def test_fast_context_matches_original_builder() -> None:
    metrics = MetricsEngine().calculate(_bars())
    trend = TrendAnalyzer().analyze(metrics)

    engine = EvidenceEngine()
    engine._metrics = metrics
    engine._trend = trend.structure
    engine._structural_swings = tuple(trend.structure.structural_swings)

    engine._structural_pattern = __import__(
        "market_structure.progression",
        fromlist=["determine_structural_pattern"],
    ).determine_structural_pattern(engine._trend.swings)
    engine._vsa_context = __import__(
        "market_structure.vsa_context",
        fromlist=["build_vsa_context"],
    ).build_vsa_context(
        trend=engine._trend,
        structural_pattern=engine._structural_pattern,
        structural_swings=engine._structural_swings,
    )

    fast = create_context_fast(engine)

    recent = engine._recent
    bars = tuple(
        engine._create_bar_context(
            recent.iloc[i],
            int(recent.index[i]),
        )
        for i in range(len(recent))
    )

    assert tuple(map(_bar_signature, fast.bars)) == tuple(map(_bar_signature, bars))
    assert fast.current == bars[-1]
    assert fast.previous == (bars[-2] if len(bars) >= 2 else None)
    assert fast.recent.equals(recent)
    assert fast.background.equals(engine._background)
    assert fast.structural_swings == engine._structural_swings
    assert fast.structural_pattern == engine._structural_pattern
    assert fast.vsa_context == engine._vsa_context
