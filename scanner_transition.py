from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from background.qualification import (
    PatternQualificationEngine,
    PatternQualificationState,
)
from engine.columns import COL_WEEK
from evidence.engine import EvidenceEngine
from model.evidence_result_model import EvidenceResult
from models import Evidence
from scanner import ScannerCandidate, ScannerEngine
from trend import TrendAnalyzer, TrendResult


@dataclass(frozen=True, slots=True)
class MarketBar:
    """Stable identity for one scanner transition bar.

    This contract object is intentionally small. It gives the future transition
    engine a row-independent bar identity without changing the current scanner
    execution path.
    """

    index: int
    week: str | None


@dataclass(frozen=True, slots=True)
class BarFeatures:
    """Feature snapshot consumed by one scanner transition.

    For the first transition-engine slice this holds the point-in-time metrics
    prefix used by the existing scanner engines. Later PRs can narrow this shape
    into immutable per-bar features without changing callers that depend on the
    step contract.
    """

    metrics_prefix: pd.DataFrame


@dataclass(frozen=True, slots=True)
class ScanState:
    """Deterministic scanner state carried between step calls.

    ``history`` temporarily mirrors the existing scanner qualification history
    so scanner semantics remain unchanged during migration. ``qualification`` is
    now first-class causal state and is advanced independently from that legacy
    history. Later M2 PRs can remove the synthetic history dependency after the
    M1 equivalence contract proves parity.
    """

    last_bar_index: int | None = None
    history: tuple[EvidenceResult, ...] = ()
    qualification: PatternQualificationState = PatternQualificationState()

    def with_step(
        self,
        bar_index: int,
        structural_evidence: EvidenceResult,
        qualification: PatternQualificationState,
    ) -> "ScanState":
        return ScanState(
            last_bar_index=bar_index,
            history=(*self.history, structural_evidence),
            qualification=qualification,
        )


@dataclass(frozen=True, slots=True)
class BarEvaluation:
    """Output of one deterministic scanner step."""

    bar: MarketBar
    trend: TrendResult
    evidence: EvidenceResult
    structural_evidence: EvidenceResult
    candidate: ScannerCandidate


class ScannerTransitionEngine:
    """Small deterministic step adapter over the existing scanner pipeline.

    The transition runner is now the shared scanner boundary behind production
    full replay/fallback, production resume, snapshot refresh, historical, and
    audit paths. It preserves current scanner semantics while exposing explicit
    sequential state seams for safe optimization.
    """

    def __init__(self, scanner: ScannerEngine | None = None) -> None:
        self._scanner = scanner or ScannerEngine()
        self._qualification = PatternQualificationEngine()

    @staticmethod
    def bar_for(metrics: pd.DataFrame, index: int) -> MarketBar:
        if index < 0 or index >= len(metrics):
            raise IndexError("bar index is outside metrics")
        value = metrics.iloc[index].get(COL_WEEK)
        week = None if value is None or pd.isna(value) else str(value)
        return MarketBar(index=index, week=week)

    @staticmethod
    def features_for(metrics: pd.DataFrame, index: int) -> BarFeatures:
        if index < 0 or index >= len(metrics):
            raise IndexError("bar index is outside metrics")
        return BarFeatures(metrics_prefix=metrics.iloc[: index + 1].copy())

    @staticmethod
    def _structural_evidence(evidence: EvidenceResult) -> tuple[Evidence, ...]:
        return tuple(
            item
            for item in evidence.evidence
            if item.code in ScannerEngine._STRUCTURAL_CODES
        )

    def step(
        self,
        state: ScanState,
        bar: MarketBar,
        features: BarFeatures,
        *,
        metrics: pd.DataFrame,
    ) -> tuple[ScanState, BarEvaluation]:
        """Advance the scanner by exactly one bar.

        The method is deliberately sequential. A caller must provide the next bar
        after `state.last_bar_index`, which prevents accidental gaps and keeps the
        future runner contract deterministic.
        """

        if bar.index < self._scanner.MIN_REPLAY_BARS:
            raise ValueError(
                f"bar index must be >= {self._scanner.MIN_REPLAY_BARS}"
            )
        if bar.index >= len(metrics):
            raise IndexError("bar index is outside metrics")
        if state.last_bar_index is not None and bar.index != state.last_bar_index + 1:
            raise ValueError("scanner transition steps must be sequential")
        if len(features.metrics_prefix) != bar.index + 1:
            raise ValueError("bar features must contain the point-in-time metrics prefix")

        trend = TrendAnalyzer().analyze(features.metrics_prefix)
        structural_swings = list(trend.structure.structural_swings)
        evidence = EvidenceEngine().collect(
            metrics=features.metrics_prefix,
            trend=trend,
            structural_swings=structural_swings,
        )
        structural = EvidenceResult(
            context=evidence.context,
            evidence=self._structural_evidence(evidence),
        )
        qualification = self._qualification.advance(
            state.qualification,
            structural.evidence,
        )
        next_state = state.with_step(
            bar.index,
            structural,
            qualification,
        )

        # Candidate evaluation still uses the legacy history path in this PR.
        # M2/PR-B2 establishes first-class qualification state without changing
        # scanner decisions; a later guarded PR will remove the legacy dependency.
        candidate = self._scanner.evaluate(
            trend=trend,
            evidence=evidence,
            history=next_state.history,
            bar_index=bar.index,
            week=bar.week,
            execution_bar_index=self._scanner._next_bar_index(metrics, bar.index),
            execution_week=self._scanner._next_week_at(metrics, bar.index),
            signal_bar_anomaly=self._scanner._signal_bar_anomaly(metrics, bar.index),
        )
        return next_state, BarEvaluation(
            bar=bar,
            trend=trend,
            evidence=evidence,
            structural_evidence=structural,
            candidate=candidate,
        )

    def run_to_index(
        self,
        metrics: pd.DataFrame,
        target_index: int,
        *,
        state: ScanState | None = None,
    ) -> tuple[ScanState, BarEvaluation]:
        """Run sequential steps through `target_index` without production wiring."""

        if target_index < self._scanner.MIN_REPLAY_BARS:
            raise ValueError(
                f"target_index must be >= {self._scanner.MIN_REPLAY_BARS}"
            )
        if target_index >= len(metrics):
            raise IndexError("target_index is outside metrics")

        current_state = state or ScanState()
        start = (
            self._scanner.MIN_REPLAY_BARS
            if current_state.last_bar_index is None
            else current_state.last_bar_index + 1
        )
        evaluation: BarEvaluation | None = None
        for index in range(start, target_index + 1):
            current_state, evaluation = self.step(
                current_state,
                self.bar_for(metrics, index),
                self.features_for(metrics, index),
                metrics=metrics,
            )
        assert evaluation is not None
        return current_state, evaluation

    def scan_to_index(self, metrics: pd.DataFrame, target_index: int) -> ScannerCandidate:
        """Return the target candidate through the transition-runner path."""

        _, evaluation = self.run_to_index(metrics, target_index)
        return evaluation.candidate

    def scan_to_indices(
        self,
        metrics: pd.DataFrame,
        target_indices: Sequence[int],
    ) -> dict[int, ScannerCandidate]:
        """Return candidates for increasing targets using one transition state.

        This is the first suffix-reuse API over the transition runner. It keeps
        every step sequential and point-in-time while avoiding repeated replay
        from ``ScannerEngine.MIN_REPLAY_BARS`` for each independent target.
        """

        targets = tuple(target_indices)
        if not targets:
            return {}

        previous: int | None = None
        for target_index in targets:
            if previous is not None and target_index <= previous:
                raise ValueError("target_indices must be strictly increasing")
            if target_index < self._scanner.MIN_REPLAY_BARS:
                raise ValueError(
                    f"target_index must be >= {self._scanner.MIN_REPLAY_BARS}"
                )
            if target_index >= len(metrics):
                raise IndexError("target_index is outside metrics")
            previous = target_index

        state = ScanState()
        candidates: dict[int, ScannerCandidate] = {}
        for target_index in targets:
            state, evaluation = self.run_to_index(
                metrics,
                target_index,
                state=state,
            )
            candidates[target_index] = evaluation.candidate
        return candidates

    def scan(self, metrics: pd.DataFrame) -> list[ScannerCandidate]:
        """Return all transition-runner candidates without production wiring.

        This mirrors `ScannerEngine.scan()` so later PRs can switch one caller at
        a time after parity is proven by tests.
        """

        if len(metrics) <= self._scanner.MIN_REPLAY_BARS:
            return []

        state = ScanState()
        candidates: list[ScannerCandidate] = []
        for index in range(self._scanner.MIN_REPLAY_BARS, len(metrics)):
            state, evaluation = self.step(
                state,
                self.bar_for(metrics, index),
                self.features_for(metrics, index),
                metrics=metrics,
            )
            candidates.append(evaluation.candidate)
        return candidates

    def scan_actionable(self, metrics: pd.DataFrame) -> list[ScannerCandidate]:
        """Return latest actionable candidate through the transition runner."""

        if len(metrics) <= self._scanner.MIN_REPLAY_BARS:
            return []
        candidate = self.scan_to_index(metrics, len(metrics) - 1)
        return [candidate] if candidate.actionable else []


__all__ = [
    "BarEvaluation",
    "BarFeatures",
    "MarketBar",
    "ScanState",
    "ScannerTransitionEngine",
]
