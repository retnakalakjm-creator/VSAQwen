"""Hypothetical weight sensitivity audit for DEMAND_COMING_IN.

Analysis-only. Replays the exact candidate definition point-in-time,
adds a synthetic DEMAND_COMING_IN evidence item at several hypothetical
weights, and measures whether the resulting background bias changes.
Production collection/registration is untouched.
"""
from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE_POSITION, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS, COL_WEEK
from evidence.engine import EvidenceEngine
from evidence.evidence_registry import build_evidence
from evidence.scoring import _score_bias
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
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
WEIGHTS = (0.00, 0.25, 0.30, 0.38, 0.45, 0.50)


def is_candidate(row) -> bool:
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
        and int(row[COL_CLOSE_POSITION]) >= 2
    )


def inspect_symbol(symbol: str) -> list[dict]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    rows: list[dict] = []

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        if not is_candidate(metrics.iloc[index]):
            continue

        replay = metrics.iloc[: index + 1]
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=replay,
        )

        synthetic = []
        for weight in WEIGHTS:
            synthetic.append(
                build_evidence(
                    EvidenceCode.DEMAND_COMING_IN,
                    bar_index=index,
                    week_beginning=str(metrics.iloc[index][COL_WEEK]),
                    weight=weight,
                )
            )

        baseline_bias = _score_bias(list(result.evidence))
        biases = {
            weight: _score_bias([*result.evidence, item])
            for weight, item in zip(WEIGHTS, synthetic)
        }

        rows.append({
            "symbol": symbol,
            "bar_index": index,
            "baseline_bias": baseline_bias.name,
            "biases": {str(weight): bias.name for weight, bias in biases.items()},
        })

    return rows


def main() -> None:
    symbols = tuple(sys.argv[1:]) or SYMBOLS
    rows: list[dict] = []
    failures: list[dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                rows.extend(future.result())
            except Exception as exc:  # noqa: BLE001
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("DEMAND COMING IN WEIGHT SENSITIVITY AUDIT")
    print({
        "symbols": len(symbols),
        "candidate_events": len(rows),
        "weights_tested": WEIGHTS,
        "failures": failures,
        "production_weight": 0.0,
        "production_path": "DISABLED",
    })

    for weight in WEIGHTS:
        changed = [row for row in rows if row["biases"][str(weight)] != row["baseline_bias"]]
        print(
            {
                "weight": weight,
                "bias_changes": len(changed),
                "bias_change_rate": len(changed) / len(rows) if rows else 0.0,
                "resulting_biases": dict(Counter(row["biases"][str(weight)] for row in rows)),
            }
        )

    print("DEMAND COMING IN WEIGHT SENSITIVITY BY_SYMBOL")
    for symbol in symbols:
        symbol_rows = [row for row in rows if row["symbol"] == symbol]
        print(symbol, {
            "events": len(symbol_rows),
            **{
                str(weight): sum(
                    row["biases"][str(weight)] != row["baseline_bias"]
                    for row in symbol_rows
                )
                for weight in WEIGHTS
            },
        })


if __name__ == "__main__":
    main()
