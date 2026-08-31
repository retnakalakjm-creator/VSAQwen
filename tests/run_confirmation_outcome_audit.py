from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from scanner import ScannerEngine
from evidence.engine import EvidenceEngine
from tests.decision_outcome_audit import mask_confirmation_only
from tests.decision_outcome_labeling import label_outcome
from background.qualification import PatternQualification
from trend import TrendAnalyzer


def _direction(candidate) -> int | None:
    if candidate.qualification is PatternQualification.PERSISTENT_BULLISH:
        return 1
    if candidate.qualification is PatternQualification.PERSISTENT_BEARISH:
        return -1
    return None


def _scan_history(metrics, scanner: ScannerEngine, sample_start: int, horizon: int):
    history = []
    results = []

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = list(trend.structure.structural_swings)
        evidence = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        history.append(evidence)

        if index < sample_start or index + horizon >= len(metrics):
            continue

        baseline = scanner.evaluate(
            trend=trend,
            evidence=evidence,
            history=history,
            bar_index=index,
            week=scanner._week_at(metrics, index),
        )
        direction = _direction(baseline)
        if direction is None:
            continue

        masked = scanner.evaluate(
            trend=trend,
            evidence=mask_confirmation_only(evidence),
            history=history,
            bar_index=index,
            week=scanner._week_at(metrics, index),
        )
        outcome = label_outcome(
            metrics,
            signal_index=index,
            direction=direction,
            horizon=horizon,
        )

        results.append((baseline, masked, outcome))

    return results


def _summarize(results):
    complete = [item for item in results if item[2].complete]
    actionable = [item for item in complete if item[0].actionable]
    masked_actionable = [item for item in complete if item[1].actionable]

    def avg(items, field):
        values = [getattr(item[2], field) for item in items]
        values = [value for value in values if value is not None]
        return (sum(values) / len(values)) if values else None

    return {
        "signals": len(results),
        "complete": len(complete),
        "baseline_actionable": len(actionable),
        "masked_actionable": len(masked_actionable),
        "changed_actionability": sum(item[0].actionable != item[1].actionable for item in complete),
        "baseline_mean_return": avg(actionable, "forward_return"),
        "masked_mean_return": avg(masked_actionable, "forward_return"),
        "baseline_mean_mfe": avg(actionable, "maximum_favorable_excursion"),
        "masked_mean_mfe": avg(masked_actionable, "maximum_favorable_excursion"),
        "baseline_mean_mae": avg(actionable, "maximum_adverse_excursion"),
        "masked_mean_mae": avg(masked_actionable, "maximum_adverse_excursion"),
    }


def run_symbol(symbol: str, horizon: int, sample_bars: int, refresh: bool) -> dict:
    daily = download_data(symbol, refresh=refresh)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)

    scanner = ScannerEngine()
    sample_start = max(
        scanner.MIN_REPLAY_BARS,
        len(metrics) - sample_bars - horizon,
    )
    results = _scan_history(metrics, scanner, sample_start, horizon)
    summary = _summarize(results)
    summary.update({
        "symbol": symbol,
        "daily_bars": len(daily),
        "weekly_bars": len(weekly),
        "sample_start": sample_start,
        "horizon": horizon,
    })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit confirmation-only VSA evidence against future outcomes.")
    parser.add_argument("symbols", nargs="+", help="Symbols accepted by data.download_data(), e.g. RELIANCE.NS TCS.NS")
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--sample-bars", type=int, default=260)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    if args.horizon <= 0:
        raise SystemExit("--horizon must be greater than zero")
    if args.sample_bars <= 0:
        raise SystemExit("--sample-bars must be greater than zero")

    for symbol in args.symbols:
        summary = run_symbol(
            symbol,
            horizon=args.horizon,
            sample_bars=args.sample_bars,
            refresh=args.refresh,
        )
        print(f"\n=== {symbol} ===")
        for key, value in summary.items():
            if key != "symbol":
                print(f"{key}: {value}")


if __name__ == "__main__":
    main()
