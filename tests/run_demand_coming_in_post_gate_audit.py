from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from matched_demand_coming_in_audit import _scan_cases
from run_nse_increasing_demand_universe_audit import SYMBOLS
from evidence.demand_coming_in import collect_demand_coming_in
from evidence.engine import EvidenceEngine
from scanner import ScannerEngine
from trend import TrendAnalyzer
from metrics_engine import MetricsEngine
from data import daily_to_weekly, download_data


def _has_event(metrics_row, index: int, previous_row) -> bool:
    engine = EvidenceEngine()
    current = engine._create_bar_context(metrics_row, index)
    previous = engine._create_bar_context(previous_row, index - 1)
    from types import SimpleNamespace
    return bool(collect_demand_coming_in(SimpleNamespace(current=current, previous=previous)))


def _outcome(row, horizon: int) -> float | None:
    return row.get("forward_return")


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-gate outcome audit for DEMAND_COMING_IN suppression.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    results: list[dict[str, object]] = []
    skipped: list[tuple[str, str, str]] = []
    for symbol in SYMBOLS:
        try:
            daily = download_data(symbol, refresh=args.refresh)
            weekly = daily_to_weekly(daily)
            metrics = MetricsEngine().calculate(weekly)
            scanner = ScannerEngine()
            sample_start = max(scanner.MIN_REPLAY_BARS + 1, len(metrics) - args.sample_bars - 10)
            history = []
            for index in range(scanner.MIN_REPLAY_BARS, len(metrics) - 10):
                replay = metrics.iloc[: index + 1].copy()
                trend = TrendAnalyzer().analyze(replay)
                evidence = EvidenceEngine().collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=list(trend.structure.structural_swings),
                )
                history.append(evidence)
                if index < sample_start:
                    continue
                candidate = scanner.evaluate(
                    trend=trend,
                    evidence=evidence,
                    history=history,
                    bar_index=index,
                    week=scanner._week_at(metrics, index),
                )
                codes = {item.code for item in evidence.evidence}
                if candidate.actionable and _has_event(metrics.iloc[index], index, metrics.iloc[index - 1]) and trend.structure.state.value == "correcting" and trend.structure.direction.value == "up":
                    results.append({"symbol": symbol, "bar_index": index, "score": candidate.base_score, "state": trend.structure.state.value, "direction": trend.structure.direction.value})
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))

    print("=== DEMAND_COMING_IN POST-GATE OUTCOME AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols scanned: {len(SYMBOLS) - len(skipped)}")
    print(f"blocked actionable cases expected: {len(results)}")
    print("This runner identifies correcting + bullish DEMAND_COMING_IN cases that remain actionable after the production gate.")
    if skipped:
        print("\n=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
