from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from incremental_scanner import IncrementalScannerEngine
from scanner import ScannerEngine
from background.qualification import PatternQualificationEngine
from model.evidence_result_model import EvidenceResult

STRUCTURAL = {
    "structural_progression_improving",
    "structural_progression_weakening",
}


def main() -> None:
    symbol = "COALINDIA.NS"
    daily = download_data(symbol, refresh=False)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    target = int(len(metrics) * 0.80)

    incremental = IncrementalScannerEngine()
    state = incremental.snapshot(
        metrics,
        target_index=target,
        symbol=symbol,
        timeframe="weekly",
    )

    full_history, _, _ = ScannerEngine()._scan_history_to_index(
        metrics,
        len(metrics) - 1,
    )

    index_by_week = {str(v): i for i, v in enumerate(metrics["week_beginning"])}
    state_evidence = incremental._events_to_evidence(
        metrics,
        state.structural_events,
    )

    full_latest = ScannerEngine().scan_to_index(metrics, len(metrics) - 1)
    resumed_history = [
        EvidenceResult(
            context=full_latest.evidence.context,
            evidence=state_evidence,
        ),
        full_latest.evidence,
    ]

    qualifier = PatternQualificationEngine()
    full_result = qualifier.evaluate(full_history)
    resumed_result = qualifier.evaluate(resumed_history)

    def events_from(history):
        events = {}
        for snapshot in history:
            for event in snapshot.evidence:
                if event.code.value in STRUCTURAL:
                    events[(event.bar_index, event.code)] = event
        return tuple(sorted(events.values(), key=lambda item: item.bar_index))

    print("TARGET", target)
    print("STATE EVENTS", len(state.structural_events))
    print("FULL QUALIFICATION", full_result)
    print("RESUMED QUALIFICATION", resumed_result)
    print()
    print("FULL EVENTS THROUGH CHECKPOINT")
    for event in events_from(full_history):
        if event.bar_index <= target:
            print(event.bar_index, event.week_beginning, event.code, event.direction)
    print()
    print("STATE EVENTS")
    for event in state.structural_events:
        print(index_by_week.get(event.bar_key), event.bar_key, event.code, event.direction)
    print()
    print("REHYDRATED EVENTS")
    for event in state_evidence:
        print(event.bar_index, event.week_beginning, event.code, event.direction)
    print()
    print("RESUMED HISTORY EVENTS")
    for event in events_from(resumed_history):
        print(event.bar_index, event.week_beginning, event.code, event.direction)


if __name__ == "__main__":
    main()
