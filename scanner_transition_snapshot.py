from __future__ import annotations

from dataclasses import replace

import pandas as pd

from market_structure.swing_engine import SwingEngine
from scanner import ScannerEngine
from scanner_state import (
    SCANNER_STATE_SCHEMA_VERSION,
    ScannerState,
    StructuralEventState,
    stamp_scanner_state,
)
from scanner_transition import ScanState, ScannerTransitionEngine


class ScannerTransitionSnapshotAdapter:
    """Build durable scanner snapshots through the transition path.

    Snapshot parity with ``IncrementalScannerEngine.snapshot(...)`` was established
    before this adapter became the production snapshot-refresh boundary.
    """

    def __init__(self, transition: ScannerTransitionEngine | None = None) -> None:
        self._transition = transition or ScannerTransitionEngine()
        self._scanner = ScannerEngine()

    @staticmethod
    def _snapshot_swing_state(
        metrics_prefix: pd.DataFrame,
        *,
        symbol: str,
        timeframe: str,
    ) -> ScannerState:
        swing_engine = SwingEngine()
        swing_engine.calculate(metrics_prefix)
        return swing_engine.snapshot_state(symbol=symbol, timeframe=timeframe)

    @staticmethod
    def _structural_events_from_transition(
        transition_state: ScanState,
    ) -> tuple[StructuralEventState, ...]:
        captured: dict[tuple[str, object], StructuralEventState] = {}
        for result in transition_state.history:
            for item in result.evidence:
                captured[(str(item.week_beginning), item.code)] = (
                    StructuralEventState.from_evidence(item)
                )

        return tuple(
            captured[key]
            for key in sorted(captured, key=lambda value: (value[0], str(value[1])))
        )

    def _validate_target_index(
        self,
        metrics: pd.DataFrame,
        target_index: int,
    ) -> None:
        if target_index < self._scanner.MIN_REPLAY_BARS:
            raise ValueError(
                f"target_index must be >= {self._scanner.MIN_REPLAY_BARS}"
            )
        if target_index >= len(metrics):
            raise IndexError("target_index is outside metrics")

    def snapshot_from_transition_state(
        self,
        metrics: pd.DataFrame,
        *,
        target_index: int,
        symbol: str,
        timeframe: str,
        transition_state: ScanState,
    ) -> ScannerState:
        """Return a durable snapshot from an already-replayed transition state.

        This keeps snapshot creation point-in-time while letting production
        bootstrap/fallback reuse the transition replay that produced the latest
        candidate instead of replaying the same bars a second time.
        """

        self._validate_target_index(metrics, target_index)
        if transition_state.last_bar_index != target_index:
            raise ValueError("transition state must end at target_index")

        prefix = metrics.iloc[: target_index + 1].copy()
        swing_state = self._snapshot_swing_state(
            prefix,
            symbol=symbol,
            timeframe=timeframe,
        )
        state = replace(
            swing_state,
            schema_version=SCANNER_STATE_SCHEMA_VERSION,
            structural_events=self._structural_events_from_transition(
                transition_state,
            ),
        )
        return stamp_scanner_state(state, prefix)

    def snapshot(
        self,
        metrics: pd.DataFrame,
        *,
        target_index: int,
        symbol: str,
        timeframe: str,
    ) -> ScannerState:
        """Return a durable scanner snapshot for ``target_index``.

        The transition path is replayed only through ``target_index``. Future bars
        are deliberately excluded from the metrics prefix so the snapshot remains
        point-in-time and compatible with the existing production state contract.
        """

        self._validate_target_index(metrics, target_index)
        prefix = metrics.iloc[: target_index + 1].copy()
        transition_state, _ = self._transition.run_to_index(
            prefix,
            target_index,
        )
        return self.snapshot_from_transition_state(
            prefix,
            target_index=target_index,
            symbol=symbol,
            timeframe=timeframe,
            transition_state=transition_state,
        )


__all__ = ["ScannerTransitionSnapshotAdapter"]
