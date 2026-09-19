from __future__ import annotations

import pytest

from audit.progression_transition_onset import (
    ONSET_EARLY,
    ONSET_IMMEDIATE,
    ONSET_NO_REVERSAL_NO_SUPPORT,
    ONSET_NO_REVERSAL_TRANSITION,
    FrozenTrajectoryArtifact,
    FrozenTrajectoryRow,
    build_progression_transition_onset_audit,
    classify_transition_onset,
)


def _row(
    *,
    signature: str,
    reversal_count: int,
    transition_count: int,
    majority_reversal: bool,
    majority_transition: bool,
    direction: str = "bullish",
) -> FrozenTrajectoryRow:
    reversal_horizons = [
        token.split(":", 1)[0]
        for token in signature.split("|")
        if token.endswith(":ACTUAL_REVERSAL")
    ]
    return FrozenTrajectoryRow(
        symbol="AAA.NS",
        event_week="2026-01-05",
        event_direction=direction,
        trend_alignment="opposed",
        horizon_count=5,
        usable_horizon_count=5,
        robust_horizon_count=5,
        robust_horizon_rate=1.0,
        role_signature=signature,
        actual_reversal_horizon_count=reversal_count,
        actual_reversal_horizons=",".join(reversal_horizons),
        transition_support_horizon_count=transition_count,
        majority_actual_reversal=majority_reversal,
        majority_transition_support=majority_transition,
    )


def _signature(*roles: str) -> str:
    return "|".join(
        f"{horizon}:{role}"
        for horizon, role in zip((1, 3, 5, 10, 15), roles)
    )


def test_immediate_reversal_persistence() -> None:
    signature = _signature(
        "ACTUAL_REVERSAL",
        "ACTUAL_REVERSAL",
        "ACTUAL_REVERSAL",
        "ACTUAL_REVERSAL",
        "ACTUAL_REVERSAL",
    )
    classified = classify_transition_onset(
        _row(
            signature=signature,
            reversal_count=5,
            transition_count=5,
            majority_reversal=True,
            majority_transition=True,
        )
    )

    assert classified.onset_class == ONSET_IMMEDIATE
    assert classified.first_reversal_horizon == 1
    assert classified.reversal_persistent_after_onset is True
    assert classified.transition_persistent_after_onset is True
    assert classified.reversal_reverted_after_onset is False


def test_early_reversal_can_revert_later() -> None:
    signature = _signature(
        "FAILED_COUNTERTREND_WARNING",
        "ACTUAL_REVERSAL",
        "ACTUAL_REVERSAL",
        "FAILED_COUNTERTREND_WARNING",
        "ACTUAL_REVERSAL",
    )
    classified = classify_transition_onset(
        _row(
            signature=signature,
            reversal_count=3,
            transition_count=3,
            majority_reversal=True,
            majority_transition=True,
        )
    )

    assert classified.onset_class == ONSET_EARLY
    assert classified.first_reversal_horizon == 3
    assert classified.reversal_persistent_after_onset is False
    assert classified.reversal_reverted_after_onset is True


def test_no_reversal_with_consensus_transition_support() -> None:
    signature = _signature(
        "CONSENSUS_DECELERATION",
        "CONSENSUS_DECELERATION",
        "CONSENSUS_DECELERATION",
        "FAILED_COUNTERTREND_WARNING",
        "FAILED_COUNTERTREND_WARNING",
    )
    classified = classify_transition_onset(
        _row(
            signature=signature,
            reversal_count=0,
            transition_count=3,
            majority_reversal=False,
            majority_transition=True,
        )
    )

    assert classified.onset_class == ONSET_NO_REVERSAL_TRANSITION
    assert classified.first_reversal_horizon is None
    assert classified.first_transition_support_horizon == 1


def test_no_reversal_and_no_transition_support() -> None:
    signature = _signature(
        "FAILED_COUNTERTREND_WARNING",
        "FAILED_COUNTERTREND_WARNING",
        "FAILED_COUNTERTREND_WARNING",
        "FAILED_COUNTERTREND_WARNING",
        "FAILED_COUNTERTREND_WARNING",
    )
    classified = classify_transition_onset(
        _row(
            signature=signature,
            reversal_count=0,
            transition_count=0,
            majority_reversal=False,
            majority_transition=False,
        )
    )

    assert classified.onset_class == ONSET_NO_REVERSAL_NO_SUPPORT


def test_signature_count_mismatch_fails_closed() -> None:
    signature = _signature(
        "ACTUAL_REVERSAL",
        "ACTUAL_REVERSAL",
        "FAILED_COUNTERTREND_WARNING",
        "FAILED_COUNTERTREND_WARNING",
        "FAILED_COUNTERTREND_WARNING",
    )
    with pytest.raises(ValueError, match="reversal count"):
        classify_transition_onset(
            _row(
                signature=signature,
                reversal_count=1,
                transition_count=2,
                majority_reversal=False,
                majority_transition=False,
            )
        )


def test_audit_filters_to_opposed_context() -> None:
    opposed = _row(
        signature=_signature(
            "ACTUAL_REVERSAL",
            "ACTUAL_REVERSAL",
            "ACTUAL_REVERSAL",
            "ACTUAL_REVERSAL",
            "ACTUAL_REVERSAL",
        ),
        reversal_count=5,
        transition_count=5,
        majority_reversal=True,
        majority_transition=True,
    )
    aligned = FrozenTrajectoryRow(
        symbol="BBB.NS",
        event_week="2026-01-05",
        event_direction="bullish",
        trend_alignment="aligned",
        horizon_count=5,
        usable_horizon_count=5,
        robust_horizon_count=5,
        robust_horizon_rate=1.0,
        role_signature=_signature(
            "CONTINUATION_FAILED",
            "CONTINUATION_FAILED",
            "CONTINUATION_FAILED",
            "CONTINUATION_FAILED",
            "CONTINUATION_FAILED",
        ),
        actual_reversal_horizon_count=0,
        actual_reversal_horizons="",
        transition_support_horizon_count=0,
        majority_actual_reversal=False,
        majority_transition_support=False,
    )
    artifact = FrozenTrajectoryArtifact(
        basket_name="fixture",
        requested_symbol_count=2,
        source_event_count=2,
        source_observation_count=10,
        source_consensus_row_count=10,
        trajectory_row_count=2,
        expected_horizons=(1, 3, 5, 10, 15),
        rows=(opposed, aligned),
    )

    audit = build_progression_transition_onset_audit(artifact)

    assert audit.source_event_count == 2
    assert audit.opposed_event_count == 1
    assert len(audit.rows) == 1
    assert audit.is_actionable is False
