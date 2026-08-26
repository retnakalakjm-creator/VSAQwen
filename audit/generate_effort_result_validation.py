"""Generate the historical dataset used by the Effort vs Result audit.

This script is observational only. It does not enable the Effort collector.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_RATIO,
    COL_DIRECTION,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_SPREAD_RATIO,
    COL_VOLUME,
    COL_VOLUME_RATIO,
    COL_WEEK,
)
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from scanner import ScannerEngine
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "ASIANPAINT.NS",
    "BHARTIARTL.NS",
    "COALINDIA.NS",
    "ETERNAL.NS",
    "HDFCBANK.NS",
    "JUBLFOOD.NS",    
    "GODREJPROP.NS",
    "NTPC.NS",
    "RELIANCE.NS",
    "SBILIFE.NS",   
)

OUTPUT_COLUMNS = (
    "symbol",
    "bar_index",
    COL_WEEK,
    COL_OPEN,
    COL_HIGH,
    COL_LOW,
    COL_CLOSE,
    COL_VOLUME,
    COL_VOLUME_RATIO,
    COL_SPREAD_RATIO,
    COL_CLOSE_RATIO,
    COL_DIRECTION,
    "trend_direction",
    "trend_state",
    "existing_events",
)


def _json_events(candidate) -> str:
    return json.dumps(
        [
            {
                "code": str(item.code),
                "category": str(item.category),
                "bar_index": item.bar_index,
            }
            for item in candidate.target_bar_evidence
        ],
        separators=(",", ":"),
    )


def _json_current_events(evidence) -> str:
    """Serialize all evidence emitted for the target bar by the production engine."""
    return json.dumps(
        [
            {
                "code": str(item.code),
                "category": str(item.category),
                "bar_index": item.bar_index,
            }
            for item in evidence.evidence
        ],
        separators=(",", ":"),
    )


def generate_symbol(symbol: str, *, refresh: bool = False) -> pd.DataFrame:
    daily = download_data(symbol, refresh=refresh)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)

    scanner = ScannerEngine()
    trend_analyzer = TrendAnalyzer()
    evidence_engine = EvidenceEngine()
    history = []
    rows: list[dict[str, object]] = []

    for bar_index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        replay = metrics.iloc[: bar_index + 1]
        trend = trend_analyzer.analyze(replay)
        structural_swings = list(trend.structure.structural_swings)
        evidence = evidence_engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        history.append(evidence)
        candidate = scanner.evaluate(
            trend=trend,
            evidence=evidence,
            history=history,
            bar_index=bar_index,
            week=scanner._week_at(metrics, bar_index),
        )

        row = metrics.iloc[bar_index]
        rows.append(
            {
                "symbol": symbol,
                "bar_index": bar_index,
                COL_WEEK: row[COL_WEEK],
                COL_OPEN: row[COL_OPEN],
                COL_HIGH: row[COL_HIGH],
                COL_LOW: row[COL_LOW],
                COL_CLOSE: row[COL_CLOSE],
                COL_VOLUME: row[COL_VOLUME],
                COL_VOLUME_RATIO: row[COL_VOLUME_RATIO],
                COL_SPREAD_RATIO: row[COL_SPREAD_RATIO],
                COL_CLOSE_RATIO: row[COL_CLOSE_RATIO],
                COL_DIRECTION: row[COL_DIRECTION],
                "trend_direction": str(trend.structure.direction),
                "trend_state": str(trend.structure.state),
                "existing_events": _json_current_events(evidence),
            }
        )

    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("historical_effort_result_validation.csv"),
    )
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    frames = [
        generate_symbol(symbol, refresh=args.refresh)
        for symbol in args.symbols
    ]
    result = pd.concat(frames, ignore_index=True)
    result.to_csv(args.output, index=False)
    print(f"Wrote {len(result)} rows to {args.output}")


if __name__ == "__main__":
    main()
