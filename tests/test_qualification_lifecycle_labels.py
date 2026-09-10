from __future__ import annotations

from types import SimpleNamespace

from background.qualification import PatternQualification
from models import EvidenceCode
from qualification_lifecycle_labels import (
    AUDIT_ONLY_CANDIDATE_CODES,
    CurrentVSABias,
    QualificationLifecycleLabel,
    QualificationSide,
    label_candidate_qualification_lifecycle,
    label_qualification_lifecycle,
)


def _evidence(code: EvidenceCode | str) -> SimpleNamespace:
    return SimpleNamespace(code=code)


def test_lifecycle_label_marks_supported_persistent_bullish_as_active() -> None:
    result = label_qualification_lifecycle(
        qualification=PatternQualification.PERSISTENT_BULLISH,
        actionable=True,
        scoring_evidence=[
            _evidence(EvidenceCode.DEMAND_COMING_IN),
            _evidence(EvidenceCode.NO_SUPPLY),
        ],
        scoring_evidence_age=0,
    )

    assert result.status is QualificationLifecycleLabel.ACTIVE
    assert result.qualification_side is QualificationSide.BULLISH
    assert result.current_vsa_bias is CurrentVSABias.BULLISH
    assert result.supporting_event_codes == ("demand_coming_in", "no_supply")
    assert result.opposing_event_codes == ()
    assert result.production_safe is True


def test_lifecycle_label_invalidates_bearish_when_fresh_demand_opposes_it() -> None:
    result = label_qualification_lifecycle(
        qualification=PatternQualification.PERSISTENT_BEARISH,
        actionable=False,
        scoring_evidence=[_evidence(EvidenceCode.DEMAND_COMING_IN)],
        scoring_evidence_age=0,
    )

    assert result.status is QualificationLifecycleLabel.INVALIDATED
    assert result.qualification_side is QualificationSide.BEARISH
    assert result.current_vsa_bias is CurrentVSABias.BULLISH
    assert result.supporting_event_codes == ()
    assert result.opposing_event_codes == ("demand_coming_in",)
    assert "fresh opposing bullish" in result.reason


def test_lifecycle_label_marks_mixed_fresh_evidence_as_conflicted() -> None:
    result = label_qualification_lifecycle(
        qualification="persistent_bearish",
        actionable=False,
        scoring_evidence=[
            _evidence(EvidenceCode.INCREASING_SUPPLY),
            _evidence(EvidenceCode.DEMAND_COMING_IN),
        ],
        scoring_evidence_age=0,
    )

    assert result.status is QualificationLifecycleLabel.CONFLICTED
    assert result.current_vsa_bias is CurrentVSABias.MIXED
    assert result.supporting_event_codes == ("increasing_supply",)
    assert result.opposing_event_codes == ("demand_coming_in",)


def test_lifecycle_label_expires_when_no_fresh_vsa_confirmation_exists() -> None:
    result = label_qualification_lifecycle(
        qualification="persistent_bearish",
        actionable=False,
        scoring_evidence=[],
        scoring_evidence_age=None,
    )

    assert result.status is QualificationLifecycleLabel.EXPIRED
    assert result.current_vsa_bias is CurrentVSABias.NONE
    assert result.supporting_event_codes == ()
    assert result.opposing_event_codes == ()


def test_lifecycle_label_waits_for_follow_through_on_stale_opposing_fallback() -> None:
    result = label_qualification_lifecycle(
        qualification="persistent_bullish",
        actionable=False,
        scoring_evidence=[_evidence(EvidenceCode.INCREASING_SUPPLY)],
        scoring_evidence_age=4,
        used_fallback_evidence=True,
    )

    assert result.status is QualificationLifecycleLabel.NEEDS_FOLLOW_THROUGH
    assert result.current_vsa_bias is CurrentVSABias.BEARISH
    assert result.opposing_event_codes == ("increasing_supply",)
    assert "fallback/stale" in result.reason


def test_lifecycle_label_keeps_audit_only_candidates_out_of_production_bias() -> None:
    result = label_qualification_lifecycle(
        qualification="persistent_bearish",
        actionable=False,
        scoring_evidence=[
            _evidence("effort_gt_result"),
            _evidence("absorption"),
        ],
        scoring_evidence_age=0,
    )

    assert {"effort_gt_result", "absorption"}.issubset(AUDIT_ONLY_CANDIDATE_CODES)
    assert result.status is QualificationLifecycleLabel.EXPIRED
    assert result.current_vsa_bias is CurrentVSABias.NONE
    assert result.ignored_audit_only_codes == ("effort_gt_result", "absorption")
    assert result.supporting_event_codes == ()
    assert result.opposing_event_codes == ()


def test_lifecycle_label_marks_unqualified_without_forcing_direction() -> None:
    result = label_qualification_lifecycle(
        qualification=PatternQualification.UNQUALIFIED,
        actionable=False,
        scoring_evidence=[_evidence(EvidenceCode.DEMAND_COMING_IN)],
        scoring_evidence_age=0,
    )

    assert result.status is QualificationLifecycleLabel.UNQUALIFIED
    assert result.qualification_side is QualificationSide.UNQUALIFIED
    assert result.current_vsa_bias is CurrentVSABias.BULLISH
    assert result.supporting_event_codes == ()
    assert result.opposing_event_codes == ()


def test_candidate_adapter_reads_existing_scanner_fields_only() -> None:
    candidate = SimpleNamespace(
        qualification=PatternQualification.PERSISTENT_BEARISH,
        actionable=False,
        scoring_evidence=[_evidence(EvidenceCode.INCREASING_DEMAND)],
        scoring_evidence_age=0,
        used_fallback_evidence=False,
    )

    result = label_candidate_qualification_lifecycle(candidate)

    assert result.status is QualificationLifecycleLabel.INVALIDATED
    assert result.to_dict()["status"] == "invalidated"
    assert result.to_dict()["production_safe"] is True
