from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from market_structure.swing_engine import SwingEngine
from tests.incremental_equivalence_harness import (
    _reopen_start,
    compare_state,
    compare_swing_sequences,
    snapshot_after_prefix,
)
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS

HARNESS_REVISION = "2026-09-01-checkpoint-continuation-v2"


def _audit_symbol(
    symbol: str,
    *,
    split_ratios: tuple[float, ...],
    refresh: bool,
) -> list[dict[str, object]]:
    daily = download_data(symbol, refresh=refresh)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)

    full_engine = SwingEngine()
    full_swings = full_engine.calculate(metrics)
    full_state = full_engine.snapshot_state(symbol=symbol, timeframe="weekly")

    results: list[dict[str, object]] = []
    for ratio in split_ratios:
        split_index = int(len(metrics) * ratio)
        if split_index <= 0 or split_index >= len(metrics):
            continue

        prefix_state = snapshot_after_prefix(
            metrics,
            symbol=symbol,
            timeframe="weekly",
            split_index=split_index,
        )
        reopen_start = _reopen_start(metrics, prefix_state)
        reopened = metrics.iloc[reopen_start:].copy()

        incremental_engine = SwingEngine()
        try:
            incremental_swings = incremental_engine.calculate_from_state(
                reopened,
                prefix_state,
            )
            incremental_state = incremental_engine.snapshot_state(
                symbol=symbol,
                timeframe="weekly",
            )
            equal_swings = compare_swing_sequences(
                full_swings,
                incremental_swings,
                full_metrics=metrics,
                incremental_metrics=reopened,
            )
            equal_state = compare_state(full_state, incremental_state)
            equivalent = equal_swings and equal_state
            error = None
        except (RuntimeError, ValueError) as exc:
            equal_swings = False
            equal_state = False
            equivalent = False
            error = f"{type(exc).__name__}: {exc}"

        results.append(
            {
                "symbol": symbol,
                "split_index": split_index,
                "split_ratio": ratio,
                "reopen_start": reopen_start,
                "reopen_bars": len(reopened),
                "equal_swings": equal_swings,
                "equal_state": equal_state,
                "equivalent": equivalent,
                "error": error,
                "full_swings": len(full_swings),
                "incremental_swings": len(incremental_engine._swings),
            }
        )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify full-history vs checkpoint-continuation swing-state equivalence."
    )
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS[:3])
    parser.add_argument("--all-symbols", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    symbols = SYMBOLS if args.all_symbols else args.symbols
    split_ratios = (0.60, 0.70, 0.80)
    all_results: list[dict[str, object]] = []

    for symbol in symbols:
        try:
            all_results.extend(
                _audit_symbol(
                    symbol,
                    split_ratios=split_ratios,
                    refresh=args.refresh,
                )
            )
        except Exception as exc:
            print(f"{symbol:<14} ERROR {type(exc).__name__}: {exc}")

    print("=== INCREMENTAL SWING EQUIVALENCE AUDIT ===")
    print(f"harness revision: {HARNESS_REVISION}")
    print(f"symbols: {len(symbols)}")
    print(f"split ratios: {', '.join(f'{r:.0%}' for r in split_ratios)}")
    print()
    print(
        f"{'Symbol':<14}{'Split':>8}{'Reopen':>9}"
        f"{'Swings':>9}{'State':>8}{'Equivalent':>13}{'Full':>8}{'Inc':>8}"
    )

    for row in all_results:
        print(
            f"{str(row['symbol']):<14}"
            f"{float(row['split_ratio']):>7.0%}"
            f"{int(row['reopen_start']):>9}"
            f"{str(row['equal_swings']):>9}"
            f"{str(row['equal_state']):>8}"
            f"{str(row['equivalent']):>13}"
            f"{int(row['full_swings']):>8}"
            f"{int(row['incremental_swings']):>8}"
        )
        if row["error"]:
            print(f"{'':<14}  {row['error']}")

    print()
    print("=== CHECKPOINT EQUIVALENCE BY SYMBOL ===")
    for symbol in symbols:
        rows = [row for row in all_results if row["symbol"] == symbol]
        if not rows:
            print(f"{symbol:<14} no valid split")
            continue
        passed = sum(bool(row["equivalent"]) for row in rows)
        print(f"{symbol:<14} {passed}/{len(rows)} checkpoints equivalent")


if __name__ == "__main__":
    main()
