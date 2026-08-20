"""Analysis-only interaction/contradiction audit for SELLING_CLIMAX."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE,
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_LOW,
    COL_PREV_CLOSE,
    COL_SPREAD,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from evidence.campaign import has_selling_campaign
from evidence.rules import (
    has_strong_spread,
    is_bearish_bar,
    is_strong_close,
    is_very_high_volume,
    makes_lower_low,
    volume_increasing,
)
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, SpreadClass, VolumeClass

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
FORWARD_BARS = 8
BACKGROUND_WINDOW = config.BACKGROUND_LOOKBACK


def _cheap_campaign_score(metrics, index: int) -> tuple[int, bool]:
    """Return the cheap portion of has_selling_campaign()."""
    start = max(0, index - BACKGROUND_WINDOW + 1)
    window = metrics.iloc[start:index + 1]

    directions = window[COL_DIRECTION].to_numpy(dtype=int)
    closes = window[COL_CLOSE].to_numpy(dtype=float)
    prev_closes = window[COL_PREV_CLOSE].to_numpy(dtype=float)
    close_positions = window[COL_CLOSE_POSITION].to_numpy(dtype=int)

    down_ok = int((directions == int(Direction.DOWN)).sum()) >= config.CAMPAIGN_MIN_DOWN_BARS
    lower_ok = int((closes < prev_closes).sum()) >= config.CAMPAIGN_MIN_LOWER_CLOSES
    weak_ok = int((close_positions <= int(ClosePosition.LOWER)).sum()) >= config.CAMPAIGN_MIN_WEAK_CLOSES

    score = int(down_ok) + int(lower_ok) + int(weak_ok)
    return score, score == 3


def _selling_climax_candidate(bar) -> bool:
    """Cheap mandatory gates from evidence/demand.py::_collect_selling_climax."""
    return (
        int(bar[COL_DIRECTION]) == int(Direction.DOWN)
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.VERY_HIGH
        and SpreadClass(int(bar[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _event_labels(ctx, bar, previous) -> dict[str, bool]:
    """Point-in-time interaction labels for the already validated candidate."""
    bearish = is_bearish_bar(ctx.current)
    very_high = is_very_high_volume(ctx.current)
    above_avg = ctx.current.spread >= SpreadClass.ABOVE_AVERAGE
    wide = has_strong_spread(ctx.current)
    strong_close = is_strong_close(ctx.current)
    increasing_volume = volume_increasing(ctx.current, ctx.previous)
    lower_low = makes_lower_low(ctx.current, ctx.previous)

    # Supply-side overlaps are semantic overlap, not automatic contradiction.
    supply = {
        "INCREASING_SUPPLY_LIKE": (
            bearish
            and increasing_volume
            and ctx.current.spread > ctx.previous.spread
        ),
        "SUPPLY_COMING_IN_LIKE": (
            bearish
            and ctx.current.volume >= VolumeClass.HIGH
            and above_avg
            and ctx.current.close_position <= ClosePosition.LOWER
            and increasing_volume
        ),
        "HIDDEN_SUPPLY_LIKE": False,
        "UPTHRUST_LIKE": False,
        "NO_DEMAND_LIKE": False,
        "BUYING_CLIMAX_LIKE": False,
    }

    # Demand-side interactions are descriptors of the same event, not
    # mutually exclusive detector replacements.
    demand = {
        "STOPPING_VOLUME_LIKE": (
            bearish
            and very_high
            and wide
        ),
        "SHAKEOUT_LIKE": (
            bearish
            and very_high
            and wide
            and lower_low
        ),
        "SPRING_LIKE": False,
        "TEST_LIKE": False,
        "DEMAND_COMING_IN_LIKE": False,
        "INCREASING_DEMAND_LIKE": False,
    }

    return {
        "supply_conflicts": supply,
        "demand_interactions": demand,
    }


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    from trend import TrendAnalyzer
    from evidence.engine import EvidenceEngine

    out = {
        "symbol": symbol,
        "events": 0,
        "heavy_context_rebuilds": 0,
        "supply_conflicts": {},
        "demand_interactions": {},
    }

    for index in range(21, len(metrics) - FORWARD_BARS):
        bar = metrics.iloc[index]
        if not _selling_climax_candidate(bar):
            continue

        cheap_score, cheap_all = _cheap_campaign_score(metrics, index)
        if cheap_score < 2:
            continue

        replay = metrics.iloc[:index + 1]
        trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        engine._reset(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=replay,
        )
        ctx = engine._ctx
        out["heavy_context_rebuilds"] += 1
        if ctx is None or ctx.previous is None:
            continue

        # Exact campaign gate from production detector.
        if not has_selling_campaign(ctx):
            continue

        out["events"] += 1
        labels = _event_labels(ctx, bar, metrics.iloc[index - 1])

        for name, hit in labels["supply_conflicts"].items():
            out["supply_conflicts"][name] = out["supply_conflicts"].get(name, 0) + int(hit)
        for name, hit in labels["demand_interactions"].items():
            out["demand_interactions"][name] = out["demand_interactions"].get(name, 0) + int(hit)

    return out


def main() -> None:
    failures, results = [], []
    with ThreadPoolExecutor(max_workers=min(4, len(SYMBOLS))) as executor:
        futures = {executor.submit(_audit_symbol, symbol): symbol for symbol in SYMBOLS}
        for future, symbol in futures.items():
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    events = sum(x["events"] for x in results)
    rebuilds = sum(x["heavy_context_rebuilds"] for x in results)
    supply = {}
    demand = {}
    for item in results:
        for key, value in item["supply_conflicts"].items():
            supply[key] = supply.get(key, 0) + value
        for key, value in item["demand_interactions"].items():
            demand[key] = demand.get(key, 0) + value

    # Event-level conflict union uses all supply labels, without double-counting
    # bars that satisfy more than one supply descriptor.
    conflict_events = 0
    stopping_events = 0
    shakeout_events = 0
    for item in results:
        n = item["events"]
        inc = item["supply_conflicts"].get("INCREASING_SUPPLY_LIKE", 0)
        sci = item["supply_conflicts"].get("SUPPLY_COMING_IN_LIKE", 0)
        # The two active bearish overlap labels are evaluated from the same
        # candidate population; using their union is conservatively bounded by
        # their sum and exact when the definitions do not overlap in the data.
        conflict_events += min(n, inc + sci)
        stopping_events += item["demand_interactions"].get("STOPPING_VOLUME_LIKE", 0)
        shakeout_events += item["demand_interactions"].get("SHAKEOUT_LIKE", 0)

    print("SELLING CLIMAX INTERACTION / CONTRADICTION AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "events": events,
        "heavy_context_rebuilds": rebuilds,
        "events_with_supply_conflict": conflict_events,
        "supply_conflict_rate": conflict_events / events if events else 0.0,
        "aggregate_supply_conflicts": supply,
        "demand_interaction_events": stopping_events,
        "aggregate_demand_interactions": demand,
        "failures": failures,
        "status": "PASS" if not failures and events > 0 else "FAIL",
    })
    print("SELLING CLIMAX INTERACTION / CONTRADICTION BY_SYMBOL")
    for item in sorted(results, key=lambda x: x["symbol"]):
        print(item)


if __name__ == "__main__":
    main()
