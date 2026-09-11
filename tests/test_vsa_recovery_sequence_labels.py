from __future__ import annotations

from background.qualification import PatternQualification
from models import EvidenceCode
from vsa_recovery_sequence_labels import (
    RecoverySequenceReviewLabel,
    label_stopping_volume_spring_shakeout_review,
)


def test_recovery_sequence_marks_valid_review_only_candidate() -> None:
    result = label_stopping_volume_spring_shakeout_review(
        qualification=PatternQualification.PERSISTENT_BEARISH,
        prior_evidence=[EvidenceCode.INCREASING_SUPPLY],
        stopping_volume_evidence=[EvidenceCode.STOPPING_VOLUME],
        spring_shakeout_evidence=[EvidenceCode.SPRING],
        follow_through_evidence=[EvidenceCode.DEMAND_COMING_IN],
        follow_through_evidence_age=0,
    )

    assert result.status is RecoverySequenceReviewLabel.REVIEW
    assert result.review_marker == "stopping_volume_spring_shakeout_review"
    assert result.qualification == "persistent_bearish"
    assert result.prior_weakness_codes == ("persistent_bearish", "increasing_supply")
    assert result.stopping_volume_codes == ("stopping_volume",)
    assert result.spring_shakeout_codes == ("spring",)
    assert result.follow_through_codes == ("demand_coming_in",)
    assert result.blocker_codes == ()
    assert result.production_safe is True
    assert "review-only" in result.reason
    assert "without flipping bullish" in result.reason


def test_recovery_sequence_does_not_mark_stopping_volume_alone() -> None:
    result = label_stopping_volume_spring_shakeout_review(
        qualification=PatternQualification.PERSISTENT_BEARISH,
        prior_evidence=[EvidenceCode.INCREASING_SUPPLY],
        stopping_volume_evidence=[EvidenceCode.STOPPING_VOLUME],
        follow_through_evidence=[EvidenceCode.DEMAND_COMING_IN],
        follow_through_evidence_age=0,
    )

    assert result.status is RecoverySequenceReviewLabel.NONE
    assert result.review_marker is None
    assert result.stopping_volume_codes == ("stopping_volume",)
    assert result.spring_shakeout_codes == ()
    assert "no later Spring or Shakeout" in result.reason


def test_recovery_sequence_does_not_mark_spring_without_prior_weakness() -> None:
    result = label_stopping_volume_spring_shakeout_review(
        stopping_volume_evidence=[EvidenceCode.STOPPING_VOLUME],
        spring_shakeout_evidence=[EvidenceCode.SHAKEOUT],
        follow_through_evidence=[EvidenceCode.INCREASING_DEMAND],
        follow_through_evidence_age=0,
    )

    assert result.status is RecoverySequenceReviewLabel.NONE
    assert result.review_marker is None
    assert result.prior_weakness_codes == ()
    assert result.spring_shakeout_codes == ("shakeout",)
    assert "No prior weakness context" in result.reason


def test_recovery_sequence_does_not_mark_demand_follow_through_without_anchor() -> None:
    result = label_stopping_volume_spring_shakeout_review(
        qualification="persistent_bearish",
        prior_evidence=[EvidenceCode.SUPPLY_COMING_IN],
        spring_shakeout_evidence=[EvidenceCode.SPRING],
        follow_through_evidence=[EvidenceCode.DEMAND_COMING_IN],
        follow_through_evidence_age=0,
    )

    assert result.status is RecoverySequenceReviewLabel.NONE
    assert result.review_marker is None
    assert result.prior_weakness_codes == ("persistent_bearish", "supply_coming_in")
    assert result.stopping_volume_codes == ()
    assert "no stopping-volume" in result.reason


def test_recovery_sequence_waits_when_follow_through_is_missing() -> None:
    result = label_stopping_volume_spring_shakeout_review(
        qualification="persistent_bearish",
        prior_evidence=[EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING],
        stopping_volume_evidence=[EvidenceCode.STOPPING_VOLUME],
        spring_shakeout_evidence=[EvidenceCode.SHAKEOUT],
        follow_through_evidence=[],
        follow_through_evidence_age=0,
    )

    assert result.status is RecoverySequenceReviewLabel.NEEDS_FOLLOW_THROUGH
    assert result.review_marker is None
    assert result.follow_through_codes == ()
    assert "fresh same-window demand follow-through is missing" in result.reason


def test_recovery_sequence_waits_when_follow_through_is_stale() -> None:
    result = label_stopping_volume_spring_shakeout_review(
        qualification="persistent_bearish",
        prior_evidence=[EvidenceCode.INCREASING_SUPPLY],
        stopping_volume_evidence=[EvidenceCode.STOPPING_VOLUME],
        spring_shakeout_evidence=[EvidenceCode.SPRING],
        follow_through_evidence=[EvidenceCode.INCREASING_DEMAND],
        follow_through_evidence_age=4,
    )

    assert result.status is RecoverySequenceReviewLabel.NEEDS_FOLLOW_THROUGH
    assert result.review_marker is None
    assert result.follow_through_codes == ("increasing_demand",)
    assert "stale" in result.reason


def test_recovery_sequence_waits_when_follow_through_is_fallback_only() -> None:
    result = label_stopping_volume_spring_shakeout_review(
        qualification="persistent_bearish",
        prior_evidence=[EvidenceCode.INCREASING_SUPPLY],
        stopping_volume_evidence=[EvidenceCode.STOPPING_VOLUME],
        spring_shakeout_evidence=[EvidenceCode.SHAKEOUT],
        follow_through_evidence=[EvidenceCode.DEMAND_COMING_IN],
        follow_through_evidence_age=0,
        used_fallback_evidence=True,
    )

    assert result.status is RecoverySequenceReviewLabel.NEEDS_FOLLOW_THROUGH
    assert result.review_marker is None
    assert result.used_fallback_evidence is True
    assert "fallback-only" in result.reason


def test_recovery_sequence_blocks_when_same_window_supply_remains_active() -> None:
    result = label_stopping_volume_spring_shakeout_review(
        qualification="persistent_bearish",
        prior_evidence=[EvidenceCode.INCREASING_SUPPLY],
        stopping_volume_evidence=[EvidenceCode.STOPPING_VOLUME],
        spring_shakeout_evidence=[EvidenceCode.SPRING],
        follow_through_evidence=[EvidenceCode.DEMAND_COMING_IN],
        same_window_evidence=[
            EvidenceCode.DEMAND_COMING_IN,
            EvidenceCode.INCREASING_SUPPLY,
            EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        ],
        follow_through_evidence_age=0,
    )

    assert result.status is RecoverySequenceReviewLabel.BLOCKED
    assert result.review_marker is None
    assert result.blocker_codes == (
        "increasing_supply",
        "structural_progression_weakening",
    )
    assert "blocks a clean review marker" in result.reason


def test_recovery_sequence_preserves_persistent_bearish_lifecycle_conservatism() -> None:
    result = label_stopping_volume_spring_shakeout_review(
        qualification=PatternQualification.PERSISTENT_BEARISH,
        prior_evidence=[],
        stopping_volume_evidence=[EvidenceCode.STOPPING_VOLUME],
        spring_shakeout_evidence=[EvidenceCode.SHAKEOUT],
        follow_through_evidence=[EvidenceCode.INCREASING_DEMAND],
        follow_through_evidence_age=0,
    )

    assert result.status is RecoverySequenceReviewLabel.REVIEW
    assert result.prior_weakness_codes == ("persistent_bearish",)
    assert result.review_marker == "stopping_volume_spring_shakeout_review"
    assert result.production_safe is True
    assert "without flipping bullish" in result.reason


def test_recovery_sequence_ignores_audit_only_candidate_codes() -> None:
    result = label_stopping_volume_spring_shakeout_review(
        qualification="persistent_bearish",
        prior_evidence=["audit_absorption_candidate"],
        stopping_volume_evidence=["audit_high_volume_reversal_candidate"],
        spring_shakeout_evidence=[EvidenceCode.SPRING],
        follow_through_evidence=[EvidenceCode.DEMAND_COMING_IN],
        follow_through_evidence_age=0,
    )

    assert result.status is RecoverySequenceReviewLabel.NONE
    assert result.review_marker is None
    assert result.ignored_audit_only_codes == (
        "audit_absorption_candidate",
        "audit_high_volume_reversal_candidate",
    )
    assert result.stopping_volume_codes == ()
    assert result.to_dict()["ignored_audit_only_codes"] == [
        "audit_absorption_candidate",
        "audit_high_volume_reversal_candidate",
    ]
    assert result.to_dict()["production_safe"] is True
