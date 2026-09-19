from __future__ import annotations

import json

import pandas as pd

from audit.progression_role_classification import (
    EXPECTED_K19_AUDIT_ID,
    PROGRESSION_ROLE_CLASSIFICATION_AUDIT_ID,
    FrozenCausalDriftArtifact,
    FrozenCausalDriftRow,
    ROLE_ACTUAL_REVERSAL,
    ROLE_CONTINUATION_FAILED,
    ROLE_CONTINUATION_OUTPERFORMS,
    ROLE_CONTINUATION_WEAKER,
    ROLE_DECELERATION_ONLY,
    ROLE_FAILED_COUNTERTREND,
    build_progression_role_audit,
    classify_progression_role,
    load_frozen_causal_drift_artifacts,
    summarize_progression_roles,
)


def _row(
    *,
    alignment: str,
    event_return: float,
    lift: float,
    direction: str = "bullish",
) -> FrozenCausalDriftRow:
    return FrozenCausalDriftRow(
        symbol="AAA.NS",
        event_week="2026-01-05",
        event_direction=direction,
        trend_alignment=alignment,
        source_event_bar_index=10,
        resolved_event_bar_index=20,
        horizon_weeks=5,
        control_window_size=26,
        control_count=26,
        event_complete=True,
        event_favorable_return=event_return,
        baseline_mean_favorable_return=event_return - lift,
        favorable_return_lift=lift,
    )


def test_opposed_actual_reversal_classification() -> None:
    classified = classify_progression_role(
        _row(
            alignment="opposed",
            event_return=0.03,
            lift=0.05,
        )
    )

    assert classified.role == ROLE_ACTUAL_REVERSAL
    assert classified.actual_reversal is True
    assert classified.transition_improvement is True


def test_opposed_deceleration_without_reversal_classification() -> None:
    classified = classify_progression_role(
        _row(
            alignment="opposed",
            event_return=-0.02,
            lift=0.04,
        )
    )

    assert classified.role == ROLE_DECELERATION_ONLY
    assert classified.actual_reversal is False
    assert classified.transition_improvement is True


def test_opposed_failed_countertrend_classification() -> None:
    classified = classify_progression_role(
        _row(
            alignment="opposed",
            event_return=-0.02,
            lift=-0.01,
        )
    )

    assert classified.role == ROLE_FAILED_COUNTERTREND
    assert classified.transition_improvement is False


def test_aligned_continuation_roles() -> None:
    outperform = classify_progression_role(
        _row(
            alignment="aligned",
            event_return=0.03,
            lift=0.01,
        )
    )
    weaker = classify_progression_role(
        _row(
            alignment="aligned",
            event_return=0.03,
            lift=-0.01,
        )
    )
    failed = classify_progression_role(
        _row(
            alignment="aligned",
            event_return=-0.01,
            lift=-0.02,
        )
    )

    assert outperform.role == ROLE_CONTINUATION_OUTPERFORMS
    assert weaker.role == ROLE_CONTINUATION_WEAKER
    assert failed.role == ROLE_CONTINUATION_FAILED


def test_summary_separates_reversal_and_deceleration() -> None:
    classified = tuple(
        classify_progression_role(row)
        for row in (
            _row(
                alignment="opposed",
                event_return=0.03,
                lift=0.04,
            ),
            _row(
                alignment="opposed",
                event_return=-0.01,
                lift=0.02,
            ),
            _row(
                alignment="opposed",
                event_return=-0.03,
                lift=-0.01,
            ),
        )
    )
    summary = next(
        item
        for item in summarize_progression_roles(classified)
        if item.cohort_dimension == "trend_alignment"
    )

    assert summary.actual_reversal_count == 1
    assert summary.deceleration_only_count == 1
    assert summary.transition_improvement_count == 2
    assert summary.transition_improvement_rate == 2 / 3
    assert summary.failed_countertrend_count == 1


def test_loader_preserves_k19_row_count(tmp_path) -> None:
    summary = {
        "audit_id": EXPECTED_K19_AUDIT_ID,
        "basket_name": "fixture",
        "requested_symbol_count": 1,
        "successful_symbol_count": 1,
        "failed_symbol_count": 0,
        "source_event_count": 1,
        "source_observation_count": 1,
        "comparison_row_count": 1,
        "control_windows": [26],
    }
    (tmp_path / "progression_causal_drift_summary.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                "event_week": "2026-01-05",
                "event_direction": "bullish",
                "trend_alignment": "opposed",
                "source_event_bar_index": 10,
                "resolved_event_bar_index": 20,
                "horizon_weeks": 5,
                "control_window_size": 26,
                "control_count": 26,
                "event_complete": True,
                "event_favorable_return": 0.03,
                "baseline_mean_favorable_return": -0.01,
                "favorable_return_lift": 0.04,
            }
        ]
    ).to_csv(
        tmp_path / "progression_causal_drift_rows.csv",
        index=False,
    )

    artifact = load_frozen_causal_drift_artifacts(
        input_dir=tmp_path,
        expected_basket_name="fixture",
    )
    audit = build_progression_role_audit(artifact)

    assert artifact.comparison_row_count == 1
    assert audit.audit_id == PROGRESSION_ROLE_CLASSIFICATION_AUDIT_ID
    assert audit.classified_row_count == 1
    assert audit.is_actionable is False


def test_build_audit_preserves_source_counts() -> None:
    artifact = FrozenCausalDriftArtifact(
        basket_name="fixture",
        requested_symbol_count=1,
        source_event_count=1,
        source_observation_count=1,
        comparison_row_count=1,
        control_windows=(26,),
        rows=(
            _row(
                alignment="opposed",
                event_return=0.01,
                lift=0.02,
            ),
        ),
    )

    audit = build_progression_role_audit(artifact)

    assert audit.source_event_count == 1
    assert audit.source_observation_count == 1
    assert audit.source_comparison_row_count == 1
    assert audit.classified_row_count == 1
