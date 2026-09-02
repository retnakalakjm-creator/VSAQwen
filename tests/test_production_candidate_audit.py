from __future__ import annotations

import numpy as np
import pandas as pd

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
from models import EvidenceCode
from scanner import ScannerEngine, rank_candidates


_STRUCTURAL_CODES = frozenset(
    {
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
        EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
    }
)

_BULLISH_CODES = ScannerEngine._BULLISH_VSA_CODES
_BEARISH_CODES = ScannerEngine._BEARISH_VSA_CODES


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


def _assert_candidate_integrity(candidate) -> None:
    scoring = tuple(candidate.scoring_evidence)
    assert candidate.actionable == (
        candidate.qualification_result.is_actionable_evidence
        and candidate.professional.confidence > 0.0
    )

    if not candidate.actionable:
        return

    assert scoring
    assert candidate.scoring_bar_index is not None
    assert candidate.bar_index is not None
    assert 0 <= candidate.bar_index - candidate.scoring_bar_index <= ScannerEngine.MAX_ACTIONABLE_VSA_AGE
    assert all(item.code not in _STRUCTURAL_CODES for item in scoring)

    bullish = tuple(item for item in scoring if item.code in _BULLISH_CODES)
    bearish = tuple(item for item in scoring if item.code in _BEARISH_CODES)

    if candidate.qualification.name == "PERSISTENT_BULLISH":
        assert bullish
        assert not bearish
    elif candidate.qualification.name == "PERSISTENT_BEARISH":
        assert bearish
        assert not bullish


def test_full_production_scan_preserves_actionability_integrity_across_history() -> None:
    metrics = _metrics()
    scanner = ScannerEngine()

    candidates = [
        scanner.scan_to_index(metrics, index)
        for index in range(scanner.MIN_REPLAY_BARS, len(metrics))
    ]

    assert len(candidates) == len(metrics) - scanner.MIN_REPLAY_BARS
    for candidate in candidates:
        _assert_candidate_integrity(candidate)


def test_full_production_scan_does_not_rank_non_actionable_above_actionable() -> None:
    metrics = _metrics()
    scanner = ScannerEngine()
    candidates = tuple(
        scanner.scan_to_index(metrics, index)
        for index in range(scanner.MIN_REPLAY_BARS, len(metrics))
    )

    actionable = [candidate for candidate in candidates if candidate.actionable]
    non_actionable = [candidate for candidate in candidates if not candidate.actionable]
    ranked = rank_candidates(candidates)

    if actionable and non_actionable:
        first_non_actionable = next(
            index for index, candidate in enumerate(ranked) if not candidate.actionable
        )
        assert all(candidate.actionable for candidate in ranked[:first_non_actionable])
