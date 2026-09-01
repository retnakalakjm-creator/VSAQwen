from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from professional.scoring_engine import ProfessionalScoringEngine
from scanner import ScannerEngine
from trend import TrendAnalyzer
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS


HORIZONS = (3, 5, 10)
WEIGHTS = (0.00, 0.10, 0.15, 0.20, 0.25, 0.30, 0.38)


def _score_with_weight(scanner, trend, evidence, bar_index: int, weight: float):
    import config
    from model.evidence_result_model import EvidenceResult
    from models import EvidenceCode

    original = config.EFFORT_EVIDENCE_WEIGHTS.get(EvidenceCode.ABSORPTION)
    config.EFFORT_EVIDENCE_WEIGHTS[EvidenceCode.ABSORPTION] = weight
    try:
        return scanner.evaluate(
            trend=trend,
            evidence=evidence,
            history=[evidence],
            bar_index=bar_index,
        )
    finally:
        if original is None:
            config.EFFORT_EVIDENCE_WEIGHTS.pop(EvidenceCode.ABSORPTION, None)
        else:
            config.EFFORT_EVIDENCE_WEIGHTS[EvidenceCode.ABSORPTION] = original


def _scan_symbol(symbol: str, sample_bars: int, refresh: bool):
    daily = download_data(symbol, refresh=refresh)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    scanner = ScannerEngine()
    engine = EvidenceEngine()
    sample_start = max(scanner.MIN_REPLAY_BARS, len(metrics) - sample_bars - 10)
    rows = []

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        if index < sample_start:
            continue
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        evidence = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=list(trend.structure.structural_swings),
        )
        target = [item for item in evidence.evidence if str(item.code) == "absorption"]
        if not target:
            continue

        baseline = _score_with_weight(scanner, trend, evidence, index, 0.0)
        for weight in WEIGHTS:
            candidate = _score_with_weight(scanner, trend, evidence, index, weight)
            rows.append(
                {
                    "symbol": symbol,
                    "bar_index": index,
                    "weight": weight,
                    "absorption_events": len(target),
                    "baseline_strength": baseline.net_strength,
                    "candidate_strength": candidate.net_strength,
                    "baseline_confidence": baseline.confidence,
                    "candidate_confidence": candidate.confidence,
                    "baseline_actionable": baseline.actionable,
                    "candidate_actionable": candidate.actionable,
                    "strength_delta": candidate.net_strength - baseline.net_strength,
                    "confidence_delta": candidate.confidence - baseline.confidence,
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="ABSORPTION production-path ranking impact audit.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--symbols", nargs="+", default=None)
    args = parser.parse_args()

    symbols = tuple(args.symbols) if args.symbols else tuple(SYMBOLS)
    all_rows = []
    failures = []

    for symbol in symbols:
        try:
            all_rows.extend(_scan_symbol(symbol, args.sample_bars, args.refresh))
        except Exception as exc:
            failures.append((symbol, type(exc).__name__, str(exc)))

    print("=== ABSORPTION PRODUCTION RANKING-IMPACT AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols with results: {len({row['symbol'] for row in all_rows})}")
    print(f"production ABSORPTION emissions: {len({(r['symbol'], r['bar_index']) for r in all_rows})}")
    print(f"weights tested: {WEIGHTS}")
    print()
    print(f"{'Weight':>8}{'Events':>8}{'Mean dStrength':>17}{'Mean dConfidence':>18}{'Actionable 0':>14}{'Actionable 1':>14}{'Gained':>9}{'Lost':>8}")

    grouped = defaultdict(list)
    for row in all_rows:
        grouped[row["weight"]].append(row)

    for weight in WEIGHTS:
        rows = grouped.get(weight, [])
        if not rows:
            continue
        print(
            f"{weight:>8.2f}{len(rows):>8}"
            f"{sum(r['strength_delta'] for r in rows)/len(rows):>17.4f}"
            f"{sum(r['confidence_delta'] for r in rows)/len(rows):>18.4f}"
            f"{sum(r['baseline_actionable'] for r in rows):>14}"
            f"{sum(r['candidate_actionable'] for r in rows):>14}"
            f"{sum((not r['baseline_actionable']) and r['candidate_actionable'] for r in rows):>9}"
            f"{sum(r['baseline_actionable'] and (not r['candidate_actionable']) for r in rows):>8}"
        )

    print()
    print("=== ABSORPTION EMISSION COVERAGE ===")
    per_symbol = defaultdict(int)
    for row in all_rows:
        if row["weight"] == 0.0:
            per_symbol[row["symbol"]] += 1
    for symbol in symbols:
        print(f"{symbol:<16}{per_symbol[symbol]:>6}")

    if failures:
        print("\n=== FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<16}{error_type}: {message}")


if __name__ == "__main__":
    main()
