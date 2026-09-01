from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from tests.full_scanner_incremental_equivalence_harness import run_incremental_equivalence
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS

HARNESS_REVISION = "2026-09-01-full-scanner-incremental-v1"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare full scanner with persisted-state continuation.")
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS[:2])
    parser.add_argument("--all-symbols", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    symbols = SYMBOLS if args.all_symbols else args.symbols
    ratios = (0.60, 0.70, 0.80)
    rows: list[tuple] = []

    for symbol in symbols:
        try:
            daily = download_data(symbol, refresh=args.refresh)
            weekly = daily_to_weekly(daily)
            metrics = MetricsEngine().calculate(weekly)
            for ratio in ratios:
                target = int(len(metrics) * ratio)
                result = run_incremental_equivalence(metrics, target_index=target, symbol=symbol)
                rows.append((symbol, ratio, target, result.state_schema_version, result.equivalent, result.full.actionable, result.incremental.actionable, result.full.net_strength, result.incremental.net_strength))
        except Exception as exc:
            print(f"{symbol:<14} ERROR {type(exc).__name__}: {exc}")

    print("=== FULL SCANNER INCREMENTAL EQUIVALENCE AUDIT ===")
    print(f"harness revision: {HARNESS_REVISION}")
    print(f"symbols: {len(symbols)}")
    print("split ratios: 60%, 70%, 80%")
    print()
    print(f"{'Symbol':<14}{'Split':>8}{'Target':>9}{'Schema':>8}{'Equivalent':>13}{'FullAct':>9}{'IncAct':>8}{'ScoreΔ':>12}")
    for symbol, ratio, target, schema, equivalent, full_act, inc_act, full_score, inc_score in rows:
        print(f"{symbol:<14}{ratio:>7.0%}{target:>9}{schema:>8}{str(equivalent):>13}{str(full_act):>9}{str(inc_act):>8}{(inc_score-full_score):>+12.6f}")

    print()
    passed = sum(row[4] for row in rows)
    print("=== EQUIVALENCE SUMMARY ===")
    print(f"passed: {passed}/{len(rows)}")
    print("status:", "PASS" if rows and passed == len(rows) else "REVIEW")


if __name__ == "__main__":
    main()
