from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from scanner import ScannerEngine
from evidence.engine import EvidenceEngine
from trend import TrendAnalyzer
from background.qualification import PatternQualification
from tests.decision_outcome_audit import CONFIRMATION_ONLY_CODES, mask_confirmation_only
from tests.decision_outcome_labeling import label_outcome


SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS", "AXISBANK.NS",
    "KOTAKBANK.NS", "HINDUNILVR.NS", "BAJFINANCE.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "HCLTECH.NS", "M&M.NS", "TITAN.NS", "ULTRACEMCO.NS", "ADANIENT.NS",
    "NTPC.NS", "POWERGRID.NS", "ONGC.NS", "TATASTEEL.NS", "JSWSTEEL.NS",
    "TECHM.NS", "WIPRO.NS", "NESTLEIND.NS", "ASIANPAINT.NS", "COALINDIA.NS",
]


def _direction(candidate) -> int | None:
    if candidate.qualification is PatternQualification.PERSISTENT_BULLISH:
        return 1
    if candidate.qualification is PatternQualification.PERSISTENT_BEARISH:
        return -1
    return None


def _audit_symbol(symbol: str, sample_bars: int, horizons: tuple[int, ...], refresh: bool) -> list[dict]:
    daily = download_data(symbol, refresh=refresh)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    scanner = ScannerEngine()
    sample_start = max(scanner.MIN_REPLAY_BARS, len(metrics) - sample_bars - max(horizons))
    history = []
    rows = []

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        evidence = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=list(trend.structure.structural_swings),
        )
        history.append(evidence)
        if index < sample_start or index + min(horizons) >= len(metrics):
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

        codes = [item.code for item in evidence.evidence if item.code in CONFIRMATION_ONLY_CODES]
        if "increasing_demand" not in {str(code.value) for code in codes}:
            continue

        direction = _direction(baseline)
        if direction is None:
            continue

        for horizon in horizons:
            if index + horizon >= len(metrics):
                continue
            outcome = label_outcome(metrics, signal_index=index, direction=direction, horizon=horizon)
            rows.append({
                "symbol": symbol,
                "state": str(trend.structure.state.value),
                "change": f"{baseline.actionable}->{masked.actionable}",
                "horizon": horizon,
                "return": outcome.forward_return,
                "positive": outcome.forward_return > 0,
            })

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Large-universe increasing_demand audit.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    horizons = (3, 5, 10)

    all_rows = []
    skipped = []
    for symbol in SYMBOLS:
        try:
            rows = _audit_symbol(symbol, args.sample_bars, horizons, args.refresh)
            all_rows.extend(rows)
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))

    print("=== NSE INCREASING_DEMAND UNIVERSE AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols with results: {len({r['symbol'] for r in all_rows})}")
    print(f"total case-horizon rows: {len(all_rows)}")
    print()
    print(f"{'State':<12}{'Change':<14}{'Horizon':>8}{'Cases':>8}{'MeanRet':>12}{'Positive':>10}")

    groups = {}
    for row in all_rows:
        key = (row["state"], row["change"], row["horizon"])
        groups.setdefault(key, []).append(row)

    for key in sorted(groups):
        state, change, horizon = key
        rows = groups[key]
        mean_return = sum(r["return"] for r in rows) / len(rows)
        positives = sum(r["positive"] for r in rows)
        print(f"{state:<12}{change:<14}{horizon:>8}{len(rows):>8}{mean_return:>11.3%}{positives:>6}/{len(rows):<4}")

    print()
    print("=== SYMBOL COVERAGE ===")
    for symbol in SYMBOLS:
        count = sum(r["symbol"] == symbol for r in all_rows)
        print(f"{symbol:<14}{count:>6}")

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
