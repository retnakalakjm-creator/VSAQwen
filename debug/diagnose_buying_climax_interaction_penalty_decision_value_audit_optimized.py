"""Decision-value sensitivity for the BUYING_CLIMAX interaction penalty.

Analysis-only. Replays the real point-in-time BUYING_CLIMAX population,
classifies the target-bar evidence combination using exact EvidenceCode
members, and applies hypothetical penalties only to
INCREASING_DEMAND + UPTHRUST. No production mutation.
"""
from __future__ import annotations

import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_VOLUME_CLASS
from evidence.campaign import has_buying_campaign
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
FORWARD_BARS = 8
BASE_WEIGHT = 0.38
PENALTIES = (0.0, 0.05, 0.10, 0.15, 0.20)
TARGET_COMBINATION = "INCREASING_DEMAND + UPTHRUST"

SELF_CODES = {EvidenceCode.BUYING_CLIMAX}
SUPPLY_CODES = {
    EvidenceCode.SUPPLY_COMING_IN,
    EvidenceCode.INCREASING_SUPPLY,
    EvidenceCode.HIDDEN_SUPPLY,
    EvidenceCode.UPTHRUST,
    EvidenceCode.NO_DEMAND,
}
DEMAND_CODES = {
    EvidenceCode.STOPPING_VOLUME,
    EvidenceCode.NO_SUPPLY,
    EvidenceCode.SHAKEOUT,
    EvidenceCode.SPRING,
    EvidenceCode.TEST,
    EvidenceCode.DEMAND_COMING_IN,
    EvidenceCode.INCREASING_DEMAND,
    EvidenceCode.HIDDEN_DEMAND,
}


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) == VolumeClass.VERY_HIGH
        and SpreadClass(int(row["spread_class"])) >= SpreadClass.ABOVE_AVERAGE
    )


def _target_bar_codes(result, index: int) -> set[EvidenceCode]:
    return {
        item.code
        for item in result.evidence
        if getattr(item, "bar_index", None) == index
        and item.code not in SELF_CODES
    }


def _is_target_combination(codes: set[EvidenceCode]) -> bool:
    supply = codes & SUPPLY_CODES
    demand = codes & DEMAND_CODES
    return (
        supply == {EvidenceCode.UPTHRUST}
        and demand == {EvidenceCode.INCREASING_DEMAND}
    )


def _audit_symbol(symbol: str):
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    closes = metrics[COL_CLOSE].to_numpy(dtype=float)
    qualified: list[tuple[bool, float]] = []
    eligible: list[float] = []
    cheap_count = 0
    rebuilds = 0

    for index in range(1, len(metrics) - FORWARD_BARS):
        forward_return = float(
            closes[index + FORWARD_BARS] / closes[index] - 1.0
        )
        eligible.append(forward_return)

        if not _cheap_candidate(metrics, index):
            continue
        cheap_count += 1

        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)

        engine = EvidenceEngine()
        engine._reset(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        rebuilds += 1
        assert engine._ctx is not None

        if not has_buying_campaign(engine._ctx):
            continue

        result = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        codes = _target_bar_codes(result, index)
        qualified.append((_is_target_combination(codes), forward_return))

    return qualified, eligible, cheap_count, rebuilds


def _market_stats(values: list[float]) -> tuple[float, float]:
    positive = sum(v > 0.0 for v in values)
    negative = sum(v < 0.0 for v in values)
    decisive = positive + negative
    rate = positive / decisive if decisive else 0.0
    mean_return = float(np.mean(values)) if values else 0.0
    return rate, mean_return


def _weighted_stats(values: list[tuple[bool, float]], penalty: float):
    total_weight = 0.0
    positive_weight = 0.0
    weighted_return = 0.0
    target_events = 0
    target_score_mass = 0.0
    unaffected_score_mass = 0.0

    for is_target, value in values:
        weight = BASE_WEIGHT * (1.0 - penalty) if is_target else BASE_WEIGHT
        total_weight += weight
        if value > 0.0:
            positive_weight += weight
        weighted_return += weight * value
        target_events += int(is_target)
        if is_target:
            target_score_mass += weight
        else:
            unaffected_score_mass += weight

    return {
        "effective_target_weight": BASE_WEIGHT * (1.0 - penalty),
        "relative_target_strength": 1.0 - penalty,
        "target_events": target_events,
        "weighted_positive_decisive_rate": positive_weight / total_weight if total_weight else 0.0,
        "weighted_mean_return": weighted_return / total_weight if total_weight else 0.0,
        "candidate_score_mass": total_weight,
        "target_score_mass": target_score_mass,
        "unaffected_score_mass": unaffected_score_mass,
    }


def main() -> None:
    all_values: list[tuple[bool, float]] = []
    eligible_returns: list[float] = []
    cheap_total = 0
    rebuild_total = 0
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            qualified, eligible, cheap, rebuilds = _audit_symbol(symbol)
            all_values.extend(qualified)
            eligible_returns.extend(eligible)
            cheap_total += cheap
            rebuild_total += rebuilds
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    target_events = sum(1 for is_target, _ in all_values if is_target)
    unaffected_events = len(all_values) - target_events
    market_rate, market_mean = _market_stats(eligible_returns)

    print("BUYING CLIMAX INTERACTION PENALTY DECISION-VALUE AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "cheap_candidates": cheap_total,
        "campaign_qualified_events": len(all_values),
        "target_combination": TARGET_COMBINATION,
        "target_events": target_events,
        "unaffected_events": unaffected_events,
        "base_weight": BASE_WEIGHT,
        "eligible_market_positive_decisive_rate": market_rate,
        "eligible_market_mean_return": market_mean,
        "penalties_tested": PENALTIES,
        "production_path_mutation": False,
        "heavy_context_rebuilds": rebuild_total,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })

    for penalty in PENALTIES:
        stats = _weighted_stats(all_values, penalty)
        print({
            "penalty": penalty,
            **stats,
            "positive_decisive_rate_lift_vs_market": (
                stats["weighted_positive_decisive_rate"] - market_rate
            ),
            "mean_return_lift_vs_market": (
                stats["weighted_mean_return"] - market_mean
            ),
        })


if __name__ == "__main__":
    main()
