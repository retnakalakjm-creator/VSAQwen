from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engine.columns import COL_WEEK
from evidence.engine import EvidenceEngine
from model.evidence_result_model import EvidenceResult
from scanner import ScannerCandidate, ScannerEngine
from scanner_state import ScannerState
from scanner_transition import ScanState, ScannerTransitionEngine
from trend import TrendAnalyzer


@dataclass(frozen=True, slots=True)
class TransitionResumeResult:
    """Result metadata for a scanner-state transition resume comparison."""

    candidate: ScannerCandidate
    checkpoint_index: int
    target_index: int
    resumed_bar_count: int


class ScannerTransitionResumeAdapter:
    """Resume durable ``ScannerState`` checkpoints through the transition runner.

    This adapter is the production resume boundary for validated checkpoints.
    Earlier guardrails established parity with
    ``IncrementalScannerEngine.resume_latest(...)`` before production resume was
    routed here.
    """

    def __init__(self, transition: ScannerTransitionEngine | None = None) -> None:
        self._transition = transition or ScannerTransitionEngine()
        self._scanner = ScannerEngine()

    @staticmethod
    def _index_by_week(metrics: pd.DataFrame) -> dict[str, int]:
        if COL_WEEK not in metrics.columns:
            raise ValueError("metrics must include week_beginning for transition resume")

        weeks = [str(value) for value in metrics[COL_WEEK]]
        if len(weeks) != len(set(weeks)):
            raise ValueError("current metrics contain duplicate checkpoint bar identities")
        return {week: index for index, week in enumerate(weeks)}

    @classmethod
    def _checkpoint_index(cls, metrics: pd.DataFrame, state: ScannerState) -> int:
        index_by_week = cls._index_by_week(metrics)
        checkpoint_index = index_by_week.get(state.last_closed_bar)
        if checkpoint_index is None:
            raise ValueError(
                f"ScannerState checkpoint bar is not present in current metrics: {state.last_closed_bar}"
            )
        return checkpoint_index

    @classmethod
    def _checkpoint_structural_history(
        cls,
        metrics: pd.DataFrame,
        state: ScannerState,
        *,
        checkpoint_index: int,
    ) -> tuple[EvidenceResult, ...]:
        if not state.structural_events:
            return ()

        index_by_week = cls._index_by_week(metrics)
        prefix = metrics.iloc[: checkpoint_index + 1].copy()
        trend = TrendAnalyzer().analyze(prefix)
        context = EvidenceEngine().collect(
            metrics=prefix,
            trend=trend,
            structural_swings=list(trend.structure.structural_swings),
        ).context
        evidence = tuple(
            event.to_evidence(index_by_week[event.bar_key])
            for event in state.structural_events
            if event.bar_key in index_by_week
        )
        if not evidence:
            return ()
        return (EvidenceResult(context=context, evidence=evidence),)

    def transition_state_from_scanner_state(
        self,
        metrics: pd.DataFrame,
        state: ScannerState,
    ) -> ScanState:
        """Convert durable production scanner state into transition ``ScanState``."""

        checkpoint_index = self._checkpoint_index(metrics, state)
        return ScanState(
            last_bar_index=checkpoint_index,
            history=self._checkpoint_structural_history(
                metrics,
                state,
                checkpoint_index=checkpoint_index,
            ),
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

        target_index = len(metrics) - 1
        if target_index < self._scanner.MIN_REPLAY_BARS:
            raise ValueError(
                f"target_index must be >= {self._scanner.MIN_REPLAY_BARS}"
            )

        checkpoint_index = self._checkpoint_index(metrics, state)
        if checkpoint_index > target_index:
            raise ValueError("ScannerState checkpoint is beyond current metrics")

        if checkpoint_index == target_index:
            candidate = self._transition.scan_to_index(metrics, target_index)
            return TransitionResumeResult(
                candidate=candidate,
                checkpoint_index=checkpoint_index,
                target_index=target_index,
                resumed_bar_count=0,
            )

        transition_state = self.transition_state_from_scanner_state(metrics, state)
        _, evaluation = self._transition.run_to_index(
            metrics,
            target_index,
            state=transition_state,
        )
        return TransitionResumeResult(
            candidate=evaluation.candidate,
            checkpoint_index=checkpoint_index,
            target_index=target_index,
            resumed_bar_count=target_index - checkpoint_index,
        )


__all__ = [
    "ScannerTransitionResumeAdapter",
    "TransitionResumeResult",
]
