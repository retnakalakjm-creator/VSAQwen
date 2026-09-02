from __future__ import annotations

import numpy as np
import pandas as pd

from background.qualification import PatternQualification, PatternQualificationResult
from engine.columns import (
    COL_AVG_SPREAD,
    COL_AVG_VOLUME,
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_SPREAD,
    COL_VOLUME,
    COL_WEEK,
)
from metrics_engine import MetricsEngine
from model.score_model import ProfessionalScore, ProfessionalScoreResult
from models import EvidenceCode
from scanner import ScannerCandidate, ScannerEngine, rank_actionable_candidates


def _metrics(size: int = 120) -> pd.DataFrame:
    anchors = [100.0, 108.0, 101.0, 111.0, 103.0, 115.0, 106.0]
    points: list[float] = []
    for start, end in zip(anchors[:-1], anchors[1:]):
        points.extend(np.linspace(start, end, 18, endpoint=False))
    points.extend(np.linspace(anchors[-1], 118.0, size - len(points)))

    close = np.asarray(points[:size], dtype=float)
    spread = np.full(size, 1.0)
    volume = np.full(size, 1_000.0)

    raw = pd.DataFrame(
        {
            COL_WEEK: [f"2025-01-{i + 1:02d}" for i in range(size)],
            COL_OPEN: close - 0.2,
            COL_HIGH: close + 0.5,
            COL_LOW: close - 0.5,
            COL_CLOSE: close,
            COL_VOLUME: volume,
            COL_SPREAD: spread,
            COL_AVG_VOLUME: volume,
            COL_AVG_SPREAD: spread,
        }
    )
    return MetricsEngine().calculate(raw)


def test_actionable_candidates_never_use_stale_vsa_confirmation() -> None:
    metrics = _metrics()
    scanner = ScannerEngine()

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        candidate = scanner.scan_to_index(metrics, index)
        if not candidate.actionable:
            continue

        assert candidate.scoring_evidence
        assert candidate.scoring_bar_index == max(
            item.bar_index for item in candidate.scoring_evidence
        )
        assert candidate.scoring_evidence_age is not None
        assert 0 <= candidate.scoring_evidence_age <= scanner.MAX_ACTIONABLE_VSA_AGE
        assert all(
            item.code
            not in {
                EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
                EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
            }
            for item in candidate.scoring_evidence
        )


def test_actionable_candidates_have_directional_vsa_confirmation() -> None:
    metrics = _metrics()
    scanner = ScannerEngine()
    bullish = scanner._BULLISH_VSA_CODES
    bearish = scanner._BEARISH_VSA_CODES

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        candidate = scanner.scan_to_index(metrics, index)
        if not candidate.actionable:
            continue

        codes = {item.code for item in candidate.scoring_evidence}
        if candidate.qualification.name == "PERSISTENT_BULLISH":
            assert codes & bullish
            assert not codes & bearish
        elif candidate.qualification.name == "PERSISTENT_BEARISH":
            assert codes & bearish
            assert not codes & bullish


def _candidate_with_confidence(confidence: float) -> ScannerCandidate:
    return ScannerCandidate(
        evidence=None,
        professional=ProfessionalScoreResult(
            scores=ProfessionalScore(
                trend=0.5,
                supply=0.5,
                demand=0.5,
                effort=0.5,
                strength=0.8,
                weakness=0.1,
                confidence=confidence,
            ),
            evidence=(),
        ),
        qualification_result=PatternQualificationResult(
            qualification=PatternQualification.PERSISTENT_BULLISH,
            is_actionable_evidence=True,
            reason="test",
        ),
    )


def test_zero_confidence_candidate_is_not_actionable_or_ranked() -> None:
    candidate = _candidate_with_confidence(0.0)

    assert not candidate.actionable
    assert rank_actionable_candidates([candidate]) == []


def test_scan_actionable_returns_only_actionable_candidates() -> None:
    metrics = _metrics()
    scanner = ScannerEngine()

    candidates = scanner.scan_actionable(metrics)

    assert all(candidate.actionable for candidate in candidates)
    assert candidates == rank_actionable_candidates(candidates)


def test_candidate_scoring_evidence_is_exactly_the_professional_input() -> None:
    metrics = _metrics()
    scanner = ScannerEngine()

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        candidate = scanner.scan_to_index(metrics, index)
        assert candidate.professional.evidence == candidate.scoring_evidence


def test_candidate_evidence_layers_are_subsets_of_campaign_evidence() -> None:
    metrics = _metrics()
    scanner = ScannerEngine()

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        candidate = scanner.scan_to_index(metrics, index)
        campaign = set(candidate.campaign_evidence)

        assert set(candidate.target_bar_evidence).issubset(campaign)
        assert set(candidate.scoring_evidence).issubset(campaign)


def test_candidate_scoring_identity_fields_match_scoring_evidence() -> None:
    metrics = _metrics()
    scanner = ScannerEngine()

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        candidate = scanner.scan_to_index(metrics, index)
        if not candidate.scoring_evidence:
            assert candidate.scoring_bar_index is None
            assert candidate.scoring_evidence_age is None
            assert not candidate.used_fallback_evidence
            continue

        latest_bar = max(item.bar_index for item in candidate.scoring_evidence)
        assert candidate.scoring_bar_index == latest_bar
        assert candidate.scoring_evidence_age == index - latest_bar
        assert candidate.used_fallback_evidence == (latest_bar != index)
