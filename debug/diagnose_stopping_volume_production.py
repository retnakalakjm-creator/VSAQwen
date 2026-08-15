from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_HIGH, COL_LOW, COL_WEEK
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import EvidenceCode
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


def forward_outcome(weekly, index: int) -> tuple[str, float | None]:
    current = float(weekly.iloc[index][COL_CLOSE])
    future_index = index + 8
    if future_index >= len(weekly):
        return "INSUFFICIENT_FORWARD_DATA", None

    future = float(weekly.iloc[future_index][COL_CLOSE])
    forward_return = (future - current) / current

    if forward_return > 0.02:
        return "POSITIVE_8_BAR", forward_return
    if forward_return < -0.02:
        return "NEGATIVE_8_BAR", forward_return
    return "FLAT_8_BAR", forward_return


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    rows: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)

        result = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )

        stopping = tuple(
            item
            for item in result.evidence
            if item.code is EvidenceCode.STOPPING_VOLUME
            and item.bar_index == index
        )
        if not stopping:
            continue

        outcome, forward_return = forward_outcome(weekly, index)
        rows.append(
            {
                "symbol": symbol,
                "bar_index": index,
                "week": str(metrics.iloc[index][COL_WEEK]),
                "stopping_volume_events": len(stopping),
                "outcome": outcome,
                "forward_return": forward_return,
                "strengths": [float(item.strength) for item in stopping],
                "weights": [float(item.weight) for item in stopping],
            }
        )

    return rows


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                symbol_events = future.result()
                events.extend(symbol_events)
                print({"symbol": symbol, "events": len(symbol_events)})
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    outcomes = {
        "POSITIVE_8_BAR": sum(row["outcome"] == "POSITIVE_8_BAR" for row in events),
        "NEGATIVE_8_BAR": sum(row["outcome"] == "NEGATIVE_8_BAR" for row in events),
        "FLAT_8_BAR": sum(row["outcome"] == "FLAT_8_BAR" for row in events),
        "INSUFFICIENT_FORWARD_DATA": sum(
            row["outcome"] == "INSUFFICIENT_FORWARD_DATA" for row in events
        ),
    }

    print("SPRING PRODUCTION REPLAY SUMMARY" if False else "STOPPING VOLUME PRODUCTION REPLAY SUMMARY")
    print(
        {
            "symbols_requested": len(symbols),
            "symbols_with_events": len({row["symbol"] for row in events}),
            "production_stopping_volume_events": len(events),
            "outcome_classes": outcomes,
            "failures": failures,
        }
    )

    print("STOPPING VOLUME PRODUCTION REPLAY EVENTS")
    for row in events:
        print(row)


if __name__ == "__main__":
    main()
