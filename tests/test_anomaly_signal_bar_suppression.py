from types import SimpleNamespace

import pandas as pd

from background.qualification import PatternQualification, PatternQualificationResult
from engine.columns import COL_CORPORATE_ACTION_ANOMALY
from scanner import ANOMALY_SIGNAL_BAR_REASON, ScannerCandidate, ScannerEngine


def _professional(confidence: float = 1.0):
    return SimpleNamespace(
        confidence=confidence,
        scores=SimpleNamespace(net_strength=1.0, net_pressure=1.0),
    )


def _qualified_candidate(*, signal_bar_anomaly: bool) -> ScannerCandidate:
    return ScannerCandidate(
        evidence=SimpleNamespace(context=None, evidence=()),
        professional=_professional(),
        qualification_result=PatternQualificationResult(
            qualification=PatternQualification.PERSISTENT_BULLISH,
            is_actionable_evidence=True,
            reason="Persistent bullish structure is confirmed.",
        ),
        bar_index=21,
        week="2026-01-30",
        signal_bar_anomaly=signal_bar_anomaly,
        signal_bar_anomaly_reason=ANOMALY_SIGNAL_BAR_REASON if signal_bar_anomaly else None,
    )


def test_candidate_is_not_actionable_when_signal_bar_is_anomalous() -> None:
    candidate = _qualified_candidate(signal_bar_anomaly=True)

    assert candidate.signal_bar_anomaly is True
    assert candidate.actionable is False
    assert candidate.reason == ANOMALY_SIGNAL_BAR_REASON


def test_candidate_remains_actionable_when_signal_bar_is_not_anomalous() -> None:
    candidate = _qualified_candidate(signal_bar_anomaly=False)

    assert candidate.signal_bar_anomaly is False
    assert candidate.actionable is True
    assert candidate.reason == "Persistent bullish structure is confirmed."


def test_signal_bar_anomaly_reads_canonical_metrics_column() -> None:
    metrics = pd.DataFrame({COL_CORPORATE_ACTION_ANOMALY: [False, True, pd.NA]})

    assert ScannerEngine._signal_bar_anomaly(metrics, 0) is False
    assert ScannerEngine._signal_bar_anomaly(metrics, 1) is True
    assert ScannerEngine._signal_bar_anomaly(metrics, 2) is False


def test_signal_bar_anomaly_defaults_false_when_column_is_absent() -> None:
    metrics = pd.DataFrame({"close": [100.0]})

    assert ScannerEngine._signal_bar_anomaly(metrics, 0) is False
    assert ScannerEngine._signal_bar_anomaly(metrics, None) is False
    assert ScannerEngine._signal_bar_anomaly(metrics, 99) is False
