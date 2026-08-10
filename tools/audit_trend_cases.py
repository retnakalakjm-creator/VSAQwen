"""Audit representative real-market VSA events before tuning context weights."""

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

TARGET_CASES = (
    ("UPTHRUST", "HEALTHY", "IMPROVING"),
    ("UPTHRUST", "HEALTHY", "STABLE"),
    ("UPTHRUST", "EXHAUSTED", "BREAKING"),
    ("SUPPLY_COMING_IN", "HEALTHY", "IMPROVING"),
    ("SUPPLY_COMING_IN", "EXHAUSTED", "BREAKING"),
    ("SHAKEOUT", "HEALTHY", None),
)


def _components(code: EvidenceCode, engine: EvidenceEngine) -> dict[str, float]:
    ctx = engine._ctx
    assert ctx is not None

    expected_bullish = code is EvidenceCode.SHAKEOUT
    environment = WeightCalculator._environment_adjustment(expected_bullish, ctx)

    if code is EvidenceCode.SHAKEOUT:
        trend = WeightCalculator._shakeout_trend_adjustment(
            ctx.trend.direction, ctx.trend.state
        )
    elif code is EvidenceCode.UPTHRUST:
        trend = WeightCalculator._upthrust_trend_adjustment(
            ctx.trend.direction, ctx.trend.state
        )
    else:
        trend = WeightCalculator._supply_coming_in_trend_adjustment(
            ctx.trend.direction, ctx.trend.state
        )

    structure = WeightCalculator._directional_structure_adjustment(
        expected_bullish, ctx.structural_pattern
    )

    return {
        "environment": environment,
        "trend": trend,
        "structure": structure,
    }


def _find_cases() -> list[dict]:
    candidates: list[dict] = []

    for path in sorted(CACHE_DIR.glob("*.NS.csv")):
        try:
            daily = pd.read_csv(path, index_col=0, parse_dates=True)
            validate_data(daily)
            weekly = daily_to_weekly(daily)
            metrics = MetricsEngine().calculate(weekly)
        except Exception:
            continue

        symbol = path.stem
        for target_index in range(2, len(metrics)):
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
            except Exception:
                continue

            for item in result.evidence:
                if item.code not in TARGET_EVENTS:
                    continue

                candidates.append(
                    {
                        "symbol": symbol,
                        "bar_index": int(item.bar_index),
                        "event": item.code.name,
                        "trend_direction": trend.structure.direction.name,
                        "trend_state": trend.structure.state.name,
                        "structural_pattern": structural_pattern.name,
                        "strength": getattr(item, "strength", None),
                        "weight": getattr(item, "weight", None),
                        "components": _components(item.code, engine),
                        "metrics": metrics,
                        "evidence": result.evidence,
                    }
                )

    return candidates


def _matches(row: dict, target: tuple[str, str, str | None]) -> bool:
    event, state, structure = target
    return (
        row["event"] == event
        and row["trend_state"] == state
        and (structure is None or row["structural_pattern"] == structure)
    )


def _print_case(row: dict, number: int, target: tuple[str, str, str | None]) -> None:
    print("\n" + "=" * 78)
    print(f"CASE {number}: requested={target}")
    print("=" * 78)
    print(
        f"symbol={row['symbol']}  bar_index={row['bar_index']}  "
        f"event={row['event']}  trend={row['trend_direction']}/{row['trend_state']}  "
        f"structure={row['structural_pattern']}"
    )
    print(f"strength={row['strength']}  weight={row['weight']}")
    print(f"adjustments={row['components']}")

    evidence_at_bar = [
        item for item in row["evidence"] if int(item.bar_index) == row["bar_index"]
    ]
    print("evidence_on_event_bar:")
    for item in evidence_at_bar:
        print(
            f"  {item.code.name} direction={item.direction.name} "
            f"strength={getattr(item, 'strength', None)} "
            f"quality={getattr(item, 'quality', None)} "
            f"weight={getattr(item, 'weight', None)}"
        )

    metrics = row["metrics"]
    start = max(0, row["bar_index"] - 4)
    end = min(len(metrics), row["bar_index"] + 4)
    window = metrics.iloc[start:end].copy()
    columns = [c for c in ("open", "high", "low", "close", "volume") if c in window.columns]
    print("weekly_ohlcv_window:")
    print(window[columns].to_string())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all-cases", action="store_true")
    args = parser.parse_args()

    candidates = _find_cases()
    print(f"Candidate events audited: {len(candidates)}")

    used_symbols: set[str] = set()
    selected: list[dict] = []

    for target in TARGET_CASES:
        pool = [row for row in candidates if _matches(row, target)]
        unused = [row for row in pool if row["symbol"] not in used_symbols]
        row = unused[0] if unused else (pool[0] if pool else None)
        if row is None:
            print(f"NOT FOUND: {target}")
            continue
        selected.append(row)
        used_symbols.add(row["symbol"])

    for number, (target, row) in enumerate(zip(TARGET_CASES, selected), start=1):
        _print_case(row, number, target)


if __name__ == "__main__":
    main()
