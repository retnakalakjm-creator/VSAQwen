from __future__ import annotations

from audit.progression_directionality_semantics import (
    ProgressionDirectionalityRow,
)
from audit.progression_shadow_semantic_projection import (
    PROGRESSION_SHADOW_SEMANTIC_AUDIT_ID,
    ROLE_ALIGNED_OBSERVATION,
    ROLE_NEUTRAL_OBSERVATION,
    ROLE_TRANSITION_WARNING,
    ROLE_UNKNOWN_CONTEXT,
    build_progression_shadow_semantic_audit,
    project_progression_shadow_semantic,
)


def _row(
    *,
    bar: int,
    direction: str,
    trend_alignment: str,
) -> ProgressionDirectionalityRow:
    return ProgressionDirectionalityRow(
        symbol="AAA.NS",
        event_bar_index=bar,
        event_week=f"W{bar}",
        event_code=(
            "structural_progression_improving"
            if direction == "bullish"
            else "structural_progression_weakening"
        ),
        event_direction=direction,
        progression_difference=0.1 if direction == "bullish" else -0.1,
        trend_direction="down" if trend_alignment == "opposed" else "up",
        trend_state="healthy",
        structural_pattern="stable",
        trend_alignment=trend_alignment,
        structural_pattern_alignment="ambiguous",
        qualification_after_event="UNQUALIFIED",
    )


def test_opposed_progression_projects_transition_warning_only() -> None:
    projected = project_progression_shadow_semantic(
        _row(
            bar=10,
            direction="bullish",
            trend_alignment="opposed",
        )
    )

    assert projected.semantic_role == ROLE_TRANSITION_WARNING
    assert projected.projected_transition_direction == "bullish"
    assert projected.reversal_confirmed is False
    assert projected.persistent_direction_claim is False
    assert projected.affects_qualification is False
    assert projected.affects_scoring is False
    assert projected.is_actionable is False


def test_aligned_progression_does_not_claim_continuation() -> None:
    projected = project_progression_shadow_semantic(
        _row(
            bar=10,
            direction="bullish",
            trend_alignment="aligned",
        )
    )

    assert projected.semantic_role == ROLE_ALIGNED_OBSERVATION
    assert projected.projected_transition_direction is None
    assert projected.reversal_confirmed is False


def test_neutral_and_unknown_context_remain_descriptive() -> None:
    neutral = project_progression_shadow_semantic(
        _row(
            bar=10,
            direction="bearish",
            trend_alignment="neutral",
        )
    )
    unknown = project_progression_shadow_semantic(
        _row(
            bar=20,
            direction="bearish",
            trend_alignment="unknown",
        )
    )

    assert neutral.semantic_role == ROLE_NEUTRAL_OBSERVATION
    assert unknown.semantic_role == ROLE_UNKNOWN_CONTEXT
    assert neutral.projected_transition_direction is None
    assert unknown.projected_transition_direction is None


def test_audit_preserves_one_projection_per_input_event() -> None:
    rows = (
        _row(
            bar=10,
            direction="bullish",
            trend_alignment="opposed",
        ),
        _row(
            bar=20,
            direction="bearish",
            trend_alignment="aligned",
        ),
        _row(
            bar=30,
            direction="bearish",
            trend_alignment="neutral",
        ),
    )

    audit = build_progression_shadow_semantic_audit(
        basket_name="fixture",
        requested_symbols=("AAA.NS",),
        rows_by_symbol={"AAA.NS": rows},
        expected_event_counts={"AAA.NS": 3},
    )

    assert audit.audit_id == PROGRESSION_SHADOW_SEMANTIC_AUDIT_ID
    assert audit.event_count == 3
    assert len(audit.rows) == 3
    assert audit.semantic_role_counts[ROLE_TRANSITION_WARNING] == 1
    assert audit.semantic_role_counts[ROLE_ALIGNED_OBSERVATION] == 1
    assert audit.semantic_role_counts[ROLE_NEUTRAL_OBSERVATION] == 1
    assert audit.transition_warning_direction_counts["bullish"] == 1
    assert audit.is_actionable is False


def test_unsupported_alignment_fails_closed() -> None:
    import pytest

    with pytest.raises(ValueError, match="unsupported"):
        project_progression_shadow_semantic(
            _row(
                bar=10,
                direction="bullish",
                trend_alignment="surprising",
            )
        )
