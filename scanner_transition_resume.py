from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from background.qualification import PatternQualificationEngine
from engine.columns import COL_WEEK
from scanner import ScannerCandidate, ScannerEngine
from scanner_exceptions import (
    ScannerResumeCheckpointBeyondMetricsError,
    ScannerResumeCheckpointMissingError,
    ScannerResumeMetricsError,
)
from scanner_state import ScannerState
from scanner_transition import ScanState, ScannerTransitionEngine


@dataclass(frozen=True, slots=True)
class TransitionResumeResult:
    """Result metadata for a scanner-state transition resume comparison."""

    candidate: ScannerCandidate
    checkpoint_index: int
    target_index: int
    resumed_bar_count: int


@dataclass(frozen=True, slots=True)
class TransitionResumeStateResult:
    """Resume result carrying the transition state reached at the latest bar."""

    candidate: ScannerCandidate
    checkpoint_index: int
    target_index: int
    resumed_bar_count: int
    transition_state: ScanState


class ScannerTransitionResumeAdapter:
    """Resume durable ``ScannerState`` checkpoints through the transition runner."""

    def __init__(self, transition: ScannerTransitionEngine | None = None) -> None:
        self._transition = transition or ScannerTransitionEngine()
        self._scanner = ScannerEngine()
        self._qualification = PatternQualificationEngine()

    @staticmethod
    def _index_by_week(metrics: pd.DataFrame) -> dict[str, int]:
        if COL_WEEK not in metrics.columns:
            raise ScannerResumeMetricsError(
                "metrics must include week_beginning for transition resume"
            )

        weeks = [str(value) for value in metrics[COL_WEEK]]
        if len(weeks) != len(set(weeks)):
            raise ScannerResumeMetricsError(
                "current metrics contain duplicate checkpoint bar identities"
            )
        return {week: index for index, week in enumerate(weeks)}

    @classmethod
    def _checkpoint_index(cls, metrics: pd.DataFrame, state: ScannerState) -> int:
        index_by_week = cls._index_by_week(metrics)
        checkpoint_index = index_by_week.get(state.last_closed_bar)
        if checkpoint_index is None:
            raise ScannerResumeCheckpointMissingError(
                f"ScannerState checkpoint bar is not present in current metrics: {state.last_closed_bar}"
            )
        return checkpoint_index

    def transition_state_from_scanner_state(
        self,
        metrics: pd.DataFrame,
        state: ScannerState,
    ) -> ScanState:
        """Convert durable production scanner state into explicit transition state."""

        checkpoint_index = self._checkpoint_index(metrics, state)
        index_by_week = self._index_by_week(metrics)
        structural_evidence = tuple(
            event.to_evidence(index_by_week[event.bar_key])
            for event in state.structural_events
            if event.bar_key in index_by_week
        )
        return ScanState(
            last_bar_index=checkpoint_index,
            qualification=self._qualification.state_from_events(structural_evidence),
            structural_events=state.structural_events,
            swing_state=state,
        )

    def resume_latest(self, metrics: pd.DataFrame, state: ScannerState) -> ScannerCandidate:
        """Return the latest candidate by resuming the transition runner from state."""

        return self.resume_latest_with_metadata(metrics, state).candidate

    def resume_latest_with_metadata(
        self,
        metrics: pd.DataFrame,
        state: ScannerState,
    ) -> TransitionResumeResult:
        """Resume from ``state`` to the latest bar and return comparison metadata."""

        result = self.resume_latest_with_state(metrics, state)
        return TransitionResumeResult(
            candidate=result.candidate,
            checkpoint_index=result.checkpoint_index,
            target_index=result.target_index,
            resumed_bar_count=result.resumed_bar_count,
        )

    def resume_latest_with_state(
        self,
        metrics: pd.DataFrame,
        state: ScannerState,
    ) -> TransitionResumeStateResult:
        """Resume from ``state`` and return the transition state at latest bar."""

        target_index = len(metrics) - 1
        if target_index < self._scanner.MIN_REPLAY_BARS:
            raise ValueError(
                f"target_index must be >= {self._scanner.MIN_REPLAY_BARS}"
            )

        checkpoint_index = self._checkpoint_index(metrics, state)
        if checkpoint_index > target_index:
            raise ScannerResumeCheckpointBeyondMetricsError(
                "ScannerState checkpoint is beyond current metrics"
            )

        transition_state = self.transition_state_from_scanner_state(metrics, state)
        if checkpoint_index == target_index:
            candidate = self._transition.scan_to_index(metrics, target_index)
            return TransitionResumeStateResult(
                candidate=candidate,
                checkpoint_index=checkpoint_index,
                target_index=target_index,
                resumed_bar_count=0,
                transition_state=transition_state,
            )

        transition_state, evaluation = self._transition.run_to_index(
            metrics,
            target_index,
            state=transition_state,
        )
        return TransitionResumeStateResult(
            candidate=evaluation.candidate,
            checkpoint_index=checkpoint_index,
            target_index=target_index,
            resumed_bar_count=target_index - checkpoint_index,
            transition_state=transition_state,
        )


__all__ = [
    "ScannerTransitionResumeAdapter",
    "TransitionResumeResult",
    "TransitionResumeStateResult",
]
