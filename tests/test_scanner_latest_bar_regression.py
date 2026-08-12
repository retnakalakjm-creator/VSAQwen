from types import SimpleNamespace

import pandas as pd

from background.qualification import PatternQualification
from scanner import ScannerCandidate, ScannerEngine


def _candidate(*, bar_index: int, actionable: bool, score: float) -> ScannerCandidate:
    qualification = PatternQualification.PERSISTENT_BEARISH
    qualification_result = SimpleNamespace(
        qualification=qualification,
        is_actionable_evidence=actionable,
        reason="test",
        evidence_codes=(),
        evidence_bar_indices=(),
    )
    professional = SimpleNamespace(
        scores=SimpleNamespace(net_strength=score, net_pressure=-0.7),
        confidence=0.45 if actionable else 0.0,
    )
    return ScannerCandidate(
        evidence=SimpleNamespace(evidence=()),
        professional=professional,
        qualification_result=qualification_result,
        bar_index=bar_index,
        week=str(pd.Timestamp("2026-08-03")),
    )


def test_scan_actionable_returns_latest_bar_only(monkeypatch) -> None:
    """Regression: historical actionable candidates must never leak into CLI output."""
    historical = _candidate(bar_index=1128, actionable=True, score=-0.20)
    latest = _candidate(bar_index=1257, actionable=True, score=-0.54)

    metrics = pd.DataFrame(
        {"week_beginning": pd.date_range("2026-01-05", periods=1258, freq="W-MON")}
    )
    captured = []

    def fake_scan_to_index(self, metrics, target_index):
        captured.append(target_index)
        assert target_index == len(metrics) - 1
        return latest

    monkeypatch.setattr(ScannerEngine, "scan_to_index", fake_scan_to_index)
    monkeypatch.setattr(
        ScannerEngine,
        "scan",
        lambda self, metrics: [historical, latest],
    )

    result = ScannerEngine().scan_actionable(metrics)

    assert result == [latest]
    assert result[0].bar_index == 1257
    assert result[0].base_score == -0.54
    assert captured == [1257]


def test_scan_actionable_does_not_filter_historical_full_scan_results(monkeypatch) -> None:
    """Regression: scan_actionable must not call scan() and rank its historical output."""
    metrics = pd.DataFrame(
        {"week_beginning": pd.date_range("2026-01-05", periods=1258, freq="W-MON")}
    )
    latest = _candidate(bar_index=1257, actionable=True, score=-0.54)

    def fail_if_called(self, metrics):
        raise AssertionError("scan_actionable must not replay through scan()")

    monkeypatch.setattr(ScannerEngine, "scan", fail_if_called)
    monkeypatch.setattr(ScannerEngine, "scan_to_index", lambda self, metrics, target_index: latest)

    assert ScannerEngine().scan_actionable(metrics) == [latest]
