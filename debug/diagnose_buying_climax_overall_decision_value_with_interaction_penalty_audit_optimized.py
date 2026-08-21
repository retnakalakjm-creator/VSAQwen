"""Overall BUYING_CLIMAX decision-value audit with interaction penalty.

Analysis-only. Replays the real point-in-time BUYING_CLIMAX population,
applies a hypothetical 0.20 penalty only to INCREASING_DEMAND + UPTHRUST,
and compares unpenalized vs penalized candidate value against the eligible
market. No production scoring mutation.
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
INTERACTION_PENALTY = 0.20

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
TARGET_COMBINATION = {
    EvidenceCode.UPTHRUST,
    EvidenceCode.INCREASING_DEMAND,
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
    return supply == {EvidenceCode.UPTHRUST} and demand == {EvidenceCode.INCREASING_DEMAND}


def _stats(values: list[float]) -> tuple[float, float, int, int, int]:
    positive = sum(v > 0.0 for v in values)
    negative = sum(v < 0.0 for v in values)
    flat = sum(v == 0.0 for v in values)
    decisive = positive + negative
    rate = positive / decisive if decisive else 0.0
    mean_return = float(np.mean(values)) if values else 0.0
    return rate, mean_return, positive, negative, flat


def _audit_symbol(symbol: str):
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    closes = metrics[COL_CLOSE].to_numpy(dtype=float)
    candidate: list[tuple[bool, float]] = []
    eligible: list[float] = []
    cheap_count = 0
    rebuilds = 0

    for index in range(1, len(metrics) - FORWARD_BARS):
        forward_return = float(closes[index + FORWARD_BARS] / closes[index] - 1.0)
        eligible.append(forward_return)
        if not _cheap_candidate(metrics, index):
            continue
        cheap_count += 1

        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        engine = EvidenceEngine()
        engine._reset(metrics=replay, trend=trend, structural_swings=structural_swings)
        rebuilds += 1
        assert engine._ctx is not None
        if not has_buying_campaign(engine._ctx):
            continue

        result = engine.collect(metrics=replay, trend=trend, structural_swings=structural_swings)
        codes = _target_bar_codes(result, index)
        candidate.append((_is_target_combination(codes), forward_return))

    return candidate, eligible, cheap_count, rebuilds


def _weighted_candidate_stats(values: list[tuple[bool, float]], penalty: float):
    weighted_positive = 0.0
    weighted_total = 0.0
    weighted_return = 0.0
    target_events = 0
    for is_target, value in values:
        weight = BASE_WEIGHT * (1.0 - penalty) if is_target else BASE_WEIGHT
        weighted_total += weight
        weighted_positive += weight * (1.0 if value > 0.0 else 0.0)
        weighted_return += weight * value
        target_events += int(is_target)
    return {
        "events": len(values),
        "target_events": target_events,
        "unaffected_events": len(values) - target_events,
        "weighted_positive_rate": weighted_positive / weighted_total if weighted_total else 0.0,
        "weighted_mean_return": weighted_return / weighted_total if weighted_total else 0.0,
        "candidate_score_mass": weighted_total,
        "effective_target_weight": BASE_WEIGHT * (1.0 - penalty),
    }


def main() -> None:
    candidate: list[tuple[bool, float]] = []
    eligible: list[float] = []
    cheap_total = 0
    rebuild_total = 0
    failures: list[dict[str, str]] = []

    for symbol in SYMBOLS:
        try:
            c, m, cheap, rebuilds = _audit_symbol(symbol)
            candidate.extend(c)
            eligible.extend(m)
            cheap_total += cheap
            rebuild_total += rebuilds
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    market_rate, market_mean, market_pos, market_neg, market_flat = _stats(eligible)
    base = _weighted_candidate_stats(candidate, 0.0)
    penalized = _weighted_candidate_stats(candidate, INTERACTION_PENALTY)
    cand_rate, cand_mean, cand_pos, cand_neg, cand_flat = _stats([v for _, v in candidate])

    print("BUYING CLIMAX OVERALL DECISION VALUE WITH INTERACTION PENALTY AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "cheap_candidates": cheap_total,
        "candidate_events": len(candidate),
        "candidate_positive": cand_pos,
        "candidate_negative": cand_neg,
        "candidate_flat": cand_flat,
        "candidate_positive_decisive_rate": cand_rate,
        "candidate_mean_return": cand_mean,
        "eligible_market_events": len(eligible),
        "eligible_market_positive_decisive_rate": market_rate,
        "eligible_market_mean_return": market_mean,
        "base_weight": BASE_WEIGHT,
        "interaction_penalty": INTERACTION_PENALTY,
        "target_combination": "INCREASING_DEMAND + UPTHRUST",
        "target_events": base["target_events"],
        "unaffected_events": base["unaffected_events"],
        "heavy_context_rebuilds": rebuild_total,
        "production_path_mutation": False,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    })
    for label, stats in (("unpenalized", base), ("penalized", penalized)):
        print({
            "mode": label,
            **stats,
            "positive_decisive_rate_lift_vs_market": stats["weighted_positive_rate"] - market_rate,
            "mean_return_lift_vs_market": stats["weighted_mean_return"] - market_mean,
        })


if __name__ == "__main__":
    main()
