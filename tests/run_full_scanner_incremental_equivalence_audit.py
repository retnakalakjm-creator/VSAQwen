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
from tests.full_scanner_incremental_equivalence_harness import run_incremental_equivalence
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS

HARNESS_REVISION = "2026-09-01-full-scanner-incremental-v4-state-diagnostics"


def _print_failure_diagnostics(symbol: str, result, metrics) -> None:
    full = result.full
    inc = result.incremental
    print()
    print(f"--- FAILURE DIAGNOSTIC: {symbol} target={result.target_index} ---")
    print(f"qualification: {full.qualification} -> {inc.qualification}")
    print(f"actionable:    {full.actionable} -> {inc.actionable}")
    print(f"qualifying:    {full.qualifying_evidence_codes} -> {inc.qualifying_evidence_codes}")

    if symbol != "COALINDIA.NS" or result.target_index != int(len(metrics) * 0.80):
        return

    from incremental_scanner import IncrementalScannerEngine

    engine = IncrementalScannerEngine()
    state = engine.snapshot(
        metrics,
        target_index=result.target_index,
        symbol=symbol,
        timeframe="weekly",
    )

    index_by_week = {str(v): i for i, v in enumerate(metrics["week_beginning"])}

    print(f"state.last_closed_bar: {state.last_closed_bar}")
    print(f"state.structural_events: {len(state.structural_events)}")
    for event in state.structural_events:
        print(
            "  STATE EVENT",
            event.bar_key,
            index_by_week.get(event.bar_key),
            event.code,
        )

    history, _, _ = ScannerEngine()._scan_history_to_index(
        metrics,
        result.target_index,
    )
    target_events: dict[tuple[int, object], object] = {}
    for snapshot in history:
        for event in snapshot.evidence:
            if str(event.code) in {
                "structural_progression_improving",
                "structural_progression_weakening",
            }:
                target_events[(event.bar_index, event.code)] = event

    print("FULL structural progression events through checkpoint:")
    for event in sorted(target_events.values(), key=lambda item: item.bar_index):
        print("  FULL EVENT", event.bar_index, event.week_beginning, event.code)

    inc_history = engine._events_to_evidence(metrics, state.structural_events)
    print("INCREMENTAL rehydrated structural progression events:")
    for event in inc_history:
        print("  INC EVENT", event.bar_index, event.week_beginning, event.code)


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
                if not result.equivalent:
                    _print_failure_diagnostics(symbol, result, metrics)
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
