from __future__ import annotations

import pytest

from decision_context import (
    DECISION_CONTEXT_SCHEMA_VERSION,
    DecisionAction,
    DecisionContext,
    DecisionContextStore,
    DecisionMode,
    MarketPhaseContext,
    SupplyDemandBias,
    TradabilityStatus,
    VSAStorySummary,
)


def _context(mode: DecisionMode) -> DecisionContext:
    return DecisionContext(
        schema_version=DECISION_CONTEXT_SCHEMA_VERSION,
        symbol="TEST.NS",
        timeframe="1W",
        mode=mode,
        latest_bar_index=21,
        latest_week="2026-09-04 00:00:00",
        qualification="observation_only",
        actionable=False,
        decision=DecisionAction.OBSERVE_ONLY,
        tradability=TradabilityStatus.OBSERVATION_ONLY,
        phase=MarketPhaseContext.UNCERTAIN,
        bias=SupplyDemandBias.NEUTRAL,
        confidence=0.42,
        net_strength=0.0,
        net_pressure=0.0,
        reason="test context",
        recent_events=(),
        structural_swings=(),
        story=VSAStorySummary(
            headline="No decisive VSA context yet",
            summary="Test summary",
            confirmation_condition="Wait for confirmation.",
            invalidation_condition="Conflicting evidence remains.",
            what_to_expect_next=("Observe only.",),
        ),
        evaluated_at_utc="2026-09-09T05:30:00+00:00",
    )


def test_store_saves_confirmed_context(tmp_path) -> None:
    store = DecisionContextStore(tmp_path)

    path = store.save(_context(DecisionMode.CONFIRMED))

    assert path.exists()
    loaded = store.load("TEST.NS", "1W")
    assert loaded.mode is DecisionMode.CONFIRMED


def test_store_rejects_developing_context_without_writing_file(tmp_path) -> None:
    store = DecisionContextStore(tmp_path)

    with pytest.raises(ValueError, match="Only confirmed DecisionContext"):
        store.save(_context(DecisionMode.DEVELOPING))

    assert not store.path_for("TEST.NS", "1W").exists()
