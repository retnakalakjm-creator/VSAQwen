from __future__ import annotations

from test_actionable_vsa_freshness_audit import _metrics
from scanner import ScannerEngine


def test_qualifying_evidence_matches_declared_qualification_pairs() -> None:
    metrics = _metrics()
    scanner = ScannerEngine()

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        candidate = scanner.scan_to_index(metrics, index)
        declared = set(
            zip(
                candidate.qualification_result.evidence_bar_indices,
                candidate.qualification_result.evidence_codes,
            )
        )
        actual = {(item.bar_index, item.code) for item in candidate.qualifying_evidence}

        assert actual == declared


def test_target_bar_evidence_contains_only_target_bar_events() -> None:
    metrics = _metrics()
    scanner = ScannerEngine()

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        candidate = scanner.scan_to_index(metrics, index)

        assert all(item.bar_index == index for item in candidate.target_bar_evidence)


def test_scoring_evidence_is_from_one_latest_vsa_bar() -> None:
    metrics = _metrics()
    scanner = ScannerEngine()

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        candidate = scanner.scan_to_index(metrics, index)
        if not candidate.scoring_evidence:
            continue

        scoring_bar = candidate.scoring_bar_index
        assert scoring_bar is not None
        assert all(item.bar_index == scoring_bar for item in candidate.scoring_evidence)
        assert candidate.professional.evidence == candidate.scoring_evidence
