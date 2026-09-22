from __future__ import annotations

import inspect

from evidence import supply
from evidence.evidence_registry import build_evidence
from model.evidence_result_model import EvidenceResult
from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
)
from scanner import ScannerEngine
from scanner_state import VSAEventState


def _event(code: EvidenceCode, bar_index: int) -> Evidence:
    return build_evidence(
        code,
        bar_index=bar_index,
        week_beginning=f"2026-W{bar_index:03d}",
        weight=1.0,
    )


def test_supply_collection_is_target_bar_only() -> None:
    source = inspect.getsource(supply.collect_supply)

    assert "for i in range" not in source
    assert "ctx.with_current" not in source
    assert "_collect_buying_climax(ctx, campaign_snapshot)" in source
    assert "_collect_supply_coming_in(ctx, campaign_snapshot)" in source
    assert "_collect_hidden_supply(ctx)" in source
    assert "_collect_increasing_supply(ctx)" in source
    assert "_collect_supply_drying_up(ctx)" in source
    assert "_collect_upthrust(ctx)" in source
    assert "_collect_no_demand(ctx)" in source


def test_scoring_fallback_can_use_causal_bullish_history() -> None:
    current = EvidenceResult(context=None, evidence=())
    historical = (_event(EvidenceCode.DEMAND_COMING_IN, 24),)

    scoring = ScannerEngine._scoring_evidence(
        current,
        bar_index=30,
        historical_evidence=historical,
    )

    assert tuple((item.bar_index, item.code) for item in scoring) == (
        (24, EvidenceCode.DEMAND_COMING_IN),
    )


def test_scoring_fallback_can_use_causal_bearish_history() -> None:
    current = EvidenceResult(context=None, evidence=())
    historical = (_event(EvidenceCode.NO_DEMAND, 24),)

    scoring = ScannerEngine._scoring_evidence(
        current,
        bar_index=30,
        historical_evidence=historical,
    )

    assert tuple((item.bar_index, item.code) for item in scoring) == (
        (24, EvidenceCode.NO_DEMAND),
    )


def test_recent_vsa_state_is_bounded_by_scoring_lookback() -> None:
    retained = ScannerEngine._advance_recent_vsa(
        (
            _event(EvidenceCode.DEMAND_COMING_IN, 19),
            _event(EvidenceCode.NO_SUPPLY, 20),
        ),
        (_event(EvidenceCode.NO_DEMAND, 30),),
        bar_index=30,
    )

    assert tuple((item.bar_index, item.code) for item in retained) == (
        (20, EvidenceCode.NO_SUPPLY),
        (30, EvidenceCode.NO_DEMAND),
    )


def test_latest_causal_vsa_bar_wins_across_history_and_current() -> None:
    historical = (
        _event(EvidenceCode.DEMAND_COMING_IN, 24),
        _event(EvidenceCode.NO_DEMAND, 27),
    )
    current = EvidenceResult(
        context=None,
        evidence=(_event(EvidenceCode.NO_SUPPLY, 30),),
    )

    scoring = ScannerEngine._scoring_evidence(
        current,
        bar_index=30,
        historical_evidence=historical,
    )

    assert tuple((item.bar_index, item.code) for item in scoring) == (
        (30, EvidenceCode.NO_SUPPLY),
    )


def test_vsa_state_round_trip_preserves_delayed_event_provenance() -> None:
    evidence = Evidence(
        code=EvidenceCode.SPRING,
        category=EvidenceCategory.DEMAND,
        direction=EvidenceDirection.BULLISH,
        strength=0.9,
        weight=0.75,
        observation="Spring",
        description="causal delayed event",
        bar_index=42,
        week_beginning="2026-08-21",
        test_index=40,
        recovery_index=42,
        quality=0.8,
    )

    state = VSAEventState.from_evidence(evidence)
    restored = VSAEventState.from_dict(state.to_dict())
    rehydrated = restored.to_evidence(42)

    assert restored == state
    assert rehydrated.code == evidence.code
    assert rehydrated.bar_index == evidence.bar_index
    assert rehydrated.week_beginning == evidence.week_beginning
    assert rehydrated.test_index == 40
    assert rehydrated.recovery_index == 42
    assert rehydrated.quality == 0.8
