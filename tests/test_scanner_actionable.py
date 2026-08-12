from types import SimpleNamespace

import pandas as pd

from background.qualification import PatternQualification, PatternQualificationResult
from models import EvidenceCode
from scanner import ScannerCandidate, ScannerEngine, rank_actionable_candidates


def _candidate(*, actionable: bool, score: float) -> ScannerCandidate:
    qualification = PatternQualification.PERSISTENT_BULLISH if actionable else PatternQualification.UNQUALIFIED
    qualification_result = PatternQualificationResult(qualification=qualification, is_actionable_evidence=actionable, reason="test")
    professional = SimpleNamespace(scores=SimpleNamespace(net_strength=score, net_pressure=0.0), confidence=1.0)
    return ScannerCandidate(evidence=SimpleNamespace(evidence=()), professional=professional, qualification_result=qualification_result)


def test_rank_actionable_candidates_excludes_unqualified() -> None:
    unqualified = _candidate(actionable=False, score=10.0)
    actionable = _candidate(actionable=True, score=-1.0)
    assert rank_actionable_candidates([unqualified, actionable]) == [actionable]


def test_scan_actionable_returns_latest_actionable_candidate(monkeypatch) -> None:
    actionable = _candidate(actionable=True, score=-1.0)
    metrics = pd.DataFrame({"week_beginning": pd.date_range("2012-01-02", periods=21, freq="W-MON")})
    captured = []

    def fake_scan_to_index(self, metrics, target_index):
        captured.append(target_index)
        return actionable

    monkeypatch.setattr(ScannerEngine, "scan_to_index", fake_scan_to_index)
    assert ScannerEngine().scan_actionable(metrics) == [actionable]
    assert captured == [20]


def test_scan_preserves_candidate_bar_metadata(monkeypatch) -> None:
    metrics = pd.DataFrame({"week_beginning": pd.date_range("2012-01-02", periods=21, freq="W-MON")})
    trend = SimpleNamespace(structure=SimpleNamespace(structural_swings=()))
    evidence = SimpleNamespace(evidence=())
    captured = []
    candidate = _candidate(actionable=True, score=1.0)
    monkeypatch.setattr("scanner.TrendAnalyzer.analyze", lambda self, replay: trend)
    monkeypatch.setattr("scanner.EvidenceEngine.collect", lambda self, *, metrics, trend, structural_swings: evidence)

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
        evidence_codes=("structural_progression_weakening",) * 3,
        evidence_bar_indices=(100, 110, 120),
    )
    assert ScannerEngine._qualification_is_current(qualification, 120)
    assert not ScannerEngine._qualification_is_current(qualification, 121)


def test_stale_qualification_is_invalidated() -> None:
    qualification = PatternQualificationResult(
        qualification=PatternQualification.PERSISTENT_BEARISH,
        is_actionable_evidence=True,
        reason="test",
        evidence_codes=("structural_progression_weakening",) * 3,
        evidence_bar_indices=(100, 110, 120),
    )
    result = ScannerEngine._invalidate_stale_qualification(qualification)
    assert result.qualification is PatternQualification.PERSISTENT_BEARISH
    assert result.is_actionable_evidence is False
    assert result.evidence_bar_indices == (100, 110, 120)


def test_evaluate_invalidates_historical_qualification_on_later_bar(monkeypatch) -> None:
    qualification = PatternQualificationResult(
        qualification=PatternQualification.PERSISTENT_BEARISH,
        is_actionable_evidence=True,
        reason="historically persistent",
        evidence_codes=(EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,) * 3,
        evidence_bar_indices=(100, 110, 120),
    )
    monkeypatch.setattr("scanner.PatternQualificationEngine.evaluate", lambda self, history: qualification)
    professional = SimpleNamespace(scores=SimpleNamespace(net_strength=-0.5, net_pressure=-0.5), confidence=0.5)
    monkeypatch.setattr("scanner.ProfessionalScoringEngine.calculate", lambda self, *, trend, evidence: professional)
    evidence = SimpleNamespace(context=None, evidence=())
    candidate = ScannerEngine().evaluate(
        trend=SimpleNamespace(),
        evidence=evidence,
        history=(evidence,),
        bar_index=121,
        week="2020-01-06 00:00:00",
    )
    assert candidate.qualification is PatternQualification.PERSISTENT_BEARISH
    assert candidate.actionable is False
    assert candidate.reason == "Historical persistence was validated, but no qualifying structural progression event occurred on the target bar."


def test_evaluate_allows_persistent_bearish_continuation_with_fresh_vsa(monkeypatch) -> None:
    qualification = PatternQualificationResult(
        qualification=PatternQualification.PERSISTENT_BEARISH,
        is_actionable_evidence=True,
        reason="historically persistent",
        evidence_codes=(EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,) * 3,
        evidence_bar_indices=(100, 110, 120),
    )
    monkeypatch.setattr("scanner.PatternQualificationEngine.evaluate", lambda self, history: qualification)
    professional = SimpleNamespace(scores=SimpleNamespace(net_strength=-0.54, net_pressure=-0.7), confidence=0.45)
    monkeypatch.setattr("scanner.ProfessionalScoringEngine.calculate", lambda self, *, trend, evidence: professional)
    evidence = SimpleNamespace(
        context=None,
        evidence=(SimpleNamespace(bar_index=121, code=EvidenceCode.INCREASING_SUPPLY),),
    )

    candidate = ScannerEngine().evaluate(
        trend=SimpleNamespace(),
        evidence=evidence,
        history=(evidence,),
        bar_index=121,
        week="2020-01-06 00:00:00",
    )

    assert candidate.actionable is True
    assert candidate.qualification is PatternQualification.PERSISTENT_BEARISH
    assert candidate.scoring_bar_index == 121
    assert candidate.scoring_evidence_age == 0
    assert candidate.used_fallback_evidence is False
    assert "fresh directional VSA evidence" in candidate.reason


def test_scoring_evidence_uses_target_bar_when_available() -> None:
    result = SimpleNamespace(evidence=(
        SimpleNamespace(bar_index=1219, code=EvidenceCode.HIDDEN_SUPPLY),
        SimpleNamespace(bar_index=1223, code=EvidenceCode.INCREASING_SUPPLY),
        SimpleNamespace(bar_index=1223, code=EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING),
    ))
    scoring = ScannerEngine._scoring_evidence(result, 1223)
    assert [(item.bar_index, item.code) for item in scoring] == [(1223, EvidenceCode.INCREASING_SUPPLY)]


def test_scoring_evidence_falls_back_to_recent_vsa_event() -> None:
    result = SimpleNamespace(evidence=(
        SimpleNamespace(bar_index=1219, code=EvidenceCode.HIDDEN_SUPPLY),
        SimpleNamespace(bar_index=1223, code=EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING),
    ))
    scoring = ScannerEngine._scoring_evidence(result, 1223)
    assert [(item.bar_index, item.code) for item in scoring] == [(1219, EvidenceCode.HIDDEN_SUPPLY)]


def test_vsa_confirmation_age_allows_recent_evidence() -> None:
    scoring = (SimpleNamespace(bar_index=120, code=EvidenceCode.INCREASING_SUPPLY),)
    assert ScannerEngine._vsa_confirmation_is_current(scoring, 123)


def test_vsa_confirmation_age_rejects_stale_evidence() -> None:
    scoring = (SimpleNamespace(bar_index=119, code=EvidenceCode.INCREASING_SUPPLY),)
    assert not ScannerEngine._vsa_confirmation_is_current(scoring, 123)


def _qualification(direction: PatternQualification) -> PatternQualificationResult:
    code = EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING if direction is PatternQualification.PERSISTENT_BULLISH else EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING
    return PatternQualificationResult(
        qualification=direction,
        is_actionable_evidence=True,
        reason="persistent structure",
        evidence_codes=(code,) * 3,
        evidence_bar_indices=(270, 277, 283),
    )


def test_structural_qualification_without_directional_vsa_is_not_actionable() -> None:
    qualification = _qualification(PatternQualification.PERSISTENT_BULLISH)
    scoring = (SimpleNamespace(bar_index=283, code=EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING),)
    assert not ScannerEngine._vsa_supports_qualification(qualification, scoring)
    result = ScannerEngine._invalidate_missing_vsa_confirmation(qualification)
    assert result.is_actionable_evidence is False
    assert "no directional VSA confirmation" in result.reason


def test_bullish_vsa_supports_bullish_structure() -> None:
    qualification = _qualification(PatternQualification.PERSISTENT_BULLISH)
    scoring = (SimpleNamespace(bar_index=283, code=EvidenceCode.NO_SUPPLY),)
    assert ScannerEngine._vsa_supports_qualification(qualification, scoring)


def test_bearish_vsa_supports_bearish_structure() -> None:
    qualification = _qualification(PatternQualification.PERSISTENT_BEARISH)
    scoring = (SimpleNamespace(bar_index=283, code=EvidenceCode.INCREASING_SUPPLY),)
    assert ScannerEngine._vsa_supports_qualification(qualification, scoring)


def test_opposing_vsa_invalidates_bullish_structure() -> None:
    qualification = _qualification(PatternQualification.PERSISTENT_BULLISH)
    professional = SimpleNamespace(scores=SimpleNamespace(net_pressure=-1.0))
    scoring = (SimpleNamespace(bar_index=283, code=EvidenceCode.UPTHRUST),)
    assert ScannerEngine._vsa_conflicts_with_qualification(qualification, professional, scoring)


def test_opposing_vsa_invalidates_bearish_structure() -> None:
    qualification = _qualification(PatternQualification.PERSISTENT_BEARISH)
    professional = SimpleNamespace(scores=SimpleNamespace(net_pressure=0.8))
    scoring = (SimpleNamespace(bar_index=283, code=EvidenceCode.STOPPING_VOLUME),)
    assert ScannerEngine._vsa_conflicts_with_qualification(qualification, professional, scoring)


def test_supply_drying_up_is_not_bearish_confirmation() -> None:
    qualification = _qualification(PatternQualification.PERSISTENT_BEARISH)
    scoring = (SimpleNamespace(bar_index=149, code=EvidenceCode.SUPPLY_DRYING_UP),)
    assert not ScannerEngine._vsa_supports_qualification(qualification, scoring)


def test_vsa_conflict_does_not_invalidate_without_scoring_evidence() -> None:
    qualification = _qualification(PatternQualification.PERSISTENT_BULLISH)
    professional = SimpleNamespace(scores=SimpleNamespace(net_pressure=-1.0))
    assert not ScannerEngine._vsa_conflicts_with_qualification(qualification, professional, ())


def test_candidate_separates_target_campaign_and_qualifying_evidence() -> None:
    target = SimpleNamespace(bar_index=1223, code=EvidenceCode.INCREASING_SUPPLY)
    campaign_only = SimpleNamespace(bar_index=1219, code=EvidenceCode.HIDDEN_SUPPLY)
    structural = SimpleNamespace(bar_index=1223, code=EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING)
    candidate = ScannerCandidate(
        evidence=SimpleNamespace(evidence=(campaign_only, target, structural)),
        professional=SimpleNamespace(scores=SimpleNamespace(net_strength=-0.1, net_pressure=-0.7), confidence=0.8),
        target_bar_evidence=(target, structural),
        campaign_evidence=(campaign_only, target, structural),
        qualifying_evidence=(structural,),
    )
    assert candidate.current_evidence_codes == ("increasing_supply", "structural_progression_weakening")
    assert candidate.campaign_evidence_codes == ("hidden_supply", "increasing_supply", "structural_progression_weakening")
    assert candidate.qualifying_evidence_codes == ("structural_progression_weakening",)


def test_target_bar_evidence_selects_only_target_bar() -> None:
    result = SimpleNamespace(evidence=(
        SimpleNamespace(bar_index=1219, code=EvidenceCode.HIDDEN_SUPPLY),
        SimpleNamespace(bar_index=1223, code=EvidenceCode.INCREASING_SUPPLY),
        SimpleNamespace(bar_index=1223, code=EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING),
    ))
    target = ScannerEngine._target_bar_evidence(result, 1223)
    assert [(item.bar_index, item.code) for item in target] == [
        (1223, EvidenceCode.INCREASING_SUPPLY),
        (1223, EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING),
    ]
