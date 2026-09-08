from __future__ import annotations

from decision_context import (
    DECISION_CONTEXT_SCHEMA_VERSION,
    DecisionAction,
    DecisionContext,
    DecisionMode,
    MarketPhaseContext,
    StructuralSwingMemory,
    SupplyDemandBias,
    TradabilityStatus,
    VSAStorySummary,
)
from decision_journal import (
    DecisionJournalEntry,
    DecisionJournalStore,
    ValidationOutcome,
    create_journal_entry,
    evaluate_journal_entry,
)


def _context(
    *,
    bias: SupplyDemandBias = SupplyDemandBias.BULLISH,
    tradability: TradabilityStatus = TradabilityStatus.WAIT_FOR_CONFIRMATION,
) -> DecisionContext:
    return DecisionContext(
        schema_version=DECISION_CONTEXT_SCHEMA_VERSION,
        symbol="SRF.NS",
        timeframe="1W",
        mode=DecisionMode.CONFIRMED,
        latest_bar_index=10,
        latest_week="2026-08-28",
        qualification="persistent_bullish",
        actionable=False,
        decision=DecisionAction.WAIT_FOR_CONFIRMATION,
        tradability=tradability,
        phase=MarketPhaseContext.LATE_ACCUMULATION,
        bias=bias,
        confidence=0.72,
        net_strength=0.64,
        net_pressure=0.31 if bias is SupplyDemandBias.BULLISH else -0.31,
        reason="Decision-support test context.",
        recent_events=(),
        structural_swings=(
            StructuralSwingMemory(
                pivot_bar_index=7,
                confirmation_bar_index=8,
                pivot_week="2026-08-07",
                type="low",
                label="HL",
                price=100.0,
                grade="MAJOR",
                is_failed=False,
                score=0.82,
            ),
            StructuralSwingMemory(
                pivot_bar_index=9,
                confirmation_bar_index=10,
                pivot_week="2026-08-21",
                type="high",
                label="HH",
                price=120.0,
                grade="MAJOR",
                is_failed=False,
                score=0.76,
            ),
        ),
        story=VSAStorySummary(
            headline="Bullish VSA context in late accumulation",
            summary="Absorption and test behavior suggest supply may be drying up.",
            confirmation_condition="Look for demand above resistance.",
            invalidation_condition="Breakdown below support weakens the story.",
            what_to_expect_next=(
                "Constructive pullbacks should hold support.",
                "Fresh demand should confirm the read.",
            ),
        ),
        evaluated_at_utc="2026-09-01T10:00:00+00:00",
    )


def test_create_journal_entry_keeps_compact_decision_expectation() -> None:
    entry = create_journal_entry(
        _context(),
        created_at_utc="2026-09-01T10:05:00+00:00",
    )

    assert entry.schema_version == 1
    assert entry.entry_id == "SRF.NS__1W__2026-08-28__10"
    assert entry.bias == "bullish"
    assert entry.tradability == "wait_for_confirmation"
    assert entry.support_price == 100.0
    assert entry.resistance_price == 120.0
    assert entry.reference_price == 100.0
    assert entry.expected_next_behavior == (
        "Constructive pullbacks should hold support.",
        "Fresh demand should confirm the read.",
    )
    assert entry.status is ValidationOutcome.PENDING


def test_journal_store_upserts_and_round_trips_entries(tmp_path) -> None:
    store = DecisionJournalStore(tmp_path)
    first = create_journal_entry(_context(), created_at_utc="2026-09-01T10:05:00+00:00")
    updated = DecisionJournalEntry.from_dict({**first.to_dict(), "confidence": 0.88})

    store.upsert(first)
    path = store.upsert(updated)

    assert path.exists()
    assert store.load_all("SRF.NS", "1W") == (updated,)


def test_bullish_journal_entry_confirms_when_later_close_clears_resistance() -> None:
    entry = create_journal_entry(_context())

    evaluation = evaluate_journal_entry(
        entry,
        [
            {"bar_index": 10, "week": "2026-08-28", "high": 110, "low": 101, "close": 108},
            {"bar_index": 11, "week": "2026-09-04", "high": 119, "low": 106, "close": 118},
            {"bar_index": 12, "week": "2026-09-11", "high": 126, "low": 112, "close": 122},
        ],
    )

    assert evaluation.outcome is ValidationOutcome.CONFIRMED
    assert evaluation.checked_bars == 2
    assert evaluation.first_checked_week == "2026-09-04"
    assert evaluation.last_checked_week == "2026-09-11"
    assert evaluation.confirmation_hit is True
    assert evaluation.invalidation_hit is False
    assert evaluation.favorable_move_pct == 26.0


def test_bullish_journal_entry_invalidates_when_later_close_breaks_support() -> None:
    entry = create_journal_entry(_context())

    evaluation = evaluate_journal_entry(
        entry,
        [
            {"bar_index": 11, "week": "2026-09-04", "high": 108, "low": 97, "close": 98},
        ],
    )

    assert evaluation.outcome is ValidationOutcome.INVALIDATED
    assert evaluation.confirmation_hit is False
    assert evaluation.invalidation_hit is True
    assert evaluation.adverse_move_pct == 3.0


def test_bearish_journal_entry_confirms_on_support_break() -> None:
    entry = create_journal_entry(_context(bias=SupplyDemandBias.BEARISH))

    evaluation = evaluate_journal_entry(
        entry,
        [
            {"bar_index": 11, "week": "2026-09-04", "high": 118, "low": 99, "close": 98},
        ],
    )

    assert evaluation.outcome is ValidationOutcome.CONFIRMED
    assert evaluation.confirmation_hit is True
    assert evaluation.invalidation_hit is False
    assert evaluation.favorable_move_pct == 17.5


def test_avoid_context_is_observation_only() -> None:
    entry = create_journal_entry(_context(tradability=TradabilityStatus.AVOID))

    evaluation = evaluate_journal_entry(
        entry,
        [
            {"bar_index": 11, "week": "2026-09-04", "high": 130, "low": 80, "close": 125},
        ],
    )

    assert entry.status is ValidationOutcome.OBSERVATION_ONLY
    assert evaluation.outcome is ValidationOutcome.OBSERVATION_ONLY
    assert evaluation.checked_bars == 1


def test_no_later_bars_returns_no_data() -> None:
    entry = create_journal_entry(_context())

    evaluation = evaluate_journal_entry(
        entry,
        [
            {"bar_index": 10, "week": "2026-08-28", "high": 110, "low": 101, "close": 108},
        ],
    )

    assert evaluation.outcome is ValidationOutcome.NO_DATA
    assert evaluation.checked_bars == 0


def test_invalid_horizon_raises() -> None:
    entry = create_journal_entry(_context())

    try:
        evaluate_journal_entry(entry, [], horizon_bars=0)
    except ValueError as exc:
        assert "horizon_bars" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
