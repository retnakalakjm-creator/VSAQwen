from types import SimpleNamespace

import pandas as pd

from background.qualification import PatternQualification, PatternQualificationResult
from scanner import ScannerCandidate, ScannerEngine, rank_actionable_candidates


def _candidate(*, actionable: bool, score: float) -> ScannerCandidate:
    qualification = (
        PatternQualification.PERSISTENT_BULLISH
        if actionable
        else PatternQualification.UNQUALIFIED
    )
    qualification_result = PatternQualificationResult(
        qualification=qualification,
        is_actionable_evidence=actionable,
        reason="test",
    )

    professional = SimpleNamespace(
        scores=SimpleNamespace(
            net_strength=score,
            net_pressure=0.0,
        ),
        confidence=1.0,
    )

    return ScannerCandidate(
        evidence=SimpleNamespace(evidence=()),
        professional=professional,
        qualification_result=qualification_result,
    )


def test_rank_actionable_candidates_excludes_unqualified() -> None:
    unqualified = _candidate(actionable=False, score=10.0)
    actionable = _candidate(actionable=True, score=-1.0)

    ranked = rank_actionable_candidates([unqualified, actionable])

    assert ranked == [actionable]


def test_scan_actionable_filters_after_full_scan(monkeypatch) -> None:
    unqualified = _candidate(actionable=False, score=10.0)
    actionable = _candidate(actionable=True, score=-1.0)

    monkeypatch.setattr(
        ScannerEngine,
        "scan",
        lambda self, metrics: [unqualified, actionable],
    )

    result = ScannerEngine().scan_actionable(SimpleNamespace())

    assert result == [actionable]


def test_scan_preserves_candidate_bar_metadata(monkeypatch) -> None:
    metrics = pd.DataFrame(
        {
            "week_beginning": pd.date_range("2012-01-02", periods=21, freq="W-MON")
        }
    )

    trend = SimpleNamespace(
        structure=SimpleNamespace(structural_swings=())
    )
    evidence = SimpleNamespace(evidence=())
    captured: list[tuple[int | None, str | None]] = []
    candidate = _candidate(actionable=True, score=1.0)

    monkeypatch.setattr(
        "scanner.TrendAnalyzer.analyze",
        lambda self, replay: trend,
    )
    monkeypatch.setattr(
        "scanner.EvidenceEngine.collect",
        lambda self, *, metrics, trend, structural_swings: evidence,
    )

    def fake_evaluate(self, *, trend, evidence, history, bar_index=None, week=None):
        captured.append((bar_index, week))
        return candidate

    monkeypatch.setattr(ScannerEngine, "evaluate", fake_evaluate)

    result = ScannerEngine().scan(metrics)

    assert len(result) == 1
    assert captured == [(20, str(metrics.iloc[20]["week_beginning"]))]
