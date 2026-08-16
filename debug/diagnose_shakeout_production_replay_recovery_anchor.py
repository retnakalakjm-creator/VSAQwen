from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from debug.diagnose_shakeout_outcomes_recovery_anchor import inspect_symbol as validated_inspect_symbol
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import EvidenceCode
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS",
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "TCS.NS",
    "SBIN.NS",
    "LT.NS",
)


def replay_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    validated = validated_inspect_symbol(symbol)
    rows: list[dict] = []

    for event in validated:
        candidate_index = int(event["candidate_bar_index"])
        recovery_index = int(event["recovery_bar_index"])

        candidate_replay = metrics.iloc[: candidate_index + 1].copy()
        candidate_trend = TrendAnalyzer().analyze(candidate_replay)
        candidate_result = EvidenceEngine().collect(
            metrics=candidate_replay,
            trend=candidate_trend,
            structural_swings=tuple(candidate_trend.structure.structural_swings),
            validation_metrics=candidate_replay,
        )
        candidate_events = [
            item for item in candidate_result.evidence
            if item.code is EvidenceCode.SHAKEOUT
        ]

        recovery_replay = metrics.iloc[: recovery_index + 1].copy()
        recovery_trend = TrendAnalyzer().analyze(recovery_replay)
        recovery_result = EvidenceEngine().collect(
            metrics=recovery_replay,
            trend=recovery_trend,
            structural_swings=tuple(recovery_trend.structure.structural_swings),
            validation_metrics=recovery_replay,
        )
        recovery_events = [
            item for item in recovery_result.evidence
            if item.code is EvidenceCode.SHAKEOUT
        ]

        rows.append({
            "symbol": symbol,
            "candidate_bar_index": candidate_index,
            "recovery_bar_index": recovery_index,
            "candidate_shakeout_events": len(candidate_events),
            "recovery_shakeout_events": len(recovery_events),
            "recovery_anchor_correct": (
                len(recovery_events) == 1
                and recovery_events[0].bar_index == recovery_index
                and recovery_events[0].recovery_index == recovery_index
            ),
        })

    return rows


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    rows: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(replay_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                rows.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    candidate_emissions = sum(row["candidate_shakeout_events"] for row in rows)
    recovery_emissions = sum(row["recovery_shakeout_events"] for row in rows)
    correct_anchors = sum(row["recovery_anchor_correct"] for row in rows)

    print("SHAKEOUT PRODUCTION REPLAY RECOVERY-ANCHOR SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "validated_events": len(rows),
        "candidate_bar_emissions": candidate_emissions,
        "recovery_bar_emissions": recovery_emissions,
        "correct_recovery_anchors": correct_anchors,
        "failures": failures,
    })

    print("SHAKEOUT PRODUCTION REPLAY RECOVERY-ANCHOR EVENTS")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
