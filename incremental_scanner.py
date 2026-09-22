from __future__ import annotations

import pandas as pd
import config

from engine.columns import COL_CORPORATE_ACTION_ANOMALY
from market_structure.incremental_trend import IncrementalTrendAnalyzer
from market_structure.progression import calculate_professional_progression
from market_structure.swing_engine import SwingEngine
from models import Evidence, EvidenceCode, EvidenceCategory, EvidenceDirection
from scanner import ScannerCandidate, ScannerEngine
from scanner_state import (
    ScannerState,
    StructuralEventState,
)
from scanner_transition_resume import ScannerTransitionResumeAdapter
from scanner_transition_snapshot import ScannerTransitionSnapshotAdapter


class IncrementalScannerEngine:
    """Resume production scanning from causal scanner state."""

    def __init__(self) -> None:
        self._scanner = ScannerEngine()
        self._trend = IncrementalTrendAnalyzer()

    @staticmethod
    def _events_to_evidence(metrics: pd.DataFrame, events: tuple[StructuralEventState, ...]) -> tuple[Evidence, ...]:
        index_by_week = {str(v): i for i, v in enumerate(metrics["week_beginning"])}
        return tuple(event.to_evidence(index_by_week[event.bar_key]) for event in events if event.bar_key in index_by_week)

    @staticmethod
    def _capture_events(structural_swings, metrics: pd.DataFrame) -> tuple[StructuralEventState, ...]:
        captured: dict[tuple[str, EvidenceCode], StructuralEventState] = {}
        for end in range(6, len(structural_swings) + 1):
            prefix = tuple(structural_swings[:end])
            _, difference = calculate_professional_progression(prefix)
            if difference is None or abs(difference) < config.PROGRESSION_NEUTRAL_MARGIN:
                continue
            current = prefix[-1].swing
            confirmation_index = current.confirmation_index
            code = EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING if difference >= config.PROGRESSION_NEUTRAL_MARGIN else EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING
            direction = EvidenceDirection.BULLISH if code == EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING else EvidenceDirection.BEARISH
            evidence = Evidence(
                code=code,
                category=EvidenceCategory.TREND,
                direction=direction,
                strength=min(abs(difference) * 5, 1.0),
                weight=1.0,
                observation=("Professional structural progression improving" if direction == EvidenceDirection.BULLISH else "Professional structural progression weakening"),
                description=("Recent structural swing quality is stronger than the previous campaign." if direction == EvidenceDirection.BULLISH else "Recent structural swing quality is weaker than the previous campaign."),
                bar_index=confirmation_index,
                week_beginning=str(metrics.iloc[confirmation_index]["week_beginning"]),
            )
            captured[(evidence.week_beginning, code)] = StructuralEventState.from_evidence(evidence)
        return tuple(captured[key] for key in sorted(captured, key=lambda value: (value[0], str(value[1]))))

    @staticmethod
    def _signal_bar_anomaly(metrics: pd.DataFrame, index: int | None) -> bool:
        if index is None or index < 0 or index >= len(metrics):
            return False
        if COL_CORPORATE_ACTION_ANOMALY not in metrics.columns:
            return False

        value = metrics.iloc[index].get(COL_CORPORATE_ACTION_ANOMALY, False)
        if value is None:
            return False
        try:
            if pd.isna(value):
                return False
        except (TypeError, ValueError):
            return False
        return bool(value)

    @staticmethod
    def _snapshot_swing_state(
        metrics: pd.DataFrame,
        *,
        target_index: int,
        symbol: str,
        timeframe: str,
    ) -> ScannerState:
        prefix = metrics.iloc[: target_index + 1].copy()
        swing_engine = SwingEngine()
        swing_engine.calculate(prefix)
        return swing_engine.snapshot_state(symbol=symbol, timeframe=timeframe)

    def snapshot(self, metrics: pd.DataFrame, *, target_index: int, symbol: str, timeframe: str) -> ScannerState:
        """Build the canonical durable snapshot through the transition path."""

        return ScannerTransitionSnapshotAdapter().snapshot(
            metrics,
            target_index=target_index,
            symbol=symbol,
            timeframe=timeframe,
        )

    def resume_latest(self, metrics: pd.DataFrame, state: ScannerState) -> ScannerCandidate:
        """Resume using the canonical transition-state implementation."""

        return ScannerTransitionResumeAdapter().resume_latest(metrics, state)


__all__ = ["IncrementalScannerEngine"]
