"""Fast point-in-time replay diagnostic for the validation-stage Spring detector."""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from evidence.spring import SpringValidationResult, detect_spring_candidate, validate_spring
from engine.columns import COL_CLOSE, COL_WEEK
from market_structure.swing_engine import SwingEngine
from market_structure.structure_filter import StructureFilter

DEFAULT_SYMBOLS = ("BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS")
MIN_REPLAY_BARS = 20
FORWARD_HORIZON = 8


def _point_in_time_structural_swings(metrics, swings, symbol: str):
    """Yield point-in-time structural swings while reporting progress."""
    by_confirmation: dict[int, list] = {}
    for swing in swings:
        by_confirmation.setdefault(swing.confirmation_index, []).append(swing)

    confirmed: list = []
    structural: tuple = ()
    start = MIN_REPLAY_BARS
    end = len(metrics) - FORWARD_HORIZON
    total = max(1, end - start)
    next_report = 10

    for bar_index in range(start, end):
        newly_confirmed = by_confirmation.get(bar_index, ())
        if newly_confirmed:
            confirmed.extend(newly_confirmed)
            # The first confirmed swing has no predecessor and therefore cannot
            # have a valid amplitude. Do not send it into structural scoring.
            if len(confirmed) >= 2:
                prefix = metrics.iloc[: bar_index + 1]
                structural = tuple(StructureFilter().filter(confirmed[1:], prefix))

        progress = int(((bar_index - start + 1) * 100) / total)
        if progress >= next_report:
            print(f"SPRING REPLAY: {symbol} {progress}%", flush=True)
            next_report += 10

        yield bar_index, structural


def inspect_symbol(symbol: str) -> list[dict]:
    print(f"SPRING REPLAY: {symbol} starting", flush=True)
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    swings = SwingEngine().calculate(metrics)
    events: list[dict] = []

    for index, structural_swings in _point_in_time_structural_swings(metrics, swings, symbol):
        candidate = detect_spring_candidate(metrics, bar_index=index, structural_swings=structural_swings)
        if candidate is None:
            continue

        validation = validate_spring(metrics, candidate=candidate)
        current = float(metrics.iloc[index][COL_CLOSE])
        future = float(metrics.iloc[index + FORWARD_HORIZON][COL_CLOSE])
        forward_return = (future - current) / current
        outcome = "POSITIVE_8_BAR" if forward_return > 0.02 else "NEGATIVE_8_BAR" if forward_return < -0.02 else "FLAT_8_BAR"
        events.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(metrics.iloc[index][COL_WEEK]),
            "penetration_ratio": candidate.penetration_ratio,
            "support_touches": candidate.support_touches,
            "candidate_volume_ratio": candidate.volume_ratio,
            "candidate_close_position": candidate.close_position,
            "test_result": validation.test.result.value,
            "test_index": validation.test.test_index,
            "test_volume_ratio": validation.test.volume_ratio,
            "test_close_position": validation.test.close_position,
            "confirmation_result": validation.confirmation.result.value,
            "confirmation_index": validation.confirmation.confirmation_index,
            "outcome": outcome,
            "forward_return_8": forward_return,
        })

    print(f"SPRING REPLAY: {symbol} complete — {len(events)} candidates", flush=True)
    return events


def _outcome_counts(rows: list[dict]) -> dict[str, int]:
    return {"POSITIVE_8_BAR": sum(x["outcome"] == "POSITIVE_8_BAR" for x in rows), "NEGATIVE_8_BAR": sum(x["outcome"] == "NEGATIVE_8_BAR" for x in rows), "FLAT_8_BAR": sum(x["outcome"] == "FLAT_8_BAR" for x in rows)}


def _feature_group(rows: list[dict], name: str, predicate) -> dict:
    selected = [row for row in rows if predicate(row)]
    counts = _outcome_counts(selected)
    return {"feature": name, "events": len(selected), **counts, "net_directional": counts["POSITIVE_8_BAR"] - counts["NEGATIVE_8_BAR"]}


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                all_events.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("SPRING REPLAY SUMMARY")
    print({"symbols_requested": len(symbols), "symbols_with_candidates": len({x["symbol"] for x in all_events}), "candidates": len(all_events), "tested": sum(x["test_result"] == SpringValidationResult.TESTED.value for x in all_events), "confirmed": sum(x["confirmation_result"] == SpringValidationResult.CONFIRMED.value for x in all_events), "failed_confirmation": sum(x["confirmation_result"] == SpringValidationResult.FAILED.value for x in all_events), "no_test": sum(x["test_result"] == SpringValidationResult.NO_TEST.value for x in all_events), "outcome_classes": _outcome_counts(all_events), "failures": failures})

    print("SPRING REPLAY BY SYMBOL")
    for symbol in symbols:
        rows = [x for x in all_events if x["symbol"] == symbol]
        print({"symbol": symbol, "candidates": len(rows), "tested": sum(x["test_result"] == SpringValidationResult.TESTED.value for x in rows), "confirmed": sum(x["confirmation_result"] == SpringValidationResult.CONFIRMED.value for x in rows), **_outcome_counts(rows)})

    print("SPRING FEATURE OUTCOME COMPARISON")
    feature_groups = [("TESTED", lambda x: x["test_result"] == SpringValidationResult.TESTED.value), ("CONFIRMED", lambda x: x["confirmation_result"] == SpringValidationResult.CONFIRMED.value), ("NO_TEST", lambda x: x["test_result"] == SpringValidationResult.NO_TEST.value), ("TEST_VOLUME_RATIO<=0.75", lambda x: x["test_volume_ratio"] is not None and x["test_volume_ratio"] <= 0.75), ("TEST_VOLUME_RATIO<=1.00", lambda x: x["test_volume_ratio"] is not None and x["test_volume_ratio"] <= 1.00), ("TEST_CLOSE_POSITION>=3", lambda x: x["test_close_position"] is not None and x["test_close_position"] >= 3), ("PENETRATION<=0.50", lambda x: x["penetration_ratio"] <= 0.50), ("PENETRATION>0.50", lambda x: x["penetration_ratio"] > 0.50)]
    for name, predicate in feature_groups:
        print(_feature_group(all_events, name, predicate))


if __name__ == "__main__":
    main()
