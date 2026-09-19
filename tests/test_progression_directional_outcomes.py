from __future__ import annotations

import json

import pandas as pd

from audit.progression_directional_outcomes import (
    PROGRESSION_DIRECTIONAL_OUTCOME_AUDIT_ID,
    build_progression_directional_outcome_audit,
    build_progression_directional_outcomes,
    load_progression_directionality_artifacts,
    summarize_progression_directional_outcomes,
    write_progression_directional_outcome_audit,
)
from audit.progression_directionality_semantics import (
    ProgressionDirectionalityRow,
)


def _weekly() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "week_beginning": pd.date_range(
                "2026-01-05",
                periods=7,
                freq="7D",
            ),
            "close": [100.0, 102.0, 105.0, 108.0, 106.0, 103.0, 101.0],
            "high": [101.0, 103.0, 106.0, 109.0, 108.0, 105.0, 103.0],
            "low": [99.0, 101.0, 104.0, 107.0, 104.0, 101.0, 99.0],
        }
    )


def _row(
    *,
    index: int,
    direction: str,
    trend_alignment: str = "aligned",
    pattern_alignment: str = "ambiguous",
) -> ProgressionDirectionalityRow:
    if trend_alignment == "aligned":
        trend_direction = "up" if direction == "bullish" else "down"
    elif trend_alignment == "opposed":
        trend_direction = "down" if direction == "bullish" else "up"
    elif trend_alignment == "neutral":
        trend_direction = "range"
    else:
        trend_direction = "unknown"

    return ProgressionDirectionalityRow(
        symbol="AAA.NS",
        event_bar_index=index,
        event_week=str(pd.Timestamp(_weekly().iloc[index]["week_beginning"])),
        event_code=(
            "structural_progression_improving"
            if direction == "bullish"
            else "structural_progression_weakening"
        ),
        event_direction=direction,
        progression_difference=0.1 if direction == "bullish" else -0.1,
        trend_direction=trend_direction,
        trend_state="healthy",
        structural_pattern="stable",
        trend_alignment=trend_alignment,
        structural_pattern_alignment=pattern_alignment,
        qualification_after_event="unqualified",
    )


def test_outcome_uses_next_week_execution_not_signal_week() -> None:
    observations = build_progression_directional_outcomes(
        weekly=_weekly(),
        rows=(_row(index=1, direction="bullish"),),
        horizons_weeks=(1,),
    )

    item = observations[0]
    assert item.outcome_available is True
    assert item.execution_bar_index == 2
    assert item.exit_bar_index == 3
    assert item.raw_return == 108.0 / 105.0 - 1.0
    assert item.favorable_return == item.raw_return


def test_bearish_event_converts_falling_return_to_favorable() -> None:
    observations = build_progression_directional_outcomes(
        weekly=_weekly(),
        rows=(_row(index=3, direction="bearish"),),
        horizons_weeks=(1,),
    )

    item = observations[0]
    assert item.execution_bar_index == 4
    assert item.exit_bar_index == 5
    assert item.raw_return == 103.0 / 106.0 - 1.0
    assert item.favorable_return == -item.raw_return
    assert item.favorable_return > 0


def test_latest_event_without_execution_bar_is_retained_unscored() -> None:
    observations = build_progression_directional_outcomes(
        weekly=_weekly(),
        rows=(_row(index=6, direction="bearish"),),
        horizons_weeks=(1, 3),
    )

    assert len(observations) == 2
    assert all(not item.outcome_available for item in observations)
    assert all(item.favorable_return is None for item in observations)


def test_summary_splits_all_direction_and_alignment_cohorts() -> None:
    observations = build_progression_directional_outcomes(
        weekly=_weekly(),
        rows=(
            _row(index=1, direction="bullish", trend_alignment="aligned"),
            _row(index=3, direction="bearish", trend_alignment="opposed"),
        ),
        horizons_weeks=(1,),
    )
    summaries = summarize_progression_directional_outcomes(observations)

    keys = {
        (item.cohort_dimension, item.cohort_value)
        for item in summaries
    }
    assert ("all", "all") in keys
    assert ("event_direction", "bullish") in keys
    assert ("event_direction", "bearish") in keys
    assert ("trend_alignment", "aligned") in keys
    assert ("trend_alignment", "opposed") in keys


def test_audit_writer_is_non_actionable_and_keeps_horizon_summary(
    tmp_path,
) -> None:
    observations = build_progression_directional_outcomes(
        weekly=_weekly(),
        rows=(_row(index=1, direction="bullish"),),
        horizons_weeks=(1, 3),
    )
    audit = build_progression_directional_outcome_audit(
        basket_name="fixture",
        requested_symbols=("AAA.NS",),
        symbol_observations=(observations,),
        event_counts=(1,),
        horizons_weeks=(1, 3),
    )
    paths = write_progression_directional_outcome_audit(
        audit,
        tmp_path,
    )
    summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    cohorts = pd.read_csv(paths.cohort_summaries_csv)

    assert audit.audit_id == PROGRESSION_DIRECTIONAL_OUTCOME_AUDIT_ID
    assert audit.is_actionable is False
    assert summary["is_actionable"] is False
    assert summary["event_count"] == 1
    assert summary["horizons_weeks"] == [1, 3]
    assert "no same-bar outcome" in summary["execution_semantics"]
    assert not cohorts.empty


def test_duplicate_event_input_fails_closed() -> None:
    row = _row(index=1, direction="bullish")

    import pytest

    with pytest.raises(ValueError, match="duplicate progression event"):
        build_progression_directional_outcomes(
            weekly=_weekly(),
            rows=(row, row),
            horizons_weeks=(1,),
        )


def test_audit_rejects_symbol_group_event_count_mismatch() -> None:
    observations = build_progression_directional_outcomes(
        weekly=_weekly(),
        rows=(_row(index=1, direction="bullish"),),
        horizons_weeks=(1, 3),
    )

    import pytest

    with pytest.raises(ValueError, match="event_count × horizon_count"):
        build_progression_directional_outcome_audit(
            basket_name="fixture",
            requested_symbols=("AAA.NS",),
            symbol_observations=(observations,),
            event_counts=(2,),
            horizons_weeks=(1, 3),
        )


def test_audit_rejects_missing_success_or_failure_symbol() -> None:
    import pytest

    with pytest.raises(
        ValueError,
        match="successful plus failed symbol counts",
    ):
        build_progression_directional_outcome_audit(
            basket_name="fixture",
            requested_symbols=("AAA.NS", "BBB.NS"),
            symbol_observations=((),),
            event_counts=(0,),
            horizons_weeks=(1,),
        )


def test_k14_artifact_loader_preserves_zero_event_symbols(tmp_path) -> None:
    events = pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                "event_bar_index": 1,
                "event_week": "2026-01-12",
                "event_code": "structural_progression_improving",
                "event_direction": "bullish",
                "progression_difference": 0.1,
                "trend_direction": "up",
                "trend_state": "healthy",
                "structural_pattern": "stable",
                "trend_alignment": "aligned",
                "structural_pattern_alignment": "ambiguous",
                "qualification_after_event": "unqualified",
            }
        ]
    )
    symbols = pd.DataFrame(
        [
            {"symbol": "AAA.NS", "event_count": 1},
            {"symbol": "BBB.NS", "event_count": 0},
        ]
    )
    events.to_csv(
        tmp_path / "progression_directionality_events.csv",
        index=False,
    )
    symbols.to_csv(
        tmp_path / "progression_directionality_symbols.csv",
        index=False,
    )

    loaded = load_progression_directionality_artifacts(
        input_dir=tmp_path,
        basket_name="fixture",
        requested_symbols=("AAA.NS", "BBB.NS"),
    )

    assert loaded.event_counts_by_symbol == {
        "AAA.NS": 1,
        "BBB.NS": 0,
    }
    assert len(loaded.rows_by_symbol["AAA.NS"]) == 1
    assert loaded.rows_by_symbol["BBB.NS"] == ()


def test_k14_artifact_loader_rejects_event_count_mismatch(tmp_path) -> None:
    pd.DataFrame(
        columns=[
            "symbol",
            "event_bar_index",
            "event_week",
            "event_code",
            "event_direction",
            "progression_difference",
            "trend_direction",
            "trend_state",
            "structural_pattern",
            "trend_alignment",
            "structural_pattern_alignment",
            "qualification_after_event",
        ]
    ).to_csv(
        tmp_path / "progression_directionality_events.csv",
        index=False,
    )
    pd.DataFrame(
        [{"symbol": "AAA.NS", "event_count": 1}]
    ).to_csv(
        tmp_path / "progression_directionality_symbols.csv",
        index=False,
    )

    import pytest

    with pytest.raises(ValueError, match="event count mismatch"):
        load_progression_directionality_artifacts(
            input_dir=tmp_path,
            basket_name="fixture",
            requested_symbols=("AAA.NS",),
        )
