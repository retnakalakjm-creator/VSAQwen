from __future__ import annotations

from types import SimpleNamespace

import pytest

from background.qualification import PatternQualification
from decision_context import (
    DecisionAction,
    DecisionContextStore,
    DecisionMode,
    MarketPhaseContext,
    TradabilityStatus,
    build_decision_context,
)
from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    SwingGrade,
    SwingLabel,
    SwingType,
    TrendDirection,
    TrendState,
)


EVALUATED_AT = "2026-09-08T09:30:00+00:00"


def _evidence(
    index: int,
    *,
    code: EvidenceCode = EvidenceCode.STOPPING_VOLUME,
    direction: EvidenceDirection = EvidenceDirection.BULLISH,
) -> Evidence:
    category = (
        EvidenceCategory.DEMAND
        if direction == EvidenceDirection.BULLISH
        else EvidenceCategory.SUPPLY
    )
    return Evidence(
        code=code,
        category=category,
        direction=direction,
        strength=0.60 + (index % 3) * 0.05,
        weight=1.0,
        observation=f"Observation {index}",
        description=f"Description {index}",
        bar_index=index,
        week_beginning=f"2026-08-{index + 1:02d}",
        quality=0.80,
    )


def _structural_swing(index: int) -> SimpleNamespace:
    swing = SimpleNamespace(
        type=SwingType.LOW,
        price=100.0 + index,
        bar_index=index,
        confirmation_index=index + 1,
        week_beginning=f"2026-07-{index + 1:02d}",
        label=SwingLabel.HL,
    )
    return SimpleNamespace(
        swing=swing,
        grade=SwingGrade.MAJOR,
        is_failed=False,
        evaluation=SimpleNamespace(
            professional=SimpleNamespace(overall=0.70 + index / 100.0),
        ),
    )


def _candidate(
    evidence: tuple[Evidence, ...],
    *,
    structural_swings: tuple[SimpleNamespace, ...] = (),
    actionable: bool = True,
    execution_pending: bool = True,
    signal_bar_anomaly: bool = False,
    net_pressure: float = 0.30,
    qualification: PatternQualification = PatternQualification.PERSISTENT_BULLISH,
) -> SimpleNamespace:
    trend = SimpleNamespace(
        direction=TrendDirection.RANGE,
        state=TrendState.DEVELOPING,
        structure=SimpleNamespace(structural_swings=structural_swings),
    )
    return SimpleNamespace(
        campaign_evidence=evidence,
        qualifying_evidence=evidence[-3:],
        scoring_evidence=evidence[-2:],
        target_bar_evidence=evidence[-1:],
        evidence=SimpleNamespace(context=SimpleNamespace(trend=trend)),
        qualification=qualification,
        actionable=actionable,
        execution_pending=execution_pending,
        signal_bar_anomaly=signal_bar_anomaly,
        confidence=0.72,
        net_strength=0.40,
        net_pressure=net_pressure,
        bar_index=99,
        week="2026-09-04",
        reason="Persistent bullish structure remains valid.",
    )


def test_decision_context_keeps_only_recent_decision_events_and_swings() -> None:
    evidence = tuple(_evidence(index) for index in range(20))
    structural_swings = tuple(_structural_swing(index) for index in range(12))

    context = build_decision_context(
        _candidate(evidence, structural_swings=structural_swings),
        symbol="srf.ns",
        max_events=5,
        max_structural_swings=4,
        evaluated_at_utc=EVALUATED_AT,
    )

    assert context.symbol == "SRF.NS"
    assert context.mode == DecisionMode.CONFIRMED
    assert context.phase == MarketPhaseContext.LATE_ACCUMULATION
    assert context.tradability == TradabilityStatus.WAIT_FOR_CONFIRMATION
    assert context.decision == DecisionAction.WAIT_FOR_CONFIRMATION
    assert [event.bar_index for event in context.recent_events] == [15, 16, 17, 18, 19]
    assert [swing.pivot_bar_index for swing in context.structural_swings] == [8, 9, 10, 11]
    assert context.story.what_to_expect_next
    assert "STOPPING_VOLUME" not in context.story.summary
    assert "stopping_volume" in context.story.summary


def test_decision_context_store_round_trips_json(tmp_path) -> None:
    evidence = tuple(_evidence(index) for index in range(3))
    context = build_decision_context(
        _candidate(evidence),
        symbol="RELIANCE.NS",
        timeframe="1W",
        evaluated_at_utc=EVALUATED_AT,
    )
    store = DecisionContextStore(tmp_path)

    path = store.save(context)
    loaded = store.load("RELIANCE.NS", "1W")

    assert path.exists()
    assert loaded == context
    assert loaded.to_dict()["recent_events"][-1]["role"] == "campaign|qualifying|scoring|target"


def test_anomaly_signal_is_avoid_decision() -> None:
    context = build_decision_context(
        _candidate(
            (_evidence(1),),
            actionable=False,
            signal_bar_anomaly=True,
        ),
        symbol="TCS.NS",
        evaluated_at_utc=EVALUATED_AT,
    )

    assert context.tradability == TradabilityStatus.AVOID
    assert context.decision == DecisionAction.AVOID
    assert context.actionable is False
    assert "Avoid" in context.story.headline


def test_bearish_context_gets_bearish_expectations() -> None:
    evidence = (
        _evidence(
            1,
            code=EvidenceCode.UPTHRUST,
            direction=EvidenceDirection.BEARISH,
        ),
    )
    context = build_decision_context(
        _candidate(
            evidence,
            actionable=False,
            net_pressure=-0.40,
            qualification=PatternQualification.PERSISTENT_BEARISH,
        ),
        symbol="INFY.NS",
        evaluated_at_utc=EVALUATED_AT,
    )

    assert context.phase == MarketPhaseContext.DISTRIBUTION
    assert context.tradability == TradabilityStatus.WAIT_FOR_CONFIRMATION
    assert "supply" in context.story.confirmation_condition.lower()
    assert "distribution" in context.story.headline


def test_invalid_decision_context_limits_raise() -> None:
    candidate = _candidate((_evidence(1),))

    with pytest.raises(ValueError, match="max_events"):
        build_decision_context(candidate, symbol="SRF.NS", max_events=0)

    with pytest.raises(ValueError, match="max_structural_swings"):
        build_decision_context(candidate, symbol="SRF.NS", max_structural_swings=0)
