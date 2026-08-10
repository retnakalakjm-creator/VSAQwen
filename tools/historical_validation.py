"""Historical VSA event validation runner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import CACHE_DIR
from data import daily_to_weekly, validate_data
from engine.columns import COL_WEEK
from evidence.engine import EvidenceEngine
from evidence.weight import WeightCalculator
from market_structure.progression import determine_structural_pattern
from metrics_engine import MetricsEngine
from models import EvidenceCode
from trend import TrendAnalyzer

TARGET_EVENTS = {
    EvidenceCode.SHAKEOUT,
    EvidenceCode.UPTHRUST,
    EvidenceCode.SUPPLY_COMING_IN,
}


def iter_cache_files(limit: int | None = None, nse_only: bool = True):
    files = sorted(CACHE_DIR.glob("*.NS.csv")) if nse_only else sorted(CACHE_DIR.glob("*.csv"))
    if limit is not None:
        files = files[:limit]
    return files


def _weight_components(code: EvidenceCode, engine: EvidenceEngine) -> dict:
    """Expose the current calculator inputs without changing production logic."""
    ctx = engine._ctx
    if ctx is None:
        return {}

    expected_bullish = code is EvidenceCode.SHAKEOUT
    environment = WeightCalculator._environment_adjustment(expected_bullish, ctx)

    if code is EvidenceCode.SHAKEOUT:
        trend = WeightCalculator._shakeout_trend_adjustment(ctx.trend.direction, ctx.trend.state)
    elif code is EvidenceCode.UPTHRUST:
        trend = WeightCalculator._upthrust_trend_adjustment(ctx.trend.direction, ctx.trend.state)
    elif code is EvidenceCode.SUPPLY_COMING_IN:
        trend = WeightCalculator._supply_coming_in_trend_adjustment(ctx.trend.direction, ctx.trend.state)
    else:
        trend = 0.0

    structure = WeightCalculator._directional_structure_adjustment(expected_bullish, ctx.structural_pattern)

    return {
        "base_weight": 1.0,
        "environment_adjustment": environment,
        "trend_adjustment": trend,
        "structural_adjustment": structure,
    }


def validate_symbol(path: Path) -> tuple[list[dict], str | None]:
    symbol = path.stem

    try:
        daily = pd.read_csv(path, index_col=0, parse_dates=True)
        validate_data(daily)
        weekly = daily_to_weekly(daily)
        metrics = MetricsEngine().calculate(weekly)
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"

    rows: list[dict] = []
    seen: set[tuple[str, int]] = set()

    for target_index in range(len(metrics)):
        if target_index < 2:
            continue

        replay_metrics = metrics.iloc[: target_index + 1].copy()

        try:
            trend = TrendAnalyzer().analyze(replay_metrics)
            structural_swings = tuple(trend.structure.structural_swings)
            structural_pattern = determine_structural_pattern(trend.structure.swings)

            engine = EvidenceEngine()
            result = engine.collect(
                metrics=replay_metrics,
                trend=trend,
                structural_swings=structural_swings,
                validation_metrics=metrics,
            )
        except Exception as exc:
            return rows, f"bar {target_index}: {type(exc).__name__}: {exc}"

        for item in result.evidence:
            if item.code not in TARGET_EVENTS:
                continue

            key = (item.code.name, int(item.bar_index))
            if key in seen:
                continue
            seen.add(key)

            components = _weight_components(item.code, engine)
            week = replay_metrics.iloc[-1][COL_WEEK]

            rows.append({
                "symbol": symbol,
                "bar_index": int(item.bar_index),
                "week": str(week),
                "event": item.code.name,
                "trend_direction": trend.structure.direction.name,
                "trend_state": trend.structure.state.name,
                "structural_pattern": structural_pattern.name,
                "quality": getattr(item, "strength", None),
                "weight": getattr(item, "weight", None),
                **components,
            })

    return rows, None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--all-exchanges", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("historical_validation.csv"))
    args = parser.parse_args()

    rows: list[dict] = []
    failures: list[dict] = []
    files = iter_cache_files(args.limit, nse_only=not args.all_exchanges)

    print(f"NSE-only: {not args.all_exchanges}")
    print(f"Cache files selected: {len(files)}")

    for path in files:
        symbol_rows, error = validate_symbol(path)
        rows.extend(symbol_rows)
        if error is not None:
            failures.append({"symbol": path.stem, "error": error})
        print(f"{path.stem}: events={len(symbol_rows)}" + (f" ERROR={error}" if error else ""))

    pd.DataFrame(rows).to_csv(args.output, index=False)

    failure_path = args.output.with_name(f"{args.output.stem}_failures.csv")
    pd.DataFrame(failures).to_csv(failure_path, index=False)

    print(f"\nSymbols processed: {len(files)}")
    print(f"Events collected: {len(rows)}")
    print(f"Failures: {len(failures)}")
    print(f"Output: {args.output}")
    print(f"Failures: {failure_path}")


if __name__ == "__main__":
    main()
