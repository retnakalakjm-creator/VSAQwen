from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from decision_outcome_audit import (
    CONFIRMATION_ONLY_CODES,
    compare_candidate_outcome,
    mask_confirmation_only,
)
from model.evidence_result_model import EvidenceResult
from models import EvidenceCode


class _Scanner:
    def __init__(self) -> None:
        self.calls = []

    def evaluate(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            actionable=True,
            base_score=0.8 if len(self.calls) == 1 else 0.6,
        )


def _evidence() -> EvidenceResult:
    evidence = []
    for code in (
        EvidenceCode.STOPPING_VOLUME,
        EvidenceCode.DEMAND_COMING_IN,
        EvidenceCode.SPRING,
    ):
        evidence.append(
            SimpleNamespace(
                code=code,
                bar_index=2,
            )
        )
    return EvidenceResult(
        context=SimpleNamespace(),
        evidence=tuple(evidence),
    )


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "High": [100.0, 104.0, 110.0, 112.0, 108.0, 115.0],
            "Low": [98.0, 101.0, 105.0, 107.0, 104.0, 111.0],
            "Close": [99.0, 103.0, 108.0, 110.0, 106.0, 114.0],
        }
    )


def test_mask_confirmation_only_retains_scored_evidence() -> None:
    masked = mask_confirmation_only(_evidence())

    assert [item.code for item in masked.evidence] == [EvidenceCode.STOPPING_VOLUME]
    assert all(item.code not in CONFIRMATION_ONLY_CODES for item in masked.evidence)


def test_mask_confirmation_only_preserves_context() -> None:
    source = _evidence()
    masked = mask_confirmation_only(source)

    assert masked.context is source.context


def test_compare_candidate_outcome_labels_only_complete_future_window() -> None:
    scanner = _Scanner()
    metrics = _frame()

    comparison = compare_candidate_outcome(
        scanner,
        trend=SimpleNamespace(),
        evidence=_evidence(),
        history=(),
        metrics=metrics,
        bar_index=2,
        direction=1,
        horizon=2,
    )

    assert comparison.bar_index == 2
    assert comparison.outcome.complete is True
    assert len(scanner.calls) == 2
    assert scanner.calls[0]["evidence"] is not scanner.calls[1]["evidence"]
    assert comparison.changed_score is True
    assert comparison.changed_actionability is False


def test_compare_candidate_outcome_marks_incomplete_horizon() -> None:
    scanner = _Scanner()

    comparison = compare_candidate_outcome(
        scanner,
        trend=SimpleNamespace(),
        evidence=_evidence(),
        history=(),
        metrics=_frame(),
        bar_index=5,
        direction=-1,
        horizon=2,
    )

    assert comparison.outcome.complete is False
    assert comparison.outcome.forward_return is None
