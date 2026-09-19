from __future__ import annotations

import pandas as pd

from audit.progression_shadow_replay_dataset import (
    PROGRESSION_SHADOW_REPLAY_DATASET_ID,
    FrozenShadowSemanticArtifact,
    FrozenShadowSemanticRow,
    build_progression_shadow_replay_dataset_audit,
    build_symbol_shadow_replay_sequences,
)
from daily_completion import completed_daily_only
from data import completed_weekly_only, daily_to_weekly


def _daily() -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=500, freq="D")
    close = [100.0 + item * 0.1 for item in range(len(index))]
    return pd.DataFrame(
        {
            "open": close,
            "high": [item + 1.0 for item in close],
            "low": [item - 1.0 for item in close],
            "close": close,
            "volume": [1000.0] * len(index),
        },
        index=index,
    )


def _event(*, week: str, source_index: int = 999) -> FrozenShadowSemanticRow:
    return FrozenShadowSemanticRow(
        symbol="AAA.NS",
        source_event_bar_index=source_index,
        event_week=week,
        event_code="STRUCTURAL_PROGRESSION_IMPROVING",
        event_direction="bullish",
        trend_direction="down",
        trend_alignment="opposed",
        semantic_role="TRANSITION_WARNING",
        projected_transition_direction="bullish",
    )


def test_replay_resolves_event_by_week_not_source_index() -> None:
    daily = _daily()
    now = "2025-12-26T16:00:00+05:30"
    weekly = completed_weekly_only(
        daily_to_weekly(completed_daily_only(daily, now=now)),
        now=now,
    )
    week = str(pd.Timestamp(weekly.iloc[20]["week_beginning"]))

    sequences = build_symbol_shadow_replay_sequences(
        symbol="AAA.NS",
        daily=daily,
        events=(_event(week=week),),
        now=now,
        lookback_bars=2,
        forward_bars=2,
    )

    assert len(sequences) == 1
    sequence = sequences[0]
    assert sequence.source_event_bar_index == 999
    assert sequence.resolved_event_bar_index == 20
    assert len(sequence.frames) == 5


def test_event_marker_appears_on_exactly_one_frame() -> None:
    daily = _daily()
    now = "2025-12-26T16:00:00+05:30"
    weekly = completed_weekly_only(
        daily_to_weekly(completed_daily_only(daily, now=now)),
        now=now,
    )
    week = str(pd.Timestamp(weekly.iloc[20]["week_beginning"]))

    sequence = build_symbol_shadow_replay_sequences(
        symbol="AAA.NS",
        daily=daily,
        events=(_event(week=week),),
        now=now,
    )[0]

    event_frames = [item for item in sequence.frames if item.is_event_bar]
    assert len(event_frames) == 1
    event = event_frames[0]
    assert event.semantic_role == "TRANSITION_WARNING"
    assert event.projected_transition_direction == "bullish"
    assert all(
        item.semantic_role is None
        for item in sequence.frames
        if not item.is_event_bar
    )


def test_every_frame_keeps_production_safety_closed() -> None:
    daily = _daily()
    now = "2025-12-26T16:00:00+05:30"
    weekly = completed_weekly_only(
        daily_to_weekly(completed_daily_only(daily, now=now)),
        now=now,
    )
    week = str(pd.Timestamp(weekly.iloc[20]["week_beginning"]))
    sequence = build_symbol_shadow_replay_sequences(
        symbol="AAA.NS",
        daily=daily,
        events=(_event(week=week),),
        now=now,
    )[0]

    for frame in sequence.frames:
        assert frame.reversal_confirmed is False
        assert frame.persistent_direction_claim is False
        assert frame.affects_qualification is False
        assert frame.affects_scoring is False
        assert frame.is_actionable is False


def test_audit_preserves_sequence_count() -> None:
    artifact = FrozenShadowSemanticArtifact(
        basket_name="fixture",
        requested_symbol_count=1,
        event_count=0,
        rows_by_symbol={"AAA.NS": ()},
    )
    audit = build_progression_shadow_replay_dataset_audit(
        artifact=artifact,
        requested_symbols=("AAA.NS",),
        symbol_sequences=((),),
        lookback_bars=4,
        forward_bars=4,
    )

    assert audit.audit_id == PROGRESSION_SHADOW_REPLAY_DATASET_ID
    assert audit.sequence_count == 0
    assert audit.is_actionable is False
