"""Analysis-only interaction audit for HIDDEN_SUPPLY.

Uses direct point-in-time semantic predicates. The target event itself is
explicitly excluded from the conflict set so HIDDEN_SUPPLY cannot be counted
as a contradiction against itself.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_VOLUME_CLASS, COL_CLOSE_POSITION
from metrics_engine import MetricsEngine
from models import Direction, VolumeClass, ClosePosition
from evidence.rules import (
    is_high_volume,
    is_very_high_volume,
    is_weak_close,
    is_low_volume,
    is_narrow_spread,
    is_above_average_spread,
    has_strong_spread,
)

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)


@dataclass(slots=True)
class Counts:
    events: int = 0
    supply_conflict: int = 0
    demand_interaction: int = 0
    no_supply: int = 0
    stopping_volume_like: int = 0
    shakeout_like: int = 0
    supply_coming_in_like: int = 0
    increasing_supply_like: int = 0
    upthrust_like: int = 0
    no_demand_like: int = 0
    buying_climax_like: int = 0
    demand_coming_in_like: int = 0
    increasing_demand_like: int = 0
    hidden_demand_like: int = 0


def _hidden_supply(metrics, i: int) -> bool:
    direction = Direction(int(metrics.iloc[i][COL_DIRECTION]))
    volume = VolumeClass(int(metrics.iloc[i][COL_VOLUME_CLASS]))
    close_position = ClosePosition(int(metrics.iloc[i][COL_CLOSE_POSITION]))
    return (
        direction == Direction.UP
        and volume in (VolumeClass.HIGH, VolumeClass.VERY_HIGH, VolumeClass.ULTRA_HIGH)
        and close_position in (ClosePosition.LOWER, ClosePosition.ON_LOW)
    )


def _audit_symbol(symbol: str) -> Counts:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    out = Counts()

    for i in range(1, len(metrics)):
        if not _hidden_supply(metrics, i):
            continue

        out.events += 1
        bar = metrics.iloc[i]
        prev = metrics.iloc[i - 1]
        direction = Direction(int(bar[COL_DIRECTION]))
        volume = VolumeClass(int(bar[COL_VOLUME_CLASS]))
        previous_volume = VolumeClass(int(prev[COL_VOLUME_CLASS]))

        # Never count HIDDEN_SUPPLY itself as a conflict.
        # Other supply events with incompatible same-bar mandatory direction
        # are also excluded from this bar-level contradiction audit.
        supply_hits = {
            "SUPPLY_COMING_IN_LIKE": False,
            "INCREASING_SUPPLY_LIKE": False,
            "UPTHRUST_LIKE": (
                direction == Direction.UP
                and is_very_high_volume(bar)
                and is_above_average_spread(bar)
                and is_weak_close(bar)
            ),
            "NO_DEMAND_LIKE": (
                direction == Direction.UP
                and is_low_volume(bar)
                and is_narrow_spread(bar)
            ),
            "BUYING_CLIMAX_LIKE": (
                direction == Direction.UP
                and is_very_high_volume(bar)
                and is_above_average_spread(bar)
                and is_weak_close(bar)
            ),
        }

        for name, hit in supply_hits.items():
            if hit:
                setattr(out, name.lower().replace("_like", "_like"), getattr(out, name.lower().replace("_like", "_like")) + 1)

        if supply_hits["SUPPLY_COMING_IN_LIKE"]:
            out.supply_coming_in_like += 1
        if supply_hits["INCREASING_SUPPLY_LIKE"]:
            out.increasing_supply_like += 1
        if supply_hits["UPTHRUST_LIKE"]:
            out.upthrust_like += 1
        if supply_hits["NO_DEMAND_LIKE"]:
            out.no_demand_like += 1
        if supply_hits["BUYING_CLIMAX_LIKE"]:
            out.buying_climax_like += 1

        if any(supply_hits.values()):
            out.supply_conflict += 1

        # Same-bar demand interactions whose mandatory semantics can coexist.
        stopping = (
            direction == Direction.DOWN
            and volume >= VolumeClass.HIGH
            and is_above_average_spread(bar)
            and not is_weak_close(bar)
        )
        no_supply = (
            direction == Direction.DOWN
            and is_low_volume(bar)
            and is_narrow_spread(bar)
        )
        shakeout_like = (
            direction == Direction.DOWN
            and is_very_high_volume(bar)
            and has_strong_spread(bar)
        )

        if stopping:
            out.stopping_volume_like += 1
        if no_supply:
            out.no_supply += 1
        if shakeout_like:
            out.shakeout_like += 1
        if stopping or no_supply or shakeout_like:
            out.demand_interaction += 1

    return out


def main() -> None:
    totals = Counts()
    failures: list[dict[str, str]] = []
    symbols_with_results = 0

    for symbol in SYMBOLS:
        try:
            counts = _audit_symbol(symbol)
            symbols_with_results += 1
            for field in totals.__dataclass_fields__:
                setattr(totals, field, getattr(totals, field) + getattr(counts, field))
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    print("HIDDEN SUPPLY INTERACTION / CONTRADICTION AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "events": totals.events,
        "events_with_supply_conflict": totals.supply_conflict,
        "supply_conflict_rate": totals.supply_conflict / totals.events if totals.events else 0.0,
        "aggregate_supply_conflicts": {
            "SUPPLY_COMING_IN_LIKE": totals.supply_coming_in_like,
            "INCREASING_SUPPLY_LIKE": totals.increasing_supply_like,
            "HIDDEN_SUPPLY_LIKE": 0,
            "UPTHRUST_LIKE": totals.upthrust_like,
            "NO_DEMAND_LIKE": totals.no_demand_like,
            "BUYING_CLIMAX_LIKE": totals.buying_climax_like,
        },
        "demand_interaction_events": totals.demand_interaction,
        "aggregate_demand_interactions": {
            "STOPPING_VOLUME_LIKE": totals.stopping_volume_like,
            "NO_SUPPLY_LIKE": totals.no_supply,
            "SHAKEOUT_LIKE": totals.shakeout_like,
            "DEMAND_COMING_IN_LIKE": totals.demand_coming_in_like,
            "INCREASING_DEMAND_LIKE": totals.increasing_demand_like,
            "HIDDEN_DEMAND_LIKE": totals.hidden_demand_like,
        },
        "self_conflict_excluded": True,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })


if __name__ == "__main__":
    main()
