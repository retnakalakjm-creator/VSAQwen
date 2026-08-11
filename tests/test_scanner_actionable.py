from types import SimpleNamespace

import pandas as pd

from background.qualification import PatternQualification, PatternQualificationResult
from models import EvidenceCode
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


def test_qualification_is_current_only_on_latest_event_bar() -> None:
    qualification = PatternQualificationResult(
        qualification=PatternQualification.PERSISTENT_BEARISH,
        is_actionable_evidence=True,
        reason="test",
        evidence_codes=(
            "structural_progression_weakening",
            "structural_progression_weakening",
            "structural_progression_weakening",
        ),
        evidence_bar_indices=(100, 110, 120),
    )

    assert ScannerEngine._qualification_is_current(qualification, 120)
    assert not ScannerEngine._qualification_is_current(qualification, 121)


def test_stale_qualification_is_invalidated() -> None:
    qualification = PatternQualificationResult(
        qualification=PatternQualification.PERSISTENT_BEARISH,
        is_actionable_evidence=True,
        reason="test",
        evidence_codes=(
            "structural_progression_weakening",
            "structural_progression_weakening",
            "structural_progression_weakening",
        ),
        evidence_bar_indices=(100, 110, 120),
    )

    result = ScannerEngine._invalidate_stale_qualification(qualification)

    assert result.qualification is PatternQualification.PERSISTENT_BEARISH
    assert result.is_actionable_evidence is False
    assert result.evidence_bar_indices == (100, 110, 120)


def test_scoring_evidence_uses_target_bar_only() -> None:
    result = SimpleNamespace(
        evidence=(
            SimpleNamespace(
                bar_index=1219,
                code=EvidenceCode.HIDDEN_SUPPLY,
            ),
            SimpleNamespace(
                bar_index=1223,
                code=EvidenceCode.INCREASING_SUPPLY,
            ),
            SimpleNamespace(
                bar_index=1223,
                code=EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
            ),
        )
    )

    scoring = ScannerEngine._scoring_evidence(result, 1223)

    assert [(item.bar_index, item.code) for item in scoring] == [
        (1223, EvidenceCode.INCREASING_SUPPLY),
    ]


def test_scoring_evidence_is_empty_without_target_bar() -> None:
    result = SimpleNamespace(
        evidence=(
            SimpleNamespace(
                bar_index=1219,
                code=EvidenceCode.HIDDEN_SUPPLY,
            ),
        )
    )

    assert ScannerEngine._scoring_evidence(result, 1223) == ()


def test_candidate_separates_target_campaign_and_qualifying_evidence() -> None:
    target = SimpleNamespace(
        bar_index=1223,
        code=EvidenceCode.INCREASING_SUPPLY,
    )
    campaign_only = SimpleNamespace(
        bar_index=1219,
        code=EvidenceCode.HIDDEN_SUPPLY,
    )
    structural = SimpleNamespace(
        bar_index=1223,
        code=EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
    )

    candidate = ScannerCandidate(
        evidence=SimpleNamespace(evidence=(campaign_only, target, structural)),
        professional=SimpleNamespace(
            scores=SimpleNamespace(net_strength=-0.1, net_pressure=-0.7),
            confidence=0.8,
        ),
        target_bar_evidence=(target, structural),
        campaign_evidence=(campaign_only, target, structural),
        qualifying_evidence=(structural,),
    )

    assert candidate.current_evidence_codes == ("increasing_supply", "structural_progression_weakening")
    assert candidate.campaign_evidence_codes == (
        "hidden_supply",
        "increasing_supply",
        "structural_progression_weakening",
    )
    assert candidate.qualifying_evidence_codes == (
        "structural_progression_weakening",
    )


def test_target_bar_evidence_selects_only_target_bar() -> None:
    result = SimpleNamespace(
        evidence=(
            SimpleNamespace(bar_index=1219, code=EvidenceCode.HIDDEN_SUPPLY),
            SimpleNamespace(bar_index=1223, code=EvidenceCode.INCREASING_SUPPLY),
            SimpleNamespace(
                bar_index=1223,
                code=EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
            ),
        )
    )

    target = ScannerEngine._target_bar_evidence(result, 1223)

    assert [(item.bar_index, item.code) for item in target] == [
        (1223, EvidenceCode.INCREASING_SUPPLY),
        (1223, EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING),
    ]
