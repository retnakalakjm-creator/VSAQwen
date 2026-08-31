from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from background.qualification import PatternQualification
from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from scanner import ScannerEngine
from trend import TrendAnalyzer
from tests.decision_outcome_audit import CONFIRMATION_ONLY_CODES, mask_confirmation_only
from tests.decision_outcome_labeling import label_outcome


def _direction(candidate) -> int | None:
    if candidate.qualification is PatternQualification.PERSISTENT_BULLISH:
        return 1
    if candidate.qualification is PatternQualification.PERSISTENT_BEARISH:
        return -1
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit increasing_demand across multiple forward horizons.")
    parser.add_argument("symbols", nargs="+", help="Symbols, e.g. RELIANCE.NS TCS.NS INFY.NS")
    parser.add_argument("--sample-bars", type=int, default=260)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    horizons = (3, 5, 10)
    scanner = ScannerEngine()
    buckets: dict[tuple[str, str, str, int], list[float]] = defaultdict(list)
    counts: dict[tuple[str, str, str, int], int] = defaultdict(int)

    for symbol in args.symbols:
        daily = download_data(symbol, refresh=args.refresh)
        weekly = daily_to_weekly(daily)
        metrics = MetricsEngine().calculate(weekly)
        sample_start = max(scanner.MIN_REPLAY_BARS, len(metrics) - args.sample_bars - max(horizons))
        history = []

        for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
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

            confirmation_items = [
                item for item in evidence.evidence
                if item.code in CONFIRMATION_ONLY_CODES and str(item.code) == "increasing_demand"
            ]
            if not confirmation_items:
                continue

            baseline = scanner.evaluate(
                trend=trend,
                evidence=evidence,
                history=history,
                bar_index=index,
                week=scanner._week_at(metrics, index),
            )
            masked = scanner.evaluate(
                trend=trend,
                evidence=mask_confirmation_only(evidence),
                history=history,
                bar_index=index,
                week=scanner._week_at(metrics, index),
            )
            if baseline.actionable == masked.actionable:
                continue

            direction = _direction(baseline)
            if direction is None:
                continue

            change = f"{baseline.actionable}->{masked.actionable}"
            state = str(trend.structure.state)
            for horizon in horizons:
                if index + horizon >= len(metrics):
                    continue
                outcome = label_outcome(metrics, signal_index=index, direction=direction, horizon=horizon)
                key = (symbol, state, change, horizon)
                buckets[key].append(outcome.forward_return)
                counts[key] += 1

    print("=== INCREASING_DEMAND HORIZON AUDIT ===")
    print(f"{'Symbol':<14} {'State':<12} {'Change':<14} {'Horizon':>7} {'Cases':>7} {'MeanRet':>11} {'Positive':>9}")
    for key in sorted(buckets):
        symbol, state, change, horizon = key
        returns = buckets[key]
        positive = sum(value > 0 for value in returns)
        mean_return = sum(returns) / len(returns)
        print(f"{symbol:<14} {state:<12} {change:<14} {horizon:>7} {len(returns):>7} {mean_return:>10.4%} {positive:>8}/{len(returns)}")


if __name__ == "__main__":
    main()
