from __future__ import annotations

from dataclasses import dataclass

from background.qualification import PatternQualification, PatternQualificationResult


@dataclass(frozen=True, slots=True)
class VSAFreshnessPolicy:
    """Freshness limits for scanner scoring evidence."""

    scoring_lookback_bars: int = 10
    max_actionable_age: int = 3

    def age(
        self,
        *,
        scoring_bar_index: int | None,
        target_bar_index: int | None,
    ) -> int | None:
        if scoring_bar_index is None or target_bar_index is None:
            return None
        return target_bar_index - scoring_bar_index

    def is_current(
        self,
        *,
        scoring_bar_index: int | None,
        target_bar_index: int | None,
    ) -> bool:
        age = self.age(
            scoring_bar_index=scoring_bar_index,
            target_bar_index=target_bar_index,
        )
        return age is not None and 0 <= age <= self.max_actionable_age


@dataclass(frozen=True, slots=True)
class CandidateActionabilityPolicy:
    """Final production candidate actionability gate."""

    def is_actionable(
        self,
        *,
        qualification: PatternQualificationResult,
        confidence: float,
        signal_bar_anomaly: bool,
    ) -> bool:
        return (
            qualification.is_actionable_evidence
            and confidence > 0.0
            and not signal_bar_anomaly
        )


@dataclass(frozen=True, slots=True)
class CandidateRankingPolicy:
    """Production ranking semantics for scanner candidates."""

    def score(
        self,
        *,
        qualification: PatternQualification,
        base_score: float,
    ) -> float:
        if qualification in (
            PatternQualification.PERSISTENT_BULLISH,
            PatternQualification.PERSISTENT_BEARISH,
        ):
            return abs(base_score)
        return base_score

    @staticmethod
    def sort_key(
        *,
        actionable: bool,
        ranking_score: float,
    ) -> tuple[bool, float]:
        return actionable, ranking_score


@dataclass(frozen=True, slots=True)
class CandidateExecutionPolicy:
    """Signal/execution separation semantics exposed by ScannerCandidate."""

    @staticmethod
    def is_available(*, execution_bar_index: int | None) -> bool:
        return execution_bar_index is not None

    def is_pending(
        self,
        *,
        actionable: bool,
        execution_bar_index: int | None,
    ) -> bool:
        return actionable and not self.is_available(
            execution_bar_index=execution_bar_index
        )

    def note(self, *, execution_bar_index: int | None) -> str:
        if self.is_available(execution_bar_index=execution_bar_index):
            return (
                "Evaluate execution only from the next bar/session after the "
                "signal bar."
            )
        return (
            "No execution bar is available yet; this is a setup signal, not a "
            "same-bar entry."
        )


DEFAULT_VSA_FRESHNESS_POLICY = VSAFreshnessPolicy()
DEFAULT_CANDIDATE_ACTIONABILITY_POLICY = CandidateActionabilityPolicy()
DEFAULT_CANDIDATE_RANKING_POLICY = CandidateRankingPolicy()
DEFAULT_CANDIDATE_EXECUTION_POLICY = CandidateExecutionPolicy()


__all__ = [
    "CandidateActionabilityPolicy",
    "CandidateExecutionPolicy",
    "CandidateRankingPolicy",
    "VSAFreshnessPolicy",
    "DEFAULT_CANDIDATE_ACTIONABILITY_POLICY",
    "DEFAULT_CANDIDATE_EXECUTION_POLICY",
    "DEFAULT_CANDIDATE_RANKING_POLICY",
    "DEFAULT_VSA_FRESHNESS_POLICY",
]
