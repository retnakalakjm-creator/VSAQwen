"""Replay Spring through the production EvidenceEngine path.

The diagnostic intentionally exercises EvidenceEngine.collect() rather than
calling the Spring collector directly. It also exposes the VSA measurements
behind each emitted Spring so production events can be audited.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_WEEK
from evidence.engine import EvidenceEngine
from evidence.spring import detect_spring_candidate, validate_spring
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
FORWARD_HORIZON = 8


def _code(item) -> str:
    return str(item.code).split(".")[-1].upper()


def _audit_spring(metrics, *, index: int, trend, spring_event) -> dict:
    """Recover the point-in-time Spring validation details for diagnostics."""
    point_in_time = metrics.iloc[: index + 1]
    structural_swings = tuple(trend.structure.structural_swings)
    start = max(1, index - 7)

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
        if validation.confirmation.result.value != "confirmed":
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
    events: list[dict] = []

    # Reuse the same analyzers/engine across replay bars.
    trend_analyzer = TrendAnalyzer()
    evidence_engine = EvidenceEngine()

    for index in range(MIN_REPLAY_BARS, len(metrics)):
        future_index = index + FORWARD_HORIZON
        if future_index >= len(metrics):
            break

        # EvidenceEngine/_collect_spring constrain their own point-in-time views;
        # avoid an unnecessary DataFrame copy on every replay bar.
        replay = metrics.iloc[: index + 1]
        trend = trend_analyzer.analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        result = evidence_engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
            validation_metrics=replay,
        )

        spring_events = [item for item in result.evidence if _code(item) == "SPRING"]
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
            audit = _audit_spring(
                metrics,
                index=index,
                trend=trend,
                spring_event=spring_event,
            )
            events.append({
                "symbol": symbol,
                "bar_index": index,
                "week": str(metrics.iloc[index][COL_WEEK]),
                "outcome": outcome,
                "forward_return": forward_return,
                "audit": audit,
            })

    return events


def main() -> None:
    all_events: list[dict] = []
    failures: list[dict] = []

    for symbol in DEFAULT_SYMBOLS:
        try:
            events = inspect_symbol(symbol)
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
        "symbols_requested": len(DEFAULT_SYMBOLS),
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
