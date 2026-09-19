from __future__ import annotations

from audit.progression_role_consensus import (
    CONSENSUS_ACTUAL_REVERSAL,
    CONSENSUS_CONTINUATION_OUTPERFORMS,
    CONSENSUS_CONTINUATION_UNSTABLE,
    CONSENSUS_DECELERATION,
    CONSENSUS_DECELERATION_UNSTABLE,
    CONSENSUS_FAILED_COUNTERTREND,
    FrozenProgressionRoleArtifact,
    FrozenProgressionRoleRow,
    build_progression_role_consensus_audit,
    build_progression_role_consensus_rows,
)


def _row(
    *,
    window: int,
    alignment: str,
    role: str,
    event_return: float,
    transition: bool = False,
    continuation_positive: bool = False,
    continuation_outperforms: bool = False,
    actual_reversal: bool = False,
) -> FrozenProgressionRoleRow:
    return FrozenProgressionRoleRow(
        symbol="AAA.NS",
        event_week="2026-01-05",
        event_direction="bullish",
        trend_alignment=alignment,
        horizon_weeks=5,
        control_window_size=window,
        control_count=window,
        event_favorable_return=event_return,
        baseline_mean_favorable_return=0.0,
        favorable_return_lift=0.01 if transition else -0.01,
        role=role,
        usable=True,
        actual_reversal=actual_reversal,
        transition_improvement=transition,
        continuation_positive=continuation_positive,
        continuation_outperforms=continuation_outperforms,
    )


def _artifact(rows) -> FrozenProgressionRoleArtifact:
    rows = tuple(rows)
    return FrozenProgressionRoleArtifact(
        basket_name="fixture",
        requested_symbol_count=1,
        source_event_count=1,
        source_observation_count=1,
        source_comparison_row_count=len(rows),
        classified_row_count=len(rows),
        control_windows=(26, 52, 104),
        rows=rows,
    )


def test_actual_reversal_is_window_independent_consensus() -> None:
    rows = build_progression_role_consensus_rows(
        _artifact(
            _row(
                window=window,
                alignment="opposed",
                role="ACTUAL_REVERSAL",
                event_return=0.03,
                transition=True,
                actual_reversal=True,
            )
            for window in (26, 52, 104)
        )
    )

    assert rows[0].consensus_role == CONSENSUS_ACTUAL_REVERSAL
    assert rows[0].robust_across_windows is True


def test_two_of_three_transition_windows_form_consensus() -> None:
    source = (
        _row(
            window=26,
            alignment="opposed",
            role="DECELERATION_WITHOUT_REVERSAL",
            event_return=-0.01,
            transition=True,
        ),
        _row(
            window=52,
            alignment="opposed",
            role="DECELERATION_WITHOUT_REVERSAL",
            event_return=-0.01,
            transition=True,
        ),
        _row(
            window=104,
            alignment="opposed",
            role="FAILED_COUNTERTREND_WARNING",
            event_return=-0.01,
            transition=False,
        ),
    )

    row = build_progression_role_consensus_rows(_artifact(source))[0]

    assert row.consensus_role == CONSENSUS_DECELERATION
    assert row.positive_transition_windows == 2
    assert row.robust_across_windows is False


def test_one_of_three_transition_windows_is_unstable() -> None:
    source = (
        _row(
            window=26,
            alignment="opposed",
            role="DECELERATION_WITHOUT_REVERSAL",
            event_return=-0.01,
            transition=True,
        ),
        _row(
            window=52,
            alignment="opposed",
            role="FAILED_COUNTERTREND_WARNING",
            event_return=-0.01,
        ),
        _row(
            window=104,
            alignment="opposed",
            role="FAILED_COUNTERTREND_WARNING",
            event_return=-0.01,
        ),
    )

    row = build_progression_role_consensus_rows(_artifact(source))[0]

    assert row.consensus_role == CONSENSUS_DECELERATION_UNSTABLE


def test_zero_transition_windows_is_failed_warning() -> None:
    source = tuple(
        _row(
            window=window,
            alignment="opposed",
            role="FAILED_COUNTERTREND_WARNING",
            event_return=-0.01,
        )
        for window in (26, 52, 104)
    )

    row = build_progression_role_consensus_rows(_artifact(source))[0]

    assert row.consensus_role == CONSENSUS_FAILED_COUNTERTREND
    assert row.robust_across_windows is True


def test_continuation_majority_and_window_sensitive_roles() -> None:
    majority = (
        _row(
            window=26,
            alignment="aligned",
            role="CONTINUATION_OUTPERFORMS_BASELINE",
            event_return=0.03,
            continuation_positive=True,
            continuation_outperforms=True,
        ),
        _row(
            window=52,
            alignment="aligned",
            role="CONTINUATION_OUTPERFORMS_BASELINE",
            event_return=0.03,
            continuation_positive=True,
            continuation_outperforms=True,
        ),
        _row(
            window=104,
            alignment="aligned",
            role="CONTINUATION_WEAKER_THAN_BASELINE",
            event_return=0.03,
            continuation_positive=True,
        ),
    )
    unstable = (
        majority[0],
        _row(
            window=52,
            alignment="aligned",
            role="CONTINUATION_WEAKER_THAN_BASELINE",
            event_return=0.03,
            continuation_positive=True,
        ),
        majority[2],
    )

    first = build_progression_role_consensus_rows(
        _artifact(majority)
    )[0]
    second = build_progression_role_consensus_rows(
        _artifact(unstable)
    )[0]

    assert first.consensus_role == CONSENSUS_CONTINUATION_OUTPERFORMS
    assert second.consensus_role == CONSENSUS_CONTINUATION_UNSTABLE


def test_missing_control_window_fails_closed() -> None:
    artifact = FrozenProgressionRoleArtifact(
        basket_name="fixture",
        requested_symbol_count=1,
        source_event_count=1,
        source_observation_count=1,
        source_comparison_row_count=2,
        classified_row_count=2,
        control_windows=(26, 52, 104),
        rows=(
            _row(
                window=26,
                alignment="opposed",
                role="FAILED_COUNTERTREND_WARNING",
                event_return=-0.01,
            ),
            _row(
                window=52,
                alignment="opposed",
                role="FAILED_COUNTERTREND_WARNING",
                event_return=-0.01,
            ),
        ),
    )

    import pytest

    with pytest.raises(ValueError, match="missing control windows"):
        build_progression_role_consensus_audit(artifact)
