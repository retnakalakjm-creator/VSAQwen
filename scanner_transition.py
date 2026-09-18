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
from models import Evidence, StructuralSwing
from scanner import ScannerCandidate, ScannerEngine
from market_structure.structure_filter import StructureFilter
from market_structure.swing_engine import SwingEngine
from scanner_state import ScannerState, StructuralEventState
from scanner_state_evaluation import evaluate_from_qualification_state
from trend import TrendAnalyzer, TrendResult


@dataclass(frozen=True, slots=True)
class MarketBar:
    """Stable identity for one scanner transition bar."""

    index: int
    week: str | None


@dataclass(frozen=True, slots=True)
class BarFeatures:
    """Feature snapshot consumed by one scanner transition."""

    metrics_prefix: pd.DataFrame


@dataclass(frozen=True, slots=True)
class ScanState:
    """Deterministic causal scanner state carried between step calls.

    Qualification and structural progression are now explicit state. The
    transition path no longer retains synthetic ``EvidenceResult`` history merely
    to satisfy candidate qualification.
    """

    last_bar_index: int | None = None
    qualification: PatternQualificationState = PatternQualificationState()
    structural_events: tuple[StructuralEventState, ...] = ()
    swing_state: ScannerState | None = None
    structural_swings: tuple[StructuralSwing, ...] = ()
    structural_scored_swing_count: int = 0

    def with_step(
        self,
        bar_index: int,
        qualification: PatternQualificationState,
        structural_events: tuple[StructuralEventState, ...],
        swing_state: ScannerState,
        structural_swings: tuple[StructuralSwing, ...],
        structural_scored_swing_count: int,
    ) -> "ScanState":
        return ScanState(
            last_bar_index=bar_index,
            qualification=qualification,
            structural_events=structural_events,
            swing_state=swing_state,
            structural_swings=structural_swings,
            structural_scored_swing_count=structural_scored_swing_count,
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
    """Deterministic step adapter over the existing scanner pipeline.

    Historical, production-resume, snapshot, audit, and replay callers share this
    sequential boundary. Candidate evaluation now consumes explicit causal
    qualification state rather than reconstructed replay history.
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
        # The transition pipeline treats feature prefixes as read-only. Use a
        # shallow frame copy so each step gets an isolated DataFrame object
        # without duplicating the underlying column buffers on every replay bar.
        return BarFeatures(
            metrics_prefix=metrics.iloc[: index + 1].copy(deep=False)
        )

    @staticmethod
    def _structural_evidence(evidence: EvidenceResult) -> tuple[Evidence, ...]:
        return tuple(
            item
            for item in evidence.evidence
            if item.code in ScannerEngine._STRUCTURAL_CODES
        )

    @staticmethod
    def _advance_structural_events(
        current: tuple[StructuralEventState, ...],
        evidence: tuple[Evidence, ...],
    ) -> tuple[StructuralEventState, ...]:
        """Advance durable structural-event state without replay-history coupling."""

        captured: dict[tuple[str, object], StructuralEventState] = {
            (item.bar_key, item.code): item for item in current
        }
        for item in evidence:
            event = StructuralEventState.from_evidence(item)
            captured[(event.bar_key, event.code)] = event
        return tuple(
            captured[key]
            for key in sorted(captured, key=lambda value: (value[0], str(value[1])))
        )

    def step(
        self,
        state: ScanState,
        bar: MarketBar,
        features: BarFeatures,
        *,
        metrics: pd.DataFrame,
    ) -> tuple[ScanState, BarEvaluation]:
        """Advance the scanner by exactly one bar."""

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

        swing_engine = SwingEngine()
        if state.swing_state is None:
            swings = swing_engine.calculate(features.metrics_prefix)
        else:
            if state.last_bar_index is None:
                raise ValueError("swing state requires last_bar_index")
            expected_week = self.bar_for(metrics, state.last_bar_index).week
            if str(state.swing_state.last_closed_bar) != str(expected_week):
                raise ValueError(
                    "scanner transition swing state does not match last_bar_index"
                )
            swings = swing_engine.calculate_from_state(
                features.metrics_prefix,
                state.swing_state,
            )
        swing_state = swing_engine.snapshot_state(
            symbol="__TRANSITION__",
            timeframe="1wk",
        )

        previous_swing_count = (
            0
            if state.swing_state is None
            else len(state.swing_state.confirmed_swings)
        )
        structure_filter = StructureFilter()
        if state.structural_scored_swing_count == previous_swing_count:
            structural_swings = structure_filter.filter_incremental(
                swings,
                features.metrics_prefix,
                cached=state.structural_swings,
                previous_swing_count=previous_swing_count,
            )
        else:
            # Durable ScannerState does not persist professional structural
            # evaluations. Rebuild them once after resume, then reuse them on
            # subsequent transition bars.
            structural_swings = structure_filter.filter(
                list(swings),
                features.metrics_prefix,
            )

        trend = TrendAnalyzer().analyze_from_swings(
            features.metrics_prefix,
            swings,
            structural_swings=structural_swings,
        )
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
        structural_events = self._advance_structural_events(
            state.structural_events,
            structural.evidence,
        )
        next_state = state.with_step(
            bar.index,
            qualification,
            structural_events,
            swing_state,
            tuple(structural_swings),
            len(swings),
        )

        candidate = evaluate_from_qualification_state(
            self._scanner,
            self._qualification,
            trend=trend,
            evidence=evidence,
            qualification_state=next_state.qualification,
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
        """Return candidates for increasing targets using one transition state."""

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
        """Return all transition-runner candidates without production wiring."""

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
