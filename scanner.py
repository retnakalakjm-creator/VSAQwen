from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from background.qualification import (
    PatternQualification,
    PatternQualificationEngine,
    PatternQualificationResult,
)
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
    qualification_result: PatternQualificationResult = field(
        default_factory=lambda: PatternQualificationResult(
            qualification=PatternQualification.UNQUALIFIED,
            is_actionable_evidence=False,
            reason="No validated persistent structural qualification applies.",
        )
    )
    target_bar_evidence: tuple[Evidence, ...] = ()
    campaign_evidence: tuple[Evidence, ...] = ()
    qualifying_evidence: tuple[Evidence, ...] = ()
    scoring_evidence: tuple[Evidence, ...] = ()
    scoring_bar_index: int | None = None
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
        """Target-bar evidence codes; kept for backward compatibility."""
        return self.current_evidence_codes

    @property
    def current_evidence_codes(self) -> tuple[str, ...]:
        """Evidence observed exactly on the scanner target bar."""
        return tuple(str(item.code) for item in self.target_bar_evidence)

    @property
    def campaign_evidence_codes(self) -> tuple[str, ...]:
        """All evidence observed in the current replay/campaign window."""
        return tuple(str(item.code) for item in self.campaign_evidence)

    @property
    def target_bar_evidence_codes(self) -> tuple[str, ...]:
        """Explicit alias for target-bar evidence codes."""
        return self.current_evidence_codes

    @property
    def qualifying_evidence_codes(self) -> tuple[str, ...]:
        return tuple(str(item.code) for item in self.qualifying_evidence)

    @property
    def scoring_evidence_codes(self) -> tuple[str, ...]:
        return tuple(str(item.code) for item in self.scoring_evidence)


def rank_candidates(
    candidates: tuple[ScannerCandidate, ...] | list[ScannerCandidate],
) -> list[ScannerCandidate]:
    """
    Rank scanner candidates without discarding diagnostics.

    Qualification is the primary gate. Professional net strength is only
    used to rank candidates inside the same qualification class.
    """

    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.actionable,
            candidate.base_score,
        ),
        reverse=True,
    )


def rank_actionable_candidates(
    candidates: tuple[ScannerCandidate, ...] | list[ScannerCandidate],
) -> list[ScannerCandidate]:
    """Return only actionable candidates, ranked by professional strength."""

    return rank_candidates(
        [candidate for candidate in candidates if candidate.actionable]
    )


class ScannerEngine:
    """
    Point-in-time scanner pipeline.

    Evidence is collected from the current replay window only. Qualification
    is evaluated separately over the chronological history of point-in-time
    EvidenceResult snapshots, so structural persistence cannot be inferred
    from a single snapshot.
    """

    MIN_REPLAY_BARS = 20

    _STRUCTURAL_CODES = frozenset(
        {
            EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
            EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        }
    )

    def __init__(self) -> None:
        self._qualification = PatternQualificationEngine()
        self._professional = ProfessionalScoringEngine()

    @classmethod
    def _meaningful_vsa_evidence(
        cls,
        result: EvidenceResult,
        bar_index: int,
    ) -> tuple[Evidence, ...]:
        """Return only target-bar VSA observations, excluding structural markers."""

        return tuple(
            item
            for item in result.evidence
            if item.bar_index == bar_index
            and item.code not in cls._STRUCTURAL_CODES
        )

    @staticmethod
    def _target_bar_evidence(
        result: EvidenceResult,
        bar_index: int | None,
    ) -> tuple[Evidence, ...]:
        """Return every evidence observation generated on the target bar."""

        if bar_index is None:
            return ()
        return tuple(
            item
            for item in result.evidence
            if item.bar_index == bar_index
        )

    @staticmethod
    def _campaign_evidence(
        result: EvidenceResult,
    ) -> tuple[Evidence, ...]:
        """Return the complete evidence snapshot for the current replay window."""

        return tuple(result.evidence)

    @classmethod
    def _scoring_evidence(
        cls,
        current: EvidenceResult,
        bar_index: int | None,
    ) -> tuple[Evidence, ...]:
        """
        Select evidence for professional scoring from the target bar only.

        Historical evidence is intentionally never substituted here. Historical
        snapshots belong to persistence qualification, not current-bar scoring.
        Structural progression markers also never contribute directly to
        professional supply/demand/effort scoring.
        """

        if bar_index is None:
            return ()
        return cls._meaningful_vsa_evidence(current, bar_index)

    @staticmethod
    def _scoring_bar_index(
        evidence: tuple[Evidence, ...],
    ) -> int | None:
        if not evidence:
            return None
        return max(item.bar_index for item in evidence)

    @staticmethod
    def _qualifying_evidence(
        history: tuple[EvidenceResult, ...] | list[EvidenceResult],
        qualification: PatternQualificationResult,
    ) -> tuple[Evidence, ...]:
        """Return the exact evidence events used to qualify persistence."""

        if not qualification.evidence_codes or not qualification.evidence_bar_indices:
            return ()

        wanted = set(
            zip(
                qualification.evidence_bar_indices,
                qualification.evidence_codes,
            )
        )

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
    def _qualification_is_current(
        qualification: PatternQualificationResult,
        bar_index: int | None,
    ) -> bool:
        """Require the latest qualifying structural event to be the target bar."""

        if not qualification.is_actionable_evidence:
            return False
        if bar_index is None:
            return True
        if not qualification.evidence_bar_indices:
            return False
        return max(qualification.evidence_bar_indices) == bar_index

    @staticmethod
    def _invalidate_stale_qualification(
        qualification: PatternQualificationResult,
    ) -> PatternQualificationResult:
        return PatternQualificationResult(
            qualification=qualification.qualification,
            is_actionable_evidence=False,
            reason=(
                "Historical persistence was validated, but no qualifying "
                "structural progression event occurred on the target bar."
            ),
            evidence_codes=qualification.evidence_codes,
            evidence_bar_indices=qualification.evidence_bar_indices,
        )

    @staticmethod
    def _vsa_conflicts_with_qualification(
        qualification: PatternQualificationResult,
        professional: ProfessionalScoreResult,
        scoring_evidence: tuple[Evidence, ...],
    ) -> bool:
        """
        Detect a current-bar professional VSA pressure conflict.

        Structural qualification remains unchanged. A contradiction only
        affects actionability, and only when meaningful current-bar VSA evidence
        exists. Missing VSA evidence is therefore not treated as a conflict.
        """

        if not qualification.is_actionable_evidence or not scoring_evidence:
            return False

        if qualification.qualification is PatternQualification.PERSISTENT_BULLISH:
            return professional.scores.net_pressure < 0.0

        if qualification.qualification is PatternQualification.PERSISTENT_BEARISH:
            return professional.scores.net_pressure > 0.0

        return False

    @staticmethod
    def _invalidate_vsa_conflict(
        qualification: PatternQualificationResult,
    ) -> PatternQualificationResult:
        return PatternQualificationResult(
            qualification=qualification.qualification,
            is_actionable_evidence=False,
            reason=(
                "Structural qualification is valid, but current-bar professional "
                "VSA pressure contradicts the qualified direction."
            ),
            evidence_codes=qualification.evidence_codes,
            evidence_bar_indices=qualification.evidence_bar_indices,
        )

    def evaluate(
        self,
        *,
        trend: TrendResult,
        evidence: EvidenceResult,
        history: tuple[EvidenceResult, ...] | list[EvidenceResult],
        bar_index: int | None = None,
        week: str | None = None,
    ) -> ScannerCandidate:
        qualification = self._qualification.evaluate(history)

        if not self._qualification_is_current(qualification, bar_index):
            if qualification.is_actionable_evidence:
                qualification = self._invalidate_stale_qualification(qualification)

        target_bar_evidence = self._target_bar_evidence(
            evidence,
            bar_index,
        )
        campaign_evidence = self._campaign_evidence(evidence)
        qualifying_evidence = self._qualifying_evidence(
            history,
            qualification,
        )
        scoring_evidence = self._scoring_evidence(evidence, bar_index)
        professional = self._professional.calculate(
            trend=trend,
            evidence=EvidenceResult(
                context=evidence.context,
                evidence=scoring_evidence,
            ),
        )

        if self._vsa_conflicts_with_qualification(
            qualification,
            professional,
            scoring_evidence,
        ):
            qualification = self._invalidate_vsa_conflict(qualification)

        return ScannerCandidate(
            evidence=evidence,
            professional=professional,
            qualification_result=qualification,
            target_bar_evidence=target_bar_evidence,
            campaign_evidence=campaign_evidence,
            qualifying_evidence=qualifying_evidence,
            scoring_evidence=scoring_evidence,
            scoring_bar_index=self._scoring_bar_index(scoring_evidence),
            bar_index=bar_index,
            week=week,
        )

    @staticmethod
    def _week_at(metrics: pd.DataFrame, index: int) -> str | None:
        value = metrics.iloc[index].get("week_beginning")
        if value is None or pd.isna(value):
            return None
        return str(value)

    def scan_to_index(
        self,
        metrics: pd.DataFrame,
        target_index: int,
    ) -> ScannerCandidate:
        """
        Replay from the beginning through target_index and return its
        point-in-time scanner candidate.
        """

        if target_index < self.MIN_REPLAY_BARS:
            raise ValueError(
                f"target_index must be >= {self.MIN_REPLAY_BARS}"
            )
        if target_index >= len(metrics):
            raise IndexError("target_index is outside metrics")

        history: list[EvidenceResult] = []
        current_trend: TrendResult | None = None
        current_evidence: EvidenceResult | None = None

        for index in range(self.MIN_REPLAY_BARS, target_index + 1):
            replay = metrics.iloc[: index + 1].copy()
            trend = TrendAnalyzer().analyze(replay)
            structural_swings = list(trend.structure.structural_swings)
            evidence = EvidenceEngine().collect(
                metrics=replay,
                trend=trend,
                structural_swings=structural_swings,
            )

            history.append(evidence)
            current_trend = trend
            current_evidence = evidence

        assert current_trend is not None
        assert current_evidence is not None

        return self.evaluate(
            trend=current_trend,
            evidence=current_evidence,
            history=history,
            bar_index=target_index,
            week=self._week_at(metrics, target_index),
        )

    def scan(
        self,
        metrics: pd.DataFrame,
    ) -> list[ScannerCandidate]:
        """Scan every eligible bar while preserving chronological evidence."""

        history: list[EvidenceResult] = []
        candidates: list[ScannerCandidate] = []

        for index in range(self.MIN_REPLAY_BARS, len(metrics)):
            replay = metrics.iloc[: index + 1].copy()
            trend = TrendAnalyzer().analyze(replay)
            structural_swings = list(trend.structure.structural_swings)
            evidence = EvidenceEngine().collect(
                metrics=replay,
                trend=trend,
                structural_swings=structural_swings,
            )

            history.append(evidence)
            candidates.append(
                self.evaluate(
                    trend=trend,
                    evidence=evidence,
                    history=history,
                    bar_index=index,
                    week=self._week_at(metrics, index),
                )
            )

        return candidates

    def scan_actionable(
        self,
        metrics: pd.DataFrame,
    ) -> list[ScannerCandidate]:
        """Scan all eligible bars and return only actionable candidates."""

        return rank_actionable_candidates(self.scan(metrics))
