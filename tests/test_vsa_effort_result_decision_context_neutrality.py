"""Effort-vs-Result decision-context saved-artifact neutrality guards.

PR #138 enabled contextual Effort/Result collection, PR #139 neutralized
professional scoring weights, PR #140 protected aggregation neutrality, PR #141
protected scanner actionability neutrality, and PR #142 protected scanner ranking
neutrality. These tests protect the compact saved decision-context artifact before
any separate Effort/Result scoring or ranking PR.
"""

from __future__ import annotations

from types import SimpleNamespace

from background.qualification import PatternQualification
from decision_context import (
    DecisionAction,
    DecisionContextStore,
    MarketPhaseContext,
    SupplyDemandBias,
    TradabilityStatus,
    build_decision_context,
)
from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    TrendDirection,
    TrendState,
)


EVALUATED_AT = "2026-09-12T09:30:00+00:00"
EFFORT_RESULT_CODES = (
    EvidenceCode.EFFORT_GT_RESULT,
    EvidenceCode.RESULT_GT_EFFORT,
    EvidenceCode.ABSORPTION,
    EvidenceCode.EFFORT_RESULT,
)


def _evidence(
    *,
    code: EvidenceCode,
    category: EvidenceCategory,
    direction: EvidenceDirection,
    bar_index: int = 42,
    strength: float = 0.80,
    weight: float = 1.0,
    quality: float = 0.80,
) -> Evidence:
    return Evidence(
        code=code,
        category=category,
        direction=direction,
        strength=strength,
        weight=weight,
        observation=f"{code.value} observation",
        description=f"{code.value} description",
        bar_index=bar_index,
        week_beginning="2026-03-02",
        quality=quality,
    )


def _effort_result(code: EvidenceCode, *, bar_index: int = 42) -> Evidence:
    return _evidence(
        code=code,
        category=EvidenceCategory.EFFORT,
        direction=EvidenceDirection.NEUTRAL,
        bar_index=bar_index,
        strength=0.70,
        weight=0.0,
    )


def _bearish_vsa(*, bar_index: int = 42) -> Evidence:
    return _evidence(
        code=EvidenceCode.UPTHRUST,
        category=EvidenceCategory.SUPPLY,
        direction=EvidenceDirection.BEARISH,
        bar_index=bar_index,
    )


def _bullish_vsa(*, bar_index: int = 42) -> Evidence:
    return _evidence(
        code=EvidenceCode.STOPPING_VOLUME,
        category=EvidenceCategory.DEMAND,
        direction=EvidenceDirection.BULLISH,
        bar_index=bar_index,
    )


def _candidate(
    *items: Evidence,
    qualification: PatternQualification,
    actionable: bool,
    execution_pending: bool,
    net_pressure: float,
    net_strength: float,
    confidence: float = 0.72,
    trend_direction: TrendDirection = TrendDirection.RANGE,
    trend_state: TrendState = TrendState.DEVELOPING,
    reason: str = "Persistent structure remains valid.",
) -> SimpleNamespace:
    trend = SimpleNamespace(
        direction=trend_direction,
        state=trend_state,
        structure=SimpleNamespace(structural_swings=()),
    )
    return SimpleNamespace(
        campaign_evidence=tuple(items),
        qualifying_evidence=(),
        scoring_evidence=tuple(items),
        target_bar_evidence=tuple(item for item in items if item.bar_index == 42),
        evidence=SimpleNamespace(context=SimpleNamespace(trend=trend)),
        qualification=qualification,
        actionable=actionable,
        execution_pending=execution_pending,
        signal_bar_anomaly=False,
        confidence=confidence,
        net_strength=net_strength,
        net_pressure=net_pressure,
        bar_index=42,
        week="2026-03-02",
        reason=reason,
    )


def _stable_decision_fields(context) -> dict[str, object]:
    return {
        "qualification": context.qualification,
        "actionable": context.actionable,
        "decision": context.decision,
        "tradability": context.tradability,
        "phase": context.phase,
        "bias": context.bias,
        "confidence": context.confidence,
        "net_strength": context.net_strength,
        "net_pressure": context.net_pressure,
        "reason": context.reason,
        "story_headline": context.story.headline,
        "confirmation_condition": context.story.confirmation_condition,
        "invalidation_condition": context.story.invalidation_condition,
        "what_to_expect_next": context.story.what_to_expect_next,
    }


def _event_codes(context) -> set[str]:
    return {event.code for event in context.recent_events}


def _effort_result_event_directions(context) -> dict[str, str]:
    effort_result_values = {code.value for code in EFFORT_RESULT_CODES}
    return {
        event.code: event.direction
        for event in context.recent_events
        if event.code in effort_result_values
    }


def test_effort_result_context_is_saved_without_changing_bearish_decision_fields() -> None:
    baseline = build_decision_context(
        _candidate(
            _bearish_vsa(),
            qualification=PatternQualification.PERSISTENT_BEARISH,
            actionable=True,
            execution_pending=False,
            net_pressure=-0.40,
            net_strength=-0.40,
            reason="Persistent bearish structure remains valid.",
        ),
        symbol="LT.NS",
        evaluated_at_utc=EVALUATED_AT,
    )
    with_context = build_decision_context(
        _candidate(
            _bearish_vsa(),
            _effort_result(EvidenceCode.EFFORT_GT_RESULT),
            _effort_result(EvidenceCode.RESULT_GT_EFFORT),
            _effort_result(EvidenceCode.ABSORPTION),
            qualification=PatternQualification.PERSISTENT_BEARISH,
            actionable=True,
            execution_pending=False,
            net_pressure=-0.40,
            net_strength=-0.40,
            reason="Persistent bearish structure remains valid.",
        ),
        symbol="LT.NS",
        evaluated_at_utc=EVALUATED_AT,
    )

    assert _stable_decision_fields(with_context) == _stable_decision_fields(baseline)
    assert baseline.bias == SupplyDemandBias.BEARISH
    assert baseline.phase == MarketPhaseContext.DISTRIBUTION
    assert baseline.tradability == TradabilityStatus.TRADABLE_NOW
    assert baseline.decision == DecisionAction.REVIEW_SETUP
    assert _event_codes(with_context) > _event_codes(baseline)
    assert _effort_result_event_directions(with_context) == {
        EvidenceCode.EFFORT_GT_RESULT.value: "NEUTRAL",
        EvidenceCode.RESULT_GT_EFFORT.value: "NEUTRAL",
        EvidenceCode.ABSORPTION.value: "NEUTRAL",
    }


def test_effort_result_context_is_saved_without_changing_bullish_decision_fields() -> None:
    baseline = build_decision_context(
        _candidate(
            _bullish_vsa(),
            qualification=PatternQualification.PERSISTENT_BULLISH,
            actionable=True,
            execution_pending=False,
            net_pressure=0.40,
            net_strength=0.40,
            reason="Persistent bullish structure remains valid.",
        ),
        symbol="LT.NS",
        evaluated_at_utc=EVALUATED_AT,
    )
    with_context = build_decision_context(
        _candidate(
            _bullish_vsa(),
            _effort_result(EvidenceCode.EFFORT_GT_RESULT),
            _effort_result(EvidenceCode.RESULT_GT_EFFORT),
            _effort_result(EvidenceCode.EFFORT_RESULT),
            qualification=PatternQualification.PERSISTENT_BULLISH,
            actionable=True,
            execution_pending=False,
            net_pressure=0.40,
            net_strength=0.40,
            reason="Persistent bullish structure remains valid.",
        ),
        symbol="LT.NS",
        evaluated_at_utc=EVALUATED_AT,
    )

    assert _stable_decision_fields(with_context) == _stable_decision_fields(baseline)
    assert baseline.bias == SupplyDemandBias.BULLISH
    assert baseline.phase == MarketPhaseContext.LATE_ACCUMULATION
    assert baseline.tradability == TradabilityStatus.TRADABLE_NOW
    assert baseline.decision == DecisionAction.REVIEW_SETUP
    assert _event_codes(with_context) > _event_codes(baseline)
    assert _effort_result_event_directions(with_context) == {
        EvidenceCode.EFFORT_GT_RESULT.value: "NEUTRAL",
        EvidenceCode.RESULT_GT_EFFORT.value: "NEUTRAL",
        EvidenceCode.EFFORT_RESULT.value: "NEUTRAL",
    }


def test_effort_result_only_saved_context_remains_neutral_observation_only() -> None:
    context = build_decision_context(
        _candidate(
            *(_effort_result(code) for code in EFFORT_RESULT_CODES),
            qualification=PatternQualification.UNQUALIFIED,
            actionable=False,
            execution_pending=False,
            net_pressure=0.0,
            net_strength=0.0,
            confidence=0.0,
            reason="No directional VSA confirmation is present.",
        ),
        symbol="LT.NS",
        evaluated_at_utc=EVALUATED_AT,
    )

    assert context.actionable is False
    assert context.bias == SupplyDemandBias.NEUTRAL
    assert context.phase == MarketPhaseContext.UNCERTAIN
    assert context.tradability == TradabilityStatus.OBSERVATION_ONLY
    assert context.decision == DecisionAction.OBSERVE_ONLY
    assert context.confidence == 0.0
    assert context.net_pressure == 0.0
    assert context.net_strength == 0.0
    assert _event_codes(context) == {code.value for code in EFFORT_RESULT_CODES}
    assert set(_effort_result_event_directions(context).values()) == {"NEUTRAL"}


def test_effort_result_neutrality_survives_saved_context_round_trip(tmp_path) -> None:
    context = build_decision_context(
        _candidate(
            *(_effort_result(code) for code in EFFORT_RESULT_CODES),
            qualification=PatternQualification.UNQUALIFIED,
            actionable=False,
            execution_pending=False,
            net_pressure=0.0,
            net_strength=0.0,
            confidence=0.0,
            reason="No directional VSA confirmation is present.",
        ),
        symbol="LT.NS",
        evaluated_at_utc=EVALUATED_AT,
    )
    store = DecisionContextStore(tmp_path)

    path = store.save(context)
    loaded = store.load("LT.NS", "1W")
    payload = loaded.to_dict()

    assert path.exists()
    assert loaded == context
    assert payload["actionable"] is False
    assert payload["decision"] == DecisionAction.OBSERVE_ONLY.value
    assert payload["tradability"] == TradabilityStatus.OBSERVATION_ONLY.value
    assert payload["bias"] == SupplyDemandBias.NEUTRAL.value
    assert payload["phase"] == MarketPhaseContext.UNCERTAIN.value
    assert {event["code"] for event in payload["recent_events"]} == {
        code.value for code in EFFORT_RESULT_CODES
    }
    assert {event["direction"] for event in payload["recent_events"]} == {"NEUTRAL"}
