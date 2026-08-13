from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.engine import EvidenceEngine
from evidence.rules import (
    is_above_average_spread,
    is_bullish_bar,
    is_high_volume,
    volume_increasing,
)
from metrics_engine import MetricsEngine
from models import Direction, SpreadClass, VolumeClass
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
HORIZON = 8
WEIGHTS = (0.25, 0.40, 0.60, 0.75, 0.85, 1.00)


def inspect_symbol(symbol: str) -> list[str]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    outcomes: list[str] = []

    for index in range(MIN_REPLAY_BARS, len(metrics) - HORIZON):
        row = metrics.iloc[index]
        if not (
            Direction(row[COL_DIRECTION]) == Direction.UP
            and VolumeClass(row[COL_VOLUME_CLASS]) >= VolumeClass.HIGH
            and SpreadClass(row[COL_SPREAD_CLASS]) >= SpreadClass.ABOVE_AVERAGE
        ):
            continue

        replay = metrics.iloc[: index + 1]
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=metrics,
        )
        assert engine._ctx is not None
        current = engine._ctx.current
        previous = engine._ctx.previous

        # Exact validated INCREASING_DEMAND definition.
        if previous is None or not all((
            is_bullish_bar(current),
            is_high_volume(current),
            is_above_average_spread(current),
            volume_increasing(current, previous),
        )):
            continue

        close = float(metrics.iloc[index][COL_CLOSE])
        future = float(metrics.iloc[index + HORIZON][COL_CLOSE])
        ret8 = (future - close) / close
        if ret8 > 0.02:
            outcomes.append("POSITIVE_8_BAR")
        elif ret8 < -0.02:
            outcomes.append("NEGATIVE_8_BAR")
        else:
            outcomes.append("FLAT_8_BAR")

    return outcomes


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_outcomes: list[str] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, s): s for s in symbols}
        for future, symbol in futures.items():
            try:
                all_outcomes.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    counts = {
        "POSITIVE_8_BAR": all_outcomes.count("POSITIVE_8_BAR"),
        "NEGATIVE_8_BAR": all_outcomes.count("NEGATIVE_8_BAR"),
        "FLAT_8_BAR": all_outcomes.count("FLAT_8_BAR"),
    }

    print("INCREASING DEMAND WEIGHT CALIBRATION SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len(symbols) - len(failures),
        "events": len(all_outcomes),
        "outcomes": counts,
        "candidate_weights": WEIGHTS,
        "failures": failures,
    })

    print("INCREASING DEMAND WEIGHT IMPACT BY OUTCOME")
    total = len(all_outcomes)
    for weight in WEIGHTS:
        positive_delta = weight * counts["POSITIVE_8_BAR"] / total if total else 0.0
        negative_delta = weight * counts["NEGATIVE_8_BAR"] / total if total else 0.0
        flat_delta = weight * counts["FLAT_8_BAR"] / total if total else 0.0
        net_directional_delta = (
            weight * (counts["POSITIVE_8_BAR"] - counts["NEGATIVE_8_BAR"]) / total
            if total else 0.0
        )
        print({
            "candidate_weight": weight,
            "positive_delta": positive_delta,
            "negative_delta": negative_delta,
            "flat_delta": flat_delta,
            "net_directional_delta": net_directional_delta,
        })


if __name__ == "__main__":
    main()
