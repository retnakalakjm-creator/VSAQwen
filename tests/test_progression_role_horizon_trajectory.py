from __future__ import annotations

import pytest

from audit.progression_role_consensus import (
    CONSENSUS_ACTUAL_REVERSAL,
    CONSENSUS_CONTINUATION_FAILED,
    CONSENSUS_CONTINUATION_OUTPERFORMS,
    CONSENSUS_DECELERATION,
    CONSENSUS_FAILED_COUNTERTREND,
)
from audit.progression_role_horizon_trajectory import (
    EXPECTED_HORIZONS,
    FrozenConsensusArtifact,
    FrozenConsensusRow,
    build_progression_role_trajectories,
    build_progression_role_trajectory_audit,
    summarize_progression_role_trajectories,
)


def _row(
    *,
    horizon: int,
    alignment: str,
    role: str,
    usable: bool = True,
    robust: bool = True,
) -> FrozenConsensusRow:
    return FrozenConsensusRow(
        symbol="AAA.NS",
        event_week="2026-01-05",
        event_direction="bullish",
        trend_alignment=alignment,
        horizon_weeks=horizon,
        usable=usable,
        event_favorable_return=(0.01 if usable else None),
        window_count=3,
        majority_threshold=2,
        positive_transition_windows=(
            3 if role == CONSENSUS_DECELERATION else 0
        ),
        positive_continuation_windows=(
            3 if role == CONSENSUS_CONTINUATION_OUTPERFORMS else 0
        ),
        consensus_role=role,
        robust_across_windows=robust,
    )


def _artifact(rows) -> FrozenConsensusArtifact:
    rows = tuple(rows)
    return FrozenConsensusArtifact(
        basket_name="fixture",
        requested_symbol_count=1,
        source_event_count=1,
        source_observation_count=len(rows),
        source_comparison_row_count=len(rows) * 3,
        source_classified_row_count=len(rows) * 3,
        consensus_row_count=len(rows),
        control_windows=(26, 52, 104),
        majority_threshold=2,
        rows=rows,
    )


def test_trajectory_preserves_exact_horizon_role_signature() -> None:
    roles = (
        CONSENSUS_FAILED_COUNTERTREND,
        CONSENSUS_DECELERATION,
        CONSENSUS_ACTUAL_REVERSAL,
        CONSENSUS_ACTUAL_REVERSAL,
        CONSENSUS_ACTUAL_REVERSAL,
    )
    artifact = _artifact(
        _row(
            horizon=horizon,
            alignment="opposed",
            role=role,
        )
        for horizon, role in zip(EXPECTED_HORIZONS, roles)
    )

    trajectory = build_progression_role_trajectories(artifact)[0]

    assert trajectory.horizon_count == 5
    assert trajectory.usable_horizon_count == 5
    assert trajectory.actual_reversal_horizon_count == 3
    assert trajectory.actual_reversal_horizons == "5,10,15"
    assert trajectory.consensus_deceleration_horizon_count == 1
    assert trajectory.failed_countertrend_horizon_count == 1
    assert trajectory.majority_actual_reversal is True
    assert trajectory.majority_transition_support is True
    assert trajectory.all_usable_horizons_robust is True
    assert trajectory.role_signature.startswith(
        "1:FAILED_COUNTERTREND_WARNING|3:CONSENSUS_DECELERATION"
    )


def test_aligned_trajectory_counts_continuation_roles() -> None:
    roles = (
        CONSENSUS_CONTINUATION_OUTPERFORMS,
        CONSENSUS_CONTINUATION_OUTPERFORMS,
        CONSENSUS_CONTINUATION_OUTPERFORMS,
        CONSENSUS_CONTINUATION_FAILED,
        CONSENSUS_CONTINUATION_FAILED,
    )
    artifact = _artifact(
        _row(
            horizon=horizon,
            alignment="aligned",
            role=role,
        )
        for horizon, role in zip(EXPECTED_HORIZONS, roles)
    )

    trajectory = build_progression_role_trajectories(artifact)[0]

    assert trajectory.continuation_outperform_horizon_count == 3
    assert trajectory.continuation_failed_horizon_count == 2
    assert trajectory.majority_continuation_outperform is True
    assert trajectory.majority_continuation_failure is False


def test_missing_horizon_fails_closed() -> None:
    artifact = _artifact(
        _row(
            horizon=horizon,
            alignment="opposed",
            role=CONSENSUS_ACTUAL_REVERSAL,
        )
        for horizon in (1, 3, 5, 10)
    )
    artifact = FrozenConsensusArtifact(
        basket_name=artifact.basket_name,
        requested_symbol_count=artifact.requested_symbol_count,
        source_event_count=artifact.source_event_count,
        source_observation_count=artifact.source_observation_count,
        source_comparison_row_count=artifact.source_comparison_row_count,
        source_classified_row_count=artifact.source_classified_row_count,
        consensus_row_count=artifact.consensus_row_count,
        control_windows=artifact.control_windows,
        majority_threshold=artifact.majority_threshold,
        rows=artifact.rows,
    )

    with pytest.raises(ValueError, match="horizon identity mismatch"):
        build_progression_role_trajectories(artifact)


def test_sparse_recent_event_cannot_form_horizon_majority() -> None:
    artifact = _artifact(
        _row(
            horizon=horizon,
            alignment="opposed",
            role=(
                CONSENSUS_ACTUAL_REVERSAL
                if horizon == 1
                else "INCOMPLETE"
            ),
            usable=(horizon == 1),
        )
        for horizon in EXPECTED_HORIZONS
    )

    trajectory = build_progression_role_trajectories(artifact)[0]

    assert trajectory.usable_horizon_count == 1
    assert trajectory.actual_reversal_horizon_count == 1
    assert trajectory.majority_actual_reversal is False
    assert trajectory.majority_transition_support is False


def test_summary_reports_event_level_majority_not_horizon_rows() -> None:
    rows = (
        build_progression_role_trajectories(
            _artifact(
                _row(
                    horizon=horizon,
                    alignment="opposed",
                    role=(
                        CONSENSUS_ACTUAL_REVERSAL
                        if horizon in (5, 10, 15)
                        else CONSENSUS_FAILED_COUNTERTREND
                    ),
                )
                for horizon in EXPECTED_HORIZONS
            )
        )[0],
    )

    summary = next(
        item
        for item in summarize_progression_role_trajectories(rows)
        if item.cohort_dimension == "direction_trend_alignment"
    )

    assert summary.event_count == 1
    assert summary.any_actual_reversal_event_count == 1
    assert summary.majority_actual_reversal_event_count == 1
    assert summary.majority_transition_support_event_count == 1


def test_audit_collapses_five_horizons_to_one_event() -> None:
    artifact = _artifact(
        _row(
            horizon=horizon,
            alignment="opposed",
            role=CONSENSUS_ACTUAL_REVERSAL,
        )
        for horizon in EXPECTED_HORIZONS
    )

    audit = build_progression_role_trajectory_audit(artifact)

    assert audit.source_event_count == 1
    assert audit.source_observation_count == 5
    assert audit.source_consensus_row_count == 5
    assert audit.trajectory_row_count == 1
    assert audit.is_actionable is False
