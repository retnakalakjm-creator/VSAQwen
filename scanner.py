from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from background.qualification import PatternQualification, PatternQualificationEngine, PatternQualificationResult
from evidence.engine import EvidenceEngine
from model.evidence_result_model import EvidenceResult
from model.score_model import ProfessionalScoreResult
from models import Evidence, EvidenceCode
from professional.scoring_engine import ProfessionalScoringEngine
from trend import TrendAnalyzer, TrendResult


@dataclass(slots=True, frozen=True)
class ScannerCandidate:
    """Final scanner candidate assembled from current and qualifying evidence."""

    evidence: EvidenceResult
    professional: ProfessionalScoreResult
    qualification_result: PatternQualificationResult = field(default_factory=lambda: PatternQualificationResult(
        qualification=PatternQualification.UNQUALIFIED,
        is_actionable_evidence=False,
        reason="No validated persistent structural qualification applies.",
    ))
    target_bar_evidence: tuple[Evidence, ...] = ()
    campaign_evidence: tuple[Evidence, ...] = ()
    qualifying_evidence: tuple[Evidence, ...] = ()
    scoring_evidence: tuple[Evidence, ...] = ()
    scoring_bar_index: int | None = None
    scoring_evidence_age: int | None = None
    used_fallback_evidence: bool = False
    bar_index: int | None = None
    week: str | None = None

    @property
    def qualification(self) -> PatternQualification:
        return self.qualification_result.qualification

    @property
    def actionable(self) -> bool:
        return self.qualification_result.is_actionable_evidence

    @property
    def reason(self) -> str:
        return self.qualification_result.reason

    @property
    def base_score(self) -> float:
        return self.professional.scores.net_strength

    @property
    def net_strength(self) -> float:
        return self.professional.scores.net_strength

    @property
    def net_pressure(self) -> float:
        return self.professional.scores.net_pressure

    @property
    def confidence(self) -> float:
        return self.professional.confidence

    @property
    def evidence_codes(self) -> tuple[str, ...]:
        return self.current_evidence_codes

    @property
    def current_evidence_codes(self) -> tuple[str, ...]:
        return tuple(str(item.code) for item in self.target_bar_evidence)

    @property
    def campaign_evidence_codes(self) -> tuple[str, ...]:
        return tuple(str(item.code) for item in self.campaign_evidence)

    @property
    def target_bar_evidence_codes(self) -> tuple[str, ...]:
        return self.current_evidence_codes

    @property
    def qualifying_evidence_codes(self) -> tuple[str, ...]:
        return tuple(str(item.code) for item in self.qualifying_evidence)

    @property
    def scoring_evidence_codes(self) -> tuple[str, ...]:
        return tuple(str(item.code) for item in self.scoring_evidence)


def rank_candidates(candidates: tuple[ScannerCandidate, ...] | list[ScannerCandidate]) -> list[ScannerCandidate]:
    return sorted(candidates, key=lambda candidate: (candidate.actionable, candidate.base_score), reverse=True)


def rank_actionable_candidates(candidates: tuple[ScannerCandidate, ...] | list[ScannerCandidate]) -> list[ScannerCandidate]:
    return rank_candidates([candidate for candidate in candidates if candidate.actionable])


class ScannerEngine:
    """Point-in-time scanner pipeline."""

    MIN_REPLAY_BARS = 20
    SCORING_LOOKBACK_BARS = 10
    MAX_ACTIONABLE_VSA_AGE = 3

    _STRUCTURAL_CODES = frozenset({
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
        EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
    })

    _BULLISH_VSA_CODES = frozenset({
        EvidenceCode.STOPPING_VOLUME,
        EvidenceCode.DEMAND_COMING_IN,
        EvidenceCode.INCREASING_DEMAND,
        EvidenceCode.HIDDEN_DEMAND,
        EvidenceCode.DEMAND_DRYING_UP,
        EvidenceCode.NO_SUPPLY,
        EvidenceCode.SPRING,
        EvidenceCode.TEST,
        EvidenceCode.SELLING_CLIMAX,
        EvidenceCode.SHAKEOUT,
    })

    _BEARISH_VSA_CODES = frozenset({
        EvidenceCode.BUYING_CLIMAX,
        EvidenceCode.SUPPLY_COMING_IN,
        EvidenceCode.INCREASING_SUPPLY,
        EvidenceCode.HIDDEN_SUPPLY,
        EvidenceCode.SUPPLY_HIGH_VOLUME,
        EvidenceCode.SUPPLY_WIDE_SPREAD,
        EvidenceCode.SUPPLY_ABSORPTION,
        EvidenceCode.UPTHRUST,
        EvidenceCode.NO_DEMAND,
    })

    def __init__(self) -> None:
        self._qualification = PatternQualificationEngine()
        self._professional = ProfessionalScoringEngine()

    @classmethod
    def _meaningful_vsa_evidence(cls, result: EvidenceResult, bar_index: int, *, earliest_bar_index: int | None = None) -> tuple[Evidence, ...]:
        return tuple(item for item in result.evidence if item.bar_index == bar_index and item.code not in cls._STRUCTURAL_CODES and (earliest_bar_index is None or item.bar_index >= earliest_bar_index))

    @staticmethod
    def _target_bar_evidence(result: EvidenceResult, bar_index: int | None) -> tuple[Evidence, ...]:
        if bar_index is None:
            return ()
        return tuple(item for item in result.evidence if item.bar_index == bar_index)

    @staticmethod
    def _campaign_evidence(result: EvidenceResult) -> tuple[Evidence, ...]:
        return tuple(result.evidence)

    @classmethod
    def _scoring_evidence(cls, current: EvidenceResult, bar_index: int | None, qualifying_evidence: tuple[Evidence, ...] = ()) -> tuple[Evidence, ...]:
        """Use target-bar VSA evidence, otherwise the latest recent VSA event."""
        if bar_index is None:
            return ()
        earliest_bar_index = min((item.bar_index for item in qualifying_evidence), default=None)
        for candidate_bar in range(bar_index, max(-1, bar_index - cls.SCORING_LOOKBACK_BARS - 1), -1):
            evidence = cls._meaningful_vsa_evidence(current, candidate_bar, earliest_bar_index=earliest_bar_index)
            if evidence:
                return evidence
        return ()

    @staticmethod
    def _scoring_bar_index(evidence: tuple[Evidence, ...]) -> int | None:
        return max((item.bar_index for item in evidence), default=None)

    @classmethod
    def _vsa_confirmation_is_current(cls, scoring_evidence: tuple[Evidence, ...], bar_index: int | None) -> bool:
        """Require directional VSA confirmation to be close enough to the target bar."""
        if bar_index is None or not scoring_evidence:
            return False
        scoring_bar_index = max(item.bar_index for item in scoring_evidence)
        return 0 <= bar_index - scoring_bar_index <= cls.MAX_ACTIONABLE_VSA_AGE

    @staticmethod
    def _qualifying_evidence(history, qualification: PatternQualificationResult) -> tuple[Evidence, ...]:
        if not qualification.evidence_codes or not qualification.evidence_bar_indices:
            return ()
        wanted = set(zip(qualification.evidence_bar_indices, qualification.evidence_codes))
        selected: list[Evidence] = []
        seen: set[tuple[int, object]] = set()
        for result in history:
            for item in result.evidence:
                key = (item.bar_index, item.code)
                if key in wanted and key not in seen:
                    selected.append(item)
                    seen.add(key)
        selected.sort(key=lambda item: item.bar_index)
        return tuple(selected)

    @staticmethod
    def _qualification_is_current(qualification: PatternQualificationResult, bar_index: int | None) -> bool:
        if not qualification.is_actionable_evidence:
            return False
        if bar_index is None:
            return True
        return bool(qualification.evidence_bar_indices) and max(qualification.evidence_bar_indices) == bar_index

    @staticmethod
    def _invalidate_stale_qualification(qualification: PatternQualificationResult) -> PatternQualificationResult:
        return PatternQualificationResult(
            qualification=qualification.qualification,
            is_actionable_evidence=False,
            reason="Historical persistence was validated, but no qualifying structural progression event occurred on the target bar.",
            evidence_codes=qualification.evidence_codes,
            evidence_bar_indices=qualification.evidence_bar_indices,
        )

    @classmethod
    def _vsa_directional_evidence(cls, scoring_evidence: tuple[Evidence, ...]) -> tuple[tuple[Evidence, ...], tuple[Evidence, ...]]:
        bullish = tuple(item for item in scoring_evidence if item.code in cls._BULLISH_VSA_CODES)
        bearish = tuple(item for item in scoring_evidence if item.code in cls._BEARISH_VSA_CODES)
        return bullish, bearish

    @classmethod
    def _vsa_conflicts_with_qualification(cls, qualification: PatternQualificationResult, professional: ProfessionalScoreResult, scoring_evidence: tuple[Evidence, ...]) -> bool:
        if not qualification.is_actionable_evidence or not scoring_evidence:
            return False
        bullish, bearish = cls._vsa_directional_evidence(scoring_evidence)
        pressure = professional.scores.net_pressure
        if qualification.qualification is PatternQualification.PERSISTENT_BULLISH:
            return bool(bearish) or (not bullish and pressure < 0.0)
        if qualification.qualification is PatternQualification.PERSISTENT_BEARISH:
            return bool(bullish) or (not bearish and pressure > 0.0)
        return False

    @classmethod
    def _vsa_supports_qualification(cls, qualification: PatternQualificationResult, scoring_evidence: tuple[Evidence, ...]) -> bool:
        if not qualification.is_actionable_evidence:
            return False
        bullish, bearish = cls._vsa_directional_evidence(scoring_evidence)
        if qualification.qualification is PatternQualification.PERSISTENT_BULLISH:
            return bool(bullish) and not bearish
        if qualification.qualification is PatternQualification.PERSISTENT_BEARISH:
            return bool(bearish) and not bullish
        return False

    @staticmethod
    def _invalidate_vsa_conflict(qualification: PatternQualificationResult, professional: ProfessionalScoreResult) -> PatternQualificationResult:
        direction = "bullish" if qualification.qualification is PatternQualification.PERSISTENT_BULLISH else "bearish"
        pressure = professional.scores.net_pressure
        side = "supply" if pressure < 0.0 else "demand"
        return PatternQualificationResult(
            qualification=qualification.qualification,
            is_actionable_evidence=False,
            reason=f"Persistent {direction} structure is contradicted by current VSA {side} pressure or opposing VSA evidence (net pressure={pressure:.3f}).",
            evidence_codes=qualification.evidence_codes,
            evidence_bar_indices=qualification.evidence_bar_indices,
        )

    @staticmethod
    def _invalidate_missing_vsa_confirmation(qualification: PatternQualificationResult) -> PatternQualificationResult:
        direction = "bullish" if qualification.qualification is PatternQualification.PERSISTENT_BULLISH else "bearish"
        return PatternQualificationResult(
            qualification=qualification.qualification,
            is_actionable_evidence=False,
            reason=f"Persistent {direction} structure is validated, but no directional VSA confirmation is present in the current scoring window.",
            evidence_codes=qualification.evidence_codes,
            evidence_bar_indices=qualification.evidence_bar_indices,
        )

    @staticmethod
    def _invalidate_stale_vsa_confirmation(qualification: PatternQualificationResult, age: int) -> PatternQualificationResult:
        direction = "bullish" if qualification.qualification is PatternQualification.PERSISTENT_BULLISH else "bearish"
        return PatternQualificationResult(
            qualification=qualification.qualification,
            is_actionable_evidence=False,
            reason=f"Persistent {direction} structure is validated, but the supporting VSA evidence is {age} bars old and exceeds the maximum actionable age of {ScannerEngine.MAX_ACTIONABLE_VSA_AGE} bars.",
            evidence_codes=qualification.evidence_codes,
            evidence_bar_indices=qualification.evidence_bar_indices,
        )

    def evaluate(self, *, trend: TrendResult, evidence: EvidenceResult, history, bar_index: int | None = None, week: str | None = None) -> ScannerCandidate:
        qualification = self._qualification.evaluate(history)
        if not self._qualification_is_current(qualification, bar_index) and qualification.is_actionable_evidence:
            qualification = self._invalidate_stale_qualification(qualification)

        target_bar_evidence = self._target_bar_evidence(evidence, bar_index)
        campaign_evidence = self._campaign_evidence(evidence)
        qualifying_evidence = self._qualifying_evidence(history, qualification)
        scoring_evidence = self._scoring_evidence(evidence, bar_index, qualifying_evidence)

        professional = self._professional.calculate(
            trend=trend,
            evidence=EvidenceResult(context=evidence.context, evidence=scoring_evidence),
        )

        if qualification.is_actionable_evidence:
            scoring_bar_index = self._scoring_bar_index(scoring_evidence)
            if scoring_bar_index is None:
                qualification = self._invalidate_missing_vsa_confirmation(qualification)
            else:
                scoring_age = bar_index - scoring_bar_index if bar_index is not None else None
                if scoring_age is not None and scoring_age > self.MAX_ACTIONABLE_VSA_AGE:
                    qualification = self._invalidate_stale_vsa_confirmation(qualification, scoring_age)
                elif self._vsa_conflicts_with_qualification(qualification, professional, scoring_evidence):
                    qualification = self._invalidate_vsa_conflict(qualification, professional)
                elif not self._vsa_supports_qualification(qualification, scoring_evidence):
                    qualification = self._invalidate_missing_vsa_confirmation(qualification)

        scoring_bar_index = self._scoring_bar_index(scoring_evidence)
        return ScannerCandidate(
            evidence=evidence,
            professional=professional,
            qualification_result=qualification,
            target_bar_evidence=target_bar_evidence,
            campaign_evidence=campaign_evidence,
            qualifying_evidence=qualifying_evidence,
            scoring_evidence=scoring_evidence,
            scoring_bar_index=scoring_bar_index,
            scoring_evidence_age=(None if scoring_bar_index is None or bar_index is None else bar_index - scoring_bar_index),
            used_fallback_evidence=(scoring_bar_index is not None and bar_index is not None and scoring_bar_index != bar_index),
            bar_index=bar_index,
            week=week,
        )

    @staticmethod
    def _week_at(metrics: pd.DataFrame, index: int) -> str | None:
        value = metrics.iloc[index].get("week_beginning")
        if value is None or pd.isna(value):
            return None
        return str(value)

    def scan_to_index(self, metrics: pd.DataFrame, target_index: int) -> ScannerCandidate:
        if target_index < self.MIN_REPLAY_BARS:
            raise ValueError(f"target_index must be >= {self.MIN_REPLAY_BARS}")
        if target_index >= len(metrics):
            raise IndexError("target_index is outside metrics")
        history = []
        current_trend = None
        current_evidence = None
        for index in range(self.MIN_REPLAY_BARS, target_index + 1):
            replay = metrics.iloc[: index + 1].copy()
            trend = TrendAnalyzer().analyze(replay)
            structural_swings = list(trend.structure.structural_swings)
            evidence = EvidenceEngine().collect(metrics=replay, trend=trend, structural_swings=structural_swings)
            history.append(evidence)
            current_trend = trend
            current_evidence = evidence
        assert current_trend is not None
        assert current_evidence is not None
        return self.evaluate(trend=current_trend, evidence=current_evidence, history=history, bar_index=target_index, week=self._week_at(metrics, target_index))

    def scan(self, metrics: pd.DataFrame) -> list[ScannerCandidate]:
        history = []
        candidates = []
        for index in range(self.MIN_REPLAY_BARS, len(metrics)):
            replay = metrics.iloc[: index + 1].copy()
            trend = TrendAnalyzer().analyze(replay)
            structural_swings = list(trend.structure.structural_swings)
            evidence = EvidenceEngine().collect(metrics=replay, trend=trend, structural_swings=structural_swings)
            history.append(evidence)
            candidates.append(self.evaluate(trend=trend, evidence=evidence, history=history, bar_index=index, week=self._week_at(metrics, index)))
        return candidates

    def scan_actionable(self, metrics: pd.DataFrame) -> list[ScannerCandidate]:
        return rank_actionable_candidates(self.scan(metrics))
