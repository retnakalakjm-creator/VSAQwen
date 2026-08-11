from types import SimpleNamespace

import pandas as pd

from scanner import ScannerCandidate, ScannerEngine
from background.qualification import PatternQualification


def _candidate(*, bar_index: int, actionable: bool) -> ScannerCandidate:
    qualification = PatternQualification.PERSISTENT_BULLISH if actionable else PatternQualification.UNQUALIFIED
    qualification_result = SimpleNamespace(
        qualification=qualification,
        is_actionable_evidence=actionable,
    )
    professional = SimpleNamespace(
        scores=SimpleNamespace(net_strength=0.5, net_pressure=0.5),
        confidence=1.0,
    )
    return ScannerCandidate(
        evidence=SimpleNamespace(evidence=()),
        professional=professional,
        qualification_result=qualification_result,
        bar_index=bar_index,
    )


def test_scan_actionable_returns_latest_bar_only(monkeypatch) -> None:
    historical = _candidate(bar_index=100, actionable=True)
    latest = _candidate(bar_index=120, actionable=True)

    monkeypatch.setattr(
        ScannerEngine,
        "scan",
        lambda self, metrics: [historical, latest],
    )
    monkeypatch.setattr(
        ScannerEngine,
        "scan_to_index",
        lambda self, metrics, target_index: latest,
    )

    metrics = pd.DataFrame({"close": range(121)})
    result = ScannerEngine().scan_actionable(metrics)

    assert result == [latest]
    assert result[0].bar_index == len(metrics) - 1


def test_scan_actionable_returns_empty_when_latest_bar_is_not_actionable(monkeypatch) -> None:
    historical = _candidate(bar_index=100, actionable=True)
    latest = _candidate(bar_index=120, actionable=False)

    monkeypatch.setattr(
        ScannerEngine,
        "scan",
        lambda self, metrics: [historical, latest],
    )
    monkeypatch.setattr(
        ScannerEngine,
        "scan_to_index",
        lambda self, metrics, target_index: latest,
    )

    metrics = pd.DataFrame({"close": range(121)})
    assert ScannerEngine().scan_actionable(metrics) == []


def test_scan_actionable_does_not_use_historical_ranked_candidates(monkeypatch) -> None:
    historical = _candidate(bar_index=100, actionable=True)
    latest = _candidate(bar_index=120, actionable=False)

    monkeypatch.setattr(
        ScannerEngine,
        "scan",
        lambda self, metrics: [historical, latest],
    )

    def fail_if_ranked(_candidates):
        raise AssertionError("historical actionable ranking must not be used")

    monkeypatch.setattr("scanner.rank_actionable_candidates", fail_if_ranked)
    monkeypatch.setattr(
        ScannerEngine,
        "scan_to_index",
        lambda self, metrics, target_index: latest,
    )

    metrics = pd.DataFrame({"close": range(121)})
    assert ScannerEngine().scan_actionable(metrics) == []


def test_scan_actionable_requires_enough_replay_bars() -> None:
    metrics = pd.DataFrame({"close": range(ScannerEngine.MIN_REPLAY_BARS + 1)})
    # This is a boundary sanity check; the method must not produce an
    # actionable historical candidate from an undersized replay window.
    assert ScannerEngine().scan_actionable(metrics.iloc[:ScannerEngine.MIN_REPLAY_BARS]) == []
