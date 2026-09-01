from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from incremental_scanner import IncrementalScannerEngine
from scanner import ScannerEngine


def main() -> None:
    symbol = "COALINDIA.NS"
    daily = download_data(symbol, refresh=False)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    target = int(len(metrics) * 0.80)

    engine = IncrementalScannerEngine()
    state = engine.snapshot(
        metrics,
        target_index=target,
        symbol=symbol,
        timeframe="weekly",
    )

    index_by_week = {str(value): i for i, value in enumerate(metrics["week_beginning"])}

    print("=== COALINDIA INCREMENTAL STATE DIAGNOSTIC ===")
    print(f"metrics: {len(metrics)}")
    print(f"target: {target}")
    print(f"state.last_closed_bar: {state.last_closed_bar}")
    print(f"state.structural_events: {len(state.structural_events)}")
    for event in state.structural_events:
        print(
            "STATE EVENT",
            index_by_week.get(event.bar_key),
            event.bar_key,
            event.code,
        )

    history, _, _ = ScannerEngine()._scan_history_to_index(metrics, target)
    full_events: dict[tuple[int, object], object] = {}
    for snapshot in history:
        for event in snapshot.evidence:
            if str(event.code) in {
                "structural_progression_improving",
                "structural_progression_weakening",
            }:
                full_events[(event.bar_index, event.code)] = event

    print("FULL EVENTS THROUGH CHECKPOINT:")
    for event in sorted(full_events.values(), key=lambda item: item.bar_index):
        print("FULL EVENT", event.bar_index, event.week_beginning, event.code)

    restored = engine._events_to_evidence(metrics, state.structural_events)
    print("REHYDRATED STATE EVENTS:")
    for event in restored:
        print("INC EVENT", event.bar_index, event.week_beginning, event.code)

    result = engine.resume_latest(metrics, state)
    print("RESUMED QUALIFICATION:", result.qualification)
    print("RESUMED ACTIONABLE:", result.actionable)
    print("RESUMED QUALIFYING:", result.qualifying_evidence_codes)


if __name__ == "__main__":
    main()
