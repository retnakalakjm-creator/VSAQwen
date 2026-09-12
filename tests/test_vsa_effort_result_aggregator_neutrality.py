"""Effort-vs-Result aggregation neutrality guards.

PR #138 enabled contextual Effort/Result collection and PR #139 neutralized
professional scoring weights. These tests protect the separate aggregation path
so contextual Effort/Result observations do not become bullish/bearish score,
bias, or directional contribution before a separate scoring/ranking validation.
"""

from __future__ import annotations

import config
from evidence.aggregator import EvidenceAggregator
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection, MarketBias


EFFORT_RESULT_CODES = (
    EvidenceCode.EFFORT_GT_RESULT,
    EvidenceCode.RESULT_GT_EFFORT,
    EvidenceCode.ABSORPTION,
    EvidenceCode.EFFORT_RESULT,
)


def _item(
    *,
    code: EvidenceCode,
    category: EvidenceCategory,
    direction: EvidenceDirection,
    weight: float,
    strength: float = 1.0,
    bar_index: int = 42,
) -> Evidence:
    return Evidence(
        code=code,
        category=category,
        direction=direction,
        strength=strength,
        weight=weight,
        observation=f"{code} observation",
        description=f"{code} description",
        bar_index=bar_index,
        week_beginning="2026-03-02",
    )


def _effort_result_item(code: EvidenceCode, *, bar_index: int = 42) -> Evidence:
    return _item(
        code=code,
        category=EvidenceCategory.EFFORT,
        direction=EvidenceDirection.NEUTRAL,
        weight=0.0,
        bar_index=bar_index,
    )


def _bullish_primary(*, bar_index: int = 42) -> Evidence:
    return _item(
        code=EvidenceCode.SHAKEOUT,
        category=EvidenceCategory.DEMAND,
        direction=EvidenceDirection.BULLISH,
        weight=1.0,
        bar_index=bar_index,
    )


def _bearish_primary(*, bar_index: int = 42) -> Evidence:
    return _item(
        code=EvidenceCode.UPTHRUST,
        category=EvidenceCategory.SUPPLY,
        direction=EvidenceDirection.BEARISH,
        weight=1.0,
        bar_index=bar_index,
    )


def test_effort_result_codes_are_registered_only_as_contextual_aggregation_codes():
    assert set(EFFORT_RESULT_CODES).issubset(config.EFFORT_RESULT_CODES)
    assert not set(EFFORT_RESULT_CODES) & config.PRIMARY_VSA_CODES
    assert not set(EFFORT_RESULT_CODES) & config.SUPPORTING_VSA_CODES
    assert not set(EFFORT_RESULT_CODES) & config.STRUCTURAL_CODES


def test_effort_result_only_aggregation_stays_neutral_and_zero_score():
    summary = EvidenceAggregator().aggregate(
        tuple(_effort_result_item(code) for code in EFFORT_RESULT_CODES)
    )

    assert summary.bullish == ()
    assert summary.bearish == ()
    assert summary.bullish_count == 0
    assert summary.bearish_count == 0
    assert summary.bullish_score == 0.0
    assert summary.bearish_score == 0.0
    assert summary.net_score == 0.0
    assert summary.bias is MarketBias.NEUTRAL


def test_effort_result_context_does_not_change_bullish_primary_aggregation_score():
    aggregator = EvidenceAggregator()
    baseline = aggregator.aggregate((_bullish_primary(),))
    with_context = aggregator.aggregate(
        (
            _bullish_primary(),
            _effort_result_item(EvidenceCode.EFFORT_GT_RESULT),
            _effort_result_item(EvidenceCode.RESULT_GT_EFFORT),
        )
    )

    assert with_context.bullish_score == baseline.bullish_score
    assert with_context.bearish_score == baseline.bearish_score
    assert with_context.net_score == baseline.net_score
    assert with_context.bias is baseline.bias
    assert with_context.bullish_count == baseline.bullish_count
    assert with_context.bearish_count == baseline.bearish_count
    assert with_context.bullish == baseline.bullish
    assert with_context.bearish == baseline.bearish


def test_effort_result_context_does_not_change_bearish_primary_aggregation_score():
    aggregator = EvidenceAggregator()
    baseline = aggregator.aggregate((_bearish_primary(),))
    with_context = aggregator.aggregate(
        (
            _bearish_primary(),
            _effort_result_item(EvidenceCode.EFFORT_GT_RESULT),
            _effort_result_item(EvidenceCode.RESULT_GT_EFFORT),
        )
    )

    assert with_context.bullish_score == baseline.bullish_score
    assert with_context.bearish_score == baseline.bearish_score
    assert with_context.net_score == baseline.net_score
    assert with_context.bias is baseline.bias
    assert with_context.bullish_count == baseline.bullish_count
    assert with_context.bearish_count == baseline.bearish_count
    assert with_context.bullish == baseline.bullish
    assert with_context.bearish == baseline.bearish
