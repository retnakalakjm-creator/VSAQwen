"""Focused audit of VSA evidence surrounding verified production Springs.

This diagnostic does not modify production logic. It replays only the 13
already-verified production Spring bars and inspects same-bar and recent
supporting/conflicting evidence from EvidenceEngine.
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
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer

FORWARD_HORIZON = 8
RECENT_WINDOW = 3

PRODUCTION_SPRINGS = {
    "BHARTIARTL.NS": (541, 698),
    "RELIANCE.NS": (1530,),
    "HDFCBANK.NS": (248, 290, 301, 836, 1055, 1195),
    "ICICIBANK.NS": (100, 928),
    "INFY.NS": (1269,),
    "SBIN.NS": (256,),
}

BULLISH_CODES = {
    "STOPPING_VOLUME", "DEMAND_COMING_IN", "INCREASING_DEMAND",
    "HIDDEN_DEMAND", "DEMAND_DRYING_UP", "NO_SUPPLY",
    "TEST", "SPRING", "SHAKEOUT", "ACCUMULATION", "REACCUMULATION",
    "MARKUP", "STRONG_UPTREND", "WEAK_UPTREND",
}

BEARISH_CODES = {
    "BUYING_CLIMAX", "SUPPLY_COMING_IN", "INCREASING_SUPPLY",
    "HIDDEN_SUPPLY", "SUPPLY_DRYING_UP", "NO_DEMAND",
    "UPTHRUST", "DISTRIBUTION", "REDISTRIBUTION", "MARKDOWN",
    "STRONG_DOWNTREND", "WEAK_DOWNTREND",
}


def code_name(item) -> str:
    return str(item.code).split(".")[-1].upper()


def inspect_symbol(symbol: str, target_bars: tuple[int, ...]) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    trend_analyzer = TrendAnalyzer()
    engine = EvidenceEngine()
    rows: list[dict] = []

    for index in target_bars:
        if index >= len(metrics) or index + FORWARD_HORIZON >= len(metrics):
            continue

        replay = metrics.iloc[: index + 1]
        trend = trend_analyzer.analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
            validation_metrics=replay,
        )

        recent = tuple(
            item for item in result.evidence
            if index - RECENT_WINDOW <= item.bar_index <= index
        )
        same_bar = tuple(item for item in recent if item.bar_index == index)

        spring = tuple(item for item in same_bar if code_name(item) == "SPRING")
        bullish_same = tuple(item for item in same_bar if code_name(item) in BULLISH_CODES and code_name(item) != "SPRING")
        bearish_same = tuple(item for item in same_bar if code_name(item) in BEARISH_CODES)

        current = float(metrics.iloc[index][COL_CLOSE])
        future = float(metrics.iloc[index + FORWARD_HORIZON][COL_CLOSE])
        forward_return = (future - current) / current if current else 0.0
        outcome = (
            "POSITIVE_8_BAR" if forward_return > 0.02
            else "NEGATIVE_8_BAR" if forward_return < -0.02
            else "FLAT_8_BAR"
        )

        rows.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(metrics.iloc[index][COL_WEEK]),
            "outcome": outcome,
            "forward_return_8": forward_return,
            "spring_count": len(spring),
            "same_bar_bullish": [code_name(x) for x in bullish_same],
            "same_bar_bearish": [code_name(x) for x in bearish_same],
            "recent_bullish": [code_name(x) for x in recent if code_name(x) in BULLISH_CODES],
            "recent_bearish": [code_name(x) for x in recent if code_name(x) in BEARISH_CODES],
            "all_recent": [
                {"bar_index": x.bar_index, "code": code_name(x), "weight": x.weight}
                for x in recent
            ],
        })

    return rows


def main() -> None:
    rows: list[dict] = []
    failures: list[dict] = []

    for symbol, bars in PRODUCTION_SPRINGS.items():
        try:
            rows.extend(inspect_symbol(symbol, bars))
        except Exception as exc:
            failures.append({"symbol": symbol, "error": repr(exc)})

    interaction_groups = {
        "SPRING + SAME_BAR_BULLISH": lambda r: bool(r["same_bar_bullish"]),
        "SPRING + SAME_BAR_BEARISH": lambda r: bool(r["same_bar_bearish"]),
        "SPRING + RECENT_BULLISH": lambda r: bool(r["recent_bullish"]),
        "SPRING + RECENT_BEARISH": lambda r: bool(r["recent_bearish"]),
        "SPRING + NO_CONFLICT_SAME_BAR": lambda r: not r["same_bar_bearish"],
    }

    print("SPRING INTERACTION AUDIT SUMMARY")
    print({
        "production_springs_expected": sum(len(x) for x in PRODUCTION_SPRINGS.values()),
        "audited": len(rows),
        "failures": failures,
    })

    print("SPRING INTERACTION BY GROUP")
    for name, predicate in interaction_groups.items():
        selected = [r for r in rows if predicate(r)]
        positive = sum(r["outcome"] == "POSITIVE_8_BAR" for r in selected)
        negative = sum(r["outcome"] == "NEGATIVE_8_BAR" for r in selected)
        flat = sum(r["outcome"] == "FLAT_8_BAR" for r in selected)
        print({
            "feature": name,
            "events": len(selected),
            "POSITIVE_8_BAR": positive,
            "NEGATIVE_8_BAR": negative,
            "FLAT_8_BAR": flat,
            "net_directional": positive - negative,
            "benefit_harm_ratio": round(positive / negative, 3) if negative else None,
        })

    print("SPRING INTERACTION EVENTS")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
