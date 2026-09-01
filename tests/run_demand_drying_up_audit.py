from __future__ import annotations

import argparse
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from evidence.demand_drying_up import collect_demand_drying_up
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from tests.decision_outcome_labeling import label_outcome
from run_nse_increasing_demand_universe_audit import SYMBOLS


def _audit_symbol(
    symbol: str,
    sample_bars: int,
    horizons: tuple[int, ...],
    refresh: bool,
) -> list[dict]:
    daily = download_data(symbol, refresh=refresh)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    context_factory = EvidenceEngine()
    sample_start = max(1, len(metrics) - sample_bars - max(horizons))
    rows: list[dict] = []

    for index in range(sample_start, len(metrics)):
        row = metrics.iloc[index]
        previous = metrics.iloc[index - 1]
        current = context_factory._create_bar_context(row, index)
        prior = context_factory._create_bar_context(previous, index - 1)
        ctx = SimpleNamespace(current=current, previous=prior)

        evidence = collect_demand_drying_up(ctx)
        if not evidence:
            continue

        for horizon in horizons:
            if index + horizon >= len(metrics):
                continue
            outcome = label_outcome(
                metrics,
                signal_index=index,
                direction=1,
                horizon=horizon,
            )
            rows.append(
                {
                    "symbol": symbol,
                    "bar_index": index,
                    "week": str(current.week_beginning),
                    "horizon": horizon,
                    "return": outcome.forward_return,
                    "mfe": outcome.maximum_favorable_excursion,
                    "mae": outcome.maximum_adverse_excursion,
                    "positive": outcome.forward_return > 0,
                }
            )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Point-in-time DEMAND_DRYING_UP audit.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    horizons = (3, 5, 10)

    all_rows: list[dict] = []
    skipped: list[tuple[str, str, str]] = []
    symbols_with_results: set[str] = set()

    for symbol in SYMBOLS:
        try:
            rows = _audit_symbol(symbol, args.sample_bars, horizons, args.refresh)
            all_rows.extend(rows)
            if rows:
                symbols_with_results.add(symbol)
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))

    print("=== DEMAND_DRYING_UP POINT-IN-TIME AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols with events: {len(symbols_with_results)}")
    print(f"event-horizon rows: {len(all_rows)}")
    print()
    print(f"{'Horizon':>8}{'Cases':>8}{'MeanRet':>12}{'WinRate':>10}{'MeanMFE':>12}{'MeanMAE':>12}")

    for horizon in horizons:
        bucket = [r for r in all_rows if r["horizon"] == horizon]
        if not bucket:
            continue
        mean_return = sum(r["return"] for r in bucket) / len(bucket)
        win_rate = sum(r["positive"] for r in bucket) / len(bucket)
        mean_mfe = sum(r["mfe"] for r in bucket) / len(bucket)
        mean_mae = sum(r["mae"] for r in bucket) / len(bucket)
        print(
            f"{horizon:>8}{len(bucket):>8}{mean_return:>11.3%}"
            f"{win_rate:>9.1%}{mean_mfe:>11.3%}{mean_mae:>11.3%}"
        )

    print()
    print("=== SYMBOL COVERAGE ===")
    for symbol in SYMBOLS:
        count = sum(1 for r in all_rows if r["symbol"] == symbol)
        print(f"{symbol:<14}{count:>6}")

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
