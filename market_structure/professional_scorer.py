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
        self._metric_array_cache = None

        
    def _metric_arrays(self, metrics: pd.DataFrame):
        cached = self._metric_array_cache

        if cached is None or cached[0] is not metrics:
            cached = (
                metrics,
                metrics[COL_VOLUME].to_numpy(copy=False),
                metrics[COL_SPREAD].to_numpy(copy=False),
                metrics[COL_AVG_VOLUME].to_numpy(copy=False),
                metrics[COL_AVG_SPREAD].to_numpy(copy=False),
            )
            self._metric_array_cache = cached

        return cached[1], cached[2], cached[3], cached[4]
    
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

        volume, spread, avg_volume, avg_spread = (
            self._metric_arrays(metrics)
        )

        i = swing.metrics_index

        return SwingMetricSnapshot(
            volume=float(volume[i]),
            spread=float(spread[i]),
            avg_volume=float(avg_volume[i]),
            avg_spread=float(avg_spread[i]),
        )

    
        
    def _smart_money_snapshot(
        self,
        metrics: pd.DataFrame,
        swing: Swing,
        lookback: int = 3,
    ) -> SmartMoneySnapshot:

        end = swing.metrics_index + 1
        start = max(0, end - lookback)

        open_values = metrics[COL_OPEN].to_numpy(copy=False)
        high_values = metrics[COL_HIGH].to_numpy(copy=False)
        low_values = metrics[COL_LOW].to_numpy(copy=False)
        close_values = metrics[COL_CLOSE].to_numpy(copy=False)
        spread_values = metrics[COL_SPREAD].to_numpy(copy=False)
        avg_spread_values = metrics[COL_AVG_SPREAD].to_numpy(copy=False)
        volume_values = metrics[COL_VOLUME].to_numpy(copy=False)
        avg_volume_values = metrics[COL_AVG_VOLUME].to_numpy(copy=False)

        bars = tuple(
            SmartMoneyBar(
                open=float(open_values[index]),
                high=float(high_values[index]),
                low=float(low_values[index]),
                close=float(close_values[index]),
                spread=float(spread_values[index]),
                avg_spread=float(avg_spread_values[index]),
                volume=float(volume_values[index]),
                avg_volume=float(avg_volume_values[index]),
            )
            for index in range(start, end)
        )

        return SmartMoneySnapshot(
            bars=bars,
        )