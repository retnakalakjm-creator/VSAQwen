from __future__ import annotations

from background.qualification import PatternQualification
from models import EvidenceCode
from vsa_absorption_background_labels import (
    ABSORPTION_BACKGROUND_PLAIN_ENGLISH,
    AbsorptionBackgroundReviewLabel,
    label_absorption_background_review,
)


def test_absorption_background_marks_valid_review_only_candidate() -> None:
    result = label_absorption_background_review(
        qualification=PatternQualification.PERSISTENT_BEARISH,
        prior_evidence=[EvidenceCode.INCREASING_SUPPLY],
        absorption_evidence=[EvidenceCode.SUPPLY_ABSORPTION],
        follow_through_evidence=[EvidenceCode.DEMAND_COMING_IN],
        follow_through_evidence_age=0,
    )

    assert result.status is AbsorptionBackgroundReviewLabel.REVIEW
    assert result.review_marker == "absorption_background_review"
    assert result.frontend_label == "Absorption Background Review"
    assert result.plain_english == ABSORPTION_BACKGROUND_PLAIN_ENGLISH
    assert "Selling pressure may be getting absorbed" in result.plain_english
    assert result.qualification == "persistent_bearish"
    assert result.prior_supply_codes == ("persistent_bearish", "increasing_supply")
    assert result.absorption_codes == ("supply_absorption",)
    assert result.follow_through_codes == ("demand_coming_in",)
    assert result.blocker_codes == ()
    assert result.production_safe is True
    assert "review-only absorption background" in result.reason
    assert "without flipping bullish" in result.reason


def test_absorption_background_preserves_persistent_bearish_context() -> None:
    result = label_absorption_background_review(
        qualification=PatternQualification.PERSISTENT_BEARISH,
        prior_evidence=[],
        absorption_evidence=[EvidenceCode.STOPPING_VOLUME],
        follow_through_evidence=[EvidenceCode.INCREASING_DEMAND],
        follow_through_evidence_age=0,
    )

    assert result.status is AbsorptionBackgroundReviewLabel.REVIEW
    assert result.prior_supply_codes == ("persistent_bearish",)
    assert result.absorption_codes == ("stopping_volume",)
    assert result.review_marker == "absorption_background_review"


def test_absorption_background_does_not_mark_without_prior_supply_context() -> None:
    result = label_absorption_background_review(
        absorption_evidence=[EvidenceCode.SUPPLY_ABSORPTION],
        follow_through_evidence=[EvidenceCode.DEMAND_COMING_IN],
        follow_through_evidence_age=0,
    )

    assert result.status is AbsorptionBackgroundReviewLabel.NONE
    assert result.review_marker is None
    assert result.frontend_label is None
    assert result.prior_supply_codes == ()
    assert result.absorption_codes == ("supply_absorption",)
    assert "No prior supply pressure" in result.reason


def test_absorption_background_keeps_diagnostic_hints_separate_from_production_evidence() -> None:
    result = label_absorption_background_review(
        qualification="persistent_bearish",
        prior_evidence=[EvidenceCode.SUPPLY_COMING_IN],
        absorption_evidence=[],
        diagnostic_evidence=[
            "review_potential_absorption",
            "audit_absorption_candidate",
            "absorption",
        ],
        follow_through_evidence=[EvidenceCode.DEMAND_COMING_IN],
        follow_through_evidence_age=0,
    )

    assert result.status is AbsorptionBackgroundReviewLabel.NONE
    assert result.review_marker is None
    assert result.absorption_codes == ()
    assert result.follow_through_codes == ("demand_coming_in",)
    assert result.diagnostic_hint_codes == (
        "review_potential_absorption",
        "audit_absorption_candidate",
        "absorption",
    )
    assert result.ignored_audit_only_codes == (
        "audit_absorption_candidate",
        "absorption",
    )
    assert "Diagnostic hints remain review context only" in result.reason


def test_absorption_background_waits_when_follow_through_is_missing() -> None:
    result = label_absorption_background_review(
        qualification="persistent_bearish",
        prior_evidence=[EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING],
        absorption_evidence=[EvidenceCode.SUPPLY_ABSORPTION],
        follow_through_evidence=[],
        follow_through_evidence_age=0,
    )

    assert result.status is AbsorptionBackgroundReviewLabel.NEEDS_FOLLOW_THROUGH
    assert result.review_marker is None
    assert result.follow_through_codes == ()
    assert "fresh demand or reversal follow-through is missing" in result.reason


def test_absorption_background_waits_when_follow_through_is_stale() -> None:
    result = label_absorption_background_review(
        qualification="persistent_bearish",
        prior_evidence=[EvidenceCode.INCREASING_SUPPLY],
        absorption_evidence=[EvidenceCode.STOPPING_VOLUME],
        follow_through_evidence=[EvidenceCode.INCREASING_DEMAND],
        follow_through_evidence_age=4,
    )

    assert result.status is AbsorptionBackgroundReviewLabel.NEEDS_FOLLOW_THROUGH
    assert result.review_marker is None
    assert result.follow_through_codes == ("increasing_demand",)
    assert "stale" in result.reason


def test_absorption_background_waits_when_follow_through_is_fallback_only() -> None:
    result = label_absorption_background_review(
        qualification="persistent_bearish",
        prior_evidence=[EvidenceCode.INCREASING_SUPPLY],
        absorption_evidence=[EvidenceCode.SUPPLY_ABSORPTION],
        follow_through_evidence=[EvidenceCode.DEMAND_COMING_IN],
        follow_through_evidence_age=0,
        used_fallback_evidence=True,
    )

    assert result.status is AbsorptionBackgroundReviewLabel.NEEDS_FOLLOW_THROUGH
    assert result.review_marker is None
    assert result.used_fallback_evidence is True
    assert "fallback-only" in result.reason


def test_absorption_background_blocks_when_same_window_supply_remains_active() -> None:
    result = label_absorption_background_review(
        qualification="persistent_bearish",
        prior_evidence=[EvidenceCode.INCREASING_SUPPLY],
        absorption_evidence=[EvidenceCode.SUPPLY_ABSORPTION],
        follow_through_evidence=[EvidenceCode.DEMAND_COMING_IN],
        same_window_evidence=[
            EvidenceCode.DEMAND_COMING_IN,
            EvidenceCode.INCREASING_SUPPLY,
            EvidenceCode.HIDDEN_SUPPLY,
        ],
        follow_through_evidence_age=0,
    )

    assert result.status is AbsorptionBackgroundReviewLabel.BLOCKED
    assert result.review_marker is None
    assert result.blocker_codes == ("increasing_supply", "hidden_supply")
    assert "blocks a clean background review marker" in result.reason


def test_absorption_background_accepts_saved_row_dict_evidence_and_high_volume_reversal_string() -> None:
    result = label_absorption_background_review(
        qualification="persistent_bearish",
        prior_evidence=[{"code": "supply_coming_in"}],
        absorption_evidence=[{"code": "stopping_volume"}],
        follow_through_evidence=[{"code": "high_volume_reversal"}],
        follow_through_evidence_age=0,
    )

    assert result.status is AbsorptionBackgroundReviewLabel.REVIEW
    assert result.prior_supply_codes == ("persistent_bearish", "supply_coming_in")
    assert result.absorption_codes == ("stopping_volume",)
    assert result.follow_through_codes == ("high_volume_reversal",)


def test_absorption_background_serializes_plain_english_for_frontend_consumers() -> None:
    result = label_absorption_background_review(
        qualification="persistent_bearish",
        prior_evidence=[EvidenceCode.INCREASING_SUPPLY],
        absorption_evidence=[EvidenceCode.STOPPING_VOLUME],
        follow_through_evidence=[EvidenceCode.DEMAND_COMING_IN],
        follow_through_evidence_age=0,
    )

    payload = result.to_dict()

    assert payload["status"] == "absorption_background_review"
    assert payload["review_marker"] == "absorption_background_review"
    assert payload["frontend_label"] == "Absorption Background Review"
    assert payload["plain_english"] == ABSORPTION_BACKGROUND_PLAIN_ENGLISH
    assert payload["production_safe"] is True
