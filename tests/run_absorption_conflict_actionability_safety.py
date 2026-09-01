from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_LOW,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, SpreadClass, VolumeClass
from tests.decision_outcome_labeling import label_outcome
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS

HORIZONS = (3, 5, 10)


def is_absorption(bar, previous) -> bool:
    return (
        Direction(int(bar[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(bar[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
        and ClosePosition(int(bar[COL_CLOSE_POSITION])) >= ClosePosition.UPPER
        and float(bar[COL_LOW]) < float(previous[COL_LOW])
    )


def is_conflict(bar, previous) -> bool:
    return (
        Direction(int(bar[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) > VolumeClass(int(previous[COL_VOLUME_CLASS]))
        and SpreadClass(int(bar[COL_SPREAD_CLASS])) > SpreadClass(int(previous[COL_SPREAD_CLASS]))
    )


def scan_symbol(symbol: str, sample_bars: int, refresh: bool) -> list[dict]:
    metrics = MetricsEngine().calculate(
        daily_to_weekly(download_data(symbol, refresh=refresh))
    )
    start = max(21, len(metrics) - sample_bars - max(HORIZONS))
    rows: list[dict] = []

    for index in range(start, len(metrics)):
        bar = metrics.iloc[index]
        previous = metrics.iloc[index - 1]
        if not is_absorption(bar, previous):
            continue
        conflict = is_conflict(bar, previous)
        for horizon in HORIZONS:
            if index + horizon >= len(metrics):
                continue
            outcome = label_outcome(
                metrics,
                signal_index=index,
                direction=1,
                horizon=horizon,
            )
            rows.append({
                "symbol": symbol,
                "index": index,
                "horizon": horizon,
                "conflict": conflict,
                "return": outcome.forward_return,
            })
    return rows


def summarize(values: list[float]) -> tuple[int, int, int, float, float]:
    positive = sum(value > 0 for value in values)
    negative = sum(value < 0 for value in values)
    decisive = positive + negative
    mean_return = sum(values) / len(values) if values else 0.0
    positive_rate = positive / decisive if decisive else 0.0
    return len(values), positive, negative, mean_return, positive_rate


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ABSORPTION conflict actionability safety audit."
    )
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--symbols", nargs="+", default=None)
    args = parser.parse_args()

    if args.sample_bars <= max(HORIZONS):
        raise ValueError("--sample-bars must exceed the maximum horizon")

    symbols = tuple(args.symbols) if args.symbols else tuple(SYMBOLS)
    rows: list[dict] = []
    failures: list[tuple[str, str, str]] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {
            executor.submit(scan_symbol, symbol, args.sample_bars, args.refresh): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                rows.extend(future.result())
            except Exception as exc:
                failures.append((symbol, type(exc).__name__, str(exc)))

    print("=== ABSORPTION CONFLICT ACTIONABILITY SAFETY AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {len(symbols) - len(failures)}")
    print(f"sample bars per symbol: {args.sample_bars}")
    print("policy under test: reject INCREASING_SUPPLY_LIKE conflict")
    print("this is counterfactual only; production collector/scoring is unchanged")
    print()
    print(
        f"{'H':>4}{'All':>8}{'Keep':>8}{'Reject':>8}"
        f"{'PosLost':>10}{'NegAvoid':>10}{'MeanAll':>12}{'MeanKeep':>12}{'Lift':>10}"
    )

    for horizon in HORIZONS:
        horizon_rows = [r for r in rows if r["horizon"] == horizon]
        all_values = [r["return"] for r in horizon_rows if r["return"] is not None]
        keep_values = [r["return"] for r in horizon_rows if not r["conflict"] and r["return"] is not None]
        rejected = [r["return"] for r in horizon_rows if r["conflict"] and r["return"] is not None]
        if not all_values:
            continue
        pos_lost = sum(value > 0 for value in rejected)
        neg_avoided = sum(value < 0 for value in rejected)
        mean_all = sum(all_values) / len(all_values)
        mean_keep = sum(keep_values) / len(keep_values) if keep_values else 0.0
        print(
            f"{horizon:>4}{len(all_values):>8}{len(keep_values):>8}{len(rejected):>8}"
            f"{pos_lost:>10}{neg_avoided:>10}"
            f"{mean_all:>11.3%}{mean_keep:>11.3%}{(mean_keep - mean_all):>9.3%}"
        )

    print()
    print("CONFLICT OUTCOME")
    print(f"{'H':>4}{'Events':>8}{'Positive':>10}{'Negative':>10}{'MeanRet':>12}{'PosRate':>10}")
    for horizon in HORIZONS:
        values = [
            r["return"]
            for r in rows
            if r["horizon"] == horizon and r["conflict"] and r["return"] is not None
        ]
        events, positive, negative, mean_return, positive_rate = summarize(values)
        print(
            f"{horizon:>4}{events:>8}{positive:>10}{negative:>10}"
            f"{mean_return:>11.3%}{positive_rate:>9.2%}"
        )

    print()
    print("DECISION")
    print("Hard rejection safety: DO NOT PROMOTE")
    print("Soft conflict penalty remains counterfactual/provisional until production-path ranking tests exist.")

    if failures:
        print()
        print("=== FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<16}{error_type}: {message}")


if __name__ == "__main__":
    main()
