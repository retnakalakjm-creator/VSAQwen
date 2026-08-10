import pandas as pd

from engine.columns import COL_CLOSE, COL_CLOSE_POSITION, COL_DIRECTION, COL_HIGH, COL_LOW, COL_OPEN, COL_SPREAD, COL_SPREAD_RATIO, COL_VOLUME, COL_VOLUME_CLASS, COL_VOLUME_RATIO, COL_WEEK
import config
from evidence.campaign import _count, _count_lower_closing_bars, _recent_structural_weakness, _validate_shakeout_test
from evidence.engine import EvidenceEngine
from evidence.rules import is_down_bar, is_weak_close
from models import BackgroundContext, EvidenceCode
from trend import TrendAnalyzer



def debug_shakeout_replay(
    metrics: pd.DataFrame,
    target_index: int,
) -> None:
    """
    Replay the Evidence Engine at a historical bar.

    The replay is strictly point-in-time:
    no trend, structural swing, or evidence calculation
    may use bars after target_index.
    """

    if target_index < 0 or target_index >= len(metrics):
        raise ValueError(
            f"Invalid target_index={target_index}; "
            f"valid range is 0..{len(metrics) - 1}"
        )

    print(
        f"\n========== SHAKEOUT REPLAY {target_index} =========="
    )

    replay_metrics = metrics.iloc[
        :target_index + 1
    ].copy()

    replay_trend = TrendAnalyzer().analyze(
        replay_metrics,
    )

    replay_structural_swings = list(
        replay_trend.structure.structural_swings
    )
    replay_engine = EvidenceEngine()
    replay_evidence = replay_engine.collect(
        metrics=replay_metrics,
        trend=replay_trend,
        structural_swings=replay_structural_swings,
    )

    print(
        "REPLAY TREND",
        {
            "target": target_index,
            "direction": replay_trend.structure.direction,
            "state": replay_trend.structure.state,
            "structural_swings": len(
                replay_structural_swings
            ),
        },
    )

    shakeouts = [
        item
        for item in replay_evidence.evidence
        if item.code == EvidenceCode.SHAKEOUT
    ]
    if shakeouts:

            print(
                "\n========== SHAKEOUT TARGET AUDIT =========="
            )

            replay_ctx = replay_engine._ctx
            assert replay_ctx is not None

            print(
                {
                    "bar_index": target_index,

                    "trend_direction": (
                        replay_trend.structure.direction
                    ),

                    "trend_state": (
                        replay_trend.structure.state
                    ),

                    "down_bars": _count(
                        replay_ctx.bars,
                        is_down_bar,
                    ),

                    "lower_closes": _count_lower_closing_bars(
                        replay_ctx.bars,
                    ),

                    "weak_closes": _count(
                        replay_ctx.bars,
                        is_weak_close,
                    ),

                    "structural_weakness": (
                        _recent_structural_weakness(
                            replay_ctx,
                        )
                    ),
                }
            )    
    print(
        "SHAKEOUT RESULTS",
        {
            "target": target_index,
            "count": len(shakeouts),
        },
    )
    
def debug_shakeout_scan(
    metrics: pd.DataFrame,
) -> None:

    results = []

    first_valid_index = config.BACKGROUND_LOOKBACK - 1

    for target_index in range(
        first_valid_index,
        len(metrics),
    ):

        replay_metrics = metrics.iloc[
            :target_index + 1
        ].copy()

        replay_trend = TrendAnalyzer().analyze(
            replay_metrics,
        )

        replay_structural_swings = list(
            replay_trend.structure.structural_swings
        )

        replay_engine = EvidenceEngine()

        replay_evidence = replay_engine.collect(
            metrics=replay_metrics,
            trend=replay_trend,
            structural_swings=replay_structural_swings,
        )

        shakeouts = [
            item
            for item in replay_evidence.evidence
            if item.code == EvidenceCode.SHAKEOUT
        ]

        # -------------------------------------------------
        # DEBUG ONLY
        # -------------------------------------------------

        if shakeouts:

            print(
                "\n========== SHAKEOUT TARGET AUDIT =========="
            )

            replay_ctx = replay_engine._ctx
            assert replay_ctx is not None

            print(
                {
                    "bar_index": target_index,

                    "trend_direction": (
                        replay_trend.structure.direction
                    ),

                    "trend_state": (
                        replay_trend.structure.state
                    ),

                    "down_bars": _count(
                        replay_ctx.bars,
                        is_down_bar,
                    ),

                    "lower_closes": _count_lower_closing_bars(
                        replay_ctx.bars,
                    ),

                    "weak_closes": _count(
                        replay_ctx.bars,
                        is_weak_close,
                    ),

                    "structural_weakness": (
                        _recent_structural_weakness(
                            replay_ctx,
                        )
                    ),
                }
            )

            results.append(
                {
                    "bar_index": target_index,
                    "shakeout_count": len(shakeouts),
                    "trend_direction": (
                        replay_trend.structure.direction
                    ),
                    "trend_state": (
                        replay_trend.structure.state
                    ),
                }
            )

    print(
        "\n========== SHAKEOUT SCAN =========="
    )

    for item in results:
        print(item)

    print(
        "TOTAL SHAKEOUT BARS:",
        len(results),
    )
    
def debug_post_shakeout(
    metrics: pd.DataFrame,
    shakeout_index: int,
    bars_after: int = 10,
) -> None:

    end_index = min(
        len(metrics),
        shakeout_index + bars_after + 1,
    )

    window = metrics.iloc[
        shakeout_index:end_index
    ]

    print(
        f"\n========== POST-SHAKEOUT AUDIT "
        f"{shakeout_index} =========="
    )

    for index, row in window.iterrows():

        print(
            {
                "bar_index": int(index),

                "open": float(row[COL_OPEN]),
                "high": float(row[COL_HIGH]),
                "low": float(row[COL_LOW]),
                "close": float(row[COL_CLOSE]),
                "volume": float(row[COL_VOLUME]),

                "week": row[COL_WEEK],

                "direction": row[COL_DIRECTION],
                "close_position": row[COL_CLOSE_POSITION],

                "spread": row[COL_SPREAD],
                "volume_class": row[COL_VOLUME_CLASS],
            }
        )  
                
def debug_post_shakeout_retest(
    metrics: pd.DataFrame,
    shakeout_index: int,
    bars_after: int = 15,
) -> None:

    shakeout = metrics.iloc[shakeout_index]

    shakeout_low = float(
        shakeout[COL_LOW]
    )

    shakeout_spread = float(
        shakeout[COL_SPREAD]
    )

    end_index = min(
        len(metrics),
        shakeout_index + bars_after + 1,
    )

    window = metrics.iloc[
        shakeout_index + 1 : end_index
    ]

    print(
        f"\n========== POST-SHAKEOUT RETEST AUDIT "
        f"{shakeout_index} =========="
    )

    print(
        "SHAKEOUT REFERENCE",
        {
            "low": shakeout_low,
            "spread": shakeout_spread,
        },
    )

    for index, row in window.iterrows():

        current_low = float(
            row[COL_LOW]
        )

        distance = current_low - shakeout_low

        distance_ratio = (
            distance / shakeout_spread
            if shakeout_spread > 0
            else float("inf")
        )

        print(
            {
                "bar_index": int(index),
                "low": current_low,
                "distance": distance,
                "distance_ratio": distance_ratio,
                "direction": row[COL_DIRECTION],
                "spread_ratio": float(
                    row[COL_SPREAD_RATIO]
                ),
                "volume_ratio": float(
                    row[COL_VOLUME_RATIO]
                ),
                "close_position": row[
                    COL_CLOSE_POSITION
                ],
            }
        )
        
def debug_test_recovery(
        metrics: pd.DataFrame,
        test_index: int,
        bars_after: int = 5,
    ) -> None:

        test_bar = metrics.iloc[test_index]

        test_low = float(
            test_bar[COL_LOW]
        )

        end_index = min(
            len(metrics),
            test_index + bars_after + 1,
        )

        window = metrics.iloc[
            test_index + 1 : end_index
        ]

        print(
            f"\n========== TEST RECOVERY AUDIT "
            f"{test_index} =========="
        )

        print(
            "TEST REFERENCE",
            {
                "bar_index": test_index,
                "low": test_low,
                "close": float(
                    test_bar[COL_CLOSE]
                ),
            },
        )

        for index, row in window.iterrows():

            current_low = float(
                row[COL_LOW]
            )

            current_close = float(
                row[COL_CLOSE]
            )

            print(
                {
                    "bar_index": int(index),
                    "low": current_low,
                    "distance_from_test_low": (
                        current_low - test_low
                    ),
                    "close": current_close,
                    "close_change": (
                        current_close
                        - float(test_bar[COL_CLOSE])
                    ),
                    "direction": row[
                        COL_DIRECTION
                    ],
                    "close_position": row[
                        COL_CLOSE_POSITION
                    ],
                    "volume_ratio": float(
                        row[COL_VOLUME_RATIO]
                    ),
                    "spread_ratio": float(
                        row[COL_SPREAD_RATIO]
                    ),
                }
            )    

def debug_shakeout_test_validation(
    metrics: pd.DataFrame,
    shakeout_index: int,
) -> None:

    trend = TrendAnalyzer().analyze(metrics)

    structural_swings = tuple(
        trend.structure.structural_swings
    )

    engine = EvidenceEngine()

    engine._reset(
        metrics=metrics,
        trend=trend,
        structural_swings=structural_swings,
    )

    result = _validate_shakeout_test(
        metrics=metrics,
        ctx=engine._ctx,
        shakeout_index=shakeout_index,
    )

    print(
        "\n========== SHAKEOUT TEST VALIDATION =========="
    )

    print(
        {
            "shakeout_index": shakeout_index,
            "result": result,
        }
    )

def debug_shakeout_recovery(
    metrics: pd.DataFrame,
    test_index: int,
) -> None:

    test = metrics.iloc[test_index]

    test_low = float(test[COL_LOW])
    test_close = float(test[COL_CLOSE])

    print(
        f"\n========== SHAKEOUT RECOVERY AUDIT {test_index} =========="
    )

    print(
        "TEST REFERENCE",
        {
            "bar_index": test_index,
            "low": test_low,
            "close": test_close,
        },
    )

    start = test_index + 1
    end = min(
        len(metrics),
        start + 5, #config.SHAKEOUT_RECOVERY_LOOKAHEAD,
    )

    for index in range(start, end):

        bar = metrics.iloc[index]

        low = float(bar[COL_LOW])
        close = float(bar[COL_CLOSE])
        spread = float(bar[COL_SPREAD])
        volume = float(bar[COL_VOLUME])

        close_change = close - test_close
        low_distance = low - test_low

        print(
            {
                "bar_index": index,
                "low": low,
                "low_distance_from_test": low_distance,
                "close": close,
                "close_change": close_change,
                "direction": int(bar[COL_DIRECTION]),
                "spread": spread,
                "volume": volume,
                "close_position": int(
                    bar[COL_CLOSE_POSITION]
                ),
            }
        )

            