from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from background.qualification import PatternQualification
from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from scanner import ScannerEngine
from tests.decision_outcome_audit import CONFIRMATION_ONLY_CODES, compare_candidate_outcome
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

        comparison = compare_candidate_outcome(
            scanner,
            trend=trend,
            evidence=evidence,
            history=history,
            metrics=metrics,
            bar_index=index,
            direction=direction,
            horizon=horizon,
        )
        if comparison.changed_actionability:
            results.append(
                (index, comparison.baseline, comparison.masked, comparison.outcome, evidence)
            )

    return results


def run_symbol(symbol: str, horizon: int, sample_bars: int, refresh: bool):
    daily = download_data(symbol, refresh=refresh)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    scanner = ScannerEngine()
    sample_start = max(scanner.MIN_REPLAY_BARS, len(metrics) - sample_bars - horizon)
    cases = _scan_history(metrics, scanner, sample_start, horizon)
    return cases, len(daily), len(weekly), sample_start, weekly


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit confirmation-only VSA evidence against future outcomes."
    )
    parser.add_argument(
        "symbols", nargs="+", help="Symbols accepted by data.download_data(), e.g. RELIANCE.NS TCS.NS"
    )
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--sample-bars", type=int, default=260)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--output", default="confirmation_outcome_changed_cases.csv")
    args = parser.parse_args()

    if args.horizon <= 0 or args.sample_bars <= 0:
        raise SystemExit("--horizon and --sample-bars must be greater than zero")

    rows = []
    summary = []
    for symbol in args.symbols:
        cases, daily_bars, weekly_bars, sample_start, weekly = run_symbol(
            symbol, args.horizon, args.sample_bars, args.refresh
        )
        true_to_false = sum(c[1].actionable and not c[2].actionable for c in cases)
        false_to_true = sum(not c[1].actionable and c[2].actionable for c in cases)
        summary.append((symbol, len(cases), true_to_false, false_to_true))

        for index, baseline, masked, outcome, evidence in cases:
            week = str(weekly.iloc[index]["week_beginning"])
            confirmation_codes = tuple(
                str(item.code)
                for item in evidence.evidence
                if item.code in CONFIRMATION_ONLY_CODES
            )
            rows.append(
                {
                    "symbol": symbol,
                    "bar_index": index,
                    "week": week,
                    "change": f"{baseline.actionable}->{masked.actionable}",
                    "baseline_score": baseline.base_score,
                    "masked_score": masked.base_score,
                    "score_delta": masked.base_score - baseline.base_score,
                    "baseline_pressure": baseline.net_pressure,
                    "masked_pressure": masked.net_pressure,
                    "pressure_delta": masked.net_pressure - baseline.net_pressure,
                    "confirmation_only_codes": ",".join(confirmation_codes),
                    "forward_return": outcome.forward_return,
                    "mfe": outcome.maximum_favorable_excursion,
                    "mae": outcome.maximum_adverse_excursion,
                    "daily_bars": daily_bars,
                    "weekly_bars": weekly_bars,
                    "sample_start": sample_start,
                    "horizon": args.horizon,
                }
            )

    _write_csv(Path(args.output), rows)

    print("\n=== CHANGED ACTIONABILITY SUMMARY ===")
    print(f"{'Symbol':<14}{'Changed':>9}{'True->False':>14}{'False->True':>14}")
    total = [0, 0, 0]
    for symbol, changed, ttf, ftt in summary:
        print(f"{symbol:<14}{changed:>9}{ttf:>14}{ftt:>14}")
        total[0] += changed
        total[1] += ttf
        total[2] += ftt
    print(f"{'TOTAL':<14}{total[0]:>9}{total[1]:>14}{total[2]:>14}")
    print(f"\nFull changed-case report: {Path(args.output).resolve()}")

    if rows:
        print("\n=== CHANGED CASES ===")
        print(
            f"{'Symbol':<14}{'Bar':>6}{'Change':>12}{'ScoreΔ':>11}"
            f"{'PressΔ':>11}{'Return':>12}{'MFE':>10}{'MAE':>10}  Codes"
        )
        for row in rows:
            print(
                f"{row['symbol']:<14}{row['bar_index']:>6}{row['change']:>12}"
                f"{row['score_delta']:>11.4f}{row['pressure_delta']:>11.4f}"
                f"{row['forward_return']:>12.4%}{row['mfe']:>10.4%}{row['mae']:>10.4%}  "
                f"{row['confirmation_only_codes'] or '-'}"
            )


if __name__ == "__main__":
    main()
