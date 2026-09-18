from __future__ import annotations

from background.qualification import PatternQualification, PatternQualificationResult
from scanner import ScannerEngine
from scanner_policy import (
    CandidateActionabilityPolicy,
    CandidateExecutionPolicy,
    CandidateRankingPolicy,
    VSAFreshnessPolicy,
)


def _qualification(
    qualification: PatternQualification,
    *,
    actionable: bool = True,
) -> PatternQualificationResult:
    return PatternQualificationResult(
        qualification=qualification,
        is_actionable_evidence=actionable,
        reason="test",
    )


def test_default_freshness_policy_matches_scanner_compatibility_constants() -> None:
    policy = VSAFreshnessPolicy()

    assert policy.scoring_lookback_bars == ScannerEngine.SCORING_LOOKBACK_BARS
    assert policy.max_actionable_age == ScannerEngine.MAX_ACTIONABLE_VSA_AGE


def test_freshness_policy_preserves_three_bar_boundary() -> None:
    policy = VSAFreshnessPolicy()

    assert policy.age(scoring_bar_index=25, target_bar_index=28) == 3
    assert policy.is_current(scoring_bar_index=25, target_bar_index=28)
    assert not policy.is_current(scoring_bar_index=24, target_bar_index=28)
    assert not policy.is_current(scoring_bar_index=29, target_bar_index=28)
    assert not policy.is_current(scoring_bar_index=None, target_bar_index=28)


def test_actionability_policy_requires_qualification_confidence_and_clean_bar() -> None:
    policy = CandidateActionabilityPolicy()
    qualified = _qualification(PatternQualification.PERSISTENT_BULLISH)

    assert policy.is_actionable(
        qualification=qualified,
        confidence=0.5,
        signal_bar_anomaly=False,
    )
    assert not policy.is_actionable(
        qualification=qualified,
        confidence=0.0,
        signal_bar_anomaly=False,
    )
    assert not policy.is_actionable(
        qualification=qualified,
        confidence=0.5,
        signal_bar_anomaly=True,
    )
    assert not policy.is_actionable(
        qualification=_qualification(
            PatternQualification.PERSISTENT_BULLISH,
            actionable=False,
        ),
        confidence=0.5,
        signal_bar_anomaly=False,
    )


def test_ranking_policy_preserves_directional_conviction_magnitude() -> None:
    policy = CandidateRankingPolicy()

    assert policy.score(
        qualification=PatternQualification.PERSISTENT_BULLISH,
        base_score=-0.5,
    ) == 0.5
    assert policy.score(
        qualification=PatternQualification.PERSISTENT_BEARISH,
        base_score=-0.8,
    ) == 0.8
    assert policy.score(
        qualification=PatternQualification.UNQUALIFIED,
        base_score=-0.4,
    ) == -0.4
    assert policy.sort_key(actionable=True, ranking_score=0.2) > policy.sort_key(
        actionable=False,
        ranking_score=1.0,
    )


def test_execution_policy_preserves_next_bar_metadata_semantics() -> None:
    policy = CandidateExecutionPolicy()

    assert policy.is_available(execution_bar_index=31)
    assert not policy.is_available(execution_bar_index=None)
    assert policy.is_pending(actionable=True, execution_bar_index=None)
    assert not policy.is_pending(actionable=False, execution_bar_index=None)
    assert not policy.is_pending(actionable=True, execution_bar_index=31)
    assert "next bar/session" in policy.note(execution_bar_index=31)
    assert "not a same-bar entry" in policy.note(execution_bar_index=None)
