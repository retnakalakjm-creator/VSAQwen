from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from debug.diagnose_shakeout_outcomes_recovery_anchor import inspect_symbol as validated_inspect_symbol
from engine.columns import (
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from evidence.campaign import ShakeoutRecoveryResult, has_selling_campaign, validate_shakeout
from evidence.demand import _collect_shakeout
from evidence.engine import EvidenceEngine
from evidence.rules import (
    has_strong_spread,
    is_bearish_bar,
    is_strong_close,
    is_very_high_volume,
    makes_lower_low,
)
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
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


def live_candidate_snapshot(metrics, candidate_index: int) -> dict:
    replay = metrics.iloc[: candidate_index + 1].copy()
    trend = TrendAnalyzer().analyze(replay)
    structural_swings = tuple(trend.structure.structural_swings)
    engine = EvidenceEngine()
    engine._reset(
        metrics=replay,
        trend=trend,
        structural_swings=structural_swings,
        validation_metrics=replay,
    )
    ctx = engine._ctx
    if ctx is None or ctx.previous is None:
        return {"context_available": False}

    bar = ctx.current
    previous = ctx.previous

    return {
        "context_available": True,
        "direction": int(bar.direction),
        "volume_class": int(bar.volume),
        "spread_class": int(bar.spread),
        "selling_campaign": has_selling_campaign(ctx),
        "bearish_bar": is_bearish_bar(bar),
        "wide_spread": has_strong_spread(bar),
        "very_high_volume": is_very_high_volume(bar),
        "strong_close": is_strong_close(bar),
        "lower_low": makes_lower_low(bar, previous),
    }


def live_recovery_snapshot(metrics, recovery_index: int) -> dict:
    replay = metrics.iloc[: recovery_index + 1].copy()
    trend = TrendAnalyzer().analyze(replay)
    structural_swings = tuple(trend.structure.structural_swings)
    engine = EvidenceEngine()
    result = engine.collect(
        metrics=replay,
        trend=trend,
        structural_swings=structural_swings,
        validation_metrics=replay,
    )
    events = [item for item in result.evidence if item.code is EvidenceCode.SHAKEOUT]
    return {
        "recovery_events": len(events),
        "recovery_event_bar_indices": [item.bar_index for item in events],
        "recovery_event_recovery_indices": [item.recovery_index for item in events],
    }


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    validated_events = validated_inspect_symbol(symbol)
    rows: list[dict] = []

    for event in validated_events:
        candidate_index = int(event["candidate_bar_index"])
        test_index = int(event["test_bar_index"])
        recovery_index = int(event["recovery_bar_index"])

        candidate_row = metrics.iloc[candidate_index]
        direction = Direction(int(candidate_row[COL_DIRECTION]))
        volume = VolumeClass(int(candidate_row[COL_VOLUME_CLASS]))
        spread = SpreadClass(int(candidate_row[COL_SPREAD_CLASS]))

        live_candidate = live_candidate_snapshot(metrics, candidate_index)
        point_in_time = metrics.iloc[: recovery_index + 1]
        validation = validate_shakeout(
            metrics=point_in_time,
            shakeout_index=candidate_index,
        )
        live_recovery = live_recovery_snapshot(metrics, recovery_index)

        rows.append(
            {
                "symbol": symbol,
                "candidate_bar_index": candidate_index,
                "test_bar_index": test_index,
                "recovery_bar_index": recovery_index,
                "validated_candidate_prereq": {
                    "direction_down": direction == Direction.DOWN,
                    "volume_very_high": volume >= VolumeClass.VERY_HIGH,
                    "spread_wide": spread >= SpreadClass.WIDE,
                },
                "live_candidate": live_candidate,
                "validation": {
                    "test_index": validation.test.test_index,
                    "test_result": str(validation.test.result),
                    "recovery_index": validation.recovery.recovery_index,
                    "recovery_result": str(validation.recovery.result),
                },
                "live_recovery": live_recovery,
            }
        )

    return rows


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    failures: list[dict] = []
    rows: list[dict] = []

    for symbol in symbols:
        try:
            rows.extend(inspect_symbol(symbol))
        except Exception as exc:
            failures.append({"symbol": symbol, "error": repr(exc)})

    mismatch_counts: Counter[str] = Counter()
    for row in rows:
        live = row["live_candidate"]
        validated = row["validated_candidate_prereq"]
        if not live.get("context_available", False):
            mismatch_counts["context_unavailable"] += 1
            continue
        if live["direction"] != -1:
            mismatch_counts["candidate_direction"] += 1
        if live["volume_class"] < int(VolumeClass.VERY_HIGH):
            mismatch_counts["candidate_volume_class"] += 1
        if live["spread_class"] < int(SpreadClass.WIDE):
            mismatch_counts["candidate_spread_class"] += 1
        if not live["selling_campaign"]:
            mismatch_counts["selling_campaign"] += 1
        if not live["bearish_bar"]:
            mismatch_counts["bearish_bar"] += 1
        if not live["wide_spread"]:
            mismatch_counts["wide_spread"] += 1
        if not live["very_high_volume"]:
            mismatch_counts["very_high_volume"] += 1
        if not live["strong_close"]:
            mismatch_counts["strong_close"] += 1
        if not live["lower_low"]:
            mismatch_counts["lower_low"] += 1
        if row["validation"]["test_index"] != row["test_bar_index"]:
            mismatch_counts["test_index_mismatch"] += 1
        if row["validation"]["recovery_index"] != row["recovery_bar_index"]:
            mismatch_counts["recovery_index_mismatch"] += 1
        if row["live_recovery"]["recovery_events"] != 1:
            mismatch_counts["production_recovery_emission"] += 1

    print("SHAKEOUT RECOVERY-ANCHOR MISMATCH SUMMARY")
    print(
        {
            "validated_events": len(rows),
            "failures": failures,
            "mismatch_counts": dict(mismatch_counts),
        }
    )

    print("SHAKEOUT RECOVERY-ANCHOR MISMATCH EVENTS")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
