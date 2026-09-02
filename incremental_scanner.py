from __future__ import annotations

from dataclasses import replace

import pandas as pd
import config

from evidence.engine import EvidenceEngine
from market_structure.progression import calculate_professional_progression
from market_structure.structure_filter import StructureFilter
from models import Evidence, EvidenceCode, EvidenceCategory, EvidenceDirection
from scanner import ScannerCandidate, ScannerEngine
from scanner_state import ScannerState, StructuralEventState, SCANNER_STATE_SCHEMA_VERSION
from model.evidence_result_model import EvidenceResult
from trend import TrendAnalyzer


class IncrementalScannerEngine:
    """Resume production scanning from causal scanner state."""

    def __init__(self) -> None:
        self._scanner = ScannerEngine()

    @staticmethod
    def _resume_trend(metrics: pd.DataFrame, state: ScannerState):
        analyzer = TrendAnalyzer()
        analyzer._reset(metrics)
        swings = list(analyzer._swing_engine.calculate_from_state(metrics, state))
        structural = StructureFilter().filter(swings, metrics)
        analyzer._classified_swings = analyzer._classify_swings(structural)
        analyzer._structural_swings = structural
        analyzer._create_structure()
        return analyzer._build_result()

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

    def snapshot(self, metrics: pd.DataFrame, *, target_index: int, symbol: str, timeframe: str) -> ScannerState:
        if target_index < self._scanner.MIN_REPLAY_BARS:
            raise ValueError(f"target_index must be >= {self._scanner.MIN_REPLAY_BARS}")
        if target_index >= len(metrics):
            raise IndexError("target_index is outside metrics")
        prefix = metrics.iloc[: target_index + 1].copy()
        analyzer = TrendAnalyzer()
        trend = analyzer.analyze(prefix)
        swing_state = analyzer._swing_engine.snapshot_state(symbol=symbol, timeframe=timeframe)
        return replace(
            swing_state,
            schema_version=SCANNER_STATE_SCHEMA_VERSION,
            structural_events=self._capture_events(trend.structure.structural_swings, prefix),
        )

    def resume_latest(self, metrics: pd.DataFrame, state: ScannerState) -> ScannerCandidate:
        weeks = [str(value) for value in metrics["week_beginning"]]
        if len(weeks) != len(set(weeks)):
            raise ValueError("current metrics contain duplicate checkpoint bar identities")
        index_by_week = {week: i for i, week in enumerate(weeks)}
        checkpoint_index = index_by_week.get(state.last_closed_bar)
        if checkpoint_index is None:
            raise ValueError(
                f"ScannerState checkpoint bar is not present in current metrics: {state.last_closed_bar}"
            )

        trend = self._resume_trend(metrics, state)
        evidence = EvidenceEngine().collect(metrics=metrics, trend=trend, structural_swings=tuple(trend.structure.structural_swings))

        new_events = self._capture_events(trend.structure.structural_swings, metrics)
        new_events = tuple(
            event
            for event in new_events
            if index_by_week.get(event.bar_key, -1) > checkpoint_index
        )

        events: dict[tuple[str, EvidenceCode], StructuralEventState] = {
            (event.bar_key, event.code): event for event in state.structural_events
        }
        events.update({(event.bar_key, event.code): event for event in new_events})
        ordered_events = tuple(events[key] for key in sorted(events, key=lambda value: (value[0], str(value[1]))))

        history = [
            EvidenceResult(
                context=evidence.context,
                evidence=self._events_to_evidence(metrics, ordered_events),
            ),
            evidence,
        ]
        return self._scanner.evaluate(
            trend=trend,
            evidence=evidence,
            history=history,
            bar_index=len(metrics) - 1,
            week=str(metrics.iloc[-1]["week_beginning"]),
        )
