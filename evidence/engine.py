"""
    Professional Market Evidence Engine.

    Produces the complete evidence-based market
    assessment used by the VSA Pattern Engine.

    Responsibilities
    ----------------
    • Supply analysis
    • Demand analysis
    • Effort vs Result analysis
    • Trend analysis
    • Wyckoff phase analysis
    • Evidence aggregation
    • Evidence scoring
    • Final EvidenceResult generation
    """


from __future__ import annotations

from background.structural_progression import collect_structural_progression

from evidence.campaign import has_selling_campaign
from evidence.demand import collect_demand
from evidence.evidence_registry import build_evidence
from evidence.rules import has_strong_spread, is_bearish_bar, is_strong_close, is_very_high_volume, makes_lower_low, volume_increasing
from evidence.weight import WeightCalculator
from market_structure.progression import determine_structural_pattern
from market_structure.vsa_context import build_vsa_context


from  .supply import collect_supply
from  .trend_context import collect_trend
from  .effort import collect_effort
import pandas as pd

import config

from engine.columns import (
    COL_AVG_VOLUME, COL_HIGH,COL_LOW, COL_PREV_SPREAD,COL_SPREAD,COL_CLOSE,
    COL_OPEN,COL_BODY,COL_SPREAD_RATIO, COL_STD_VOLUME, COL_VOLUME,
    COL_VOLUME_RATIO,COL_SPREAD_PERCENTILE,
    COL_VOLUME_PERCENTILE,COL_SPREAD_CLASS,COL_VOLUME_CLASS,
    COL_DIRECTION,COL_CLOSE_POSITION,
    COL_UPPER_SHADOW,COL_LOWER_SHADOW,
    COL_CLOSE_RATIO,COL_PRICE_CHANGE,
    COL_PRICE_CHANGE_PCT,COL_PREV_OPEN,
    COL_PREV_HIGH,COL_PREV_LOW,COL_PREV_CLOSE,
    COL_PREV_VOLUME,COL_AVG_SPREAD, COL_WEEK,   
)
from model.evidence_result_model import EvidenceResult
from models import (
    BackgroundContext,
    
    BarContext,
    ClosePosition,
    Direction,
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    MarketBias,
    SpreadClass,
    StructuralSwing,
    TrendResult,
    TrendStructure,
    VolumeClass,    
    WyckoffPhase,
)

class EvidenceEngine:
    """
    Produces the professional market background
    used by the VSA Pattern Engine.
    """

    def __init__(self) -> None:

        self._metrics: pd.DataFrame | None = None

        self._trend: TrendStructure | None = None
        
        self._ctx: BackgroundContext | None = None

        self._evidence: list[Evidence] = []   
        
        self._structural_swings: tuple[StructuralSwing, ...] = ()   
        
        


    
    # ==========================================================
    # Public API
    # ==========================================================
    def collect(
            self,
            metrics: pd.DataFrame,
            trend: TrendResult,
            structural_swings: tuple[StructuralSwing, ...],
            validation_metrics: pd.DataFrame | None = None,
    ) -> EvidenceResult:
        """
        Analyze the market background.
        """
        
        self._reset(
            metrics=metrics,
            trend=trend,
            structural_swings=structural_swings,
            validation_metrics=validation_metrics,
        )
        
        self._collect_supply()
        
        self._collect_demand()
        
        # self._collect_demand()
        # self._collect_no_demand()
        # self._collect_no_supply()
        # self._collect_test()
        # self._collect_upthrust()
        # self._collect_shakeout()
        #self._collect_buying_climax()

        # self._collect_demand()

        # self._collect_effort()

        # self._collect_trend()

        # self._collect_phase()
        
        self._collect_structural_progression()
        
        return self._finalize()        
    
    
    # ==========================================================
    # Initialization
    # ==========================================================
    def _reset(
        self,
        metrics: pd.DataFrame,
        trend: TrendResult,
        structural_swings: tuple[StructuralSwing, ...],
        validation_metrics: pd.DataFrame | None = None,
    ) -> None:

        self._metrics = metrics
        self._validation_metrics = (
            validation_metrics
            if validation_metrics is not None
            else metrics
        )

        self._trend = trend.structure
        self._structural_swings = structural_swings
        self._structural_pattern = determine_structural_pattern(
            self._trend.swings,
        )

        self._vsa_context = build_vsa_context(
            trend=self._trend,
            structural_pattern=self._structural_pattern,
            structural_swings=self._structural_swings,
        )
        
        self._evidence.clear()
        
        self._ctx = self._create_context()
    
    
    
    def _create_bar_context(
        self,
        metrics_row: pd.Series,
        bar_index:int,
    ) -> BarContext:

        return BarContext(
            # -------------------------------------------------
            # Week
            # -------------------------------------------------
            week_beginning=str(metrics_row[COL_WEEK]),
           
            bar_index=bar_index,    

            # -------------------------------------------------
            # Semantic classifications
            # -------------------------------------------------
            spread=SpreadClass(int(metrics_row[COL_SPREAD_CLASS])),
            volume=VolumeClass(int(metrics_row[COL_VOLUME_CLASS])),
            direction=Direction(int(metrics_row[COL_DIRECTION])),
            close_position=ClosePosition(int(metrics_row[COL_CLOSE_POSITION])),

            # -------------------------------------------------
            # Normalized metrics
            # -------------------------------------------------
            spread_ratio=float(metrics_row[COL_SPREAD_RATIO]),
            volume_ratio=float(metrics_row[COL_VOLUME_RATIO]),
            
            # -------------------------------------------------
            # Price
            # -------------------------------------------------
            open=float(metrics_row[COL_OPEN]),
            high=float(metrics_row[COL_HIGH]),
            low=float(metrics_row[COL_LOW]),
            close_price=float(metrics_row[COL_CLOSE]),

            # -------------------------------------------------
            # Derived geometry
            # -------------------------------------------------
            body=float(metrics_row[COL_BODY]),
            upper_shadow=float(metrics_row[COL_UPPER_SHADOW]),
            lower_shadow=float(metrics_row[COL_LOWER_SHADOW]),
            close_ratio=float(metrics_row[COL_CLOSE_RATIO]),

            # -------------------------------------------------
            # Previous bar
            # -------------------------------------------------
            
            prev_high=float(metrics_row[COL_PREV_HIGH]),
            prev_low=float(metrics_row[COL_PREV_LOW]),
            prev_close=float(metrics_row[COL_PREV_CLOSE]),            
            prev_spread=float(metrics_row[COL_PREV_SPREAD]),           
        )
    
        
    #original version
    def _create_context(self) -> BackgroundContext:
        """
        Build the immutable context shared by all
        Evidence Engine detectors.
        """

        assert self._metrics is not None
        assert self._trend is not None

        recent = self._recent
        assert not recent.empty

        # ----------------------------------------
        # Build BarContext objects
        # ----------------------------------------
        
        bars = tuple(
            self._create_bar_context(
                recent.iloc[i],
                int(recent.index[i]),
            )
            for i in range(len(recent))
        )
        # ----------------------------------------
        # Current / Previous
        # ----------------------------------------

        current = bars[-1]

        previous = (
            bars[-2]
            if len(bars) >= 2
            else None
        )

        # ----------------------------------------
        # Context
        # ----------------------------------------

        return BackgroundContext(
            background=self._background,
            recent=recent,
            trend=self._trend,
            bars=bars,
            current=current,
            previous=previous,
            structural_swings=self._structural_swings,
            structural_pattern=self._structural_pattern,
            vsa_context=self._vsa_context,
        )
    
    
    # ==========================================================
    # Properties
    # ==========================================================
    @property
    def _recent(self) -> pd.DataFrame:
        """
        Return the recent lookback window used by
        the Background Engine.
        """

        assert self._metrics is not None

        return self._metrics.tail(
            config.BACKGROUND_LOOKBACK
        )
    
    @property
    def _background(self) -> pd.DataFrame:
        """
        Return the historical background preceding
        the recent lookback window.
        """

        assert self._metrics is not None
        
        if len(self._metrics) <= config.BACKGROUND_LOOKBACK:
            return self._metrics.iloc[0:0]


        return self._metrics.iloc[
            :-config.BACKGROUND_LOOKBACK
        ]   
    
    
    # ==========================================================
    # Evidence Helper
    # ==========================================================

    def _add_evidence(
            self,
            category: EvidenceCategory,
            code: EvidenceCode,
            strength: float,
            weight: float,
            observation: str,            
    ) -> None:
        """
        Add validated evidence to the Background Engine.
        """

        assert 0.0 <= strength <= 1.0
        assert weight > 0.0

        self._evidence.append(
            Evidence(
                category=category,
                code=code,
                strength=strength,
                weight=weight,
                observation=observation,               
            )
        )
    
    def _emit(
        self,
        code: EvidenceCode,
        bar: BarContext,
        strength: float | None = None,
    ) -> None:
        
        weight = WeightCalculator.calculate(
            code,
            self._ctx,
        )       
        
        self._evidence.append(
            build_evidence(
                code,
                strength=strength,
                weight=weight,
                bar_index=bar.bar_index,
                week_beginning=bar.week_beginning,
            )
        )
     
    # ==========================================================
    # Supply
    # ==========================================================
   
    def _collect_supply(self) -> None:
        """
        Collect supply evidence.        """
                
        assert self._ctx is not None
        collected = collect_supply(self._ctx)
        
        # print(
        #     "SUPPLY COLLECTED",
        #     [
        #         {
        #             "code": item.code,
        #             "bar_index": item.bar_index,
        #         }
        #         for item in collected
        #     ],
        # )

        self._evidence.extend(collected)        
       
    

    # ==========================================================
    # Demand
    # ==========================================================
    def _collect_demand(self) -> None:
        """
        Collect demand evidence.
        """
        assert self._ctx is not None
        assert self._metrics is not None
        assert self._validation_metrics is not None
        
        self._evidence.extend(
            collect_demand(
                ctx=self._ctx,
                metrics=self._validation_metrics,
            )
        )  
            
         
    # ==========================================================
    # Effort vs Result
    # ==========================================================
    def _collect_effort(self) -> None:
        """
        Collect effort-result evidence.
        """

        assert self._ctx is not None
        
        self._evidence.extend(
            collect_effort(self._ctx)
        )
        
    
    
    # ==========================================================
    # Trend
    # ==========================================================

    def _collect_trend(self) -> None:
        """
        Collect trend evidence.
        """
        
        assert self._ctx is not None
        
        self._evidence.extend(
            collect_trend(self._ctx)
        )
        
    
    
    # ==========================================================
    # Wyckoff Phase
    # ==========================================================

    def _collect_phase(self) -> None:
        """
        Collect Wyckoff phase evidence.
        """
        """ assert self._ctx is not None
        self._evidence.extend(
            collect_phase(self._ctx) """
    #)
          
    
    

    def _collect_structural_progression(
        self,
    ) -> None:

        assert self._ctx is not None

        self._evidence.extend(
            collect_structural_progression(
                self._ctx,
            )
        )

    def debug_shakeout_history(
        self,
        metrics: pd.DataFrame,
        target_index: int | None = None,
    ) -> None:
        self._debug_target_index = target_index
        print(
            "ENGINE INPUT",
            {
                "len_metrics": len(metrics),
                "last_index": len(metrics) - 1,
                "target_index": target_index,
            },
        )
        for i in range(1, len(metrics)):

            current = metrics.iloc[i]
            previous = metrics.iloc[i - 1]

            current_bar = self._create_bar_context(
                current,
                int(metrics.index[i]),
            )

            previous_bar = self._create_bar_context(
                previous,
                int(metrics.index[i - 1]),
            )
            
            if target_index is not None and i == target_index:
                print(
                    f"\n========== BAR {target_index} FULL AUDIT ==========",
                    {
                        "bar_index": current_bar.bar_index,
                        "data_index": int(metrics.index[i]),

                        # -----------------------------
                        # Raw market data
                        # -----------------------------
                        "open": current_bar.open,
                        "high": current_bar.high,
                        "low": current_bar.low,
                        "close_price": current_bar.close_price,
                        "raw_volume": float(current[COL_VOLUME]),
                        "raw_spread": float(current[COL_SPREAD]),

                        # -----------------------------
                        # Normalized metrics
                        # -----------------------------
                        "spread_ratio": current_bar.spread_ratio,
                        "spread_percentile": float(
                            current[COL_SPREAD_PERCENTILE]
                        ),
                        "avg_volume": float(
                            current[COL_AVG_VOLUME]
                        ),
                        "volume_ratio": current_bar.volume_ratio,
                        "volume_percentile": float(
                            current[COL_VOLUME_PERCENTILE]
                        ),

                        # -----------------------------
                        # Semantic classifications
                        # -----------------------------
                        "spread_class": SpreadClass(
                            int(current_bar.spread)
                        ).name,
                        "volume_class": VolumeClass(
                            int(current_bar.volume)
                        ).name,
                        "direction": Direction(
                            int(current_bar.direction)
                        ).name,
                        "close_position": ClosePosition(
                            int(current_bar.close_position)
                        ).name,

                        # -----------------------------
                        # VSA conditions
                        # -----------------------------
                        "bearish": is_bearish_bar(current_bar),
                        "wide_spread": has_strong_spread(current_bar),
                        "lower_low": makes_lower_low(
                            current_bar,
                            previous_bar,
                        ),
                        "strong_close": is_strong_close(current_bar),
                        "very_high_volume": is_very_high_volume(
                            current_bar
                        ),
                        "increasing_volume": volume_increasing(
                            current_bar,
                            previous_bar,
                        ),
                    },
                )

            if target_index is not None and i == target_index:
                print(
                    "VOLUME CLASSIFICATION AUDIT",
                    {
                        "current_raw_volume": float(metrics.iloc[i][COL_VOLUME]),
                        "current_avg_volume": float(metrics.iloc[i][COL_AVG_VOLUME]),
                        "current_volume_ratio": current_bar.volume_ratio,
                        "current_percentile": float(metrics.iloc[i][COL_VOLUME_PERCENTILE]),
                        "current_class": VolumeClass(int(current_bar.volume)).name,

                        "previous_raw_volume": float(metrics.iloc[i - 1][COL_VOLUME]),
                        "previous_avg_volume": float(metrics.iloc[i - 1][COL_AVG_VOLUME]),
                        "previous_volume_ratio": previous_bar.volume_ratio,
                        "previous_percentile": float(metrics.iloc[i - 1][COL_VOLUME_PERCENTILE]),
                        "previous_class": VolumeClass(int(previous_bar.volume)).name,

                        "very_high": is_very_high_volume(current_bar),
                        "volume_increasing": volume_increasing(current_bar, previous_bar),
                    },
                )            
            
    # ==========================================================
    # Finalization
    # ==========================================================

    def _finalize(
        self,
    ) -> EvidenceResult:

        assert self._ctx is not None
        result = EvidenceResult(
            context=self._ctx,
            evidence=tuple(self._evidence),
        )
        return result
        