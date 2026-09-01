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
from tests.full_scanner_equivalence_harness import run_production_path_equivalence
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS

HARNESS_REVISION = "2026-09-01-full-scanner-production-path-v1"


def _audit_symbol(
    symbol: str,
    *,
    split_ratios: tuple[float, ...],
    refresh: bool,
) -> list[dict[str, object]]:
    daily = download_data(symbol, refresh=refresh)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)

    results: list[dict[str, object]] = []
    for ratio in split_ratios:
        target_index = int(len(metrics) * ratio)
        if target_index < ScannerEngine.MIN_REPLAY_BARS or target_index >= len(metrics):
            continue

        result = run_production_path_equivalence(
            metrics,
            target_index=target_index,
        )
        results.append(
            {
                "symbol": symbol,
                "split_ratio": ratio,
                "target_index": target_index,
                "equivalent": result.equivalent,
                "historical_actionable": result.scan_to_index.actionable,
                "latest_actionable": (
                    result.scan_actionable.actionable
                    if result.scan_actionable is not None
                    else False
                ),
                "qualification": str(result.scan_to_index.qualification),
                "historical_score": result.scan_to_index.net_strength,
                "latest_score": (
                    result.scan_actionable.net_strength
                    if result.scan_actionable is not None
                    else None
                ),
                "historical_evidence": tuple(result.scan_to_index.scoring_evidence_codes),
                "latest_evidence": (
                    tuple(result.scan_actionable.scoring_evidence_codes)
                    if result.scan_actionable is not None
                    else (),
                ),
            }
        )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare the existing production scanner paths at historical cutoffs."
    )
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS[:2])
    parser.add_argument("--all-symbols", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    symbols = SYMBOLS if args.all_symbols else args.symbols
    split_ratios = (0.60, 0.70, 0.80)
    all_results: list[dict[str, object]] = []

    for symbol in symbols:
        try:
            all_results.extend(
                _audit_symbol(
                    symbol,
                    split_ratios=split_ratios,
                    refresh=args.refresh,
                )
            )
        except Exception as exc:
            print(f"{symbol:<14} ERROR {type(exc).__name__}: {exc}")

    print("=== FULL SCANNER PRODUCTION-PATH EQUIVALENCE AUDIT ===")
    print(f"harness revision: {HARNESS_REVISION}")
    print(f"symbols: {len(symbols)}")
    print(f"split ratios: {', '.join(f'{r:.0%}' for r in split_ratios)}")
    print()
    print(
        f"{'Symbol':<14}{'Split':>8}{'Target':>9}"
        f"{'Equivalent':>13}{'HistAct':>10}{'LatestAct':>11}"
        f"{'ScoreΔ':>12}"
    )

    for row in all_results:
        historical_score = row["historical_score"]
        latest_score = row["latest_score"]
        score_delta = (
            None
            if latest_score is None
            else float(latest_score) - float(historical_score)
        )
        score_text = "n/a" if score_delta is None else f"{score_delta:+.6f}"
        print(
            f"{str(row['symbol']):<14}"
            f"{float(row['split_ratio']):>7.0%}"
            f"{int(row['target_index']):>9}"
            f"{str(row['equivalent']):>13}"
            f"{str(row['historical_actionable']):>10}"
            f"{str(row['latest_actionable']):>11}"
            f"{score_text:>12}"
        )
        if not row["equivalent"]:
            print(f"{'':<14} qualification={row['qualification']}")
            print(f"{'':<14} historical evidence={row['historical_evidence']}")
            print(f"{'':<14} latest evidence={row['latest_evidence']}")

    print()
    print("=== EQUIVALENCE SUMMARY ===")
    total = len(all_results)
    passed = sum(bool(row["equivalent"]) for row in all_results)
    print(f"passed: {passed}/{total}")
    print("status:", "PASS" if total and passed == total else "REVIEW")


if __name__ == "__main__":
    main()
