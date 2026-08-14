"""Replay Spring through the production EvidenceEngine path.

The diagnostic exercises EvidenceEngine.collect() for production evidence.
A research-only Spring prefilter reduces the number of expensive production
replays; the EvidenceEngine itself still receives only point-in-time data.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_WEEK
from evidence.engine import EvidenceEngine
from evidence.spring import SpringValidationResult, detect_spring_candidate, validate_spring
from market_structure.structure_filter import StructureFilter
from market_structure.swing_engine import SwingEngine
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
FORWARD_HORIZON = 8
_PRODUCTION_LOOKBACK = 7
_TARGET_TEST_VOLUME_RATIO = 0.75
_TARGET_PENETRATION_RATIO = 0.50


def _code(item) -> str:
    return str(item.code).split(".")[-1].upper()


def _is_target_interaction(validation) -> bool:
    return (
        validation.confirmation.result is SpringValidationResult.CONFIRMED
        and validation.test.result is SpringValidationResult.TESTED
        and validation.test.volume_ratio is not None
        and validation.test.volume_ratio <= _TARGET_TEST_VOLUME_RATIO
        and validation.candidate.penetration_ratio <= _TARGET_PENETRATION_RATIO
    )


def _point_in_time_structural_swings(metrics, swings):
    by_confirmation: dict[int, list] = {}
    for swing in swings:
        by_confirmation.setdefault(swing.confirmation_index, []).append(swing)

    confirmed: list = []
    structural: tuple = ()
    structure_filter = StructureFilter()

    for bar_index in range(MIN_REPLAY_BARS, len(metrics) - FORWARD_HORIZON):
        newly_confirmed = by_confirmation.get(bar_index, ())
        if newly_confirmed:
            confirmed.extend(newly_confirmed)
            if len(confirmed) >= 2:
                prefix = metrics.iloc[: bar_index + 1]
                structural = tuple(structure_filter.filter(confirmed, prefix))
        yield bar_index, structural


def _audit_spring(metrics, *, index: int, trend, spring_event) -> dict:
    point_in_time = metrics.iloc[: index + 1]
    structural_swings = tuple(trend.structure.structural_swings)
    start = max(1, index - _PRODUCTION_LOOKBACK)

    for candidate_index in range(index - 1, start - 1, -1):
        candidate = detect_spring_candidate(
            point_in_time,
            bar_index=candidate_index,
            structural_swings=structural_swings,
        )
        if candidate is None:
            continue

        validation = validate_spring(point_in_time, candidate=candidate)
        if validation.confirmation.confirmation_index != index:
            continue
        if validation.confirmation.result is not SpringValidationResult.CONFIRMED:
            continue
        if validation.test.test_index != spring_event.test_index:
            continue

        test = validation.test
        return {
            "candidate_index": candidate.bar_index,
            "candidate_support": candidate.support,
            "candidate_penetration_ratio": candidate.penetration_ratio,
            "candidate_volume_ratio": candidate.volume_ratio,
            "candidate_close_position": candidate.close_position,
            "test_index": test.test_index,
            "test_distance_ratio": test.distance_ratio,
            "test_penetration_ratio": test.penetration_ratio,
            "test_volume_ratio": test.volume_ratio,
            "test_close_position": test.close_position,
            "confirmation_index": validation.confirmation.confirmation_index,
            "spring_weight": spring_event.weight,
        }

    return {
        "candidate_index": None,
        "candidate_support": None,
        "candidate_penetration_ratio": None,
        "candidate_volume_ratio": None,
        "candidate_close_position": None,
        "test_index": spring_event.test_index,
        "test_distance_ratio": None,
        "test_penetration_ratio": None,
        "test_volume_ratio": None,
        "test_close_position": None,
        "confirmation_index": spring_event.recovery_index,
        "spring_weight": spring_event.weight,
    }


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    swings = SwingEngine().calculate(metrics)
    events: list[dict] = []

    # Research-only prefilter. This may inspect the completed history solely
    # to identify possible target bars; no future row is passed to production
    # EvidenceEngine.collect().
    candidate_bars: set[int] = set()
    for index, structural_swings in _point_in_time_structural_swings(metrics, swings):
        candidate = detect_spring_candidate(
            metrics,
            bar_index=index,
            structural_swings=structural_swings,
        )
        if candidate is None:
            continue

        validation = validate_spring(metrics, candidate=candidate)
        if validation.confirmation.confirmation_index != index:
            continue
        if not _is_target_interaction(validation):
            continue
        candidate_bars.add(index)

    trend_analyzer = TrendAnalyzer()
    evidence_engine = EvidenceEngine()

    for index in sorted(candidate_bars):
        future_index = index + FORWARD_HORIZON
        if future_index >= len(metrics):
            continue

        replay = metrics.iloc[: index + 1]
        trend = trend_analyzer.analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        result = evidence_engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
            validation_metrics=replay,
        )

        spring_events = tuple(
            item for item in result.evidence
            if _code(item) == "SPRING"
        )
        if not spring_events:
            continue

        current = float(metrics.iloc[index][COL_CLOSE])
        future = float(metrics.iloc[future_index][COL_CLOSE])
        if current != current or future != future or current == 0.0:
            continue

        forward_return = (future - current) / current
        outcome = (
            "POSITIVE_8_BAR" if forward_return > 0.02
            else "NEGATIVE_8_BAR" if forward_return < -0.02
            else "FLAT_8_BAR"
        )

        for spring_event in spring_events:
            events.append({
                "symbol": symbol,
                "bar_index": index,
                "week": str(metrics.iloc[index][COL_WEEK]),
                "outcome": outcome,
                "forward_return": forward_return,
                "audit": _audit_spring(
                    metrics,
                    index=index,
                    trend=trend,
                    spring_event=spring_event,
                ),
            })

    return events


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {
            executor.submit(inspect_symbol, symbol): symbol
            for symbol in symbols
        }
        for future, symbol in futures.items():
            try:
                events = future.result()
                all_events.extend(events)
                print({"symbol": symbol, "production_spring_events": len(events)})
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})
                print(f"FAILED {symbol}: {exc!r}")

    by_outcome = {
        "POSITIVE_8_BAR": sum(e["outcome"] == "POSITIVE_8_BAR" for e in all_events),
        "NEGATIVE_8_BAR": sum(e["outcome"] == "NEGATIVE_8_BAR" for e in all_events),
        "FLAT_8_BAR": sum(e["outcome"] == "FLAT_8_BAR" for e in all_events),
    }

    print("SPRING PRODUCTION REPLAY SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({e["symbol"] for e in all_events}),
        "production_spring_events": len(all_events),
        "outcome_classes": by_outcome,
        "failures": failures,
    })

    print("SPRING PRODUCTION REPLAY EVENTS")
    for event in all_events:
        print(event)


if __name__ == "__main__":
    main()
