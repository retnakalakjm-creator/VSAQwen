from __future__ import annotations

from test_actionable_vsa_freshness_audit import _metrics
from scanner import ScannerEngine


def test_earlier_candidate_is_point_in_time_invariant() -> None:
    metrics = _metrics()
    scanner = ScannerEngine()
    target_index = scanner.MIN_REPLAY_BARS + 8

    prefix_candidate = scanner.scan_to_index(
        metrics.iloc[: target_index + 1].copy(),
        target_index,
    )
    full_candidate = scanner.scan_to_index(metrics, target_index)

    assert prefix_candidate.qualification == full_candidate.qualification
    assert prefix_candidate.actionable == full_candidate.actionable
    assert prefix_candidate.base_score == full_candidate.base_score
    assert prefix_candidate.ranking_score == full_candidate.ranking_score
    assert prefix_candidate.net_strength == full_candidate.net_strength
    assert prefix_candidate.net_pressure == full_candidate.net_pressure
    assert prefix_candidate.confidence == full_candidate.confidence
    assert prefix_candidate.target_bar_evidence == full_candidate.target_bar_evidence
    assert prefix_candidate.campaign_evidence == full_candidate.campaign_evidence
    assert prefix_candidate.qualifying_evidence == full_candidate.qualifying_evidence
    assert prefix_candidate.scoring_evidence == full_candidate.scoring_evidence


def test_candidate_evidence_never_references_future_bars() -> None:
    metrics = _metrics()
    scanner = ScannerEngine()

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        candidate = scanner.scan_to_index(metrics, index)

        all_evidence = (
            candidate.target_bar_evidence
            + candidate.campaign_evidence
            + candidate.qualifying_evidence
            + candidate.scoring_evidence
        )
        assert all(item.bar_index <= index for item in all_evidence)
        assert candidate.scoring_bar_index is None or candidate.scoring_bar_index <= index
