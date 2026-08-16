from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS, COL_WEEK
from evidence.campaign import has_selling_campaign, validate_shakeout
from evidence.engine import EvidenceEngine
from evidence.rules import has_strong_spread, is_bearish_bar, is_very_high_volume, makes_lower_low
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS",
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "TCS.NS",
    "SBIN.NS",
    "LT.NS",
)
MIN_REPLAY_BARS = 20


def candidate_indices(metrics) -> list[int]:
    """Prefilter using only current-bar semantic requirements."""
    indices: list[int] = []
    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]
        direction = Direction(int(row[COL_DIRECTION]))
        volume = VolumeClass(int(row[COL_VOLUME_CLASS]))
        spread = SpreadClass(int(row[COL_SPREAD_CLASS]))
        if direction == Direction.DOWN and volume >= VolumeClass.VERY_HIGH and spread >= SpreadClass.ABOVE_AVERAGE:
            indices.append(index)
    return indices


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    rows: list[dict] = []

    for index in candidate_indices(metrics):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)

        engine = EvidenceEngine()
        engine.collect(metrics=replay, trend=trend, structural_swings=structural_swings)
        ctx = engine._ctx
        if ctx is None:
            continue

        bar = ctx.current
        previous = ctx.previous
        current_bar_requirements = {
            "selling_campaign": has_selling_campaign(ctx),
            "bearish_bar": is_bearish_bar(bar),
            "wide_spread": has_strong_spread(bar),
            "very_high_volume": is_very_high_volume(bar),
            "lower_low": makes_lower_low(bar, previous) if previous is not None else False,
        }
        if not all(current_bar_requirements.values()):
            continue

        # Historical diagnostic only: this deliberately uses the complete
        # metrics frame to measure how many current-bar candidates are
        # retrospectively confirmed by the existing TEST/RECOVERY logic.
        validation = validate_shakeout(metrics=metrics, shakeout_index=index)
        valid_test = validation.test.test_index is not None
        valid_recovery = validation.recovery.recovery_index is not None

        rows.append(
            {
                "symbol": symbol,
                "shakeout_index": index,
                "week": str(metrics.iloc[index][COL_WEEK]),
                "historical_test_valid": valid_test,
                "test_index": validation.test.test_index,
                "historical_recovery_valid": valid_recovery,
                "recovery_index": validation.recovery.recovery_index,
                "test_bars_after_shakeout": (
                    None
                    if validation.test.test_index is None
                    else validation.test.test_index - index
                ),
                "recovery_bars_after_shakeout": (
                    None
                    if validation.recovery.recovery_index is None
                    else validation.recovery.recovery_index - index
                ),
                "test_result": validation.test.result.value,
                "recovery_result": validation.recovery.result.value,
                **current_bar_requirements,
            }
        )

    return rows


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    rows: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                symbol_rows = future.result()
                rows.extend(symbol_rows)
                print({"symbol": symbol, "candidates": len(symbol_rows)})
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    historical_valid = [row for row in rows if row["historical_recovery_valid"]]
    print("SHAKEOUT SEMANTIC AUDIT SUMMARY")
    print(
        {
            "symbols_requested": len(symbols),
            "symbols_with_candidates": len({row["symbol"] for row in rows}),
            "current_bar_candidates": len(rows),
            "historically_validated_shakeouts": len(historical_valid),
            "valid_test_count": sum(row["historical_test_valid"] for row in rows),
            "valid_recovery_count": sum(row["historical_recovery_valid"] for row in rows),
            "average_test_delay": (
                sum(row["test_bars_after_shakeout"] for row in historical_valid) / len(historical_valid)
                if historical_valid else None
            ),
            "average_recovery_delay": (
                sum(row["recovery_bars_after_shakeout"] for row in historical_valid) / len(historical_valid)
                if historical_valid else None
            ),
            "failures": failures,
        }
    )

    print("SHAKEOUT SEMANTIC AUDIT BY_SYMBOL")
    for symbol in symbols:
        subset = [row for row in rows if row["symbol"] == symbol]
        valid = [row for row in subset if row["historical_recovery_valid"]]
        print(
            {
                "symbol": symbol,
                "current_bar_candidates": len(subset),
                "historically_validated_shakeouts": len(valid),
            }
        )

    print("SHAKEOUT SEMANTIC AUDIT EVENTS")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
