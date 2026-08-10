from __future__ import annotations

import pandas as pd

from engine.columns import COL_AVG_SPREAD, COL_AVG_VOLUME, COL_CLOSE, COL_HIGH, COL_LOW, COL_OPEN, COL_SPREAD, COL_VOLUME
import config


from market_structure.swing_history import SwingHistoryAnalyzer

from models import (    
    SmartMoneyBar,
    SmartMoneySnapshot,
    Swing,
    SwingContext,
    SwingMetricSnapshot,
    SwingProfessionalEvaluation,
    SwingProfessionalScore,    
)
from .structural_swing_scorer import StructuralSwingScorer

from .smart_money import SmartMoneyAnalyzer


class ProfessionalScorer:
    
    def __init__(self) -> None:

        self._structure = StructuralSwingScorer(
            structure_lookback=config.STRUCTURE_LOOKBACK,
        )
        self._smart_money = SmartMoneyAnalyzer()
        
        
    def _build_context(
            self,
            history: SwingHistoryAnalyzer,
            metrics: pd.DataFrame,
            current: Swing,
        ) -> SwingContext:
    
            return SwingContext(
                swing=current,
                history=history.snapshot(
                    metrics,
                    config.STRUCTURE_LOOKBACK,
                ),
                metrics=self._metric_snapshot(
                    metrics,
                    current,
                ),  
            )
    
    
    def score(
        self,
        history: SwingHistoryAnalyzer,
        metrics: pd.DataFrame,
    ) -> SwingProfessionalEvaluation:

        current = history.current()

        ctx = self._build_context(
            history,
            metrics,
            current,
        )

        evaluation  = self._structure.score(ctx)

        snapshot  = self._smart_money_snapshot(
            metrics,
            current,
        )

        smart_money = self._smart_money.score(
            snapshot,
        )        
        
        professional_score = SwingProfessionalScore.create(
            evaluation.score,
            smart_money,
        )
        return SwingProfessionalEvaluation(
            structure=evaluation,
            smart_money=smart_money,
            professional=professional_score,
        )
    
    def _metric_snapshot(
        self,
        metrics: pd.DataFrame,
        swing: Swing,
    ) -> SwingMetricSnapshot:

        row = metrics.iloc[swing.metrics_index]

        return SwingMetricSnapshot(
            volume=float(row[COL_VOLUME]),
            spread=float(row[COL_SPREAD]),
            avg_volume=float(row[COL_AVG_VOLUME]),
            avg_spread=float(row[COL_AVG_SPREAD]),
        )
    
        
    def _smart_money_snapshot(
        self,
        metrics: pd.DataFrame,
        swing: Swing,
        lookback: int = 3,
    ) -> SmartMoneySnapshot:

        end = swing.metrics_index + 1
        start = max(0, end - lookback)

        rows = metrics.iloc[start:end]

        bars = tuple(
            SmartMoneyBar(
                open=float(row[COL_OPEN]),
                high=float(row[COL_HIGH]),
                low=float(row[COL_LOW]),
                close=float(row[COL_CLOSE]),
                spread=float(row[COL_SPREAD]),
                avg_spread=float(row[COL_AVG_SPREAD]),
                volume=float(row[COL_VOLUME]),
                avg_volume=float(row[COL_AVG_VOLUME]),
            )
            for _, row in rows.iterrows()
        )

        return SmartMoneySnapshot(
            bars=bars,
        )